#!/usr/bin/env python3
"""Controleer de layout op elk paneelformaat en of de QR echt uitleesbaar is.

Draait zonder hardware. De QR wordt uit de gerenderde afbeelding
teruggelezen, zodat we weten dat de payload -- inclusief escaping van
puntkomma's en backslashes -- er ongeschonden uitkomt.
"""

from __future__ import annotations

import os
import sys

import zxingcpp
from PIL import Image

import screens

PANELS = {
    "2in13_250x122": (250, 122),
    "2in9_296x128": (296, 128),
    "4in2_400x300": (400, 300),
    "7in5_800x480": (800, 480),
}

CASES = [
    ("kort", "Proximus-1A2B", "zomerhuis42"),
    ("normaal", "Telenet-3F2A9", "Xk7mQp2ravenzwart"),
    ("lang random", "KLANT-GASTNET-2026", "b7Q!x2Lm9pR4vZ8tK1nS"),
    ("speciale tekens", 'Cafe;t Hoekje', 'wacht"woord\\met;tekens'),
    # router gaf de afgeleide sleutel i.p.v. de passphrase: niet over te
    # typen, dus het scherm hoort dat te zeggen in plaats van 64 tekens te
    # proppen. De QR moet er wel gewoon mee werken.
    ("hex-sleutel", "Proximus-9182", "a3f" + "0" * 61),
]

OUT = "preview"


def check(name, size, label, ssid, psk, show_password=True):
    payload = screens.wifi_payload(ssid, psk)
    image, box = screens.connected(size, ssid, psk, payload, show_password)
    suffix = "" if show_password else "_zonderpw"
    path = os.path.join(OUT, f"qr_{name}_{label.replace(' ', '_')}{suffix}.png")
    image.convert("L").save(path)

    results = zxingcpp.read_barcodes(Image.open(path))
    if not results:
        return False, box, "NIET LEESBAAR"
    decoded = results[0].text
    if decoded != payload:
        return False, box, f"payload verminkt: {decoded!r}"
    return True, box, "ok"


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    failures = 0

    for name, size in PANELS.items():
        screens.searching(size, 3, "wlan0", 130).convert("L").save(
            os.path.join(OUT, f"zoek_{name}.png"))
        print(f"\n{name}  ({size[0]}x{size[1]})")
        print(f"  {'':<24} {'met wachtwoord':>15}  {'zonder':>9}")
        for label, ssid, psk in CASES:
            ok_a, box_a, note_a = check(name, size, label, ssid, psk, True)
            ok_b, box_b, note_b = check(name, size, label, ssid, psk, False)
            flag = "PASS" if ok_a and ok_b else "FAIL"
            note = "" if ok_a and ok_b else f"  {note_a} / {note_b}"
            warn = "  <- krap" if min(box_a, box_b) < 3 else ""
            print(f"  {flag}  {label:<18} {box_a:>8} px/mod {box_b:>6} px/mod"
                  f"{note}{warn}")
            failures += not (ok_a and ok_b)

    print(f"\n{failures} mislukt")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
