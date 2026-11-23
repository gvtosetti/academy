"""Cliente HTTP seguro para ingestao de URLs externas (protecao contra SSRF).

Todo acesso a conteudo externo da Academy passa por `SafeFetcher.get()`:

- apenas `https://` na porta 443, sem credenciais embutidas na URL;
- o host e resolvido UMA vez e TODOS os enderecos precisam ser publicos (bloqueia
  localhost, redes privadas, link-local, metadados de nuvem 169.254.169.254, CGNAT,
  multicast, reservados, IPv6 ULA/link-local e IPv4 mapeado);
- a conexao e feita no IP validado (DNS pinning) com SNI/verificacao TLS no nome
  original: um DNS que muda entre a validacao e a conexao (rebinding) nao tem efeito;
- redirects sao seguidos manualmente (no maximo `max_redirects`) e cada destino e
  revalidado; cabecalhos de autenticacao nunca acompanham um redirect para outro host;
- timeouts de conexao/leitura, limite de bytes (mesmo apos descompressao) e lista de
  content-types aceitos;
- intervalo minimo por host e limite global de requisicoes por minuto;
- robots.txt e respeitado para paginas (APIs oficiais podem dispensar, explicitamente).

O conteudo retornado e DADO NAO CONFIAVEL: nunca e executado nem interpretado como
instrucao.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib import robotparser
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

log = logging.getLogger("academy.net")

USER_AGENT = "AcademyCurator/1.0 (+content curation; respects robots.txt)"
TEXT_TYPES = (
    "text/html", "application/xhtml+xml", "text/plain", "text/markdown", "text/x-markdown",
    "application/json", "application/xml", "text/xml", "application/atom+xml", "application/rss+xml",
)


class FetchError(Exception):
    """Falha controlada; `code` e estavel (testes/UI) e `message` e legivel em pt-BR."""

    def __init__(self, code: str, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class FetchResult:
    url: str  # URL final (apos redirects)
    status: int
    content_type: str
    text: str = ""
    headers: dict = field(default_factory=dict)
    truncated: bool = False
    body_skipped: bool = False  # content-type nao textual: so metadados

    def json(self):
        import json

        return json.loads(self.text)


# ---- validacao de URL e de enderecos -------------------------------------
_BLOCKED_NETS = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12",
    "192.0.0.0/24", "192.0.2.0/24", "192.168.0.0/16", "198.18.0.0/15", "198.51.100.0/24",
    "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4", "255.255.255.255/32",
    "::/128", "::1/128", "::ffff:0:0/96", "64:ff9b::/96", "100::/64", "2001:db8::/32",
    "fc00::/7", "fe80::/10", "ff00::/8",
)]
_BLOCKED_HOSTS = {"localhost", "metadata", "metadata.google.internal", "metadata.azure.com", "instance-data"}
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".intranet", ".lan", ".home", ".corp")


def is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if getattr(addr, "ipv4_mapped", None):
        addr = addr.ipv4_mapped
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast \
            or addr.is_reserved or addr.is_unspecified:
        return False
    return not any(addr in n for n in _BLOCKED_NETS if n.version == addr.version)


def validate_url(url: str) -> tuple[str, str]:
    """Valida a forma da URL. Retorna (url_normalizada, host). Nao resolve DNS."""
    if not isinstance(url, str) or not url.strip():
        raise FetchError("invalid_url", "Informe uma URL.")
    url = url.strip()
    if len(url) > 2048 or any(c in url for c in "\r\n\t "):
        raise FetchError("invalid_url", "URL invalida (espacos, quebras de linha ou tamanho excessivo).")
    try:
        p = urlsplit(url)
        port = p.port
    except ValueError:
        raise FetchError("invalid_url", "URL invalida.") from None
    if p.scheme.lower() != "https":
        raise FetchError("blocked_scheme", "Apenas URLs https:// sao aceitas.")
    if p.username or p.password or "@" in p.netloc:
        raise FetchError("blocked_url", "URLs com usuario/senha embutidos nao sao aceitas.")
    host = (p.hostname or "").rstrip(".").lower()
    if not host:
        raise FetchError("invalid_url", "URL sem dominio.")
    if port not in (None, 443):
        raise FetchError("blocked_url", "Apenas a porta padrao HTTPS (443) e aceita.")
    try:
        ipaddress.ip_address(host.strip("[]"))
        raise FetchError("blocked_url", "Use o nome de dominio, nao um endereco IP.")
    except ValueError:
        pass
    if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_SUFFIXES) or "." not in host:
        raise FetchError("blocked_url", "Endereco interno ou local bloqueado.")
    try:
        host.encode("idna")
    except UnicodeError:
        raise FetchError("invalid_url", "Dominio invalido.") from None
    norm = urlunsplit(("https", host, p.path or "/", p.query, ""))
    return norm, host


Resolver = Callable[[str], list[str]]


def system_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return sorted({i[4][0] for i in infos}, key=lambda ip: ":" in ip)  # IPv4 primeiro


# ---- limites de taxa -------------------------------------------------------
class RateLimiter:
    def __init__(self, per_host_interval: float = 0.5, global_per_minute: int = 90):
        self.interval, self.cap = per_host_interval, global_per_minute
        self._last: dict[str, float] = {}
        self._window: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self, host: str) -> None:
        with self._lock:
            now = time.monotonic()
            while self._window and now - self._window[0] > 60:
                self._window.popleft()
            if len(self._window) >= self.cap:
                raise FetchError("rate_limited", "Limite de requisicoes externas atingido. Aguarde um minuto.")
            wait = self._last.get(host, 0) + self.interval - now
            if wait > 0:
                time.sleep(min(wait, self.interval))
            self._last[host] = time.monotonic()
            self._window.append(self._last[host])


# ---- transporte com IP fixado -------------------------------------------
def pinned_transport(ip: str, host: str, path: str, headers: dict, timeout: tuple[float, float]):
    """GET via urllib3 conectando no IP validado, com SNI e verificacao TLS no hostname."""
    import certifi
    import urllib3

    pool = urllib3.HTTPSConnectionPool(
        host=ip, port=443, server_hostname=host, assert_hostname=host, cert_reqs="CERT_REQUIRED",
        ca_certs=certifi.where(), timeout=urllib3.Timeout(connect=timeout[0], read=timeout[1]),
        retries=False, maxsize=1,
    )
    return pool.urlopen("GET", path, headers={**headers, "Host": host}, redirect=False,
                        preload_content=False, assert_same_host=False, decode_content=True)


class SafeFetcher:
    def __init__(self, *, resolver: Resolver = system_resolver, transport=pinned_transport,
                 timeout: tuple[float, float] = (5, 12), max_bytes: int = 2_000_000, max_redirects: int = 4,
                 limiter: Optional[RateLimiter] = None, respect_robots: bool = True):
        self.resolver, self.transport = resolver, transport
        self.timeout, self.max_bytes, self.max_redirects = timeout, max_bytes, max_redirects
        self.limiter = limiter or RateLimiter()
        self.respect_robots = respect_robots
        self._robots: dict[str, tuple[float, Optional[robotparser.RobotFileParser]]] = {}

    # -- dns ---------------------------------------------------------------
    def resolve_public(self, host: str) -> str:
        try:
            ips = self.resolver(host)
        except (socket.gaierror, UnicodeError, OSError):
            raise FetchError("dns_failed", f"Nao foi possivel resolver o dominio {host}.") from None
        if not ips:
            raise FetchError("dns_failed", f"Nao foi possivel resolver o dominio {host}.")
        bad = [ip for ip in ips if not is_public_ip(ip)]
        if bad:
            raise FetchError("blocked_url", "O dominio aponta para um endereco privado ou interno; acesso bloqueado.")
        return ips[0]

    # -- robots ------------------------------------------------------------
    def allowed_by_robots(self, url: str) -> bool:
        p = urlsplit(url)
        host = p.hostname or ""
        cached = self._robots.get(host)
        if not cached or time.time() - cached[0] > 3600:
            rp: Optional[robotparser.RobotFileParser] = robotparser.RobotFileParser()
            try:
                res = self.get(f"https://{host}/robots.txt", robots=False, accept_status=(200, 401, 403, 404, 410),
                               max_bytes=300_000)
                if res.status == 200:
                    rp.parse(res.text.splitlines())
                else:
                    rp = None  # sem robots.txt => permitido
            except FetchError as exc:
                log.info("robots.txt indisponivel em %s: %s", host, exc.code)
                rp = None
            cached = (time.time(), rp)
            self._robots[host] = cached
        rp = cached[1]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    # -- get ---------------------------------------------------------------
    def get(self, url: str, *, params: Optional[dict] = None, headers: Optional[dict] = None,
            robots: Optional[bool] = None, accept_status: tuple[int, ...] = (200,),
            max_bytes: Optional[int] = None, auth_hosts: tuple[str, ...] = ()) -> FetchResult:
        if params:
            url = url + ("&" if "?" in url else "?") + urlencode(params)
        url, host = validate_url(url)
        check_robots = self.respect_robots if robots is None else robots
        if check_robots and not self.allowed_by_robots(url):
            raise FetchError("robots_disallowed", "O robots.txt do site nao permite este acesso automatizado.")
        limit = max_bytes or self.max_bytes
        base_headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.5",
                        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8", "Accept-Encoding": "gzip, deflate"}
        extra = dict(headers or {})
        origin_host = host
        for _hop in range(self.max_redirects + 1):
            ip = self.resolve_public(host)
            self.limiter.acquire(host)
            p = urlsplit(url)
            path = (p.path or "/") + (f"?{p.query}" if p.query else "")
            hdrs = dict(base_headers)
            # credenciais so seguem para os hosts autorizados (e nunca apos redirect cross-host)
            for k, v in extra.items():
                if k.lower() in ("authorization", "x-goog-api-key", "cookie") and \
                        (host != origin_host or (auth_hosts and host not in auth_hosts)):
                    continue
                hdrs[k] = v
            try:
                resp = self.transport(ip, host, path, hdrs, self.timeout)
            except FetchError:
                raise
            except Exception as exc:  # urllib3/ssl/socket
                name = type(exc).__name__
                if "Timeout" in name or "timed out" in str(exc).lower():
                    raise FetchError("timeout", "A fonte demorou demais para responder (timeout).") from None
                if "SSL" in name or "Certificate" in name or "certificate" in str(exc):
                    raise FetchError("tls_error", "Falha na verificacao do certificado TLS da fonte.") from None
                raise FetchError("network", f"Falha de rede ao acessar a fonte ({name}).") from None
            status = int(resp.status)
            if status in (301, 302, 303, 307, 308):
                loc = resp.headers.get("Location")
                resp.release_conn()
                if not loc:
                    raise FetchError("http_error", "Redirect sem destino.", status)
                url, host = validate_url(urljoin(url, loc))
                if check_robots and not self.allowed_by_robots(url):
                    raise FetchError("robots_disallowed", "O robots.txt do destino nao permite este acesso.")
                continue
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            hsub = {k: resp.headers.get(k) for k in ("Content-Type", "Content-Length", "Last-Modified",
                                                      "X-RateLimit-Remaining", "X-RateLimit-Reset", "Link")
                    if resp.headers.get(k)}
            if status not in accept_status:
                resp.release_conn()
                raise FetchError("http_error", _status_message(status), status)
            if ctype and not ctype.startswith(TEXT_TYPES):
                resp.release_conn()
                return FetchResult(url, status, ctype, headers=hsub, body_skipped=True)
            chunks, size, truncated = [], 0, False
            try:
                for chunk in resp.stream(64 * 1024, decode_content=True):
                    size += len(chunk)
                    if size > limit:
                        chunks.append(chunk[: max(0, limit - (size - len(chunk)))])
                        truncated = True
                        break
                    chunks.append(chunk)
            except Exception as exc:
                raise FetchError("network", f"Falha ao ler a resposta ({type(exc).__name__}).") from None
            finally:
                resp.release_conn()
            raw = b"".join(chunks)
            charset = "utf-8"
            ct_full = resp.headers.get("Content-Type") or ""
            if "charset=" in ct_full:
                charset = ct_full.split("charset=")[-1].split(";")[0].strip() or "utf-8"
            try:
                text = raw.decode(charset, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            return FetchResult(url, status, ctype, text=text, headers=hsub, truncated=truncated)
        raise FetchError("too_many_redirects", "Redirects demais; acesso interrompido.")


def _status_message(status: int) -> str:
    return {
        401: "A fonte exige autenticacao (401). Conteudo protegido nao e importado.",
        403: "A fonte recusou o acesso (403). Pode exigir login ou bloquear acesso automatizado.",
        404: "Pagina nao encontrada na fonte (404).",
        410: "O conteudo foi removido da fonte (410).",
        429: "A fonte limitou as requisicoes (429). Tente novamente mais tarde.",
    }.get(status, f"A fonte respondeu com erro HTTP {status}.")
