"""
page_5.py — Relatórios de devoluções (admin).

Visão consolidada: status das devoluções, divergências (declarado × recebido) e
histórico completo com exportação em CSV.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

import data_processing as dp

CORES_STATUS = {
    dp.STATUS_TRANSITO: "#00baff",
    dp.STATUS_RECEBIDO: "#0067fc",
    dp.STATUS_CONFERIDO: "#90EE90",
    dp.STATUS_DIVERGENTE: "#F08080",
    dp.STATUS_CANCELADO: "#c9c9c9",
}


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def page_5():
    st.subheader("Relatórios de devoluções")

    devs = dp.devolucoes_df()
    if devs.empty:
        st.info("Nenhuma devolução registrada ainda.")
        return

    # ---- Cartões por status ----
    cont = devs["status"].value_counts().to_dict()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Em trânsito", cont.get(dp.STATUS_TRANSITO, 0))
    c2.metric("Recebidas/Conferidas",
              cont.get(dp.STATUS_RECEBIDO, 0) + cont.get(dp.STATUS_CONFERIDO, 0))
    c3.metric("Divergentes", cont.get(dp.STATUS_DIVERGENTE, 0))
    c4.metric("Canceladas", cont.get(dp.STATUS_CANCELADO, 0))

    st.markdown("---")

    # ---- Gráfico por status ----
    sdf = devs["status"].value_counts().reset_index()
    sdf.columns = ["status", "qtd"]
    sdf["rotulo"] = sdf["status"].map(lambda s: dp.STATUS_LABEL.get(s, s))
    fig = px.bar(
        sdf, x="rotulo", y="qtd", color="status",
        color_discrete_map=CORES_STATUS, title="Devoluções por status",
        labels={"rotulo": "Status", "qtd": "Quantidade"},
    )
    fig.update_layout(showlegend=False, height=330, font_family="Montserrat")
    st.plotly_chart(fig, width="stretch")

    # ---- Divergências ----
    st.markdown("#### Divergências (declarado × recebido)")
    its = dp.itens_df()
    divs = devs[devs["status"] == dp.STATUS_DIVERGENTE]
    if divs.empty or its.empty:
        st.caption("Nenhuma divergência registrada.")
    else:
        it = its[its["id_devolucao"].isin(set(divs["id"]))].copy()
        it["qtd_recebida"] = it["qtd_recebida"].fillna(0)
        it["diferenca"] = it["qtd_recebida"].astype(int) - it["qtd_declarada"].astype(int)
        it = it[it["diferenca"] != 0]
        tab = it[["id_devolucao", "tipo", "qtd_declarada", "qtd_recebida", "diferenca"]].copy()
        tab.columns = ["Devolução", "Tipo", "Declarado", "Recebido", "Diferença"]
        st.dataframe(tab, width="stretch", hide_index=True)

    # ---- Histórico ----
    st.markdown("#### Histórico completo")
    hist = devs.copy()
    hist["status"] = hist["status"].map(lambda s: dp.STATUS_LABEL.get(s, s))
    cols = ["id", "data_criacao", "usuario", "destino", "status",
            "total_declarado", "total_recebido", "data_recebimento", "recebido_por"]
    hist = hist[cols].sort_values("data_criacao", ascending=False)
    hist.columns = ["Devolução", "Emissão", "Operação", "Destino", "Status",
                    "Declarado", "Recebido", "Data recebimento", "Recebido por"]
    st.dataframe(hist, width="stretch", hide_index=True)
    st.download_button(
        "Baixar CSV", hist.to_csv(index=False).encode("utf-8-sig"),
        file_name="devolucoes.csv", mime="text/csv", key="dl_devs",
    )
