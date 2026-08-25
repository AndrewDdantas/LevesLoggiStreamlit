"""
page_6.py — Conciliação enviado × devolvido (cobrança).

Confronta, por operação × tipo, o que foi enviado e o que já foi devolvido
(recebido), destacando o que está em aberto e o que é cobrável (parado há mais
que o prazo). Aging FIFO. Somente quantidades (o valor R$ é aplicado fora).
"""

from __future__ import annotations

from datetime import datetime

import plotly.express as px
import streamlit as st

import data_extraction as dados
import data_processing as dp
import emailer


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def page_6():
    st.subheader("Conciliação e cobrança")
    st.markdown(
        "<p class='custom-text'>Cobrança por <b>competência de mês</b>. A operação tem até o "
        "<b>dia 5 do mês seguinte</b> para devolver os itens do mês. O que não voltar até lá é cobrável.</p>",
        unsafe_allow_html=True,
    )

    env = dp.envios_df()
    if env.empty:
        st.info("Nenhum envio registrado ainda.")
        return

    # ---- Competência ----
    meses = sorted(env["mes"].unique(), reverse=True)
    rotulos = {m: dp.rotulo_mes(m) for m in meses}
    # Padrão: a competência mais recente que já passou do prazo (fechável); senão a mais recente.
    idx = next((i for i, m in enumerate(meses) if dp.competencia_fechavel(m)), 0)
    escolha = st.selectbox("Competência", [rotulos[m] for m in meses], index=idx)
    mes = next(m for m, r in rotulos.items() if r == escolha)

    prazo_ts = dp.prazo_devolucao(mes)
    fechavel = dp.competencia_fechavel(mes)
    prazo_txt = prazo_ts.strftime("%d/%m/%Y")
    if fechavel:
        st.caption(f"Prazo de devolução encerrado em **{prazo_txt}** — competência pronta para fechar.")
    else:
        st.caption(f"⏳ Devoluções desta competência são aceitas até **{prazo_txt}** "
                   "— feche a cobrança após essa data.")

    df = dp.conciliacao(mes)
    if df.empty:
        st.warning("Sem envios nesta competência.")
        return

    # ---- Totais ----
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Enviado no mês", _fmt(df["enviado"].sum()))
    c2.metric("Devolvido", _fmt(df["devolvido"].sum()))
    c3.metric("Já cobrado", _fmt(df["cobrado"].sum()))
    c4.metric("Cobrável" if fechavel else "Em aberto", _fmt(df["cobravel"].sum()))

    st.markdown("---")

    # ---- Fechar cobrança (baixa definitiva) ----
    with st.container(border=True):
        st.markdown("#### Fechar cobrança da competência")
        total_cobravel = int(df["cobravel"].sum())
        if dados.competencia_ja_fechada(mes):
            st.success(f"A competência **{escolha}** já foi fechada. "
                       "Os itens cobrados foram baixados (não são recobrados nem aceitam devolução).")
        elif not fechavel:
            st.info(f"Ainda dentro do prazo de devolução (até {prazo_txt}). "
                    "O fechamento fica disponível a partir do dia 6.")
        elif total_cobravel == 0:
            st.caption("Nenhum item cobrável nesta competência. Nada a fechar.")
        else:
            st.warning(
                f"Ao fechar, **{_fmt(total_cobravel)}** itens não devolvidos até {prazo_txt} serão "
                "registrados como cobrados e recebem **baixa definitiva** — saem do saldo e não aceitam mais devolução."
            )
            confirma = st.checkbox("Confirmo o fechamento desta competência (ação irreversível).")
            if st.button("💰 Registrar cobrança e dar baixa", type="primary", disabled=not confirma):
                agora = datetime.now(dp.TZ).strftime("%Y-%m-%d %H:%M:%S")
                quem = (st.session_state.get("usuario") or {}).get("nome", "admin")
                cobraveis = df[df["cobravel"] > 0]
                rows = [
                    {
                        "id": f"COB-{mes}-{i:03d}", "data": agora, "competencia": mes,
                        "destino": r["destino"], "tipo": r["tipo"], "qtd": int(r["cobravel"]),
                        "prazo_dias": prazo_txt, "gerado_por": quem,
                    }
                    for i, (_, r) in enumerate(cobraveis.iterrows(), start=1)
                ]
                dados.registrar_cobrancas(rows)
                st.success(f"Cobrança da competência {escolha} registrada. Itens baixados.")
                st.rerun()

    st.markdown("---")

    # ---- Cobrável por tipo (gráfico) ----
    g1, g2 = st.columns([1, 1.3])
    with g1:
        tdf = df.groupby("tipo", as_index=False)["cobravel"].sum()
        fig = px.bar(
            tdf, x="tipo", y="cobravel", color="tipo",
            color_discrete_map=dp.CORES_TIPO, title="Cobrável por tipo",
            labels={"tipo": "Tipo", "cobravel": "Cobrável"},
        )
        fig.update_layout(showlegend=False, height=330, font_family="Montserrat")
        st.plotly_chart(fig, width="stretch")

    with g2:
        st.markdown("**Cobrável por operação (top 15)**")
        rank = (df.groupby("destino", as_index=False)["cobravel"].sum()
                .query("cobravel > 0").sort_values("cobravel", ascending=True).tail(15))
        if rank.empty:
            st.caption("Nenhum item cobrável no período. 🎉")
        else:
            figd = px.bar(rank, x="cobravel", y="destino", orientation="h",
                          labels={"cobravel": "Cobrável", "destino": "Operação"})
            figd.update_traces(marker_color="#F08080")
            figd.update_layout(height=330, font_family="Montserrat")
            st.plotly_chart(figd, width="stretch")

    # ---- Tabela detalhada (destino × tipo) ----
    st.markdown("#### Detalhamento por operação × tipo")
    so_cobravel = st.checkbox("Mostrar apenas com cobrável > 0", value=False)
    tab = df.copy()
    if so_cobravel:
        tab = tab[tab["cobravel"] > 0]
    tab_disp = tab.drop(columns=["em_aberto"]).rename(columns={
        "destino": "Operação", "tipo": "Tipo", "enviado": "Enviado",
        "devolvido": "Devolvido", "cobrado": "Já cobrado", "cobravel": "Cobrável",
    })
    st.dataframe(tab_disp, width="stretch", hide_index=True)

    # ---- Resumo por operação (para faturamento) ----
    st.markdown("#### Resumo por operação (cobrável por tipo)")
    piv = tab.pivot_table(index="destino", columns="tipo", values="cobravel",
                          aggfunc="sum", fill_value=0)
    piv["TOTAL"] = piv.sum(axis=1)
    piv = piv[piv["TOTAL"] > 0].sort_values("TOTAL", ascending=False)
    if piv.empty:
        st.caption("Nenhuma operação com itens cobráveis no período.")
    else:
        st.dataframe(piv, width="stretch")

    sufixo = mes or "ate_hoje"
    st.download_button(
        "Baixar conciliação (CSV)",
        tab_disp.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"conciliacao_{sufixo}.csv", mime="text/csv", key="dl_concil",
    )

    # ---- Histórico de cobranças fechadas (auditoria) ----
    st.markdown("---")
    st.markdown("#### Histórico de cobranças fechadas")
    cobs = dp.cobrancas_df()
    if cobs.empty:
        st.caption("Nenhuma cobrança fechada ainda.")
        return

    cobs = cobs.sort_values("dt", ascending=False)
    cobs["Competência"] = cobs["competencia"].map(
        lambda m: dp.rotulo_mes(m) if len(str(m)) == 7 else str(m))

    # Resumo por competência
    resumo = (cobs.groupby(["competencia", "Competência"], as_index=False)
              .agg(itens_cobrados=("qtd", "sum"), operacoes=("destino", "nunique"),
                   fechada_em=("data", "max")))
    resumo = resumo.sort_values("competencia", ascending=False)
    st.dataframe(
        resumo[["Competência", "itens_cobrados", "operacoes", "fechada_em"]].rename(
            columns={"itens_cobrados": "Itens cobrados", "operacoes": "Operações",
                     "fechada_em": "Fechada em"}),
        width="stretch", hide_index=True,
    )

    # Detalhamento (filtrável por competência)
    comps = list(dict.fromkeys(cobs["competencia"]))
    rot_comp = {c: (dp.rotulo_mes(c) if len(str(c)) == 7 else str(c)) for c in comps}
    fcomp = st.selectbox("Detalhar competência", ["Todas"] + [rot_comp[c] for c in comps],
                         key="hist_comp")
    det = cobs
    if fcomp != "Todas":
        alvo = next(c for c, r in rot_comp.items() if r == fcomp)
        det = cobs[cobs["competencia"] == alvo]

    det_disp = det[["id", "data", "Competência", "destino", "tipo", "qtd",
                    "prazo_dias", "gerado_por"]].rename(columns={
        "id": "Cobrança", "data": "Data/hora", "destino": "Operação", "tipo": "Tipo",
        "qtd": "Qtd cobrada", "prazo_dias": "Prazo (até)", "gerado_por": "Gerado por"})
    st.dataframe(det_disp, width="stretch", hide_index=True)
    st.download_button(
        "Baixar histórico de cobranças (CSV)",
        det_disp.to_csv(index=False).encode("utf-8-sig"),
        file_name="cobrancas_fechadas.csv", mime="text/csv", key="dl_cobs",
    )

    # ---- Enviar cobrança por e-mail (competência selecionada) ----
    st.markdown("---")
    st.markdown("#### Enviar cobrança por e-mail")
    cobs_mes = cobs[cobs["competencia"] == mes] if not cobs.empty else cobs
    if cobs_mes.empty:
        st.caption(f"Feche a cobrança de {escolha} para poder enviar os e-mails.")
        return
    if not emailer.smtp_configurado():
        st.warning("Configure o servidor de e-mail (SMTP) em **Configurações** para enviar cobranças.")
        return

    _enviar_cobrancas_email(cobs_mes, escolha, prazo_txt)


