#!/usr/bin/env bash
# Installeer wpscatcher op een Raspberry Pi Zero 2 W met Raspberry Pi OS Lite.
# Draaien met: sudo bash install.sh
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP=/opt/wpscatcher
ETC=/etc/wpscatcher
EPAPER_REPO=https://github.com/waveshareteam/e-Paper.git

# Welk paneel op dit toestel zit. Eén codebase, twee toestellen: het
# verschil zit alleen in deze regel.
PANEL="${1:-4in2}"

[[ $EUID -eq 0 ]] || { echo "Draai dit met sudo."; exit 1; }

case "$PANEL" in
  2in13|2in13v3|2in9|4in2|7in5) ;;
  *) echo "Onbekend paneel '$PANEL'."
     echo "Gebruik: sudo bash install.sh [2in13|2in13v3|2in9|4in2|7in5]"
     exit 1 ;;
esac
echo "Installeren voor paneel: $PANEL"

echo "== 1/6  pakketten =="
apt-get update
apt-get install -y --no-install-recommends \
  python3 python3-pil python3-qrcode python3-spidev python3-gpiozero \
  python3-lgpio wpasupplicant iw git

echo
echo "== 2/6  SPI aanzetten =="
if command -v raspi-config >/dev/null; then
  raspi-config nonint do_spi 0
else
  grep -q '^dtparam=spi=on' /boot/firmware/config.txt 2>/dev/null \
    || echo 'dtparam=spi=on' >> /boot/firmware/config.txt
fi

echo
echo "== 3/6  waveshare_epd ophalen =="
if [[ -d $APP/waveshare_epd ]]; then
  echo "staat er al, overslaan"
else
  TMP=$(mktemp -d)
  # sparse checkout: de volle repo is honderden MB, wij willen één map
  git clone --depth 1 --filter=blob:none --sparse "$EPAPER_REPO" "$TMP/e-Paper"
  git -C "$TMP/e-Paper" sparse-checkout set RaspberryPi_JetsonNano/python/lib/waveshare_epd
  mkdir -p "$APP"
  cp -r "$TMP/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd" "$APP/"
  rm -rf "$TMP"
fi

echo
echo "== 4/6  NetworkManager uitschakelen op wlan0 =="
# NetworkManager kan geen WPS en pakt anders wlan0 af van onze supplicant.
if systemctl is-enabled NetworkManager >/dev/null 2>&1; then
  cat <<'WARN'
NetworkManager wordt gemaskeerd. Dit toestel beheert wlan0 daarna zelf.
Zorg dat je een andere weg naar binnen hebt (usb gadget, serieel, of
toetsenbord+scherm) voor het geval er iets misloopt.
WARN
  if [[ ${WPSCATCHER_ASSUME_YES:-} == 1 ]]; then
    echo "WPSCATCHER_ASSUME_YES=1 -- niet vragen, doorgaan"
  else
    read -r -p "Doorgaan? [j/N] " answer
    [[ ${answer,,} == j ]] || { echo "Afgebroken."; exit 1; }
  fi
  systemctl disable --now NetworkManager
  systemctl mask NetworkManager
  systemctl disable --now wpa_supplicant 2>/dev/null || true
else
  echo "NetworkManager staat niet aan, niets te doen"
fi

echo
echo "== 5/6  bestanden plaatsen =="
mkdir -p "$APP" "$ETC"
install -m 755 "$SRC/wpscatcher.py" "$APP/wpscatcher.py"
install -m 644 "$SRC/wps.py" "$SRC/screens.py" "$SRC/display.py" "$APP/"
if [[ -f $ETC/config.ini ]]; then
  echo "$ETC/config.ini bestaat al -- niet overschreven"
  install -m 644 "$SRC/config.ini" "$ETC/config.ini.nieuw"
  sed -i "s/^panel = .*/panel = $PANEL/" "$ETC/config.ini.nieuw"
else
  install -m 644 "$SRC/config.ini" "$ETC/config.ini"
  sed -i "s/^panel = .*/panel = $PANEL/" "$ETC/config.ini"
  echo "panel = $PANEL gezet in $ETC/config.ini"
fi

echo
echo "== 6/6  service =="
install -m 644 "$SRC/wpscatcher.service" /etc/systemd/system/wpscatcher.service
systemctl daemon-reload
systemctl enable wpscatcher.service

cat <<EOF

Klaar, ingesteld voor paneel '$PANEL'. Nog even doen:
  1. Herstart (SPI heeft een reboot nodig):   sudo reboot
  2. Meekijken:                               journalctl -u wpscatcher -f

Klopt de drivernaam niet met jouw revisie (Waveshare heeft _V2/_V3/_V4
naast elkaar), pas dan PANEL_PRESETS aan in $APP/wpscatcher.py.

Handmatig testen zonder de service:
  sudo systemctl stop wpscatcher
  sudo python3 $APP/wpscatcher.py -c $ETC/config.ini --simulate
EOF
