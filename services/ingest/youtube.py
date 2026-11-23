"""Adaptador YouTube: videos, playlists, canais e paginas de playlists de canais.

Ordem de preferencia:
1. YouTube Data API v3 oficial, quando `YOUTUBE_API_KEY` estiver configurada (chave vai
   so no header `x-goog-api-key` para www.googleapis.com).
2. Sem chave: metadados publicos acessiveis sem login e permitidos pelo robots.txt —
   oEmbed, pagina publica da playlist/canal (dados embutidos lidos como JSON, nunca
   executados). `/feeds/videos.xml` e `/youtubei/` sao bloqueados pelo robots.txt do
   YouTube e NAO sao usados.

Transcricoes nao sao acessadas. O que nao vier da fonte fica em `missing`.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional
from urllib.parse import parse_qs, urlsplit

from services.ingest.base import Child, Extraction, canonical_url, failed
from services.ingest.net import FetchError, SafeFetcher

API = "https://www.googleapis.com/youtube/v3"
HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"}
VID = re.compile(r"^[A-Za-z0-9_-]{11}$")
LIST = re.compile(r"^[A-Za-z0-9_-]{10,64}$")
HANDLE = re.compile(r"^@[A-Za-z0-9._-]{3,100}$")
CHAN = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
CONSENT = {"Cookie": "SOCS=CAI"}  # recusa cookies opcionais; evita a tela de consentimento
MAX_ITEMS = 50
_INITIAL = re.compile(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>", re.S)
_PLAYER = re.compile(r"var ytInitialPlayerResponse\s*=\s*(\{.*?\});\s*(?:var |</script>)", re.S)


def parse_youtube_url(url: str) -> Optional[dict]:
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    if host not in HOSTS:
        return None
    parts = [x for x in p.path.split("/") if x]
    q = parse_qs(p.query)
    if host == "youtu.be":
        return {"kind": "video", "id": parts[0]} if parts and VID.match(parts[0]) else None
    if parts[:1] == ["watch"] and q.get("v") and VID.match(q["v"][0]):
        info = {"kind": "video", "id": q["v"][0]}
        if q.get("list") and LIST.match(q["list"][0]):
            info["list"] = q["list"][0]
        return info
    if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live") and VID.match(parts[1]):
        return {"kind": "video", "id": parts[1]}
    if parts[:1] == ["playlist"] and q.get("list") and LIST.match(q["list"][0]):
        return {"kind": "playlist", "id": q["list"][0]}
    if parts and HANDLE.match(parts[0]):
        return {"kind": "channel", "handle": parts[0], "tab": parts[1] if len(parts) > 1 else None}
    if len(parts) >= 2 and parts[0] == "channel" and CHAN.match(parts[1]):
        return {"kind": "channel", "channel_id": parts[1], "tab": parts[2] if len(parts) > 2 else None}
    if len(parts) >= 2 and parts[0] in ("c", "user"):
        return {"kind": "channel", "legacy": f"{parts[0]}/{parts[1]}", "tab": parts[2] if len(parts) > 2 else None}
    return None


def _walk(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                yield v
            yield from _walk(v, key)
    elif isinstance(o, list):
        for x in o:
            yield from _walk(x, key)


def _embedded_json(html_text: str, var: str) -> Optional[dict]:
    """Le `var <nome> = {...}` como JSON (raw_decode: sem regex fragil, sem executar nada)."""
    m = re.search(r"var " + re.escape(var) + r"\s*=\s*\{", html_text)
    if not m:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(html_text, m.end() - 1)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def initial_data(html_text: str) -> Optional[dict]:
    return _embedded_json(html_text, "ytInitialData")


def lockups(data: dict, content_type: str) -> list[dict]:
    """Itens de grade (playlists ou videos) do JSON publico da pagina."""
    out = []
    for l in _walk(data, "lockupViewModel"):
        ctype = l.get("contentType") if isinstance(l, dict) else None
        if ctype != content_type and not (content_type.endswith("PLAYLIST") and ctype == "LOCKUP_CONTENT_TYPE_COURSE"):
            continue
        cid = l.get("contentId")
        title = (((l.get("metadata") or {}).get("lockupMetadataViewModel") or {}).get("title") or {}).get("content")
        img = json.dumps(l.get("contentImage") or {}, ensure_ascii=False)
        badge = re.findall(r'"text":\s*"([^"]{1,40})"', img)
        count = next((b for b in badge if re.search(r"\d+\s+v[ií]deos?|um v[ií]deo|\d+\s+videos?", b, re.I)), None)
        dur = next((b for b in badge if re.fullmatch(r"\d{1,2}(:\d{2}){1,2}", b)), None)
        if cid and title:
            out.append({"id": cid, "title": title, "count": count, "duration": dur})
    return out


def guess_language(text: str) -> Optional[str]:
    words = re.findall(r"[a-zà-ú]+", (text or "").lower())
    if len(words) < 12:
        return None
    pt = sum(w in {"de", "da", "do", "e", "em", "para", "com", "uma", "aula", "dados", "não", "introdução"} for w in words)
    en = sum(w in {"the", "and", "of", "to", "in", "for", "with", "lecture", "data", "introduction"} for w in words)
    if max(pt, en) < 3:
        return None
    return "pt" if pt > en * 1.5 else "en" if en > pt * 1.5 else None


class YouTubeAdapter:
    name = "youtube"

    def __init__(self, fetcher: SafeFetcher, api_key: Optional[str] = None):
        self.fetcher = fetcher
        self.api_key = api_key if api_key is not None else os.environ.get("YOUTUBE_API_KEY")

    def matches(self, url: str) -> bool:
        return parse_youtube_url(url) is not None

    # -- http --------------------------------------------------------------
    def _api(self, resource: str, **params) -> dict:
        res = self.fetcher.get(f"{API}/{resource}", params=params, headers={"x-goog-api-key": self.api_key},
                               robots=False, auth_hosts=("www.googleapis.com",))
        return res.json()

    def _page(self, url: str) -> str:
        return self.fetcher.get(url, headers=dict(CONSENT), auth_hosts=("www.youtube.com",)).text

    def _oembed(self, url: str) -> Optional[dict]:
        try:
            return self.fetcher.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"}).json()
        except (FetchError, ValueError):
            return None

    # -- extract -----------------------------------------------------------
    def extract(self, url: str) -> Extraction:
        info = parse_youtube_url(url)
        if not info:
            return failed(url, self.name, "YouTube", "unknown", "invalid_url", "URL do YouTube nao reconhecida.")
        try:
            fn = {"video": self._video, "playlist": self._playlist, "channel": self._channel}[info["kind"]]
            ex = fn(url, info)
        except FetchError as exc:
            return failed(url, self.name, "YouTube", info["kind"], exc.code, exc.message)
        except (ValueError, KeyError, TypeError, IndexError):
            return failed(url, self.name, "YouTube", info["kind"], "bad_response", "Resposta inesperada do YouTube.")
        if not self.api_key:
            ex.warnings.append("YouTube Data API nao configurada: usando metadados publicos (sem login).")
        if not ex.language:
            g = guess_language(" ".join([ex.title or "", ex.description or "", ex.text]))
            if g:
                ex.language = g
                ex.facts["language_inferred"] = True
            else:
                ex.missing.append("idioma")
        ex.missing.append("transcricao (nao acessada)")
        return ex.clamp()

    def _video(self, url: str, info: dict) -> Extraction:
        vid = info["id"]
        watch = f"https://www.youtube.com/watch?v={vid}"
        ex = Extraction(url=url, canonical_url=canonical_url(watch), adapter=self.name, provider="YouTube", kind="video")
        if self.api_key:
            items = self._api("videos", part="snippet,contentDetails", id=vid).get("items") or []
            if not items:
                raise FetchError("not_found", "Video nao encontrado ou privado.")
            sn, cd = items[0]["snippet"], items[0].get("contentDetails", {})
            ex.title, ex.description, ex.author = sn.get("title"), sn.get("description"), sn.get("channelTitle")
            ex.language = (sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "")[:2] or None
            ex.topics = [t.lower() for t in sn.get("tags", [])][:15]
            ex.updated_at = sn.get("publishedAt")
            ex.facts.update(duration=cd.get("duration"), channel_id=sn.get("channelId"))
            return ex
        o = self._oembed(watch)
        if not o:
            raise FetchError("not_found", "Video nao encontrado, privado ou com incorporacao desativada.")
        ex.title, ex.author = o.get("title"), o.get("author_name")
        ex.status = "partial"
        try:
            page = self._page(watch + "&hl=pt-BR")
            vd = (_embedded_json(page, "ytInitialPlayerResponse") or {}).get("videoDetails") or {}
            if vd:
                ex.description = (vd.get("shortDescription") or "")[:2000] or None
                ex.topics = [k.lower() for k in vd.get("keywords", [])][:15]
                if str(vd.get("lengthSeconds", "")).isdigit():
                    s = int(vd["lengthSeconds"])
                    ex.facts["duration"] = f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"
                ex.status = "ok"
        except (FetchError, ValueError):
            ex.missing.append("descricao do video")
        if "duration" not in ex.facts:
            ex.missing.append("duracao")
        return ex

    def _playlist(self, url: str, info: dict) -> Extraction:
        pid = info["id"]
        purl = f"https://www.youtube.com/playlist?list={pid}"
        ex = Extraction(url=url, canonical_url=canonical_url(purl), adapter=self.name, provider="YouTube", kind="playlist")
        if self.api_key:
            items = self._api("playlists", part="snippet,contentDetails", id=pid).get("items") or []
            if not items:
                raise FetchError("not_found", "Playlist nao encontrada ou privada.")
            sn = items[0]["snippet"]
            ex.title, ex.description, ex.author = sn.get("title"), sn.get("description"), sn.get("channelTitle")
            ex.language = (sn.get("defaultLanguage") or "")[:2] or None
            ex.updated_at = sn.get("publishedAt")
            ex.facts["video_count"] = items[0].get("contentDetails", {}).get("itemCount")
            vids = self._api("playlistItems", part="snippet", playlistId=pid, maxResults=MAX_ITEMS).get("items") or []
            ex.children = [Child(title=v["snippet"].get("title"), kind="video",
                                 url=f"https://www.youtube.com/watch?v={v['snippet'].get('resourceId', {}).get('videoId')}")
                           for v in vids if v.get("snippet", {}).get("title")]
        else:
            o = self._oembed(purl)
            if not o:
                raise FetchError("not_found", "Playlist nao encontrada ou privada.")
            ex.title, ex.author = o.get("title"), o.get("author_name")
            data = initial_data(self._page(purl + "&hl=pt-BR")) or {}
            pm = (data.get("metadata") or {}).get("playlistMetadataRenderer") or {}
            ex.description = pm.get("description") or None
            vids = lockups(data, "LOCKUP_CONTENT_TYPE_VIDEO")
            ex.children = [Child(title=v["title"], url=f"https://www.youtube.com/watch?v={v['id']}", kind="video",
                                 meta={"duration": v["duration"]} if v["duration"] else {}) for v in vids[:MAX_ITEMS]]
            hdr = json.dumps(data.get("header") or {}, ensure_ascii=False)
            cnt = re.search(r'"(\d+)\s+v[ií]deos?"', hdr)
            ex.facts["video_count"] = int(cnt.group(1)) if cnt else (len(vids) or None)
            if not cnt and vids:
                ex.facts["video_count_note"] = "contagem de videos listados na pagina publica"
            if not data:
                ex.status = "partial"
                ex.missing.append("lista de videos")
            ex.missing.append("duracao total")
        ex.text = "\n".join(f"- {c.title}" for c in ex.children)
        ex.headings = [c.title for c in ex.children[:30]]
        if not ex.description:
            ex.missing.append("descricao da playlist")
        return ex

    def _channel(self, url: str, info: dict) -> Extraction:
        base = (f"https://www.youtube.com/{info['handle']}" if info.get("handle") else
                f"https://www.youtube.com/channel/{info['channel_id']}" if info.get("channel_id") else
                f"https://www.youtube.com/{info['legacy']}")
        ex = Extraction(url=url, canonical_url=canonical_url(base + ("/playlists" if info.get("tab") == "playlists" else "")),
                        adapter=self.name, provider="YouTube", kind="channel")
        if self.api_key:
            q = {"forHandle": info["handle"]} if info.get("handle") else {"id": info.get("channel_id")} if info.get("channel_id") \
                else {"forUsername": info["legacy"].split("/")[1]}
            items = self._api("channels", part="snippet,statistics", **q).get("items") or []
            if not items:
                raise FetchError("not_found", "Canal nao encontrado.")
            ch = items[0]
            sn = ch["snippet"]
            ex.title, ex.description, ex.author = sn.get("title"), sn.get("description"), sn.get("title")
            ex.language = (sn.get("defaultLanguage") or "")[:2] or None
            ex.facts.update(channel_id=ch.get("id"), video_count=ch.get("statistics", {}).get("videoCount"),
                            country=sn.get("country"))
            pls = self._api("playlists", part="snippet,contentDetails", channelId=ch["id"], maxResults=MAX_ITEMS).get("items") or []
            ex.children = [Child(title=p["snippet"]["title"], url=f"https://www.youtube.com/playlist?list={p['id']}",
                                 kind="playlist", meta={"video_count": p.get("contentDetails", {}).get("itemCount")})
                           for p in pls]
        else:
            data = initial_data(self._page(base + "/playlists?hl=pt-BR"))
            if not data:
                raise FetchError("unavailable", "Nao foi possivel ler os metadados publicos do canal.")
            md = (data.get("metadata") or {}).get("channelMetadataRenderer") or {}
            ex.title, ex.description, ex.author = md.get("title"), (md.get("description") or "").strip() or None, md.get("title")
            ex.facts["channel_id"] = md.get("externalId")
            ex.topics = [k.strip().lower() for k in (md.get("keywords") or "").split('"') if k.strip()][:15]
            pls = lockups(data, "LOCKUP_CONTENT_TYPE_PLAYLIST")
            ex.children = [Child(title=p["title"], url=f"https://www.youtube.com/playlist?list={p['id']}", kind="playlist",
                                 meta={"video_count": p["count"]} if p["count"] else {}) for p in pls]
            if list(_walk(data, "continuationCommand")):
                ex.status = "partial"
                ex.warnings.append(f"O canal pode ter mais playlists alem das {len(pls)} exibidas na primeira pagina publica.")
                ex.missing.append("lista completa de playlists")
        ex.facts["playlist_count_listed"] = len(ex.children)
        ex.text = "\n".join(f"- {c.title} ({c.meta.get('video_count') or '?'} videos)" for c in ex.children)
        ex.headings = [c.title for c in ex.children]
        if not ex.children:
            ex.missing.append("playlists")
        return ex
