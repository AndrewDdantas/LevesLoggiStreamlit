"""
criar_admin.py
Cria o primeiro administrador direto na planilha (rode UMA vez no terminal).

Uso:
    streamlit run criar_admin.py
  ou, sem interface:
    python criar_admin.py admin MinhaSenhaForte!

Precisa do .streamlit/secrets.toml preenchido.
"""

import sys

import auth


def criar(usuario: str, senha: str):
    try:
        if auth.buscar_usuario(usuario):
            print(f'Admin "{usuario}" já existe. Nada a fazer.')
            return
        ok, msg = auth.criar_usuario(usuario, senha, "*", "Administrador", auth.PERFIL_ADM)
        print(msg if ok else f"Falha: {msg}")
    except Exception as e:  # noqa: BLE001
        print("\n[ERRO] Não foi possível acessar a planilha:")
        print("      ", e)
        print("\nDicas: coloque o .json da service account na pasta STREAMLIT/,")
        print("       preencha [app].spreadsheet_id no .streamlit/secrets.toml e")
        print("       compartilhe a planilha (Editor) com o client_email da chave.")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        criar(sys.argv[1], sys.argv[2])
    else:
        # Modo interface (streamlit run criar_admin.py)
        import streamlit as st

        st.title("Criar administrador — Portal LEVES")
        with st.form("adm"):
            u = st.text_input("Usuário", value="admin")
            s = st.text_input("Senha", type="password")
            ok = st.form_submit_button("Criar admin")
        if ok:
            if len(s) < 6:
                st.error("Senha deve ter ao menos 6 caracteres.")
            elif auth.buscar_usuario(u):
                st.warning(f'Usuário "{u}" já existe.')
            else:
                sucesso, msg = auth.criar_usuario(u, s, "*", "Administrador", auth.PERFIL_ADM)
                (st.success if sucesso else st.error)(msg)
