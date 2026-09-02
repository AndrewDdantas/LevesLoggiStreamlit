"""
page_9.py — Minhas cobranças (operação).

Mostra ao parceiro as cobranças que foram fechadas para a sua operação
(itens não devolvidos no prazo), por competência, com valor quando houver preço.
"""

from __future__ import annotations

import streamlit as st

import data_processing as dp


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def page_9():
    user = st.session_state.get("usuario") or {}
    destino = user.get("destino", "")

    st.subheader("Minhas cobranças")
    st.markdown(
        "<p class='custom-text'>Cobranças fechadas para a sua operação — ativos que não "
        "foram devolvidos dentro do prazo.</p>",
        unsafe_allow_html=True,
    )

    cobs = dp.cobrancas_df()
    minhas = cobs[cobs["destino"].map(dp._normalizar) == dp._normalizar(destino)].copy() \
        if not cobs.empty else cobs
    if minhas.empty:
        st.success("Nenhuma cobrança registrada para a sua operação. 🎉")
        return

    pr = dp.precos()
    usa_valor = dp.tem_precos()
    minhas["Competência"] = minhas["competencia"].map(
        lambda m: dp.rotulo_mes(m) if len(str(m)) == 7 else str(m))
    if usa_valor:
        minhas["valor"] = minhas.apply(
            lambda r: int(r["qtd"]) * pr.get(str(r["tipo"]).upper(), 0), axis=1)

    # ---- Totais ----
    total_q = int(minhas["qtd"].sum())
    if usa_valor:
        c1, c2 = st.columns(2)
        c1.metric("Total de itens cobrados", _fmt(total_q))
        c2.metric("Valor total", dp.fmt_brl(minhas["valor"].sum()))
    else:
        st.metric("Total de itens cobrados", _fmt(total_q))

    # ---- Resumo por competência ----
    st.markdown("#### Por competência")
    agg = {"qtd": "sum"}
    if usa_valor:
        agg["valor"] = "sum"
    resumo = minhas.groupby(["competencia", "Competência"], as_index=False).agg(agg)
    resumo = resumo.sort_values("competencia", ascending=False)
    resumo_disp = resumo[["Competência", "qtd"] + (["valor"] if usa_valor else [])].rename(
        columns={"qtd": "Itens cobrados", "valor": "Valor"})
    if usa_valor:
        resumo_disp["Valor"] = resumo_disp["Valor"].map(dp.fmt_brl)
    st.dataframe(resumo_disp, width="stretch", hide_index=True)

    # ---- Detalhamento ----
    st.markdown("#### Detalhamento")
    det = minhas.sort_values(["competencia", "tipo"], ascending=[False, True]).copy()
    cols = ["Competência", "tipo", "qtd"] + (["valor"] if usa_valor else []) + ["data"]
    det_disp = det[cols].rename(columns={
        "tipo": "Tipo", "qtd": "Qtd cobrada", "valor": "Valor", "data": "Fechada em"})
    if usa_valor:
        det_disp["Valor"] = det_disp["Valor"].map(dp.fmt_brl)
    st.dataframe(det_disp, width="stretch", hide_index=True)
    st.download_button(
        "Baixar minhas cobranças (CSV)",
        det_disp.to_csv(index=False).encode("utf-8-sig"),
        file_name="minhas_cobrancas.csv", mime="text/csv", key="dl_minhas_cob",
    )
