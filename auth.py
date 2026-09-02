"""
auth.py
Autenticação do Portal LEVES (versão Streamlit).

Compatível com o app em Apps Script: usa o MESMO esquema de hash
  senha_hash = SHA-256(salt + senha)  (hex)
com salt único por usuário. Assim os usuários criados em qualquer um dos
dois apps funcionam nos dois.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import unicodedata

import data_extraction as sheets

PERFIL_ADM = "admin"
PERFIL_OP = "operacao"
PERFIL_RECEB = "recebimento"
PERFIS_VALIDOS = (PERFIL_ADM, PERFIL_OP, PERFIL_RECEB)


def gerar_salt() -> str:
    return os.urandom(16).hex()


def hash_senha(senha: str, salt: str) -> str:
    return hashlib.sha256((salt + senha).encode("utf-8")).hexdigest()


def normalizar(v) -> str:
    """trim + minúsculas + sem acento (para comparar destinos)."""
    s = "" if v is None else str(v)
    s = s.strip().lower()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def buscar_usuario(usuario: str) -> dict | None:
    usuario = (usuario or "").strip().lower()
    for u in sheets.ler_usuarios():
        if u["usuario"] == usuario:
            return u
    return None


def autenticar(usuario: str, senha: str) -> dict | None:
    """Retorna o usuário se credenciais válidas e ativo; senão None."""
    u = buscar_usuario(usuario)
    if not u or not u["ativo"]:
        return None
    calc = hash_senha(senha, u["salt"])
    if not hmac.compare_digest(calc, u["senha_hash"]):
        return None
    return u


def criar_usuario(usuario, senha, destino, nome, perfil=PERFIL_OP, email="") -> tuple[bool, str]:
    """Valida e cria um usuário. Retorna (ok, mensagem)."""
    usuario = (usuario or "").strip().lower()
    senha = senha or ""
    destino = (destino or "").strip()
    nome = (nome or "").strip() or usuario
    email = (email or "").strip()
    perfil = perfil if perfil in PERFIS_VALIDOS else PERFIL_OP

    if not usuario or not senha or not destino:
        return False, "Usuário, senha e destino são obrigatórios."
    if " " in usuario:
        return False, "O usuário não pode conter espaços."
    if len(senha) < 6:
        return False, "A senha deve ter pelo menos 6 caracteres."
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        return False, "E-mail inválido."
    if buscar_usuario(usuario):
        return False, "Já existe um usuário com esse login."

    salt = gerar_salt()
    sheets.inserir_usuario(usuario, hash_senha(senha, salt), salt, destino, nome, perfil, email=email)
    return True, f'Usuário "{usuario}" criado com sucesso.'


def preparar_usuario_row(usuario, senha, destino, nome, perfil, email, ocupados: set):
    """Valida um registro para importação em massa e devolve a linha pronta para a planilha.

    `ocupados` é o conjunto de logins já usados (existentes + os desta importação).
    Retorna (row | None, erro | None). Não escreve nada.
    """
    from datetime import datetime

    usuario = str(usuario or "").strip().lower()
    senha = str(senha or "")
    destino = str(destino or "").strip()
    nome = str(nome or "").strip() or usuario
    email = str(email or "").strip()
    perfil = perfil if perfil in PERFIS_VALIDOS else PERFIL_OP

    if perfil in (PERFIL_ADM, PERFIL_RECEB) and not destino:
        destino = "*"
    if not usuario or not senha or not destino:
        return None, "usuário, senha e destino são obrigatórios"
    if " " in usuario:
        return None, "usuário não pode conter espaços"
    if len(senha) < 6:
        return None, "senha deve ter ao menos 6 caracteres"
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        return None, "e-mail inválido"
    if usuario in ocupados:
        return None, "login duplicado"

    salt = gerar_salt()
    row = [usuario, hash_senha(senha, salt), salt, destino, nome, perfil,
           "TRUE", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email]
    return row, None


def normalizar_perfil(v) -> str:
    """Converte rótulos livres de perfil para o valor canônico."""
    s = str(v or "").strip().lower()
    if s in ("admin", "administrador"):
        return PERFIL_ADM
    if s in ("recebimento", "recebedor"):
        return PERFIL_RECEB
    return PERFIL_OP
