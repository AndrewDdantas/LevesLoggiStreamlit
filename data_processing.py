"""
data_processing.py — transformação e regras (padrão DLE).

Importa os dados brutos de data_extraction, normaliza tipos e timezone e expõe
o DataFrame canônico de envios usado pelas páginas.

Schema canônico de envios:
  data (str) | tipo | destino | total | dt (datetime) | mes ("AAAA-MM") | dia (date)

Obs.: este painel é de ATIVOS a devolver (SACA/GAYLORD/ROLLCONTAINER), não usa as
regras de expedição/status (AT/NP/AD) do DLE clássico.
"""

from __future__ import annotations

import os

import pandas as pd
import pytz
import streamlit as st

import data_extraction

TZ = pytz.timezone("America/Sao_Paulo")

# Meses em português para rótulos de filtro/gráfico.
MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

# Cores por tipo de ativo (paleta Loggi — padrão DLE).
CORES_TIPO = {
    "SACA": "#0067fc",
    "GAYLORD": "#00baff",
    "ROLLCONTAINER": "#FFD580",
    "PALLET": "#B5651D",  # derivado 1:1 do GAYLORD
}

# Tipos derivados: para cada GAYLORD enviado, vai 1 PALLET (critério).
TIPO_ORIGEM_DERIVADO = "GAYLORD"
TIPO_DERIVADO = "PALLET"

# Estados de uma devolução.
STATUS_TRANSITO = "EM_TRANSITO"
STATUS_RECEBIDO = "RECEBIDO"
STATUS_CONFERIDO = "CONFERIDO"
STATUS_DIVERGENTE = "DIVERGENTE"
STATUS_CANCELADO = "CANCELADO"

# Rótulos e cores de status para a UI.
STATUS_LABEL = {
    STATUS_TRANSITO: "🚚 Em trânsito",
    STATUS_RECEBIDO: "📥 Recebido",
    STATUS_CONFERIDO: "✅ Conferido",
    STATUS_DIVERGENTE: "⚠️ Divergente",
    STATUS_CANCELADO: "🚫 Cancelado",
}
# Comprometidos = tudo que "saiu" do saldo (não cancelado).
STATUS_COMPROMETIDOS = {STATUS_TRANSITO, STATUS_RECEBIDO, STATUS_CONFERIDO, STATUS_DIVERGENTE}
# Recebidos de fato (contam para conciliação/cobrança).
STATUS_RECEBIDOS = {STATUS_RECEBIDO, STATUS_CONFERIDO, STATUS_DIVERGENTE}

# Prazo padrão (dias) para devolver antes de virar cobrável.
PRAZO_PADRAO_DIAS = 15


def envios_df() -> pd.DataFrame:
    """DataFrame canônico de todos os envios (sem filtro de usuário)."""
    envios = data_extraction.ler_envios()
    df = pd.DataFrame(envios, columns=["data", "tipo", "destino", "total"])
    if df.empty:
        return df
    df["dt"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["dt"]).copy()
    df["tipo"] = df["tipo"].astype(str).str.upper().str.strip()
    df["destino"] = df["destino"].astype(str).str.strip()
    df["total"] = pd.to_numeric(df["total"], errors="coerce").fillna(0)

    # PALLET é derivado 1:1 do GAYLORD (para cada gaylord enviado, 1 pallet).
    # Só deriva se a planilha ainda não trouxer PALLET como tipo próprio.
    if TIPO_DERIVADO not in set(df["tipo"]):
        gay = df[df["tipo"] == TIPO_ORIGEM_DERIVADO].copy()
        if not gay.empty:
            gay["tipo"] = TIPO_DERIVADO
            df = pd.concat([df, gay], ignore_index=True)

    df["mes"] = df["dt"].dt.to_period("M").astype(str)  # "2026-08"
    df["dia"] = df["dt"].dt.date
    return df


def envios_do_usuario(user: dict) -> pd.DataFrame:
    """Aplica o multi-tenant: admin vê tudo; operação vê só o seu destino."""
    df = envios_df()
    if df.empty:
        return df
    if user.get("perfil") == "admin":
        return df
    alvo = _normalizar(user.get("destino", ""))
    return df[df["destino"].map(_normalizar) == alvo].copy()


