"""
page_7.py — Configurações (admin): servidor de e-mail (SMTP) para envio de cobranças.

Para ENVIAR e-mail usa-se SMTP (IMAP é só para leitura). O admin preenche aqui
o servidor de saída; as credenciais ficam na aba Config da planilha.
"""

from __future__ import annotations

import streamlit as st

import data_extraction as dados
import data_processing as dp
import emailer


def page_7():
    st.subheader("Configurações de e-mail (SMTP)")
    st.markdown(
        "<p class='custom-text'>Servidor de <b>saída (SMTP)</b> usado para enviar as cobranças. "
        "IMAP serve apenas para ler a caixa de entrada — para envio, use SMTP.</p>",
        unsafe_allow_html=True,
    )

    cfg = dados.get_config()

    with st.form("smtp"):
        c1, c2 = st.columns([2, 1])
        host = c1.text_input("Servidor SMTP", value=cfg.get("smtp_host", ""),
                             placeholder="ex.: smtp.gmail.com")
        port = c2.text_input("Porta", value=cfg.get("smtp_port", "587"),
                             placeholder="587 (TLS) ou 465 (SSL)")
        user = st.text_input("Usuário / e-mail de login", value=cfg.get("smtp_user", ""),
                             placeholder="ex.: cobranca@empresa.com")
        pwd = st.text_input("Senha (ou senha de app)", value=cfg.get("smtp_password", ""),
                            type="password")
        remetente = st.text_input("Remetente (From)", value=cfg.get("smtp_from", ""),
                                  placeholder="ex.: Portal LEVES <cobranca@empresa.com>")
        usar_tls = st.checkbox("Usar TLS (STARTTLS na porta 587)",
                               value=str(cfg.get("smtp_tls", "true")).lower() in ("true", "1", "sim"))
        st.markdown("**Canal de dúvidas**")
        suporte = st.text_input("E-mail que recebe as dúvidas da operação",
                                value=cfg.get("email_suporte", ""),
                                placeholder="ex.: suporte.leves@empresa.com")
        salvar = st.form_submit_button("Salvar configuração", type="primary", width="stretch")

    if salvar:
        dados.set_config({
            "smtp_host": host.strip(), "smtp_port": port.strip(), "smtp_user": user.strip(),
            "smtp_password": pwd, "smtp_from": remetente.strip(),
            "smtp_tls": "true" if usar_tls else "false",
            "email_suporte": suporte.strip(),
        })
        st.success("Configuração salva.")
        st.rerun()

    st.divider()
    st.markdown("#### Destinos de devolução")
    st.caption("Locais/CDs para onde as operações podem devolver. Um por linha. "
               "Aparecem como lista suspensa no formulário de devolução.")
    with st.form("destinos"):
        destinos_txt = st.text_area(
            "Destinos (um por linha)", value=cfg.get("destinos_devolucao", ""),
            placeholder="CD Cajamar\nCD Guarulhos\nHub CJ2", height=120)
        salvar_dest = st.form_submit_button("Salvar destinos", type="primary", width="stretch")
    if salvar_dest:
        dados.set_config({"destinos_devolucao": destinos_txt.strip()})
        st.success("Destinos salvos.")
        st.rerun()

    st.divider()
    st.markdown("#### Valores dos itens (R$)")
    st.caption("Preço unitário por tipo de ativo. Usado para mostrar às operações quanto devem em dinheiro.")
    with st.form("precos"):
        tipos = list(dp.CORES_TIPO.keys())
        pcols = st.columns(len(tipos))
        vals = {}
        for i, t in enumerate(tipos):
            atual = dp._to_float(cfg.get(f"preco_{t}", ""))
            vals[t] = pcols[i].number_input(t.title(), min_value=0.0, value=float(atual),
                                            step=1.0, format="%.2f", key=f"preco_{t}")
        salvar_precos = st.form_submit_button("Salvar valores", type="primary", width="stretch")
    if salvar_precos:
        dados.set_config({f"preco_{t}": f"{v:.2f}" for t, v in vals.items()})
        st.success("Valores salvos.")
        st.rerun()

    st.divider()
    st.markdown("#### Testar envio")
    if not emailer.smtp_configurado():
        st.info("Preencha e salve o SMTP acima antes de testar.")
        return
    col_a, col_b = st.columns([2, 1])
    destino_teste = col_a.text_input("Enviar e-mail de teste para", placeholder="seu@email.com")
    if col_b.button("Enviar teste", width="stretch"):
        if not destino_teste.strip():
            st.error("Informe um destinatário.")
        else:
            ok, msg = emailer.enviar_email(
                destino_teste.strip(), "Teste — Portal LEVES",
                "<p>Este é um <b>e-mail de teste</b> do Portal LEVES. "
                "Se você recebeu, o SMTP está funcionando.</p>",
            )
            (st.success if ok else st.error)(msg)

    st.caption("⚠️ A senha do SMTP fica na aba Config da planilha. Restrinja o acesso à planilha "
               "e prefira uma **senha de app** dedicada (não a senha principal do e-mail).")
