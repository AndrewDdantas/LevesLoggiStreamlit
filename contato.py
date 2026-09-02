"""
contato.py — formulário "Fale conosco / Dúvidas".

Reutilizável na tela de login (não autenticado) e dentro do app (pré-preenchido
com o e-mail do usuário logado). Envia para o e-mail de suporte definido pelo
admin em Configurações, com Reply-To do remetente.
"""

from __future__ import annotations

import time

import streamlit as st

import emailer

# Intervalo mínimo entre envios (por sessão) para evitar spam.
COOLDOWN_SEG = 60


def form_contato(key: str, nome: str = "", email: str = ""):
    """Renderiza o formulário de dúvidas. `key` deve ser único por local de uso."""
    if not emailer.email_suporte() or not emailer.smtp_configurado():
        st.caption("Canal de dúvidas indisponível no momento.")
        return

    ts_key = f"_duvida_ts_{key}"

    with st.form(f"contato_{key}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nome_in = c1.text_input("Seu nome", value=nome, key=f"ct_nome_{key}")
        email_in = c2.text_input("Seu e-mail", value=email, key=f"ct_mail_{key}",
                                 placeholder="para retornarmos")
        msg_in = st.text_area("Sua dúvida ou mensagem", key=f"ct_msg_{key}",
                              placeholder="Descreva sua dúvida...")
        enviar = st.form_submit_button("Enviar dúvida", type="primary", width="stretch")

    if enviar:
        restante = COOLDOWN_SEG - (time.time() - st.session_state.get(ts_key, 0))
        if restante > 0:
            st.warning(f"Aguarde {int(restante)}s antes de enviar outra mensagem.")
            return
        ok, resp = emailer.enviar_duvida(nome_in, email_in, msg_in)
        if ok:
            st.session_state[ts_key] = time.time()
            st.success("Sua mensagem foi enviada. Retornaremos por e-mail. ✅")
        else:
            st.error(resp)
