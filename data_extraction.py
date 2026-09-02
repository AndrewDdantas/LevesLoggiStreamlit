"""
data_extraction.py — camada de extração crua (padrão DLE).

Conecta ao Google Sheets via service account (chave JSON) e expõe os dados
BRUTOS das abas. Sem regra de negócio aqui — a transformação fica em
data_processing.py.

Esquema compartilhado com o app em Apps Script:
  Envios   -> data | tipo | destino | total
  Usuarios -> usuario | senha_hash | salt | destino | nome | perfil | ativo | criado_em
"""

from __future__ import annotations

import glob
import os
from datetime import datetime

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

# Abas.
ABA_ENVIOS = "Envios"
ABA_USUARIOS = "Usuarios"
ABA_DEVOLUCOES = "Devolucoes"
ABA_DEV_ITENS = "Devolucoes_Itens"
ABA_COBRANCAS = "Cobrancas"
ABA_CONFIG = "Config"

CAB_ENVIOS = ["DATA", "tipo", "destino", "total"]
CAB_USUARIOS = ["usuario", "senha_hash", "salt", "destino", "nome", "perfil", "ativo", "criado_em", "email"]
CAB_CONFIG = ["chave", "valor"]
CAB_DEVOLUCOES = [
    "id", "token", "data_criacao", "usuario", "destino", "status",
    "total_declarado", "total_recebido", "data_recebimento", "recebido_por", "obs",
    "placa", "local_devolucao",
]
CAB_DEV_ITENS = ["id_devolucao", "tipo", "qtd_declarada", "qtd_recebida"]
CAB_COBRANCAS = ["id", "data", "competencia", "destino", "tipo", "qtd", "prazo_dias", "gerado_por"]

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _achar_json_local() -> str | None:
    """Procura um arquivo .json de service account na pasta do projeto."""
    base = os.path.dirname(os.path.abspath(__file__))
    try:
        cfg = st.secrets.get("app", {}).get("service_account_file")
    except Exception:  # noqa: BLE001
        cfg = None
    candidatos = []
    if cfg:
        candidatos.append(cfg if os.path.isabs(cfg) else os.path.join(base, cfg))
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        candidatos.append(os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
    candidatos += sorted(glob.glob(os.path.join(base, "*.json")))
    for c in candidatos:
        if c and os.path.isfile(c):
            return c
    return None


def _secrets_validos() -> bool:
    """True se [gcp_service_account] tem uma private_key que parece real."""
    try:
        pk = st.secrets["gcp_service_account"].get("private_key", "")
    except Exception:  # noqa: BLE001
        return False
    return "BEGIN PRIVATE KEY" in pk and len(pk) > 500


@st.cache_resource(show_spinner=False)
def _cliente() -> gspread.Client:
    """Autentica via [gcp_service_account] do secrets OU via arquivo .json local."""
    if _secrets_validos():
        info = dict(st.secrets["gcp_service_account"])
        # Corrige "\n" literais (erro comum ao colar). Seguro: PEM não contém "\n".
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
        return gspread.authorize(creds)

    caminho = _achar_json_local()
    if caminho:
        creds = Credentials.from_service_account_file(caminho, scopes=_SCOPES)
        return gspread.authorize(creds)

    raise RuntimeError(
        "Credenciais não encontradas. Coloque o arquivo .json da service account "
        "nesta pasta (STREAMLIT/) OU preencha [gcp_service_account] no "
        ".streamlit/secrets.toml com os dados reais da chave."
    )


def _spreadsheet_id() -> str:
    sid = ""
    try:
        sid = st.secrets["app"].get("spreadsheet_id", "")
    except Exception:  # noqa: BLE001
        sid = ""
    sid = (sid or os.environ.get("SPREADSHEET_ID", "")).strip()
    if not sid or sid.startswith("COLE_AQUI"):
        raise RuntimeError(
            "spreadsheet_id não configurado. Defina [app].spreadsheet_id no "
            ".streamlit/secrets.toml (o ID fica na URL da planilha, entre /d/ e /edit)."
        )
    return sid


@st.cache_resource(show_spinner=False)
def _planilha() -> gspread.Spreadsheet:
    """Abre a planilha pelo ID configurado."""
    return _cliente().open_by_key(_spreadsheet_id())


def _aba(nome: str, cabecalho: list[str]) -> gspread.Worksheet:
    """Retorna a aba, criando-a com cabeçalho se não existir."""
    ss = _planilha()
    try:
        return ss.worksheet(nome)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=nome, rows=100, cols=max(4, len(cabecalho)))
        ws.append_row(cabecalho)
        return ws