def _emails_do_destino(destino: str) -> list[str]:
    alvo = dp._normalizar(destino)
    return [u["email"] for u in dados.ler_usuarios()
            if u.get("email") and u.get("ativo") and dp._normalizar(u["destino"]) == alvo]


def _enviar_cobrancas_email(cobs_mes, competencia_label: str, prazo_txt: str):
    # Agrupa por operação (destino).
    grupos = []
    for destino, g in cobs_mes.groupby("destino"):
        itens = [{"tipo": r["tipo"], "qtd": int(r["qtd"])} for _, r in g.iterrows()]
        total = int(g["qtd"].sum())
        emails = _emails_do_destino(destino)
        grupos.append({"destino": destino, "itens": itens, "total": total, "emails": emails})

    resumo = [{"Operação": x["destino"], "Total cobrado": x["total"],
               "E-mail(s)": ", ".join(x["emails"]) or "— sem e-mail —"} for x in grupos]
    st.dataframe(resumo, width="stretch", hide_index=True)

    sem_email = [x["destino"] for x in grupos if not x["emails"]]
    if sem_email:
        st.caption("Sem e-mail cadastrado (não serão notificadas): " + ", ".join(sem_email))

    if st.button("✉️ Enviar e-mails de cobrança", type="primary", key="send_all"):
        enviados, falhas = 0, []
        for x in grupos:
            if not x["emails"]:
                continue
            corpo = emailer.corpo_cobranca(x["destino"], competencia_label, prazo_txt,
                                           x["itens"], x["total"])
            for email in x["emails"]:
                ok, msg = emailer.enviar_email(
                    email, f"Cobrança de ativos — {competencia_label} — Portal LEVES", corpo)
                if ok:
                    enviados += 1
                else:
                    falhas.append(msg)
        if enviados:
            st.success(f"{enviados} e-mail(s) de cobrança enviado(s).")
        for f in falhas:
            st.error(f)
        if not enviados and not falhas:
            st.info("Nenhuma operação com e-mail para enviar.")
