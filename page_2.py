"""
page_2.py — Administração de usuários (somente admin).

Cria novos usuários e ativa/desativa os existentes. Escreve na aba Usuarios
pela camada de extração; o login/hash é responsabilidade de auth.py.
"""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

import auth
import data_extraction as dados
import data_processing as dp

TEMPLATE_COLS = ["nome", "usuario", "senha", "destino", "perfil", "email"]


def _importar_massa():
    """Importação de usuários via CSV (com template, prévia e relatório)."""
    st.markdown("<p class='subtitle'>Importar em massa (CSV)</p>", unsafe_allow_html=True)
    st.caption("Colunas: nome, usuario, senha, destino, perfil, email. "
               "Perfil aceita: operacao, admin ou recebimento (padrão operacao).")

    modelo = pd.DataFrame([
        {"nome": "Base São Paulo", "usuario": "base_sp", "senha": "trocar123",
         "destino": "GJM", "perfil": "operacao", "email": "base_sp@empresa.com"},
    ], columns=TEMPLATE_COLS)
    st.download_button("Baixar modelo (CSV)", modelo.to_csv(index=False).encode("utf-8-sig"),
                       file_name="modelo_usuarios.csv", mime="text/csv", key="tpl_users")

    up = st.file_uploader("Arraste o CSV preenchido", type=["csv"], key="up_users")
    if not up:
        return

    try:
        raw = up.getvalue()
        df = None
        for sep in (",", ";", "\t"):
            try:
                cand = pd.read_csv(io.BytesIO(raw), sep=sep, dtype=str).fillna("")
                if cand.shape[1] >= 4:
                    df = cand
                    break
            except Exception:  # noqa: BLE001
                continue
        if df is None:
            st.error("Não consegui ler o CSV. Use o modelo como base.")
            return
    except Exception as e:  # noqa: BLE001
        st.error(f"Falha ao ler o arquivo: {e}")
        return

    df.columns = [str(c).strip().lower() for c in df.columns]
    faltando = [c for c in ("usuario", "senha", "destino") if c not in df.columns]
    if faltando:
        st.error("Faltam colunas obrigatórias: " + ", ".join(faltando))
        return

    st.markdown("**Prévia**")
    st.dataframe(df.head(20), width="stretch", hide_index=True)
    st.caption(f"{len(df)} linha(s) no arquivo.")

    if st.button("Importar usuários", type="primary", key="do_import"):
        ocupados = {u["usuario"] for u in dados.ler_usuarios()}
        rows, erros = [], []
        for i, r in df.iterrows():
            perfil = auth.normalizar_perfil(r.get("perfil", ""))
            row, err = auth.preparar_usuario_row(
                r.get("usuario", ""), r.get("senha", ""), r.get("destino", ""),
                r.get("nome", ""), perfil, r.get("email", ""), ocupados)
            if err:
                erros.append({"linha": int(i) + 2, "usuario": r.get("usuario", ""), "motivo": err})
            else:
                rows.append(row)
                ocupados.add(row[0])

        if rows:
            dados.inserir_usuarios_lote(rows)
        st.success(f"{len(rows)} usuário(s) importado(s).")
        if erros:
            st.warning(f"{len(erros)} linha(s) ignorada(s):")
            st.dataframe(pd.DataFrame(erros), width="stretch", hide_index=True)
        if rows:
            st.rerun()


def page_2():
    st.subheader("Administração de usuários")

    with st.expander("📥 Importar usuários em massa (CSV)"):
        _importar_massa()

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