# ---------------------------------------------------------------------------
# Leitura (crua) — cacheada com ttl curto (padrão DLE)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def ler_envios() -> list[dict]:
    """Lê os envios brutos da aba Envios."""
    ws = _aba(ABA_ENVIOS, CAB_ENVIOS)
    valores = ws.get_all_values()
    linhas = []
    for i, row in enumerate(valores):
        if i == 0 or not any(row):
            continue
        row = (row + ["", "", "", ""])[:4]
        try:
            total = float(str(row[3]).replace(".", "").replace(",", ".")) if row[3] else 0
        except ValueError:
            total = 0
        linhas.append(
            {
                "data": str(row[0]).strip(),
                "tipo": str(row[1]).strip(),
                "destino": str(row[2]).strip(),
                "total": total,
            }
        )
    return linhas


@st.cache_data(ttl=30, show_spinner=False)
def ler_usuarios() -> list[dict]:
    """Lê todos os usuários (inclui hash/salt — uso interno)."""
    ws = _aba(ABA_USUARIOS, CAB_USUARIOS)
    valores = ws.get_all_values()
    linhas = []
    for i, row in enumerate(valores):
        if i == 0 or not any(row):
            continue
        row = (row + [""] * 9)[:9]
        linhas.append(
            {
                "linha": i + 1,
                "usuario": str(row[0]).strip().lower(),
                "senha_hash": str(row[1]).strip(),
                "salt": str(row[2]).strip(),
                "destino": str(row[3]).strip(),
                "nome": str(row[4]).strip(),
                "perfil": (str(row[5]).strip().lower() or "operacao"),
                "ativo": str(row[6]).strip().lower() in ("true", "1", "sim", "verdadeiro"),
                "email": str(row[8]).strip(),
            }
        )
    return linhas


@st.cache_data(ttl=20, show_spinner=False)
def ler_devolucoes() -> list[dict]:
    """Lê os cabeçalhos de devolução."""
    ws = _aba(ABA_DEVOLUCOES, CAB_DEVOLUCOES)
    valores = ws.get_all_values()
    linhas = []
    for i, row in enumerate(valores):
        if i == 0 or not any(row):
            continue
        row = (row + [""] * len(CAB_DEVOLUCOES))[: len(CAB_DEVOLUCOES)]
        d = dict(zip(CAB_DEVOLUCOES, row))
        d["linha"] = i + 1
        linhas.append(d)
    return linhas


@st.cache_data(ttl=20, show_spinner=False)
def ler_dev_itens() -> list[dict]:
    """Lê os itens de devolução."""
    ws = _aba(ABA_DEV_ITENS, CAB_DEV_ITENS)
    valores = ws.get_all_values()
    linhas = []
    for i, row in enumerate(valores):
        if i == 0 or not any(row):
            continue
        row = (row + [""] * 4)[:4]
        linhas.append(
            {
                "linha": i + 1,
                "id_devolucao": str(row[0]).strip(),
                "tipo": str(row[1]).strip().upper(),
                "qtd_declarada": _num(row[2]),
                "qtd_recebida": _num(row[3]) if str(row[3]).strip() != "" else None,
            }
        )
    return linhas


def _num(v) -> float:
    try:
        return float(str(v).replace(".", "").replace(",", ".")) if str(v).strip() != "" else 0
    except ValueError:
        return 0


def proximo_codigo_devolucao() -> str:
    """Gera DEV-AAAA-NNNNNN sequencial dentro do ano."""
    ano = datetime.now().year
    devs = ler_devolucoes()
    n = sum(1 for d in devs if str(d.get("id", "")).startswith(f"DEV-{ano}-")) + 1
    return f"DEV-{ano}-{n:06d}"


def criar_devolucao(dev: dict, itens: list[dict]):
    """Grava o cabeçalho e os itens de uma nova devolução."""
    ws = _aba(ABA_DEVOLUCOES, CAB_DEVOLUCOES)
    ws.append_row([dev.get(c, "") for c in CAB_DEVOLUCOES], value_input_option="USER_ENTERED")
    wsi = _aba(ABA_DEV_ITENS, CAB_DEV_ITENS)
    rows = [
        [dev["id"], it["tipo"], it["qtd_declarada"], it.get("qtd_recebida", "")]
        for it in itens
    ]
    if rows:
        wsi.append_rows(rows, value_input_option="USER_ENTERED")
    limpar_cache()


def _col(cab, nome) -> int:
    return cab.index(nome) + 1


def atualizar_devolucao(id_dev: str, campos: dict):
    """Atualiza colunas do cabeçalho de uma devolução pelo id."""
    ws = _aba(ABA_DEVOLUCOES, CAB_DEVOLUCOES)
    valores = ws.get_all_values()
    for i, row in enumerate(valores):
        if i == 0:
            continue
        if row and str(row[0]).strip() == id_dev:
            for nome, val in campos.items():
                ws.update_cell(i + 1, _col(CAB_DEVOLUCOES, nome), val)
            break
    limpar_cache()


