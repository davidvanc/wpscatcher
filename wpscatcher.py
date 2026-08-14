#!/usr/bin/env python3
"""wpscatcher -- verbind via WPS en toon de credentials als QR op e-ink.

Twee schermen, meer niet:
  1. WPS zoeken   -- staat er zolang er geen verbinding is
  2. QR           -- verschijnt zodra we ssid + wachtwoord hebben

Valt de verbinding weg, dan begint hij gewoon opnieuw bij scherm 1.
"""

from __future__ import annotations

import argparse
import configparser
import logging
import os
import signal
import sys
import time

import display as display_mod
import screens
from wps import Credentials, Supplicant, WpaError

log = logging.getLogger("wpscatcher")

# driver, rotatie en paneelmaat horen bij elkaar: de kleine panelen zijn
# staand gemonteerd en moeten 90 graden gedraaid worden. Als losse
# instellingen raken ze uit de pas, vandaar één naam per paneel.
PANEL_PRESETS = {
    "2in13": ("epd2in13_V4", 90, (250, 122)),
    "2in9": ("epd2in9_V2", 90, (296, 128)),
    "4in2": ("epd4in2_V2", 0, (400, 300)),
    "7in5": ("epd7in5_V2", 0, (800, 480)),
}

DEFAULTS = {
    "wifi": {
        "interface": "wlan0",
        "country": "BE",
        "conf": "/etc/wpscatcher/wpa_supplicant.conf",
        "window": "130",        # WPS-venster is 120 s, iets marge
        "retry_delay": "10",
        "forget_on_boot": "yes",
        "request_ip": "yes",
    },
    "display": {
        "panel": "4in2",
        # alleen gebruikt als 'panel' leeggemaakt wordt
        "driver": "epd4in2_V2",
        "rotate": "0",
        "preview_size": "400x300",
        "preview_dir": "preview",
    },
    "ui": {
        "title": "wpscatcher",
        "show_password": "yes",
        "clear_on_stop": "yes",
    },
}


def load_config(path: str | None) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read_dict(DEFAULTS)
    if path and os.path.exists(path):
        # utf-8-sig: een op Windows bewerkte config kan een BOM hebben, en
        # daar struikelt configparser over
        cfg.read(path, encoding="utf-8-sig")
        log.info("config gelezen uit %s", path)
    return cfg


def build_display(cfg, panel: str | None = None):
    section = cfg["display"]
    name = (panel or section.get("panel", "")).strip()

    if name:
        if name not in PANEL_PRESETS:
            raise SystemExit(
                f"onbekend paneel '{name}' -- kies uit: "
                f"{', '.join(sorted(PANEL_PRESETS))}")
        driver, rotate, size = PANEL_PRESETS[name]
        log.info("paneel %s -> %s, rotatie %d", name, driver, rotate)
    else:
        # ontsnappingsluik voor een paneel dat niet in de tabel staat
        width, _, height = section["preview_size"].partition("x")
        driver = section["driver"]
        rotate = section.getint("rotate")
        size = (int(width), int(height))

    return display_mod.make_display(
        driver=driver, rotate=rotate, size=size,
        out_dir=section["preview_dir"],
    )


def show_credentials(disp, creds: Credentials, cfg) -> None:
    payload = screens.wifi_payload(creds.ssid, creds.psk, creds.hidden)
    image, box = screens.connected(disp.size, creds.ssid, creds.psk, payload,
                                   cfg["ui"].getboolean("show_password"))
    if box < 3:
        log.warning(
            "QR staat op %d px per module -- krap; een groter paneel scant "
            "betrouwbaarder", box)
    if creds.is_raw_psk:
        log.warning("QR bevat een hex-PSK; niet elke telefoon accepteert die")
    disp.show(image)
    log.info("QR getoond voor '%s' (%d px per module)", creds.ssid, box)


def watch_connection(sup: Supplicant, poll: int = 30) -> None:
    """Blijf hangen tot de verbinding wegvalt."""
    misses = 0
    while misses < 2:
        time.sleep(poll)
        if sup.state() == "COMPLETED":
            misses = 0
        else:
            misses += 1
    log.info("verbinding weg -- terug naar WPS")


def run(cfg, disp) -> None:
    wifi = cfg["wifi"]
    title = cfg["ui"]["title"]
    interface = wifi["interface"]
    window = wifi.getint("window")

    sup = Supplicant(interface, wifi["conf"], wifi["country"])
    if wifi.getboolean("forget_on_boot"):
        sup.reset_config()
    sup.start()

    attempt = 0
    while True:
        attempt += 1
        disp.show(screens.searching(disp.size, attempt, interface, window, title))

        try:
            sup.wps_pbc()
        except WpaError as exc:
            log.error("WPS starten mislukt: %s", exc)
            time.sleep(wifi.getint("retry_delay"))
            continue

        if not sup.wait_connected(window):
            log.info("poging %d: geen WPS binnen %ds", attempt, window)
            sup.wps_cancel()
            time.sleep(wifi.getint("retry_delay"))
            continue

        creds = sup.credentials()
        if creds is None or not creds.psk:
            log.error("verbonden, maar geen bruikbaar wachtwoord in de config")
            disp.show(screens.message(
                disp.size, "Geen wachtwoord",
                "verbonden, maar niets om te tonen", title))
            time.sleep(wifi.getint("retry_delay"))
            continue

        if wifi.getboolean("request_ip"):
            address = sup.request_ip()
            log.info("ip: %s", address or "geen")

        show_credentials(disp, creds, cfg)
        watch_connection(sup)


def simulate(cfg, disp, ssid: str, psk: str) -> None:
    """Beide schermen renderen zonder wifi, om de layout te controleren."""
    title = cfg["ui"]["title"]
    disp.show(screens.searching(disp.size, 3, cfg["wifi"]["interface"],
                                cfg["wifi"].getint("window"), title))
    show_credentials(disp, Credentials(ssid=ssid, psk=psk), cfg)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", default="/etc/wpscatcher/config.ini")
    parser.add_argument("--simulate", action="store_true",
                        help="render beide schermen met nepgegevens")
    parser.add_argument("--panel", choices=sorted(PANEL_PRESETS),
                        help="paneel uit de config overrulen, handig om "
                             "beide toestellen te vergelijken")
    parser.add_argument("--ssid", default="Telenet-3F2A9")
    parser.add_argument("--psk", default="Xk7mQp2ravenzwart")
    parser.add_argument("--clear", action="store_true",
                        help="scherm wit maken en stoppen")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = load_config(args.config)
    disp = build_display(cfg, args.panel)

    # E-ink houdt zijn beeld vast zonder stroom: bij een nette stop wissen we
    # het scherm, anders blijft een klantwachtwoord op het toestel staan.
    stopping = False

    def on_term(*_):
        nonlocal stopping
        stopping = True
        sys.exit(0)

    signal.signal(signal.SIGTERM, on_term)

    try:
        if args.clear:
            disp.clear()
        elif args.simulate:
            simulate(cfg, disp, args.ssid, args.psk)
        else:
            run(cfg, disp)
    except KeyboardInterrupt:
        stopping = True
    finally:
        if stopping and cfg["ui"].getboolean("clear_on_stop"):
            log.info("scherm wissen bij het stoppen")
            disp.clear()
        disp.sleep()
    return 0


if __name__ == "__main__":
    sys.exit(main())
