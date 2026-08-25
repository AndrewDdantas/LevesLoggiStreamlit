"""
page_1.py — Visão de Envios (ativos a devolver).

Filtro por mês (principal) + tipo de ativo. Cartões por tipo e gráficos em
Plotly Express, no padrão visual da Loggi. Multi-tenant: operação vê só o seu
destino; admin vê tudo e ganha o ranking de destinos.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

import data_processing as dp

AZUL = "#0067fc"


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def page_1():
    user = st.session_state.get("usuario") or {}
    eh_admin = user.get("perfil") == "admin"

    st.subheader("Visão geral dos ativos" if eh_admin else "Ativos enviados para você")
    st.markdown(
        "<p class='custom-text'>Estes são os ativos enviados que precisam ser "
        "devolvidos. Use o filtro de mês para ver o período desejado.</p>",
        unsafe_allow_html=True,
    )

    df = dp.envios_do_usuario(user)
    if df.empty:
        st.info("Nenhum envio encontrado."
                if eh_admin else "Nenhum envio encontrado para a sua operação.")
        return

    # ---- Filtros ----
    meses = sorted(df["mes"].unique(), reverse=True)
    rotulos = {m: dp.rotulo_mes(m) for m in meses}
    fcol1, fcol2 = st.columns([1, 1.4])
    opcoes = ["Todo o período"] + [rotulos[m] for m in meses]
    escolha = fcol1.selectbox("Mês", opcoes, index=1 if meses else 0)

    tipos_disp = sorted(df["tipo"].unique())
    sel_tipos = fcol2.multiselect("Tipo de ativo", tipos_disp, default=tipos_disp)

    dfx = df.copy()
    if escolha != "Todo o período":
        mes_sel = next(m for m, r in rotulos.items() if r == escolha)
        dfx = dfx[dfx["mes"] == mes_sel]
    if sel_tipos:
        dfx = dfx[dfx["tipo"].isin(sel_tipos)]

    if dfx.empty:
        st.warning("Sem dados para os filtros selecionados.")
        return

    # ---- Cartões: total geral + por tipo ----
    total_geral = int(dfx["total"].sum())
    por_tipo = dfx.groupby("tipo")["total"].sum().to_dict()
    cols = st.columns(1 + len(tipos_disp))
    cols[0].metric("Total de ativos", _fmt(total_geral))
    for i, t in enumerate(tipos_disp, start=1):
        cols[i].metric(t.title(), _fmt(por_tipo.get(t, 0)))

    st.markdown("---")

    # ---- Gráficos (Plotly Express) ----
    g1, g2 = st.columns(2)

    tdf = dfx.groupby("tipo", as_index=False)["total"].sum().sort_values("total", ascending=False)
    fig_tipo = px.bar(
        tdf, x="tipo", y="total", color="tipo",
        color_discrete_map=dp.CORES_TIPO, title="Total por tipo de ativo",
        labels={"tipo": "Tipo de ativo", "total": "Total"},
    )
    fig_tipo.update_layout(showlegend=False, height=340, font_family="Montserrat")
    g1.plotly_chart(fig_tipo, width="stretch")

    ddf = dfx.groupby(["dia", "tipo"], as_index=False)["total"].sum()
    fig_dia = px.bar(
        ddf, x="dia", y="total", color="tipo",
        color_discrete_map=dp.CORES_TIPO, title="Envios por dia",
        labels={"dia": "Data", "total": "Total", "tipo": "Tipo"},
    )
    fig_dia.update_layout(height=340, font_family="Montserrat",
                          legend_title_text="Tipo", barmode="stack")
    g2.plotly_chart(fig_dia, width="stretch")

    # ---- Admin: ranking de destinos ----
    if eh_admin:
        st.markdown("#### Top destinos no período")
        rank = (
            dfx.groupby("destino", as_index=False)["total"].sum()
            .sort_values("total", ascending=True).tail(15)
        )
        fig_dest = px.bar(
            rank, x="total", y="destino", orientation="h",
            title="15 maiores destinos", labels={"total": "Total", "destino": "Destino"},
        )
        fig_dest.update_traces(marker_color=AZUL)
        fig_dest.update_layout(height=460, font_family="Montserrat")
        st.plotly_chart(fig_dest, width="stretch")

    # ---- Tabela detalhada + CSV ----
    with st.expander("Ver tabela detalhada"):
        cols_tab = ["dt", "tipo", "destino", "total"] if eh_admin else ["dt", "tipo", "total"]
        tab = dfx[cols_tab].sort_values("dt", ascending=False).copy()
        tab["dt"] = tab["dt"].dt.strftime("%d/%m/%Y")
        nomes = {"dt": "Data", "tipo": "Tipo de ativo", "destino": "Destino", "total": "Total"}
        tab = tab.rename(columns=nomes)
        st.dataframe(tab, width="stretch", hide_index=True)
        st.download_button(
            "Baixar CSV",
            tab.to_csv(index=False).encode("utf-8-sig"),
            file_name="ativos_leves.csv",
            mime="text/csv",
            key="dl_envios",
        )
