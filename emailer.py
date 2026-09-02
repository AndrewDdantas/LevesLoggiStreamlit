"""
emailer.py — envio de e-mail via SMTP (configurado pelo admin no app).

Observação: para ENVIAR e-mail usa-se SMTP (IMAP serve apenas para LER a caixa
de entrada). As credenciais ficam na aba Config (chave/valor), preenchidas pelo
admin na tela de Configurações.

Chaves esperadas em Config:
  smtp_host, smtp_port, smtp_user, smtp_password, smtp_from, smtp_tls
"""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import data_extraction as dados

CAMPOS_OBRIGATORIOS = ["smtp_host", "smtp_port", "smtp_user", "smtp_from"]


def config_smtp() -> dict:
    return dados.get_config()


def smtp_configurado() -> bool:
    c = config_smtp()
    return all(str(c.get(k, "")).strip() for k in CAMPOS_OBRIGATORIOS)


def _abrir_conexao(c: dict):
    host = str(c.get("smtp_host", "")).strip()
    port = int(str(c.get("smtp_port", "587")).strip() or 587)
    usar_tls = str(c.get("smtp_tls", "true")).strip().lower() in ("true", "1", "sim")
    if port == 465:  # SSL direto
        server = smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(host, port, timeout=20)
        if usar_tls:
            server.starttls(context=ssl.create_default_context())
    user = str(c.get("smtp_user", "")).strip()
    pwd = str(c.get("smtp_password", ""))
    if user:
        server.login(user, pwd)
    return server


def enviar_email(destinatario: str, assunto: str, corpo_html: str,
                 reply_to: str | None = None) -> tuple[bool, str]:
    """Envia um e-mail HTML. Retorna (ok, mensagem)."""
    destinatario = (destinatario or "").strip()
    if not destinatario:
        return False, "Destinatário vazio."
    c = config_smtp()
    if not smtp_configurado():
        return False, "SMTP não configurado. Preencha em Configurações."
    remetente = str(c.get("smtp_from", "")).strip() or str(c.get("smtp_user", "")).strip()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))
    try:
        server = _abrir_conexao(c)
        server.sendmail(remetente, [destinatario], msg.as_string())
        server.quit()
        return True, f"E-mail enviado para {destinatario}."
    except Exception as e:  # noqa: BLE001
        return False, f"Falha ao enviar para {destinatario}: {e}"


def email_suporte() -> str:
    """E-mail que recebe as dúvidas enviadas pela operação (config email_suporte)."""
    return str(config_smtp().get("email_suporte", "")).strip()


