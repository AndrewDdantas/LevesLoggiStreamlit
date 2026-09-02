"""
manual.py — disponibiliza o PDF de treinamento (padrão de devolução) no app.

O arquivo fica em assets/manual_devolucao.pdf e é oferecido como download.
"""

from __future__ import annotations

import os

import streamlit as st

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "manual_devolucao.pdf")
NOME_DOWNLOAD = "Padrao_Devolucao_de_Insumos.pdf"


@st.cache_data(show_spinner=False)
def _bytes() -> bytes | None:
    if os.path.exists(_PATH):
        with open(_PATH, "rb") as f:
            return f.read()
    return None


def disponivel() -> bool:
    return _bytes() is not None


def botao_manual(key: str, label: str = "📘 Manual de devolução (treinamento)"):
    data = _bytes()
    if not data:
        return
    st.download_button(label, data, file_name=NOME_DOWNLOAD, mime="application/pdf",
                       key=key, width="stretch")
