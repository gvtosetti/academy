# Academy

**Knowledge & Discovery Hub** multidisciplinar, em pt-BR, feito em **Python + Streamlit**.

A Academy não é um curso nem um LMS: é um espaço de curadoria para **descobrir → entender em 30 segundos → acessar o conteúdo original**. Não há trilhas, inscrição, quizzes nem progresso. Atende Data Science (com destaque editorial), AI & LLMs, Dev & Backend, Data Engineering, Data Governance, Produto, Market Research, Analytics e Creative Tech.

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

Para publicar:

- **Streamlit Community Cloud** (ou qualquer host Streamlit): aponte para `app.py`.
- **Databricks Apps**: o `app.yaml` já define o comando `streamlit run app.py`; crie o app apontando para esta pasta.

### Token do GitHub (opcional)

Sem token, o app usa a API pública do GitHub (limite de requisições baixo) e continua funcionando com o catálogo local se a API falhar. Para aumentar o limite, defina `GITHUB_TOKEN` em `.streamlit/secrets.toml` (não versionado) ou como variável de ambiente.

## Seções

- **Discover** (`?page=discover`): hero, busca global, chips de área (filtram a própria página) e as seções editoriais Explore & Discover, Worth Checking Out, Quick Knowledge e Tools & Resources. Seções sem conteúdo para a área escolhida não aparecem.
- **Library** (`?page=library&q=...&area=...`): todos os recursos (GitHub, cursos, playlists, ferramentas, coleções) num só catálogo, com busca sem acento e filtros opcionais por área, tipo, nível, idioma e tags.
- **Tips & Insights** (`?page=tips&kind=...`): notas curtas e independentes (Quick Explainers, Dev Tips, Tools Worth Knowing, Good Practices, Concepts in Practice). O tempo de leitura é calculado do texto (200 palavras/min).

Cada card tem **Explorar** (abre a fonte original em um clique) e **Saiba mais** (`?page=resource&resource=<id>`), uma apresentação curta com: O que é? Por que é útil? Para quem faz sentido? O que vou encontrar? Acessar material. Detalhes técnicos ficam em expansores opcionais. Notas abrem em `?page=note&note=<id>`.

Links antigos (`?page=explore`, `paths`, `videos`, `github`, `knowledge&concept=...`, `my_learning`, `about`) são redirecionados para as novas seções.

## Estrutura

```
app.py              # entrada e roteamento por query params
app.yaml            # comando para Databricks Apps
components/         # layout (topo, navegação), cards e estilo
views/              # discover, library, tips, resource (Saiba mais), note
services/           # catálogo, busca, recomendações, GitHub (com cache)
utils/              # texto (normalização de acentos) e salvaguardas (URLs https)
data/
  resources.yaml    # recursos curados (fonte de verdade)
  areas.yaml        # áreas/disciplinas e ordem dos chips
  glossary.yaml     # Quick Explainers (conceitos em camadas)
  tips.yaml         # Dev Tips, Tools, Good Practices, Concepts in Practice
  home.yaml         # seleção editorial da Discover
  categories.yaml   # temas amplos (exibidos no detalhe e usados em recomendações)
tests/              # catálogo, busca, notas e smoke test com interações reais
```

## Como adicionar um recurso

1. Adicione o item em `data/resources.yaml` (o schema está em `services/models.py`). Campos essenciais: `id` (estável, usado na URL), `title`, `url` (https), `type`, `areas` (uma ou mais; a primeira é a principal) e `blurb` (1–2 frases: o que é e por que me interessa, até 260 caracteres).
2. Use apenas ids de conceitos existentes em `data/glossary.yaml` em `key_concepts`.
3. Se algo não foi conferido na fonte, use `metadata_status: partial` ou `pending` e explique em `metadata_notes`.
4. Opcional: destaque o recurso na home em `data/home.yaml`.
5. Rode `pytest`: os testes falham se houver referência quebrada ou área com menos de 2 itens.

## Como adicionar uma nota (Tips & Insights)

- Conceito (“O que é X?”): adicione em `data/glossary.yaml` com `simple`, `technical`, `example`, `why` e `areas`.
- Dica, ferramenta, boa prática ou exemplo prático: adicione em `data/tips.yaml` com `kind` (`dev-tip`, `tool`, `practice`, `in-practice`), `summary`, `body` (Markdown) e `areas`. Não informe tempo de leitura: ele é calculado.
- Não invente links: notas podem referenciar recursos do catálogo via `related_resources`.

## Testes

```bash
pytest -q
```

## Licença do conteúdo

Os materiais pertencem aos seus autores e são apenas referenciados. Explicações, níveis e guias de estudo são texto autoral da curadoria da Academy.
