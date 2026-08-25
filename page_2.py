"""
page_2.py — Administração de usuários (somente admin).

Cria novos usuários e ativa/desativa os existentes. Escreve na aba Usuarios
pela camada de extração; o login/hash é responsabilidade de auth.py.
"""

from __future__ import annotations

import streamlit as st

import auth
import data_extraction as dados
import data_processing as dp


def page_2():
    st.subheader("Administração de usuários")

    esq, dir_ = st.columns([1, 1.4])

    with esq:
        st.markdown("<p class='subtitle'>Novo usuário</p>", unsafe_allow_html=True)
        # Destinos sugeridos a partir dos envios.
        df = dp.envios_df()
        destinos = sorted(df["destino"].unique()) if not df.empty else []
        with st.form("novo_user", clear_on_submit=True):
            nome = st.text_input("Nome da operação", placeholder="Ex.: Base São Paulo")
            usuario = st.text_input("Usuário (login)", placeholder="ex.: base_sp")
            senha = st.text_input("Senha", placeholder="mín. 6 caracteres")
            email = st.text_input("E-mail (para cobrança)", placeholder="ex.: base_sp@empresa.com")
            perfil_lbl = st.selectbox("Perfil", ["Operação", "Administrador", "Recebimento"])
            if destinos:
                destino = st.selectbox("Destino (da planilha)", options=[""] + destinos)
                destino_livre = st.text_input("...ou digite um destino novo")
                destino = destino_livre.strip() or destino
            else:
                destino = st.text_input("Destino (exato da planilha)")
            st.caption("Admin e Recebimento não usam destino (preenche com '*' automaticamente).")
            criar = st.form_submit_button("Criar usuário", type="primary", width="stretch")

        if criar:
            perfil = {
                "Administrador": auth.PERFIL_ADM,
                "Recebimento": auth.PERFIL_RECEB,
            }.get(perfil_lbl, auth.PERFIL_OP)
            # Admin/Recebimento veem tudo — destino não é usado para filtro.
            if perfil in (auth.PERFIL_ADM, auth.PERFIL_RECEB) and not destino.strip():
                destino = "*"
            ok, msg = auth.criar_usuario(usuario, senha, destino, nome, perfil, email=email)
            (st.success if ok else st.error)(msg)

    with dir_:
        st.markdown("<p class='subtitle'>Usuários cadastrados</p>", unsafe_allow_html=True)
        usuarios = dados.ler_usuarios()
        if not usuarios:
            st.info("Nenhum usuário cadastrado.")
            return

        logado = (st.session_state.get("usuario") or {}).get("usuario")
        for u in usuarios:
            l1, l2, l3, l4 = st.columns([2.5, 2, 1.2, 1.1])
            l1.markdown(f"**{u['nome']}**  \n`{u['usuario']}`")
            l2.markdown(f"{u['destino']}  \n<span style='color:#6e6e6e;font-size:12px'>"
                        f"{u.get('email') or '— sem e-mail —'}</span>", unsafe_allow_html=True)
            tag = "🛡️ Admin" if u["perfil"] == auth.PERFIL_ADM else "Operação"
            l3.write(f"{tag}  \n{'🟢 Ativo' if u['ativo'] else '⚪ Inativo'}")
            if u["usuario"] == logado:
                l4.caption("você")
            else:
                rotulo = "Desativar" if u["ativo"] else "Ativar"
                if l4.button(rotulo, key=f"tog_{u['usuario']}"):
                    dados.definir_ativo(u["linha"], not u["ativo"])
                    st.rerun()
