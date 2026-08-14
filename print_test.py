#!/usr/bin/env python3
"""Maak een testblad op ware grootte om met een echte telefoon te scannen.

De simulatie in test_scan.py zegt hoeveel onscherpte de QR verdraagt, maar
dat blijft een model. Dit blad drukt de schermen af op exact de fysieke maat
van het paneel, zodat je met je eigen toestel, in echt licht, kan proberen of
het scant -- nog voor de hardware binnen is.

E-ink en papier zijn qua contrast vergelijkbaar (allebei diffuus reflecterend,
geen achtergrondverlichting), dus wat op papier op ware grootte leest, leest
op het paneel ook.

    python print_test.py --panel 2in13

Druk het pdf af op 100% / "werkelijke grootte", niet "passend maken".
Controleer met een lat de meetlijn bovenaan.
"""

from __future__ import annotations

import argparse
import sys

from PIL import Image, ImageDraw, ImageFont

import screens

DPI = 300
MM = DPI / 25.4
A4 = (round(210 * MM), round(297 * MM))

# resolutie en actieve schermmaat in mm, volgens de Waveshare-specificaties
PANELS = {
    "2in13": {"res": (250, 122), "mm": (48.55, 23.71)},
    "2in9": {"res": (296, 128), "mm": (66.89, 29.05)},
    "4in2": {"res": (400, 300), "mm": (84.80, 63.60)},
}

CASES = [
    ("kort wachtwoord", "Proximus-1A2B", "zomerhuis42"),
    ("gewoon wachtwoord", "Telenet-3F2A9", "Xk7mQp2ravenzwart"),
    ("lang willekeurig", "KLANT-GASTNET-2026", "b7Q!x2Lm9pR4vZ8tK1nS"),
    ("slechtste geval", 'Cafe;t Hoekje', 'wacht"woord\\met;tekens'),
]


def font(px, bold=False):
    for path in (("C:/Windows/Fonts/arialbd.ttf" if bold else
                  "C:/Windows/Fonts/arial.ttf"),
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, px)
        except OSError:
            continue
    return ImageFont.load_default()


def ruler(draw, x, y, mm_len=100):
    """Meetlijn om te controleren of er echt op 100% is afgedrukt."""
    draw.line([x, y, x + round(mm_len * MM), y], fill=0, width=3)
    for i in range(mm_len + 1):
        if i % 10:
            continue
        tick = x + round(i * MM)
        draw.line([tick, y - 12, tick, y + 12], fill=0, width=3)
    draw.text((x, y + 22), f"Meet deze lijn na: exact {mm_len} mm, "
              f"anders staat je printer niet op 100%", font=font(30), fill=0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", choices=sorted(PANELS), default="2in13")
    parser.add_argument("--wachtwoord", action="store_true",
                        help="wachtwoordregel meedrukken")
    parser.add_argument("-o", "--out", default="scantest.pdf")
    args = parser.parse_args()

    spec = PANELS[args.panel]
    res, (mm_w, mm_h) = spec["res"], spec["mm"]
    target = (round(mm_w * MM), round(mm_h * MM))

    page = Image.new("L", A4, 255)
    draw = ImageDraw.Draw(page)
    margin = round(20 * MM)

    draw.text((margin, margin), f"wpscatcher - scantest {args.panel}",
              font=font(58, bold=True), fill=0)
    draw.text((margin, margin + 78),
              f"Schermen op ware grootte ({mm_w} x {mm_h} mm actief vlak). "
              f"Druk af op 100%, niet passend maken.",
              font=font(32), fill=0)

    y = margin + 175
    ruler(draw, margin, y)
    y += round(18 * MM)

    for label, ssid, psk in CASES:
        payload = screens.wifi_payload(ssid, psk)
        shot, box = screens.connected(res, ssid, psk, payload,
                                      show_password=args.wachtwoord)
        # NEAREST: de moduleranden moeten hard blijven, niet uitgesmeerd
        page.paste(shot.convert("L").resize(target, Image.NEAREST),
                   (margin, y))
        draw.rectangle([margin - 1, y - 1, margin + target[0],
                        y + target[1]], outline=170)

        text_x = margin + target[0] + round(8 * MM)
        draw.text((text_x, y), label, font=font(38, bold=True), fill=0)
        draw.text((text_x, y + 52), f"{ssid} / {psk}", font=font(28), fill=90)
        draw.text((text_x, y + 96), f"{box} px per module = "
                  f"{box * mm_w / res[0]:.2f} mm", font=font(28), fill=90)
        y += target[1] + round(12 * MM)

    draw.text((margin, A4[1] - margin - 150),
              "Lukt scannen hier op papier, dan lukt het op e-ink ook: "
              "vergelijkbaar contrast, geen achtergrondverlichting.",
              font=font(30), fill=0)
    draw.text((margin, A4[1] - margin - 100),
              "Lukt het slechtste geval niet, neem dan een groter paneel - "
              "dat is dan gemeten en niet gegokt.",
              font=font(30), fill=0)

    page.save(args.out, resolution=DPI)
    print(f"{args.out} geschreven -- A4, {DPI} dpi, paneel {args.panel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
