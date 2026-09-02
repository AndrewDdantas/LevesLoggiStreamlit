"""
romaneio.py — geração do Romaneio de Devolução em PDF (com QR code).

O QR aponta para a URL do app com o id e o token da devolução, de modo que a
câmera do time de recebimento abra direto a página de conferência.
"""

from __future__ import annotations

import io

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

AZUL = (0.0, 0.404, 0.988)      # #0067fc
CINZA = (0.35, 0.35, 0.38)


def url_devolucao(base_url: str, id_dev: str, token: str) -> str:
    base = (base_url or "").rstrip("/")
    return f"{base}/?dev={id_dev}&t={token}"


def _qr_png(dados: str) -> ImageReader:
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(dados)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def gerar_romaneio_pdf(dev: dict, itens: list[dict], base_url: str) -> bytes:
    """Gera o PDF do romaneio. `dev` é o cabeçalho; `itens` são {tipo, qtd_declarada}."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    x = 20 * mm
    top = h - 20 * mm

    # Cabeçalho / marca (à esquerda)
    c.setFillColorRGB(*AZUL)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(x, top - 6 * mm, "loggi")
    c.setFillColorRGB(*CINZA)
    c.setFont("Helvetica", 10)
    c.drawString(x, top - 11 * mm, "PORTAL LEVES — Romaneio de Devolução")

    # QR num quadro no canto superior direito, alinhado ao topo
    qr = 30 * mm
    qr_x = w - 20 * mm - qr
    qr_bottom = top - qr
    c.setStrokeColorRGB(0.85, 0.85, 0.85)
    c.setLineWidth(0.8)
    c.roundRect(qr_x - 2.5 * mm, qr_bottom - 6.5 * mm,
                qr + 5 * mm, qr + 9 * mm, 3 * mm, stroke=1, fill=0)
    url = url_devolucao(base_url, dev.get("id", ""), dev.get("token", ""))
    c.drawImage(_qr_png(url), qr_x, qr_bottom, qr, qr)
    c.setFont("Helvetica", 6.5)
    c.setFillColorRGB(*CINZA)
    c.drawCentredString(qr_x + qr / 2, qr_bottom - 4 * mm, "Escaneie para validar o recebimento")

    # Divisor abaixo do bloco (marca + QR)
    y = qr_bottom - 12 * mm
    c.setStrokeColorRGB(*AZUL)
    c.setLineWidth(1.2)
    c.line(x, y, w - 20 * mm, y)

    # Dados da devolução
    y -= 22
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, dev.get("id", ""))
    y -= 18
    c.setFont("Helvetica", 11)

    def linha(rot, val):
        nonlocal y
        c.setFillColorRGB(*CINZA)
        c.drawString(x, y, rot)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(x + 45 * mm, y, str(val))
        y -= 15

    linha("Operação:", dev.get("usuario", ""))
    linha("Destino:", dev.get("destino", ""))
    linha("Devolver para:", dev.get("local_devolucao", "") or "—")
    linha("Veículo (placa):", dev.get("placa", "") or "—")
    linha("Data de emissão:", dev.get("data_criacao", ""))
    linha("Status:", dev.get("status", ""))

    # Tabela de itens
    y -= 12
    c.setFillColorRGB(*AZUL)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, "Tipo de ativo")
    c.drawRightString(w - 20 * mm, y, "Qtd. declarada")
    y -= 6
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(0.6)
    c.line(x, y, w - 20 * mm, y)
    y -= 16

    c.setFont("Helvetica", 11)
    total = 0
    for it in itens:
        c.setFillColorRGB(0, 0, 0)
        c.drawString(x, y, str(it.get("tipo", "")))
        qtd = int(it.get("qtd_declarada", 0) or 0)
        total += qtd
        c.drawRightString(w - 20 * mm, y, f"{qtd:,}".replace(",", "."))
        y -= 15

    y -= 4
    c.line(x, y, w - 20 * mm, y)
    y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, "Total de ativos")
    c.drawRightString(w - 20 * mm, y, f"{total:,}".replace(",", "."))

    # Espaço de conferência (recebimento)
    y -= 40
    c.setFillColorRGB(*CINZA)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(x, y, "Uso do time de recebimento: a conferência/contagem é registrada no sistema ao ler o QR.")
    y -= 18
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 10)
    c.drawString(x, y, "Recebido por: ______________________________")
    c.drawString(x + 90 * mm, y, "Data: ____/____/______")

    # Rodapé
    c.setFillColorRGB(*CINZA)
    c.setFont("Helvetica", 7)
    c.drawString(x, 15 * mm, f"{dev.get('id','')} · token {str(dev.get('token',''))[:8]}… · gerado pelo Portal LEVES")

    c.showPage()
    c.save()
    return buf.getvalue()
