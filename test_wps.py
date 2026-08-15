#!/usr/bin/env python3
"""Controleer het uitlezen van wpa_supplicant.conf na een WPS-sessie.

Dit is het stuk dat stilletjes fout kan gaan: als de router geen passphrase
maar een hex-PSK teruggeeft, of als de ssid rare tekens bevat, moeten we dat
zien in plaats van een lege of verminkte QR te tonen.
"""

from __future__ import annotations

import os
import sys
import tempfile

import screens
from wps import Supplicant

HEADER = """ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=BE
"""

CASES = [
    (
        "gewone WPS-uitkomst",
        'network={\n\tssid="Telenet-3F2A9"\n\tpsk="Xk7mQp2ravenzwart"\n'
        '\tproto=RSN\n\tkey_mgmt=WPA-PSK\n}\n',
        {"ssid": "Telenet-3F2A9", "psk": "Xk7mQp2ravenzwart", "raw": False},
    ),
    (
        "hex-PSK i.p.v. passphrase",
        "network={\n\tssid=\"Proximus-9182\"\n\tpsk="
        + "a" * 64 + "\n\tkey_mgmt=WPA-PSK\n}\n",
        {"ssid": "Proximus-9182", "psk": "a" * 64, "raw": True},
    ),
    (
        "aanhalingsteken in wachtwoord",
        'network={\n\tssid="Cafe t Hoekje"\n\tpsk="wacht\\"woord"\n}\n',
        {"ssid": "Cafe t Hoekje", "psk": 'wacht"woord', "raw": False},
    ),
    (
        # een } in het wachtwoord mag het blok niet afkappen, en de velden
        # erna moeten nog gelezen worden
        "accolade in wachtwoord",
        'network={\n\tssid="Frituur"\n\tpsk="friet}es123"\n\tkey_mgmt=WPA-PSK\n}\n',
        {"ssid": "Frituur", "psk": "friet}es123", "raw": False},
    ),
    (
        "hex-encoded ssid",
        "network={\n\tssid=4b6c616e7457696669\n\tpsk=\"geheim123\"\n}\n",
        {"ssid": "KlantWifi", "psk": "geheim123", "raw": False},
    ),
    (
        "verborgen netwerk",
        'network={\n\tssid="StilNet"\n\tpsk="abc12345"\n\tscan_ssid=1\n}\n',
        {"ssid": "StilNet", "psk": "abc12345", "raw": False, "hidden": True},
    ),
    (
        "twee blokken -- laatste telt",
        'network={\n\tssid="Oud"\n\tpsk="oudwachtwoord"\n}\n'
        'network={\n\tssid="Nieuw"\n\tpsk="nieuwwachtwoord"\n}\n',
        {"ssid": "Nieuw", "psk": "nieuwwachtwoord", "raw": False},
    ),
]


def main() -> int:
    failures = 0
    tmp = tempfile.mkdtemp(prefix="wpscatcher-")
    conf = os.path.join(tmp, "wpa_supplicant.conf")

    for label, block, want in CASES:
        with open(conf, "w", encoding="utf-8") as fh:
            fh.write(HEADER + block)

        creds = Supplicant("wlan0", conf, "BE").credentials()
        problems = []
        if creds is None:
            problems.append("niets teruggekregen")
        else:
            if creds.ssid != want["ssid"]:
                problems.append(f"ssid {creds.ssid!r} != {want['ssid']!r}")
            if creds.psk != want["psk"]:
                problems.append(f"psk {creds.psk!r} != {want['psk']!r}")
            if creds.is_raw_psk != want["raw"]:
                problems.append(f"is_raw_psk {creds.is_raw_psk} != {want['raw']}")
            if creds.hidden != want.get("hidden", False):
                problems.append(f"hidden {creds.hidden}")

        print(f"  {'FAIL' if problems else 'PASS'}  {label:<28} "
              f"{'; '.join(problems) or 'ok'}")
        failures += bool(problems)

    # lege config: geen netwerk -> geen credentials, geen crash
    with open(conf, "w", encoding="utf-8") as fh:
        fh.write(HEADER)
    empty = Supplicant("wlan0", conf, "BE").credentials()
    ok = empty is None
    print(f"  {'PASS' if ok else 'FAIL'}  {'lege config':<28} "
          f"{'ok' if ok else f'kreeg {empty!r}'}")
    failures += not ok

    # de payload moet ook kloppen voor een verborgen netwerk
    payload = screens.wifi_payload("StilNet", "abc12345", hidden=True)
    ok = payload == "WIFI:S:StilNet;T:WPA;P:abc12345;H:true;;"
    print(f"  {'PASS' if ok else 'FAIL'}  {'payload verborgen net':<28} {payload}")
    failures += not ok

    print(f"\n{failures} mislukt")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
