"""De twee schermen, gerenderd naar een 1-bit PIL-image.

Alles schaalt mee met de schermhoogte, zodat dezelfde code werkt op een
2,13" (250x122) en op een 4,2" (400x300).
"""

from __future__ import annotations

import re
from functools import lru_cache

import qrcode
from PIL import Image, ImageDraw, ImageFont

BLACK = 0
WHITE = 255

_FONTS = {
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
    # wachtwoorden in mono: anders is 0/O en l/1 niet uit elkaar te houden
    "mono": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "C:/Windows/Fonts/consolab.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ],
}


@lru_cache(maxsize=64)
def _font(px: int, style: str = "regular"):
    for path in _FONTS[style]:
        try:
            return ImageFont.truetype(path, px)
        except OSError:
            continue
    return ImageFont.load_default()


def _width(draw, text, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _fit(draw, text: str, max_w: int, px: int, style: str = "regular"):
    """Verklein tot het past; kap pas af als verkleinen niet meer helpt."""
    while px > 8:
        font = _font(px, style)
        if _width(draw, text, font) <= max_w:
            return text, font
        px -= 1
    font = _font(px, style)
    while len(text) > 1 and _width(draw, text + "...", font) > max_w:
        text = text[:-1]
    return text + "...", font


def _center(draw, y: int, text: str, font, width: int) -> int:
    draw.text(((width - _width(draw, text, font)) // 2, y), text, font=font, fill=BLACK)
    box = draw.textbbox((0, 0), text, font=font)
    return y + (box[3] - box[1]) + box[1]


def _canvas(size):
    image = Image.new("1", size, WHITE)
    return image, ImageDraw.Draw(image)


def _chrome(draw, size, label: str, right: str = "") -> int:
    """Kader + kopregel. Geeft de y terug waar de inhoud mag beginnen."""
    width, height = size
    pad = max(3, height // 40)
    draw.rectangle([pad, pad, width - pad - 1, height - pad - 1], outline=BLACK)

    px = max(9, height // 22)
    font = _font(px, "bold")
    inner = pad + max(4, height // 40)
    draw.text((inner, inner), " ".join(label.upper()), font=font, fill=BLACK)
    if right:
        rfont = _font(px)
        draw.text((width - inner - _width(draw, right, rfont), inner), right,
                  font=rfont, fill=BLACK)

    rule = inner + px + max(3, height // 45)
    draw.line([inner, rule, width - inner, rule], fill=BLACK)
    return rule + max(4, height // 25)


# ---------------------------------------------------------------- scherm 1

def searching(size, attempt: int, interface: str, window: int, title: str = "wpscatcher"):
    width, height = size
    image, draw = _canvas(size)
    top = _chrome(draw, size, title, f"poging {attempt}")
    pad = max(3, height // 40) + max(4, height // 40)
    inner_w = width - 2 * pad

    bottom = height - pad - max(9, height // 22) - max(4, height // 30)

    title_text, title_font = _fit(draw, "WPS zoeken", inner_w,
                                  max(16, height // 6), "bold")
    sub_text, sub_font = _fit(draw, "Druk nu op de WPS-knop van de router",
                              inner_w, max(10, height // 14))

    # textbbox[3] is de volle hoogte vanaf het tekenpunt, inclusief de
    # ruimte boven de letters -- daarmee rekenen, niet met (bottom - top).
    tb = draw.textbbox((0, 0), title_text, font=title_font)
    sb = draw.textbbox((0, 0), sub_text, font=sub_font)
    gap = max(6, height // 12)
    y = top + ((bottom - top) - (tb[3] + gap + sb[3])) // 2

    draw.text(((width - (tb[2] - tb[0])) // 2 - tb[0], y), title_text,
              font=title_font, fill=BLACK)
    y += tb[3] + gap
    draw.text(((width - (sb[2] - sb[0])) // 2 - sb[0], y), sub_text,
              font=sub_font, fill=BLACK)

    foot = _font(max(9, height // 24))
    draw.text((pad, height - pad - max(9, height // 22)),
              f"{interface} · venster {window}s", font=foot, fill=BLACK)
    return image


# ---------------------------------------------------------------- scherm 2

def wifi_payload(ssid: str, psk: str, hidden: bool = False) -> str:
    """Het WIFI:-formaat dat Android en iOS lezen."""
    def esc(value: str) -> str:
        return re.sub(r'([\\;,":])', r"\\\1", value)

    payload = f"WIFI:S:{esc(ssid)};T:{'WPA' if psk else 'nopass'};P:{esc(psk)};"
    if hidden:
        payload += "H:true;"
    return payload + ";"


def _qr(payload: str, target_px: int):
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L,
                         border=2, box_size=1)
    code.add_data(payload)
    code.make(fit=True)
    modules = code.modules_count + 2 * code.border
    code.box_size = max(1, target_px // modules)
    image = code.make_image(fill_color="black", back_color="white").convert("1")
    return image, code.box_size


def connected(size, ssid: str, psk: str, payload: str):
    """QR met de netwerknaam en het wachtwoord ernaast of eronder.

    Het wachtwoord staat er voluit bij: scannen is de snelle weg, overtypen
    de weg die altijd werkt. Geen kopregel hier -- die ruimte gaat naar de QR.
    """
    width, height = size
    image, draw = _canvas(size)
    pad = max(3, height // 40) + max(4, height // 40)
    wide = width / height >= 1.6

    if wide:
        qr_px = height - 2 * pad
    else:
        qr_px = min(width - 2 * pad,
                    height - 2 * pad - max(28, height * 22 // 100))

    qr_image, box = _qr(payload, qr_px)
    qr_x = pad if wide else (width - qr_image.width) // 2
    qr_y = pad + (qr_px - qr_image.height) // 2 if wide else pad
    image.paste(qr_image, (qr_x, qr_y))

    if wide:
        # tekstkolom naast de QR, als één blok verticaal gecentreerd
        text_x = qr_x + qr_image.width + max(10, width // 24)
        text_w = width - text_x - pad - max(3, width // 50)
        lines = [
            _fit(draw, "VERBONDEN MET", text_w, max(9, height // 14)),
            _fit(draw, ssid, text_w, max(12, height // 8), "bold"),
            _fit(draw, psk, text_w, max(11, height // 10), "mono"),
        ]
        boxes = [draw.textbbox((0, 0), text, font=font) for text, font in lines]
        gaps = [max(2, height // 40), max(5, height // 14), 0]
        y = (height - sum(b[3] for b in boxes) - sum(gaps)) // 2
        for (text, font), bbox, gap in zip(lines, boxes, gaps):
            draw.text((text_x, y), text, font=font, fill=BLACK)
            y += bbox[3] + gap
    else:
        y = qr_y + qr_image.height + max(6, height // 30)
        name, font = _fit(draw, ssid, width - 2 * pad, max(14, height // 11), "bold")
        y = _center(draw, y, name, font, width)
        key, kfont = _fit(draw, psk, width - 2 * pad, max(12, height // 14), "mono")
        _center(draw, y + max(4, height // 40), key, kfont, width)

    return image, box


# ---------------------------------------------------------------- fout

def message(size, headline: str, detail: str = "", title: str = "wpscatcher"):
    width, height = size
    image, draw = _canvas(size)
    top = _chrome(draw, size, title)
    pad = max(3, height // 40) + max(4, height // 40)
    inner_w = width - 2 * pad

    text, font = _fit(draw, headline, inner_w, max(14, height // 8), "bold")
    y = _center(draw, top + (height - top) // 4, text, font, width)
    if detail:
        text, font = _fit(draw, detail, inner_w, max(10, height // 15))
        _center(draw, y + max(4, height // 25), text, font, width)
    return image
