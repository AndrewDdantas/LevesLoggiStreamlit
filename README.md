# Portal LEVES — Loggi (Streamlit)

Mesma ferramenta do app em Apps Script, agora em **Streamlit**, lendo o Google
Sheets via **service account (chave JSON)**. Operações externas fazem login
próprio e veem apenas os ativos enviados ao seu destino; o perfil **admin**
cria e gerencia usuários pela própria tela.

> Usa o **mesmo esquema e o mesmo hash** do app Apps Script, então os dois
> compartilham as abas `Envios` e `Usuarios` da mesma planilha.

## O que o painel mostra

- **Filtro por mês** (padrão: mês mais recente) + filtro por tipo de ativo.
- **Cartões**: total geral e total por tipo (`SACA`, `GAYLORD`, `ROLLCONTAINER`).
- **Gráficos**: total por tipo e envios por dia (empilhado por tipo).
- **Admin**: além de tudo, ranking dos 15 maiores destinos no período.
- **Tabela detalhada** com exportação em CSV.

Dados esperados na aba `Envios`: `data (AAAA-MM-DD) | tipo | destino | total`.

## Fluxo de devolução (ativos a devolver)

Perfis: `operacao`, `recebimento` e `admin`.

1. **Operação** (aba *Devoluções*) vê o **saldo a devolver** (`enviado − devolvido`),
   declara quantidades ≤ saldo e o sistema cria a devolução (`EM_TRANSITO`) e gera
   o **Romaneio em PDF com QR** para imprimir e enviar com os itens.
2. **Recebimento** aponta a câmera no QR → abre a página da devolução (o QR é uma
   URL com token) → escolhe **Confirmar sem contar** (aceita o declarado →
   `RECEBIDO`) ou **Contar e confirmar** (registra o contado → `CONFERIDO` se bate,
   `DIVERGENTE` se difere). O saldo é baixado automaticamente.
3. **Admin** (aba *Relatórios*) acompanha status, divergências e histórico (CSV).

Abas usadas: `Devolucoes` e `Devolucoes_Itens` (criadas automaticamente).
Configure `[app].base_url` no `secrets.toml` com a URL pública para o QR funcionar.

> Crie um usuário de recebimento pela tela de admin (perfil **Recebimento**).

## Arquitetura (padrão DLE — 3 camadas)

```
data_extraction.py  ->  data_processing.py  ->  page_N()  ->  app.main()
   (Sheets cru)          (schema canônico)       (visões)     (rota+estilo)
```

| Arquivo                     | Papel                                                       |
|-----------------------------|-------------------------------------------------------------|
| `data_extraction.py`        | Extração crua do Google Sheets (service account, cache).    |
| `data_processing.py`        | Normaliza e monta o DataFrame canônico + cores/rótulos.     |
| `app.py`                    | Configura página, estilo, login e roteia via `sidebar.radio`.|
| `page_1.py`                 | Visão de Envios (filtro de mês, cartões, gráficos Plotly).  |
| `page_2.py`                 | Administração de usuários (somente admin).                  |
| `auth.py`                   | Hash de senha, autenticação e criação de usuários.          |
| `streamlit_estilizador.py`  | `PageStyler` — CSS da marca (Montserrat, azul `#0067fc`).   |
| `streamlit_sidebar.py`      | Sidebar azul da marca (logo da lebre opcional).             |
| `.streamlit/config.toml`    | Tema Loggi.                                                  |
| `criar_admin.py`            | Cria o primeiro administrador.                              |
| `.streamlit/secrets.toml.example` | Modelo dos segredos (chave JSON + ID).                |

> **Logo da sidebar:** coloque `image_simbolo_lebre.png` nesta pasta para exibir
> a lebre no topo da sidebar. Sem o arquivo, a sidebar continua azul, só sem logo.

## Pré-requisitos no Google Cloud (uma vez)

1. Criar um projeto no **Google Cloud** e ativar as APIs **Google Sheets** e **Google Drive**.
2. Criar uma **service account** e gerar uma **chave JSON**.
3. **Compartilhar a planilha** com o e-mail da service account
   (`...@...iam.gserviceaccount.com`) como **Editor**.

## Configuração local (jeito fácil — arquivo .json)

1. Instalar dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. **Coloque o arquivo `.json` da service account dentro da pasta `STREAMLIT/`.**
   O app detecta qualquer `*.json` automaticamente (o `.json` está no `.gitignore`).
3. Copiar o modelo de segredos e preencher só o ID da planilha:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
   - Em `[app].spreadsheet_id`, cole o ID da planilha (trecho da URL entre `/d/` e `/edit`).
   - Não precisa preencher `[gcp_service_account]` no uso local — isso só é usado no
     Streamlit Cloud, onde não dá para subir arquivo (veja "Publicar").
4. Criar o admin (uma vez):
   ```bash
   python criar_admin.py admin MinhaSenhaForte!
   ```
4. Rodar o app:
   ```bash
   streamlit run app.py
   ```

## Publicar (acesso externo)

Este é o caminho que **contorna o bloqueio do domínio** do Apps Script, pois o
acesso externo não depende do Google:

- **Streamlit Community Cloud** (grátis): suba o repositório e cole o conteúdo
  do `secrets.toml` em *App → Settings → Secrets*. Gera uma URL pública.
- Ou qualquer host (Cloud Run, Render, etc.) rodando `streamlit run app.py`.

Em qualquer opção, o login continua sendo o **nosso** (usuário+senha na aba
`Usuarios`); a chave JSON serve apenas para o app ler/escrever na planilha.

## Segurança

- Senhas com `SHA-256(salt + senha)` e salt único por usuário — nunca em texto puro.
- Comparação de hash em tempo constante (`hmac.compare_digest`).
- Filtro por destino aplicado no servidor a cada leitura (multi-tenant).
- Limite de 5 tentativas de login por sessão.
- A chave JSON e o `secrets.toml` ficam fora do versionamento (`.gitignore`).
