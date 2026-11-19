# Academy

Plataforma de aprendizado em pt-BR sobre IA, LLMs, agentes, LLMOps, engenharia de software assistida por IA e visualização, feita em **Python + Streamlit**.

Cada recurso curado traz explicação simples, visão técnica, guia de estudo, conceitos-chave e a indicação do que foi **verificado na fonte original** (e do que ainda está em validação).

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

Para publicar, use o Streamlit Community Cloud (ou outro host Streamlit) apontando para `app.py`.

### Token do GitHub (opcional)

Sem token, o app usa a API pública do GitHub (limite de requisições baixo) e continua funcionando com o catálogo local se a API falhar. Para aumentar o limite, defina `GITHUB_TOKEN` em `.streamlit/secrets.toml` (não versionado) ou como variável de ambiente.

## Páginas

- **Início**: busca, trilhas, destaques e categorias
- **Trilhas**: 6 trilhas com módulos, conceitos, prática e progresso
- **Explorar**: busca local (sem acento, por relevância) com filtros
- **Detalhe do recurso**: abas de visão geral, técnico, como estudar, conteúdo e verificação; recomendações
- **GitHub Explorer**: metadados ao vivo, estrutura da raiz e prévia do README sanitizada
- **Vídeos e cursos**: playlists com lista de aulas
- **Base de Conhecimento**: 39 conceitos em camadas + quizzes
- **Meu aprendizado**: status, salvos e progresso (temporário, por sessão) com exportação em JSON

As URLs são compartilháveis via query params, por exemplo `?page=resource&resource=manim`.

## Estrutura

```
app.py              # entrada e roteamento
components/         # navegação, cards e estilo
views/              # uma página por módulo
services/           # catálogo, busca, recomendações, GitHub, progresso
utils/              # texto e salvaguardas (URLs https, Markdown sanitizado)
data/               # catálogo curado (fonte de verdade)
tests/              # validação do catálogo, busca, trilhas e smoke test das páginas
```

## Como adicionar um recurso

1. Adicione o item em `data/resources.yaml` (o schema está em `services/models.py`).
2. Se usar `learning_paths`, inclua o id também em um módulo de `data/tracks.yaml`.
3. Use apenas ids de conceitos existentes em `data/glossary.yaml`.
4. Se algo não foi conferido na fonte, use `metadata_status: partial` ou `pending` e explique em `metadata_notes`.
5. Rode `pytest`: os testes falham se houver referência quebrada.

## Testes

```bash
pytest -q
```

## Licença do conteúdo

Os materiais pertencem aos seus autores e são apenas referenciados. Explicações, níveis e guias de estudo são texto autoral da curadoria da Academy.