def atualizar_itens_recebidos(id_dev: str, recebidos: dict):
    """Grava qtd_recebida por tipo (dict tipo->qtd) nos itens da devolução."""
    ws = _aba(ABA_DEV_ITENS, CAB_DEV_ITENS)
    valores = ws.get_all_values()
    for i, row in enumerate(valores):
        if i == 0 or not row:
            continue
        if str(row[0]).strip() == id_dev:
            tipo = str(row[1]).strip().upper() if len(row) > 1 else ""
            if tipo in recebidos:
                ws.update_cell(i + 1, 4, recebidos[tipo])
    limpar_cache()


@st.cache_data(ttl=20, show_spinner=False)
def ler_cobrancas() -> list[dict]:
    """Lê as cobranças registradas (itens já baixados por cobrança)."""
    ws = _aba(ABA_COBRANCAS, CAB_COBRANCAS)
    valores = ws.get_all_values()
    linhas = []
    for i, row in enumerate(valores):
        if i == 0 or not any(row):
            continue
        row = (row + [""] * len(CAB_COBRANCAS))[: len(CAB_COBRANCAS)]
        d = dict(zip(CAB_COBRANCAS, row))
        d["qtd"] = _num(d.get("qtd"))
        linhas.append(d)
    return linhas


def registrar_cobrancas(rows: list[dict]):
    """Grava linhas de cobrança (uma por destino×tipo). Cada linha dá baixa."""
    if not rows:
        return
    ws = _aba(ABA_COBRANCAS, CAB_COBRANCAS)
    ws.append_rows(
        [[r.get(c, "") for c in CAB_COBRANCAS] for r in rows],
        value_input_option="USER_ENTERED",
    )
    limpar_cache()


def competencia_ja_fechada(competencia: str) -> bool:
    """True se já existe cobrança registrada para a competência."""
    return any(str(c.get("competencia", "")) == competencia for c in ler_cobrancas())


# ---------------------------------------------------------------------------
# Configuração (chave/valor) — usada para o SMTP de e-mail
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30, show_spinner=False)
def get_config() -> dict:
    """Lê a aba Config como dicionário chave->valor."""
    ws = _aba(ABA_CONFIG, CAB_CONFIG)
    valores = ws.get_all_values()
    cfg = {}
    for i, row in enumerate(valores):
        if i == 0 or not any(row):
            continue
        row = (row + ["", ""])[:2]
        chave = str(row[0]).strip()
        if chave:
            cfg[chave] = str(row[1])
    return cfg


def set_config(novos: dict):
    """Grava/atualiza chaves na aba Config (upsert por chave)."""
    ws = _aba(ABA_CONFIG, CAB_CONFIG)
    valores = ws.get_all_values()
    linha_por_chave = {}
    for i, row in enumerate(valores):
        if i == 0 or not row:
            continue
        if row[0]:
            linha_por_chave[str(row[0]).strip()] = i + 1
    for chave, valor in novos.items():
        if chave in linha_por_chave:
            ws.update_cell(linha_por_chave[chave], 2, str(valor))
        else:
            ws.append_row([chave, str(valor)], value_input_option="USER_ENTERED")
    get_config.clear()


def limpar_cache():
    """Invalida os caches de leitura após uma escrita."""
    ler_envios.clear()
    ler_usuarios.clear()
    ler_devolucoes.clear()
    ler_dev_itens.clear()
    ler_cobrancas.clear()


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------

def inserir_usuario(usuario, senha_hash, salt, destino, nome, perfil, ativo=True, email=""):
    ws = _aba(ABA_USUARIOS, CAB_USUARIOS)
    ws.append_row(
        [usuario, senha_hash, salt, destino, nome, perfil, "TRUE" if ativo else "FALSE",
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email],
        value_input_option="USER_ENTERED",
    )
    limpar_cache()


def inserir_usuarios_lote(rows: list[list]):
    """Insere vários usuários de uma vez (cada `row` na ordem de CAB_USUARIOS)."""
    if not rows:
        return
    ws = _aba(ABA_USUARIOS, CAB_USUARIOS)
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    limpar_cache()


def definir_ativo(linha: int, ativo: bool):
    """Atualiza a coluna 'ativo' (7ª) de uma linha específica."""
    ws = _aba(ABA_USUARIOS, CAB_USUARIOS)
    ws.update_cell(linha, 7, "TRUE" if ativo else "FALSE")
    limpar_cache()
