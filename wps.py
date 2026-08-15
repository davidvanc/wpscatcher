"""Aansturing van een eigen wpa_supplicant-instantie via wpa_cli.

We draaien bewust *niet* via NetworkManager: NM ondersteunt geen WPS.
Een eigen supplicant met update_config=1 schrijft na een geslaagde
wps_pbc het netwerk weg als psk="wachtwoord" -- en dat plaintext
wachtwoord is precies wat we in de QR nodig hebben.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass

log = logging.getLogger("wps")

CONF_TEMPLATE = """# Aangemaakt door wpscatcher -- niet handmatig bewerken.
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country={country}
"""

_HEX64 = re.compile(r"\A[0-9a-fA-F]{64}\Z")


def _network_blocks(text: str) -> list[dict[str, str]]:
    """Splits de config in network-blokken, regel voor regel.

    Niet met een regex over het hele blok: een } in een gequote waarde
    (psk="abc}def") kapt zo'n match te vroeg af. wpa_supplicant schrijft
    één veld per regel en de sluitaccolade op een eigen regel, dus
    regelgewijs is er geen dubbelzinnigheid.
    """
    blocks: list[dict[str, str]] = []
    fields: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if fields is None:
            if re.fullmatch(r"network\s*=\s*\{", line):
                fields = {}
        elif line == "}":
            blocks.append(fields)
            fields = None
        elif "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            fields[key.strip()] = value.strip()
    return blocks


class WpaError(RuntimeError):
    pass


@dataclass
class Credentials:
    ssid: str
    psk: str
    hidden: bool = False

    @property
    def is_raw_psk(self) -> bool:
        """True als we de 32-byte PMK hebben i.p.v. de passphrase.

        Dan is de QR onbetrouwbaar: lang niet elke telefoon accepteert een
        hex-PSK in het P:-veld.
        """
        return bool(_HEX64.match(self.psk))


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return re.sub(r"\\(.)", r"\1", value[1:-1])
    return value


def _decode_ssid(value: str) -> str:
    """Een niet-gequote ssid is hex-encoded (gebeurt bij niet-ascii namen)."""
    raw = value.strip()
    if raw.startswith('"'):
        return _unquote(raw)
    if len(raw) % 2 == 0 and re.fullmatch(r"[0-9a-fA-F]+", raw or "x"):
        try:
            return bytes.fromhex(raw).decode("utf-8", "replace")
        except ValueError:
            pass
    return raw


class Supplicant:
    def __init__(self, interface: str, conf_path: str, country: str = "BE"):
        self.interface = interface
        self.conf_path = conf_path
        self.country = country

    # -- procesbeheer ----------------------------------------------------

    def reset_config(self) -> None:
        """Gooi opgeslagen netwerken weg zodat elke boot echt via WPS gaat."""
        os.makedirs(os.path.dirname(self.conf_path) or ".", exist_ok=True)
        with open(self.conf_path, "w", encoding="utf-8") as fh:
            fh.write(CONF_TEMPLATE.format(country=self.country))
        os.chmod(self.conf_path, 0o600)
        log.info("wpa_supplicant.conf leeggemaakt (%s)", self.conf_path)

    def start(self) -> None:
        subprocess.run(["killall", "wpa_supplicant"], capture_output=True)
        time.sleep(1)
        subprocess.run(["ip", "link", "set", self.interface, "up"], capture_output=True)
        cmd = [
            "wpa_supplicant", "-B",
            "-i", self.interface,
            "-c", self.conf_path,
            "-D", "nl80211",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise WpaError(f"wpa_supplicant start faalde: {result.stderr.strip()}")
        # de control socket is er niet meteen
        for _ in range(20):
            if self._cli("ping", check=False).strip().endswith("PONG"):
                log.info("wpa_supplicant draait op %s", self.interface)
                return
            time.sleep(0.5)
        raise WpaError("geen contact met wpa_supplicant via wpa_cli")

    def stop(self) -> None:
        self._cli("terminate", check=False)

    # -- commando's ------------------------------------------------------

    def _cli(self, *args: str, check: bool = True, timeout: int = 15) -> str:
        try:
            result = subprocess.run(
                ["wpa_cli", "-i", self.interface, *args],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise WpaError(f"wpa_cli {' '.join(args)} liep vast") from exc
        except FileNotFoundError as exc:
            if check:
                raise WpaError("wpa_cli niet gevonden") from exc
            return ""
        if check and result.returncode != 0:
            raise WpaError(f"wpa_cli {' '.join(args)}: {result.stderr.strip()}")
        return result.stdout

    def wps_pbc(self) -> None:
        """Start een WPS push-button sessie.

        Het venster is 120 s: de router accepteert ons pas nadat iemand
        daar op de knop drukt. Tot zolang staan we gewoon te wachten.
        """
        out = self._cli("wps_pbc").strip()
        if "OK" not in out:
            raise WpaError(f"wps_pbc geweigerd: {out or '(geen antwoord)'}")
        log.info("WPS push-button sessie gestart")

    def wps_cancel(self) -> None:
        self._cli("wps_cancel", check=False)

    def state(self) -> str:
        for line in self._cli("status", check=False).splitlines():
            if line.startswith("wpa_state="):
                return line.split("=", 1)[1].strip()
        return "UNKNOWN"

    def wait_connected(self, timeout: float, poll: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            current = self.state()
            if current != last:
                log.info("wpa_state=%s", current)
                last = current
            if current == "COMPLETED":
                return True
            time.sleep(poll)
        return False

    # -- resultaat -------------------------------------------------------

    def credentials(self) -> Credentials | None:
        """Bewaar de config en lees ssid + wachtwoord terug."""
        self._cli("save_config", check=False)
        try:
            with open(self.conf_path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            log.error("kan %s niet lezen: %s", self.conf_path, exc)
            return None

        blocks = _network_blocks(text)
        if not blocks:
            log.error("geen network={} blok in de config na WPS")
            return None
        fields = blocks[-1]  # laatste blok = wat WPS net schreef

        ssid = _decode_ssid(fields.get("ssid", ""))
        if not ssid:
            log.error("network-blok zonder ssid")
            return None

        creds = Credentials(
            ssid=ssid,
            psk=_unquote(fields.get("psk", "")),
            hidden=fields.get("scan_ssid", "0") == "1",
        )
        if creds.is_raw_psk:
            log.warning("router leverde een hex-PSK i.p.v. een passphrase")
        return creds

    def request_ip(self) -> str | None:
        """Optioneel: een IP halen. Voor de QR zelf is dit niet nodig."""
        for client, args in (
            ("dhcpcd", ["-n", self.interface]),
            ("dhclient", ["-1", self.interface]),
            ("udhcpc", ["-i", self.interface, "-n", "-q"]),
        ):
            if shutil.which(client):
                subprocess.run([client, *args], capture_output=True, timeout=40)
                break
        else:
            log.info("geen dhcp-client gevonden, blijf zonder IP")
            return None

        out = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", self.interface],
            capture_output=True, text=True,
        ).stdout
        match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
        return match.group(1) if match else None
