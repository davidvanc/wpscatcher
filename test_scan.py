#!/usr/bin/env python3
"""Hoeveel onscherpte verdraagt de QR op elk paneel?

test_render.py decodeert een perfecte PNG en zegt dus alleen dat de QR
wiskundig klopt. In het echt kijkt een telefooncamera naar grijswit e-ink
onder een hoek, met bewegingsonscherpte. Deze test bootst dat na:

  1. zwart/wit -> de werkelijke grijswaarden van e-ink
  2. schalen naar een vaste fysieke maat (10 px per mm), zodat panelen
     eerlijk vergeleken worden -- een module op 4,2" is fysiek groter dan
     een module op 2,9", ook bij hetzelfde aantal pixels
  3. gaussische vervaging in millimeters opvoeren tot het decoderen stukloopt

De uitkomst is geen absolute garantie, wel een eerlijke vergelijking: hoeveel
marge heeft elk paneel voordat het onleesbaar wordt.
"""

from __future__ import annotations

import sys

import zxingcpp
from PIL import Image, ImageFilter

import screens

# actieve schermmaat volgens de Waveshare-specificaties
PANELS = {
    '2,13" 250x122': {"size": (250, 122), "mm_per_px": 48.55 / 250},
    '2,9" 296x128': {"size": (296, 128), "mm_per_px": 66.89 / 296},
    '4,2" 400x300': {"size": (400, 300), "mm_per_px": 84.80 / 400},
}

CASES = [
    ("kort", "Proximus-1A2B", "zomerhuis42"),
    ("normaal", "Telenet-3F2A9", "Xk7mQp2ravenzwart"),
    ("lang random", "KLANT-GASTNET-2026", "b7Q!x2Lm9pR4vZ8tK1nS"),
]

PX_PER_MM = 10          # gemeenschappelijke fysieke schaal
EINK_BLACK, EINK_WHITE = 45, 205    # e-ink is geen inkt op papier
MAX_BLUR_MM = 2.0
STEP_MM = 0.05


def to_photo(image: Image.Image, mm_per_px: float) -> Image.Image:
    """Paneelpixels -> hoe het er fysiek uitziet, in e-ink grijswaarden."""
    grey = image.convert("L").point(
        lambda v: EINK_WHITE if v > 127 else EINK_BLACK)
    scale = mm_per_px * PX_PER_MM
    return grey.resize(
        (max(1, round(grey.width * scale)), max(1, round(grey.height * scale))),
        Image.LANCZOS)


def max_readable_blur(photo: Image.Image) -> float:
    """Grootste vervaging (in mm) waarbij de QR nog decodeert."""
    last = 0.0
    blur = 0.0
    while blur <= MAX_BLUR_MM:
        candidate = photo.filter(ImageFilter.GaussianBlur(blur * PX_PER_MM))
        if not zxingcpp.read_barcodes(candidate):
            return last
        last = blur
        blur += STEP_MM
    return MAX_BLUR_MM


def main() -> int:
    print(f"Vervaging die de QR nog overleeft (hoger = meer marge)\n")
    results: dict[str, list[float]] = {}

    for name, spec in PANELS.items():
        print(f"{name}")
        margins = []
        for label, ssid, psk in CASES:
            payload = screens.wifi_payload(ssid, psk)
            image, box = screens.connected(spec["size"], ssid, psk, payload)
            photo = to_photo(image, spec["mm_per_px"])
            blur = max_readable_blur(photo)
            margins.append(blur)
            module_mm = box * spec["mm_per_px"]
            print(f"  {label:<14} {box} px/module = {module_mm:.2f} mm  "
                  f"-> leesbaar tot {blur:.2f} mm onscherpte")
        results[name] = margins
        print()

    print("Slechtste geval per paneel:")
    basis = min(min(v) for v in results.values()) or 1
    for name, margins in results.items():
        worst = min(margins)
        print(f"  {name:<16} {worst:.2f} mm   ({worst / basis:.1f}x)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
