"""
page_3.py — Devoluções (operação).

Mostra o saldo a devolver (enviado − devolvido), permite declarar uma nova
devolução (limitada ao saldo) e gerar o Romaneio em PDF com QR. Lista as
devoluções da operação com status, reimpressão e cancelamento (em trânsito).
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pandas as pd
import streamlit as st

import data_extraction as dados
import data_processing as dp
import romaneio


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def page_3():
    user = st.session_state.get("usuario") or {}
    destino = user.get("destino", "")

    st.subheader("Devoluções")
    st.markdown(
        "<p class='custom-text'>Declare o que está devolvendo, gere o romaneio com "
        "QR e envie impresso junto com os itens.</p>",
        unsafe_allow_html=True,
    )

    # ---- Saldo a devolver ----
    saldo = dp.saldo_por_tipo(destino)
    if saldo.empty or saldo["enviado"].sum() == 0:
        st.info("Nenhum ativo enviado para a sua operação até o momento.")
        return

    st.markdown("#### Saldo a devolver")
    tipos_com_saldo = saldo[saldo["saldo"] > 0]
    cols = st.columns(max(len(saldo), 1))
    for i, (_, r) in enumerate(saldo.iterrows()):
        cols[i].metric(r["tipo"].title(), _fmt(r["saldo"]),
                       help=f"Enviado: {_fmt(r['enviado'])} · Já devolvido: {_fmt(r['devolvido'])}")

    st.markdown("<hr class='sb-sep' style='border-top-color:#e6e6e6;'>", unsafe_allow_html=True)

    # ---- Nova devolução ----
    st.markdown("#### Nova devolução")
    if tipos_com_saldo.empty:
        st.success("Você não tem saldo pendente de devolução. 🎉")
    else:
        with st.form("nova_devolucao", clear_on_submit=True):
            qtds = {}
            fcols = st.columns(len(tipos_com_saldo))
            for i, (_, r) in enumerate(tipos_com_saldo.iterrows()):
                qtds[r["tipo"]] = fcols[i].number_input(
                    f"{r['tipo'].title()} (máx. {_fmt(r['saldo'])})",
                    min_value=0, max_value=int(r["saldo"]), step=1, value=0,
                )
            placa = st.text_input("Placa do veículo", placeholder="ex.: ABC1D23")
            local = st.text_input("Devolvendo para (local/CD de destino)",
                                  placeholder="ex.: CD Cajamar")
            obs = st.text_input("Observação (opcional)")
            enviar = st.form_submit_button("Gerar devolução", type="primary")

        if enviar:
            itens = [{"tipo": t, "qtd_declarada": int(q)} for t, q in qtds.items() if q > 0]
            placa_norm = "".join(str(placa or "").upper().split()).replace("-", "")
            local_norm = str(local or "").strip()
            if not itens:
                st.error("Informe ao menos uma quantidade.")
            elif not placa_norm:
                st.error("Informe a placa do veículo.")
            elif not local_norm:
                st.error("Informe para onde está devolvendo.")
            else:
                total = sum(it["qtd_declarada"] for it in itens)
                id_dev = dados.proximo_codigo_devolucao()
                token = uuid.uuid4().hex
                agora = datetime.now(dp.TZ).strftime("%Y-%m-%d %H:%M:%S")
                dev = {
                    "id": id_dev, "token": token, "data_criacao": agora,
                    "usuario": user.get("nome", user.get("usuario", "")),
                    "destino": destino, "status": dp.STATUS_TRANSITO,
                    "total_declarado": total, "total_recebido": "",
                    "data_recebimento": "", "recebido_por": "", "obs": obs,
                    "placa": placa_norm, "local_devolucao": local_norm,
                }
                dados.criar_devolucao(dev, itens)
                st.success(f"Devolução **{id_dev}** criada. Baixe o romaneio abaixo e envie com os itens.")
                pdf = romaneio.gerar_romaneio_pdf(dev, itens, dp.base_url())
                st.download_button(
                    "📄 Baixar romaneio (PDF)", pdf, file_name=f"{id_dev}.pdf",
                    mime="application/pdf", key=f"dl_{id_dev}", type="primary",
                )

    # ---- Minhas devoluções ----
    st.markdown("#### Minhas devoluções")
    devs = dp.devolucoes_df()
    if devs.empty:
        st.caption("Nenhuma devolução registrada ainda.")
        return
    minhas = devs[devs["destino"].map(dp._normalizar) == dp._normalizar(destino)]
    minhas = minhas.sort_values("dt_criacao", ascending=False)
    if minhas.empty:
        st.caption("Nenhuma devolução registrada ainda.")
        return

    for _, d in minhas.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 1.4, 1, 1.2])
            c1.markdown(f"**{d['id']}**  \n{d['data_criacao']}")
            c2.markdown(dp.STATUS_LABEL.get(d["status"], d["status"])
                        + (f"  \n🚚 {d.get('placa')}" if d.get("placa") else ""))
            c3.markdown(f"Total: **{_fmt(d['total_declarado'])}**")
            with c4:
                itens = dp.itens_da_devolucao(d["id"])
                itens_l = [{"tipo": r["tipo"], "qtd_declarada": r["qtd_declarada"]}
                           for _, r in itens.iterrows()]
                dev_h = d.to_dict()
                st.download_button(
                    "📄 Romaneio",
                    romaneio.gerar_romaneio_pdf(dev_h, itens_l, dp.base_url()),
                    file_name=f"{d['id']}.pdf", mime="application/pdf",
                    key=f"rom_{d['id']}",
                )
                if d["status"] == dp.STATUS_TRANSITO:
                    if st.button("Cancelar", key=f"can_{d['id']}"):
                        dados.atualizar_devolucao(d["id"], {"status": dp.STATUS_CANCELADO})
                        st.rerun()
