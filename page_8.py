"""
page_8.py — Pendências de devolução (admin): cobrança/lembrete por e-mail.

Lista as operações com saldo em aberto (enviado − devolvido − cobrado) e envia
um e-mail de lembrete usando o SMTP configurado. Diferente da aba Conciliação,
aqui não há competência nem baixa — é só um lembrete do que ainda está em aberto.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

import data_processing as dp
import emailer


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def _grupos(pend):
    grupos = []
    for destino, g in pend.groupby("destino"):
        itens = [{"tipo": r["tipo"], "pendente": int(r["pendente"])} for _, r in g.iterrows()]
        grupos.append({
            "destino": destino,
            "itens": itens,
            "total": int(g["pendente"].sum()),
            "emails": dp.emails_por_destino(destino),
        })
    return grupos


def page_8():
    st.subheader("Pendências de devolução")
    st.markdown(
        "<p class='custom-text'>Operações com ativos ainda não devolvidos. "
        "Envie um lembrete de cobrança por e-mail.</p>",
        unsafe_allow_html=True,
    )

    pend = dp.pendencias_df()
    if pend.empty:
        st.success("Nenhuma pendência de devolução no momento. 🎉")
        return

    grupos = _grupos(pend)
    total_geral = sum(x["total"] for x in grupos)
    pr = dp.precos()
    usa_valor = dp.tem_precos()
    for x in grupos:
        x["valor"] = sum(it["pendente"] * pr.get(it["tipo"], 0) for it in x["itens"])
    valor_geral = sum(x["valor"] for x in grupos)

    cols = st.columns(3 if usa_valor else 2)
    cols[0].metric("Operações com pendência", len(grupos))
    cols[1].metric("Total de ativos pendentes", _fmt(total_geral))
    if usa_valor:
        cols[2].metric("Valor total pendente", dp.fmt_brl(valor_geral))

    # Gráfico: pendente por tipo
    tdf = pend.groupby("tipo", as_index=False)["pendente"].sum()
    fig = px.bar(tdf, x="tipo", y="pendente", color="tipo",
                 color_discrete_map=dp.CORES_TIPO, title="Pendente por tipo",
                 labels={"tipo": "Tipo", "pendente": "Pendente"})
    fig.update_layout(showlegend=False, height=300, font_family="Montserrat")
    st.plotly_chart(fig, width="stretch")

    # Tabela por operação
    resumo = []
    for x in grupos:
        linha = {"Operação": x["destino"], "Total pendente": x["total"]}
        if usa_valor:
            linha["Valor"] = dp.fmt_brl(x["valor"])
        linha["E-mail(s)"] = ", ".join(x["emails"]) or "— sem e-mail —"
        resumo.append(linha)
    st.dataframe(resumo, width="stretch", hide_index=True)

    sem_email = [x["destino"] for x in grupos if not x["emails"]]
    if sem_email:
        st.caption("Sem e-mail cadastrado (não serão notificadas): " + ", ".join(sem_email))

    st.markdown("---")
    if not emailer.smtp_configurado():
        st.warning("Configure o servidor de e-mail (SMTP) em **Configurações** para enviar cobranças.")
        return

    st.markdown("#### Enviar cobrança da pendência")
    rot = {f"{x['destino']} · {_fmt(x['total'])} pendentes": x for x in grupos if x["emails"]}
    if rot:
        col_a, col_b = st.columns([2, 1])
        escolha = col_a.selectbox("Enviar para uma operação", ["—"] + list(rot.keys()))
        if col_b.button("Enviar", width="stretch") and escolha != "—":
            x = rot[escolha]
            _enviar_grupo(x)

    if st.button("✉️ Enviar cobrança para TODAS as operações com e-mail", type="primary"):
        enviados, falhas = 0, []
        for x in grupos:
            if not x["emails"]:
                continue
            ok_any = _enviar_grupo(x, silencioso=True)
            enviados += ok_any[0]
            falhas += ok_any[1]
        if enviados:
            st.success(f"{enviados} e-mail(s) de cobrança enviado(s).")
        for f in falhas:
            st.error(f)
        if not enviados and not falhas:
            st.info("Nenhuma operação com e-mail para enviar.")


def _enviar_grupo(x, silencioso=False):
    pr = dp.precos()
    enviados, falhas = 0, []
    for email in x["emails"]:
        ok, msg = emailer.enviar_pendencia(email, x["destino"], x["itens"], x["total"], precos=pr)
        if ok:
            enviados += 1
        else:
            falhas.append(msg)
    if not silencioso:
        if enviados:
            st.success(f"{enviados} e-mail(s) enviado(s) para {x['destino']}.")
        for f in falhas:
            st.error(f)
    return enviados, falhas