def enviar_duvida(nome: str, email_remetente: str, mensagem: str) -> tuple[bool, str]:
    """Envia uma dúvida da operação para o e-mail de suporte configurado."""
    nome = (nome or "").strip()
    email_remetente = (email_remetente or "").strip()
    mensagem = (mensagem or "").strip()
    if not mensagem:
        return False, "Escreva sua mensagem."
    if not email_remetente or "@" not in email_remetente:
        return False, "Informe um e-mail válido para contato."
    destino = email_suporte()
    if not destino:
        return False, "Canal de dúvidas indisponível (suporte não configurado)."
    if not smtp_configurado():
        return False, "Envio indisponível no momento. Tente mais tarde."

    corpo = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;max-width:560px">
      <div style="font-size:22px;font-weight:800;color:#0067fc">loggi</div>
      <div style="color:#6e6e6e;letter-spacing:2px;text-transform:uppercase;font-size:11px;margin-bottom:14px">Portal LEVES · Dúvida</div>
      <p><b>De:</b> {nome or '(sem nome)'} &lt;{email_remetente}&gt;</p>
      <p><b>Mensagem:</b></p>
      <div style="background:#f1f5fb;border-radius:8px;padding:12px 14px;white-space:pre-wrap">{_escape(mensagem)}</div>
      <p style="color:#6e6e6e;font-size:12px;margin-top:14px">Responda diretamente a este e-mail para falar com a operação.</p>
    </div>
    """
    return enviar_email(destino, f"[Dúvida Portal LEVES] {nome or email_remetente}",
                        corpo, reply_to=email_remetente)


def _escape(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _fmt(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def _brl(v) -> str:
    return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _tabela_itens(itens: list[dict], qtd_key: str, rot_qtd: str, precos: dict | None) -> tuple[str, float]:
    """Monta as linhas da tabela e devolve (html, valor_total). Usa precos se houver."""
    usa_valor = bool(precos) and any((precos or {}).get(str(it["tipo"]).upper(), 0) > 0 for it in itens)
    linhas, valor_total, total_qtd = "", 0.0, 0
    for it in itens:
        q = int(it[qtd_key])
        total_qtd += q
        col_val = ""
        if usa_valor:
            v = q * float((precos or {}).get(str(it["tipo"]).upper(), 0))
            valor_total += v
            col_val = f"<td style='padding:6px 12px;border-bottom:1px solid #eee;text-align:right'>{_brl(v)}</td>"
        linhas += (f"<tr><td style='padding:6px 12px;border-bottom:1px solid #eee'>{it['tipo'].title()}</td>"
                   f"<td style='padding:6px 12px;border-bottom:1px solid #eee;text-align:right'>{_fmt(q)}</td>{col_val}</tr>")
    th_val = "<th style='padding:8px 12px;text-align:right'>Valor</th>" if usa_valor else ""
    td_val_total = (f"<td style='padding:8px 12px;font-weight:700;text-align:right'>{_brl(valor_total)}</td>"
                    if usa_valor else "")
    cabecalho = (f"<tr style='background:#f1f5fb'><th style='padding:8px 12px;text-align:left'>Tipo de ativo</th>"
                 f"<th style='padding:8px 12px;text-align:right'>{rot_qtd}</th>{th_val}</tr>")
    rodape = (f"<tr><td style='padding:8px 12px;font-weight:700'>Total</td>"
              f"<td style='padding:8px 12px;font-weight:700;text-align:right'>{_fmt(total_qtd)}</td>{td_val_total}</tr>")
    html = f"<table style='border-collapse:collapse;width:100%;margin:12px 0'>{cabecalho}{linhas}{rodape}</table>"
    return html, valor_total


def corpo_pendencia(operacao: str, itens: list[dict], total: int, precos: dict | None = None) -> str:
    """HTML do lembrete de pendência de devolução (itens ainda em aberto)."""
    tabela, _ = _tabela_itens(itens, "pendente", "Pendente", precos)
    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;max-width:560px">
      <div style="font-size:26px;font-weight:800;color:#0067fc">loggi</div>
      <div style="color:#6e6e6e;letter-spacing:2px;text-transform:uppercase;font-size:11px;margin-bottom:16px">Portal LEVES</div>
      <p>Olá, <b>{operacao}</b>.</p>
      <p>Consta a seguinte <b>pendência de devolução</b> de ativos com a sua operação.
      Por favor, programe a devolução o quanto antes:</p>
      {tabela}
      <p style="color:#6e6e6e;font-size:13px">Aviso automático do Portal LEVES. Em caso de dúvida, responda a este e-mail.</p>
    </div>
    """


def enviar_pendencia(destinatario: str, operacao: str, itens: list[dict], total: int,
                     precos: dict | None = None) -> tuple[bool, str]:
    """Envia o lembrete de pendência de devolução para um destinatário."""
    return enviar_email(destinatario, f"Pendência de devolução — {operacao} — Portal LEVES",
                        corpo_pendencia(operacao, itens, total, precos))


def corpo_cobranca(operacao: str, competencia_label: str, prazo: str,
                   itens: list[dict], total: int, precos: dict | None = None) -> str:
    """Monta o HTML da cobrança (padrão visual Loggi)."""
    tabela, _ = _tabela_itens(itens, "qtd", "Quantidade", precos)
    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;max-width:560px">
      <div style="font-size:26px;font-weight:800;color:#0067fc">loggi</div>
      <div style="color:#6e6e6e;letter-spacing:2px;text-transform:uppercase;font-size:11px;margin-bottom:16px">Portal LEVES</div>
      <p>Olá, <b>{operacao}</b>.</p>
      <p>Referente à competência <b>{competencia_label}</b>, identificamos ativos enviados que
      <b>não foram devolvidos até o prazo</b> ({prazo}). Segue o detalhamento para acerto:</p>
      {tabela}
      <p style="color:#6e6e6e;font-size:13px">Este é um aviso automático do Portal LEVES.
      Em caso de dúvida, responda a este e-mail.</p>
    </div>
    """