def rotulo_mes(mes: str) -> str:
    """'2026-08' -> 'Agosto/2026'."""
    return f"{MESES_PT[int(mes[5:7])]}/{mes[:4]}"


def base_url() -> str:
    """URL pública do app (para o QR). Configure [app].base_url no secrets."""
    b = ""
    try:
        b = st.secrets["app"].get("base_url", "")
    except Exception:  # noqa: BLE001
        b = ""
    return (b or os.environ.get("BASE_URL", "") or "http://localhost:8501").rstrip("/")


def _normalizar(v) -> str:
    import unicodedata
    s = "" if v is None else str(v)
    s = s.strip().lower()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Devoluções
# ---------------------------------------------------------------------------

def devolucoes_df() -> pd.DataFrame:
    devs = data_extraction.ler_devolucoes()
    df = pd.DataFrame(devs)
    if df.empty:
        return df
    for c in ("total_declarado", "total_recebido"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["dt_criacao"] = pd.to_datetime(df["data_criacao"], errors="coerce")
    return df


def itens_df() -> pd.DataFrame:
    df = pd.DataFrame(data_extraction.ler_dev_itens())
    if df.empty:
        return df
    df["tipo"] = df["tipo"].astype(str).str.upper().str.strip()
    df["qtd_declarada"] = pd.to_numeric(df["qtd_declarada"], errors="coerce").fillna(0)
    return df


def saldo_por_tipo(destino: str) -> pd.DataFrame:
    """Saldo a devolver por tipo: enviado − devolvido_comprometido.

    Retorna colunas: tipo, enviado, devolvido, saldo (saldo >= 0).
    """
    alvo = _normalizar(destino)

    env = envios_df()
    if env.empty:
        enviado = {}
    else:
        e = env[env["destino"].map(_normalizar) == alvo]
        enviado = e.groupby("tipo")["total"].sum().to_dict()

    # Devolvido comprometido (não cancelado) para este destino.
    devolvido = {}
    devs = devolucoes_df()
    its = itens_df()
    if not devs.empty and not its.empty:
        devs_dest = devs[
            (devs["destino"].map(_normalizar) == alvo)
            & (devs["status"].isin(STATUS_COMPROMETIDOS))
        ]
        ids = set(devs_dest["id"])
        it = its[its["id_devolucao"].isin(ids)]
        devolvido = it.groupby("tipo")["qtd_declarada"].sum().to_dict()

    # Já cobrado (baixado) — sai do saldo, pois não aceita mais devolução.
    cobrado = _cobrado_por_chave(pd.Timestamp.now())
    cobrado = {t: q for (dn, t), q in cobrado.items() if dn == alvo}

    tipos = sorted(set(enviado) | set(devolvido) | set(cobrado) | set(CORES_TIPO))
    linhas = []
    for t in tipos:
        env_v = int(enviado.get(t, 0))
        dev_v = int(devolvido.get(t, 0))
        cob_v = int(cobrado.get(t, 0))
        linhas.append({"tipo": t, "enviado": env_v, "devolvido": dev_v,
                       "saldo": max(env_v - dev_v - cob_v, 0)})
    return pd.DataFrame(linhas)


def itens_da_devolucao(id_dev: str) -> pd.DataFrame:
    its = itens_df()
    if its.empty:
        return its
    return its[its["id_devolucao"] == id_dev].copy()


# ---------------------------------------------------------------------------
# Conciliação enviado × devolvido (cobrança)
# ---------------------------------------------------------------------------

def prazo_devolucao(mes: str) -> pd.Timestamp:
    """Prazo de devolução da competência: dia 5 do mês seguinte (fim do dia)."""
    prox = (pd.Period(mes, freq="M") + 1).start_time  # 1º dia do mês seguinte
    return prox + pd.Timedelta(days=4, hours=23, minutes=59, seconds=59)  # dia 5, 23:59


def competencia_fechavel(mes: str) -> bool:
    """True quando já passou o prazo (dia 5 do mês seguinte) e a competência pode ser fechada."""
    return pd.Timestamp.now() > prazo_devolucao(mes)


def _cutoff_competencia(mes: str) -> pd.Timestamp:
    """Corte para contar devoluções da competência: dia 5 do mês seguinte (ou hoje, se antes)."""
    return min(prazo_devolucao(mes), pd.Timestamp.now())


def _competencia_do_dev(row) -> str:
    """Competência de uma devolução: o campo escolhido; senão, o mês da criação (legado)."""
    c = str(row.get("competencia", "") or "").strip()
    if c:
        return c
    dt = pd.to_datetime(row.get("data_criacao"), errors="coerce")
    return dt.to_period("M").strftime("%Y-%m") if pd.notna(dt) else ""


def competencias_elegiveis(destino: str) -> list[str]:
    """Meses (competências) que a operação ainda pode devolver: dentro do prazo (até dia 5 do mês seguinte)."""
    env = envios_df()
    if env.empty:
        return []
    alvo = _normalizar(destino)
    e = env[env["destino"].map(_normalizar) == alvo]
    if e.empty:
        return []
    now = pd.Timestamp.now()
    meses = sorted(set(e["mes"]), reverse=True)
    return [m for m in meses if now <= prazo_devolucao(m)]


def pending_mes_tipo(destino: str, mes: str) -> dict:
    """Pendência por tipo de UMA competência: enviado no mês − devolvido(comp==mes) − cobrado(comp==mes)."""
    alvo = _normalizar(destino)
    per = pd.Period(mes, freq="M")
    ini, fim = per.start_time, per.end_time

    env = envios_df()
    enviado = {}
    if not env.empty:
        e = env[(env["destino"].map(_normalizar) == alvo) & (env["dt"] >= ini) & (env["dt"] <= fim)]
        enviado = e.groupby("tipo")["total"].sum().to_dict()

    devolvido = {}
    devs = devolucoes_df()
    its = itens_df()
    if not devs.empty and not its.empty:
        d = devs[(devs["destino"].map(_normalizar) == alvo)
                 & (devs["status"].isin(STATUS_COMPROMETIDOS))].copy()
        if not d.empty:
            d["comp"] = d.apply(_competencia_do_dev, axis=1)
            d = d[d["comp"] == mes]
            it = its[its["id_devolucao"].isin(set(d["id"]))]
            devolvido = it.groupby("tipo")["qtd_declarada"].sum().to_dict()

    cobrado = {t: q for (dn, t), q in _cobrado_por_competencia(mes, ate=False).items() if dn == alvo}

    tipos = set(enviado) | set(devolvido) | set(cobrado)
    return {t: max(int(enviado.get(t, 0)) - int(devolvido.get(t, 0)) - int(cobrado.get(t, 0)), 0)
            for t in tipos}


def _consome_fifo(lots: list, retornado: float) -> list:
    """Consome `retornado` dos lotes mais antigos (FIFO). Devolve os lotes restantes."""
    r = retornado
    rem = []
    for d, q in lots:
        if r <= 0:
            rem.append((d, q))
        elif r >= q:
            r -= q
        else:
            rem.append((d, q - r))
            r = 0
    return rem


def _recebido_por_chave(cutoff: pd.Timestamp) -> dict:
    """Qtd efetivamente recebida por (destino_norm, tipo) até o corte."""
    devs = devolucoes_df()
    its = itens_df()
    if devs.empty or its.empty:
        return {}
    d = devs[devs["status"].isin(STATUS_RECEBIDOS)].copy()
    if d.empty:
        return {}
    d["dt_receb"] = pd.to_datetime(d["data_recebimento"], errors="coerce")
    d = d[d["dt_receb"].notna() & (d["dt_receb"] <= cutoff)]
    if d.empty:
        return {}
    d["destino_norm"] = d["destino"].map(_normalizar)
    mapa = d.set_index("id")["destino_norm"].to_dict()
    it = its[its["id_devolucao"].isin(set(d["id"]))].copy()
    it["q"] = it["qtd_recebida"].fillna(it["qtd_declarada"])
    it["destino_norm"] = it["id_devolucao"].map(mapa)
    it = it.dropna(subset=["destino_norm"])
    g = it.groupby(["destino_norm", "tipo"])["q"].sum()
    return {k: int(v) for k, v in g.items()}


def emails_por_destino(destino: str) -> list[str]:
    """E-mails dos usuários ativos daquele destino (para cobrança/lembrete)."""
    alvo = _normalizar(destino)
    return [u["email"] for u in data_extraction.ler_usuarios()
            if u.get("email") and u.get("ativo") and _normalizar(u["destino"]) == alvo]


def pendencias_df() -> pd.DataFrame:
    """Pendência de devolução por destino×tipo (em aberto = enviado − devolvido − cobrado).

    Considera TODO o período (não é por competência). Só linhas com pendente > 0.
    """
    cols = ["destino", "tipo", "enviado", "devolvido", "cobrado", "pendente"]
    env = envios_df()
    if env.empty:
        return pd.DataFrame(columns=cols)
    env = env.copy()
    env["destino_norm"] = env["destino"].map(_normalizar)
    enviado = env.groupby(["destino_norm", "tipo"])["total"].sum()
    disp = env.groupby("destino_norm")["destino"].first().to_dict()

    devolvido = {}
    devs = devolucoes_df()
    its = itens_df()
    if not devs.empty and not its.empty:
        d = devs[devs["status"].isin(STATUS_COMPROMETIDOS)].copy()
        d["destino_norm"] = d["destino"].map(_normalizar)
        mapa = d.set_index("id")["destino_norm"].to_dict()
        it = its[its["id_devolucao"].isin(set(d["id"]))].copy()
        it["destino_norm"] = it["id_devolucao"].map(mapa)
        it = it.dropna(subset=["destino_norm"])
        devolvido = it.groupby(["destino_norm", "tipo"])["qtd_declarada"].sum().to_dict()

    cobrado = _cobrado_por_chave(pd.Timestamp.now())

    linhas = []
    for (dn, tipo), env_v in enviado.items():
        dev_v = int(devolvido.get((dn, tipo), 0))
        cob_v = int(cobrado.get((dn, tipo), 0))
        pend = max(int(env_v) - dev_v - cob_v, 0)
        if pend > 0:
            linhas.append({"destino": disp.get(dn, dn), "tipo": tipo, "enviado": int(env_v),
                           "devolvido": dev_v, "cobrado": cob_v, "pendente": pend})
    return pd.DataFrame(linhas, columns=cols).sort_values(["destino", "tipo"]).reset_index(drop=True)


def cobrancas_df() -> pd.DataFrame:
    """Histórico de cobranças fechadas (aba Cobrancas)."""
    cobs = data_extraction.ler_cobrancas()
    df = pd.DataFrame(cobs)
    if df.empty:
        return df
    df["qtd"] = pd.to_numeric(df["qtd"], errors="coerce").fillna(0).astype(int)
    df["dt"] = pd.to_datetime(df["data"], errors="coerce")
    return df


def _cobrado_por_chave(cutoff: pd.Timestamp) -> dict:
    """Qtd já cobrada (baixada) por (destino_norm, tipo) até o corte."""
    cobs = data_extraction.ler_cobrancas()
    if not cobs:
        return {}
    df = pd.DataFrame(cobs)
    df["dt_cob"] = pd.to_datetime(df["data"], errors="coerce")
    df = df[df["dt_cob"].notna() & (df["dt_cob"] <= cutoff)]
    if df.empty:
        return {}
    df["destino_norm"] = df["destino"].map(_normalizar)
    df["tipo"] = df["tipo"].astype(str).str.upper().str.strip()
    df["qtd"] = pd.to_numeric(df["qtd"], errors="coerce").fillna(0)
    g = df.groupby(["destino_norm", "tipo"])["qtd"].sum()
    return {k: int(v) for k, v in g.items()}


def _cobrado_por_competencia(mes: str, ate: bool = True) -> dict:
    """Qtd cobrada por (destino_norm, tipo). ate=True: competências <= mes; senão só == mes."""
    cobs = data_extraction.ler_cobrancas()
    if not cobs:
        return {}
    df = pd.DataFrame(cobs)
    df["competencia"] = df["competencia"].astype(str)
    df = df[df["competencia"] <= mes] if ate else df[df["competencia"] == mes]
    if df.empty:
        return {}
    df["destino_norm"] = df["destino"].map(_normalizar)
    df["tipo"] = df["tipo"].astype(str).str.upper().str.strip()
    df["qtd"] = pd.to_numeric(df["qtd"], errors="coerce").fillna(0)
    g = df.groupby(["destino_norm", "tipo"])["qtd"].sum()
    return {k: int(v) for k, v in g.items()}


def _recebido_por_competencia(mes: str, cutoff: pd.Timestamp) -> dict:
    """Qtd recebida por (destino_norm, tipo) das devoluções da competência `mes`, até o corte."""
    devs = devolucoes_df()
    its = itens_df()
    if devs.empty or its.empty:
        return {}
    d = devs[devs["status"].isin(STATUS_RECEBIDOS)].copy()
    if d.empty:
        return {}
    d["dt_receb"] = pd.to_datetime(d["data_recebimento"], errors="coerce")
    d = d[d["dt_receb"].notna() & (d["dt_receb"] <= cutoff)]
    if d.empty:
        return {}
    d["comp"] = d.apply(_competencia_do_dev, axis=1)
    d = d[d["comp"] == mes]
    if d.empty:
        return {}
    d["destino_norm"] = d["destino"].map(_normalizar)
    mapa = d.set_index("id")["destino_norm"].to_dict()
    it = its[its["id_devolucao"].isin(set(d["id"]))].copy()
    it["q"] = it["qtd_recebida"].fillna(it["qtd_declarada"])
    it["destino_norm"] = it["id_devolucao"].map(mapa)
    it = it.dropna(subset=["destino_norm"])
    g = it.groupby(["destino_norm", "tipo"])["q"].sum()
    return {k: int(v) for k, v in g.items()}


def conciliacao(mes: str) -> pd.DataFrame:
    """Concilia por competência (mês). A devolução informa a competência a que se refere.

    Colunas: destino, tipo, enviado, devolvido, cobrado, em_aberto, cobravel
      - enviado: enviado NO mês `mes`
      - devolvido: recebido de devoluções cuja competência == mes (até o dia 5 do mês seguinte)
      - cobrado: já baixado por cobrança desta competência
      - em_aberto / cobravel: enviado do mês ainda não devolvido nem cobrado
    """
    cols = ["destino", "tipo", "enviado", "devolvido", "cobrado", "em_aberto", "cobravel"]
    env = envios_df()
    if env.empty:
        return pd.DataFrame(columns=cols)

    per = pd.Period(mes, freq="M")
    ini, fim = per.start_time, per.end_time
    cutoff = _cutoff_competencia(mes)

    envc = env[(env["dt"] >= ini) & (env["dt"] <= fim)].copy()  # só os envios do mês da competência
    if envc.empty:
        return pd.DataFrame(columns=cols)
    envc["destino_norm"] = envc["destino"].map(_normalizar)
    enviado = envc.groupby(["destino_norm", "tipo"])["total"].sum()
    disp = envc.groupby("destino_norm")["destino"].first().to_dict()

    recebido = _recebido_por_competencia(mes, cutoff)
    cobrado_mes = _cobrado_por_competencia(mes, ate=False)

    linhas = []
    for (dn, tipo), env_v in enviado.items():
        env_i = int(env_v)
        r = int(recebido.get((dn, tipo), 0))
        cb = int(cobrado_mes.get((dn, tipo), 0))
        em_aberto = max(env_i - r - cb, 0)
        linhas.append({
            "destino": disp.get(dn, dn), "tipo": tipo, "enviado": env_i,
            "devolvido": min(r, env_i), "cobrado": min(cb, env_i),
            "em_aberto": em_aberto, "cobravel": em_aberto,
        })
    return pd.DataFrame(linhas, columns=cols).sort_values(["destino", "tipo"]).reset_index(drop=True)
