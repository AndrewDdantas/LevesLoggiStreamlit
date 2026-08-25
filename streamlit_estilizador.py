import streamlit as st


class PageStyler:
    """Estilizador padrão dos painéis do time de Dados da Loggi (padrão DLE).

    Uso:
        estilizador = PageStyler()
        estilizador.apply_general_css()                 # em app.main()
        estilizador.apply_sidebar_css(image_base64)     # a partir de streamlit_sidebar.py
    """

    def __init__(self):
        pass

    def apply_general_css(self):
        """Aplica o CSS geral: fonte Montserrat, cores da marca e layout."""
        st.markdown(
            """
        <style>
        li, span, input, label, small {
            font-family: Monteserrat, sans-serif;
        }
        li, input, label, small { font-size: 16px; }
        [data-testid=textInputRootElement] { font-family: Monteserrat, sans-serif; }
        .st-emotion-cache-1jmvea6 p {
            word-break: break-word; margin-bottom: 0px; font-size: 16px;
        }
        /* Subtítulos em azul da marca */
        h2, .stSubheader {
            font-family: Monteserrat, sans-serif;
            font-size: 40px; font-weight: bold; color: #0067fc;
        }
        .tool-subtitle {
            font-family: Monteserrat, sans-serif;
            font-size: 16px; font-weight: bold; color: #00baff; text-decoration: underline;
        }
        .page-title {
            font-family: Monteserrat, sans-serif;
            font-size: 30px; font-weight: 400; text-align: center; color: #000000;
        }
        p { font-family: Monteserrat, sans-serif; font-size: 16px; }
        [data-testid=stCheckbox] { font-size: 16px; }
        .custom-text { font-family: Monteserrat, sans-serif; text-align: justify; }
        .css-1y4p8pa { max-width: 975px; }
        .st-emotion-cache-1y4p8pa { max-width: 62rem; }
        h1 {
            text-align: center; font-size: 30px;
            font-family: Monteserrat, sans-serif; font-weight: 400;
        }
        .custom-sidebar-footer {
            position: relative; bottom: 0px; left: 0; width: 100%;
            font-size: 14px; text-align: left;
        }
        .custom-sidebar-footer a:hover { text-decoration: underline; }
        .subtitle { font-family: Monteserrat, sans-serif; font-size: 20px; font-weight: bold; }
        .descricao { font-family: Monteserrat, sans-serif; max-width: 200px; text-align: justify; }
        [data-testid=stAppViewBlockContainer] { padding-left: 50px; padding-top: 0; }
        .streamlit-expanderHeader { background-color: #f0f2f6; }
        .streamlit-expanderContent { background-color: #ffffff; }
        </style>
        """,
            unsafe_allow_html=True,
        )

    def apply_sidebar_css(self, image_base64):
        """Sidebar azul da marca com a logo (base64) no topo e texto branco.

        Argumentos:
            image_base64: str — imagem (ex.: logo da lebre) codificada em base64.
        """
        st.markdown(
            f"""
        <style>
            [data-testid="stSidebar"] {{
                background-image: url("data:image/png;base64,{image_base64}");
                background-repeat: no-repeat;
                background-size: 160px;
                background-position: center top;
                position: relative;
                padding-top: 40px;
                background-color: #0067fc;
            }}
            [data-testid="stSidebar"]::before {{
                margin-left: 20px; margin-top: 20px; font-size: 30px;
                position: relative; top: 100px;
            }}
            [data-testid="stSidebar"] h1,
            [data-testid="stSidebar"] li,
            [data-testid="stSidebar"] p {{ color: white; }}
        </style>
        """,
            unsafe_allow_html=True,
        )
