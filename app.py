"""
app.py — Portal LEVES (Loggi) — camada de apresentação (padrão DLE).

Configura a página, aplica o estilo, trata o login próprio (multi-tenant) e
roteia entre as páginas via st.sidebar.radio.

Fluxo: data_extraction -> data_processing -> page_N() -> app.main()
Executar:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

import auth
import contato
import manual
from streamlit_estilizador import PageStyler
from streamlit_sidebar import sidebar

st.set_page_config(page_title="Portal LEVES — Loggi", page_icon="📦", layout="wide")

from page_1 import page_1  # noqa: E402
from page_2 import page_2  # noqa: E402
from page_3 import page_3  # noqa: E402
from page_4 import page_4  # noqa: E402
from page_5 import page_5  # noqa: E402
from page_6 import page_6  # noqa: E402
from page_7 import page_7  # noqa: E402
from page_8 import page_8  # noqa: E402


# ---------------------------------------------------------------------------
# Sessão / login
# ---------------------------------------------------------------------------
def _init_state():
    st.session_state.setdefault("usuario", None)
    st.session_state.setdefault("tentativas", 0)


def logout():
    st.session_state["usuario"] = None
    st.session_state["tentativas"] = 0


def tela_login():
    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        st.markdown(
            "<div style='font-size:34px;font-weight:800;color:#0067fc;"
            "font-family:Montserrat,sans-serif;'>loggi</div>"
            "<div style='letter-spacing:2px;text-transform:uppercase;color:#6e6e6e;"
            "font-size:12px;'>Portal LEVES</div>",
            unsafe_allow_html=True,
        )
        st.caption("Acesse para ver os ativos enviados para a sua operação.")

        if st.session_state["tentativas"] >= 5:
            st.error("Muitas tentativas. Recarregue a página e tente novamente.")

        with st.form("login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar", type="primary", width="stretch")

        if entrar and st.session_state["tentativas"] < 5:
            try:
                u = auth.autenticar(usuario, senha)
            except Exception as e:  # noqa: BLE001
                st.error(f"Erro ao acessar a planilha: {e}")
                return
            if u:
                st.session_state["usuario"] = u
                st.session_state["tentativas"] = 0
                st.rerun()
            else:
                st.session_state["tentativas"] += 1
                st.error("Usuário ou senha inválidos.")

        if manual.disponivel():
            manual.botao_manual(key="manual_login")
        with st.expander("💬 Dúvidas? Fale com o suporte"):
            contato.form_contato(key="login")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    _init_state()
    estilizador = PageStyler()
    estilizador.apply_general_css()

    if not st.session_state["usuario"]:
        tela_login()
        return

    user = st.session_state["usuario"]
    perfil = user.get("perfil")
    eh_admin = perfil == "admin"
    eh_receb = perfil == "recebimento"

    # Devolução aberta pelo QR (id + token na URL).
    scan_id = st.query_params.get("dev")
    scan_token = st.query_params.get("t")

    sidebar()
    with st.sidebar:
        papel = {"admin": "Administrador", "recebimento": "Recebimento"}.get(
            perfil, f"Destino: {user['destino']}")
        st.markdown(
            f"<div class='sb-card'><div class='nome'>{user['nome']}</div>"
            f"<div class='papel'>{papel}</div></div>",
            unsafe_allow_html=True,
        )

        if eh_receb:
            opcoes = ["📥 Recebimento"]
        elif eh_admin:
            opcoes = ["📦 Envios", "📥 Recebimento", "🧾 Conciliação", "🔔 Pendências",
                      "👥 Usuários", "📊 Relatórios", "⚙️ Configurações"]
        else:
            opcoes = ["📦 Envios", "↩️ Devoluções"]

        # Se veio de um QR, já abre o Recebimento.
        idx = 0
        if scan_id and (eh_admin or eh_receb):
            idx = next((i for i, o in enumerate(opcoes) if "Recebimento" in o), 0)

        if len(opcoes) > 1:
            pagina = st.radio("Navegação", opcoes, index=idx, label_visibility="collapsed")
        else:
            pagina = opcoes[0]

        st.markdown("<hr class='sb-sep'>", unsafe_allow_html=True)
        manual.botao_manual(key="manual_side")
        if st.button("↻ Atualizar dados", width="stretch"):
            import data_extraction
            data_extraction.limpar_cache()
            st.rerun()
        if st.button("Sair", width="stretch"):
            logout()
            st.rerun()

        with st.expander("💬 Dúvidas / suporte"):
            contato.form_contato(key="app", nome=user.get("nome", ""),
                                 email=user.get("email", ""))

    try:
        if "Usuários" in pagina:
            page_2()
        elif "Conciliação" in pagina:
            page_6()
        elif "Pendências" in pagina:
            page_8()
        elif "Relatórios" in pagina:
            page_5()
        elif "Configurações" in pagina:
            page_7()
        elif "Recebimento" in pagina:
            page_4(scan_id if (eh_admin or eh_receb) else None, scan_token)
        elif "Devoluções" in pagina:
            page_3()
        else:
            page_1()
    except Exception as e:  # noqa: BLE001
        st.error(
            "Erro ao acessar a planilha: "
            f"{e}. Verifique a chave da service account e o spreadsheet_id (veja o README)."
        )


if __name__ == "__main__":
    main()
