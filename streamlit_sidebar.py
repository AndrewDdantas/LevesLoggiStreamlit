"""
streamlit_sidebar.py — sidebar padrão Loggi (padrão DLE).

Pinta a sidebar de azul da marca, coloca a logo da lebre (se existir) e injeta
estilos extras para deixar botões e controles legíveis sobre o fundo azul.
"""

import base64
import os

import streamlit as st

from streamlit_estilizador import PageStyler

LOGO_PATH = "image_simbolo_lebre.png"


def get_base64_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _estilos_extra():
    """Ajustes finos: botões, radio e inputs visíveis sobre o azul da sidebar."""
    st.markdown(
        """
    <style>
      /* Gradiente sutil sobre o azul da marca */
      [data-testid="stSidebar"] > div:first-child {
        background: linear-gradient(180deg, #0067fc 0%, #0052d6 100%);
      }
      /* Botões da sidebar: contorno branco translúcido, texto branco legível */
      [data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.12);
        color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.55);
        border-radius: 10px;
        font-weight: 600;
        transition: all .15s ease;
      }
      [data-testid="stSidebar"] .stButton > button:hover {
        background: #ffffff;
        color: #0067fc !important;
        border-color: #ffffff;
      }
      [data-testid="stSidebar"] .stButton > button * { color: inherit !important; }
      /* Radio de navegação */
      [data-testid="stSidebar"] [role="radiogroup"] label {
        color: #ffffff !important;
      }
      [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color:#ffffff !important; }
      /* Cartão do usuário */
      .sb-card {
        background: rgba(255,255,255,0.14);
        border: 1px solid rgba(255,255,255,0.25);
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 8px;
      }
      .sb-card .nome { color:#fff; font-weight:700; font-size:15px; }
      .sb-card .papel { color:rgba(255,255,255,.85); font-size:13px; margin-top:2px; }
      .sb-sep { border:none; border-top:1px solid rgba(255,255,255,.25); margin:14px 0; }
    </style>
    """,
        unsafe_allow_html=True,
    )


def sidebar():
    estilizador = PageStyler()
    base = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(base, LOGO_PATH)
    if os.path.exists(caminho):
        estilizador.apply_sidebar_css(get_base64_image(caminho))
    else:
        estilizador.apply_sidebar_css("")  # sem logo, mantém o azul
    _estilos_extra()

    with st.sidebar:
        st.markdown(
            "<div style='color:#fff;font-size:22px;font-weight:800;"
            "letter-spacing:.3px;margin-top:6px;'>Portal LEVES</div>"
            "<div style='color:rgba(255,255,255,.8);font-size:11px;"
            "letter-spacing:2px;text-transform:uppercase;'>loggi</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<hr class='sb-sep'>", unsafe_allow_html=True)
