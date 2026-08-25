"""
page_4.py — Recebimento (valida devoluções).

Abre automaticamente uma devolução quando acessada pelo QR (id + token na URL),
verificando o token. Caso contrário, lista as devoluções em trânsito para
seleção manual. A conferência/contagem é decisão do time de recebimento:
"Confirmar sem contar" (aceita o declarado) ou "Contar e confirmar" (registra o
que chegou e marca divergência se diferir).
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

import data_extraction as dados
import data_processing as dp


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def _confirmar(dev: dict, itens: list[dict], recebidos: dict, quem: str):
    """Grava o recebimento. recebidos=None => aceita o declarado (sem contar)."""
    agora = datetime.now(dp.TZ).strftime("%Y-%m-%d %H:%M:%S")
    if recebidos is None:
        recebidos = {it["tipo"]: int(it["qtd_declarada"]) for it in itens}
        divergente = False
    else:
        divergente = any(
            int(recebidos.get(it["tipo"], 0)) != int(it["qtd_declarada"]) for it in itens
        )
    total_receb = sum(int(v) for v in recebidos.values())
    status = dp.STATUS_DIVERGENTE if divergente else dp.STATUS_CONFERIDO
    if recebidos is None:
        status = dp.STATUS_RECEBIDO

    dados.atualizar_itens_recebidos(dev["id"], recebidos)
    dados.atualizar_devolucao(
        dev["id"],
        {"status": status, "total_recebido": total_receb,
         "data_recebimento": agora, "recebido_por": quem},
    )
    return status


def _card_devolucao(dev: dict, quem: str):
    itens_df = dp.itens_da_devolucao(dev["id"])
    itens = [{"tipo": r["tipo"], "qtd_declarada": int(r["qtd_declarada"])}
             for _, r in itens_df.iterrows()]

    st.markdown(f"### {dev['id']}")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Operação:** {dev.get('usuario','')}")
    c2.markdown(f"**Destino:** {dev.get('destino','')}")
    c3.markdown(f"**Emissão:** {dev.get('data_criacao','')}")

    # Já processada?
    if dev.get("status") != dp.STATUS_TRANSITO:
        st.warning(
            f"Esta devolução já está **{dp.STATUS_LABEL.get(dev['status'], dev['status'])}**"
            + (f" — recebida em {dev.get('data_recebimento','')} por {dev.get('recebido_por','')}."
               if dev.get("recebido_por") else ".")
        )
        st.dataframe(
            itens_df.rename(columns={"tipo": "Tipo", "qtd_declarada": "Declarado",
                                     "qtd_recebida": "Recebido"})[["Tipo", "Declarado", "Recebido"]],
            width="stretch", hide_index=True,
        )
        return

    st.markdown("#### Itens declarados")
    for it in itens:
        st.markdown(f"- **{it['tipo'].title()}**: {_fmt(it['qtd_declarada'])}")
    st.markdown(f"**Total declarado:** {_fmt(sum(i['qtd_declarada'] for i in itens))}")

    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Aceitar o declarado**")
        if st.button("✅ Confirmar sem contar", type="primary", key=f"semcontar_{dev['id']}"):
            _confirmar(dev, itens, None, quem)
            st.success("Recebimento confirmado (declarado aceito).")
            st.rerun()

    with col_b:
        st.markdown("**Contar e confirmar**")
        with st.form(f"contar_{dev['id']}"):
            recebidos = {}
            for it in itens:
                recebidos[it["tipo"]] = st.number_input(
                    f"{it['tipo'].title()} recebido", min_value=0, step=1,
                    value=int(it["qtd_declarada"]),
                )
            ok = st.form_submit_button("Registrar contagem")
        if ok:
            status = _confirmar(dev, itens, recebidos, quem)
            if status == dp.STATUS_DIVERGENTE:
                st.warning("Recebido com **divergência** entre declarado e contado.")
            else:
                st.success("Recebimento **conferido** — quantidades batem.")
            st.rerun()


def page_4(scan_id: str | None = None, scan_token: str | None = None):
    user = st.session_state.get("usuario") or {}
    quem = user.get("nome", user.get("usuario", ""))
    st.subheader("Recebimento de devoluções")

    devs = dp.devolucoes_df()

    # Aberto via QR (id + token na URL).
    if scan_id:
        if devs.empty:
            st.error("Devolução não encontrada.")
            return
        achou = devs[devs["id"] == scan_id]
        if achou.empty:
            st.error(f"Devolução {scan_id} não encontrada.")
        else:
            dev = achou.iloc[0].to_dict()
            if scan_token and str(dev.get("token", "")) != scan_token:
                st.error("Token inválido para esta devolução. Verifique o QR.")
            else:
                _card_devolucao(dev, quem)
        if st.button("← Voltar à lista"):
            st.query_params.clear()
            st.rerun()
        return

    # Lista de pendentes (em trânsito).
    if devs.empty:
        st.info("Nenhuma devolução registrada.")
        return
    pendentes = devs[devs["status"] == dp.STATUS_TRANSITO].sort_values("dt_criacao")
    st.caption("Aponte a câmera no QR do romaneio ou selecione uma devolução em trânsito abaixo.")
    if pendentes.empty:
        st.success("Nenhuma devolução em trânsito no momento.")
        return

    opcoes = {
        f"{r['id']} — {r['usuario']} ({r['destino']}) · {_fmt(r['total_declarado'])} itens": r["id"]
        for _, r in pendentes.iterrows()
    }
    escolha = st.selectbox("Devoluções em trânsito", list(opcoes.keys()))
    if escolha:
        dev = devs[devs["id"] == opcoes[escolha]].iloc[0].to_dict()
        st.markdown("---")
        _card_devolucao(dev, quem)
