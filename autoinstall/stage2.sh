#!/bin/bash
# Fase 2 van de autoinstall -- draait als systemd-unit na network-online.
#
# Hier is er wel netwerk, dus dit doet het echte werk: pakketten, de
# waveshare-driver ophalen, en install.sh draaien. Die laatste maskeert
# NetworkManager en neemt wlan0 over, dus dit is eenrichtingsverkeer.
#
# Lukt het netwerk niet, dan stopt dit script zonder de unit uit te
# schakelen: de volgende boot probeert het gewoon opnieuw.

BOOT=/boot/firmware
LOG=$BOOT/wpscatcher-install.log
SRC=/opt/wpscatcher-src

exec >>"$LOG" 2>&1
echo "=== fase 2: $(date -Is) ==="

PANEL=$(cat "$BOOT/wpscatcher-panel" 2>/dev/null || echo 4in2)

# wachten tot er echt iets bereikbaar is; network-online.target is optimistisch
for i in $(seq 1 30); do
  if getent hosts deb.debian.org >/dev/null 2>&1; then
    echo "netwerk ok na ${i} pogingen"
    break
  fi
  echo "wacht op netwerk ($i/30)"
  sleep 10
done

if ! getent hosts deb.debian.org >/dev/null 2>&1; then
  echo "GEEN NETWERK -- unit blijft aan, volgende boot opnieuw"
  exit 1
fi

set -x
export DEBIAN_FRONTEND=noninteractive
export WPSCATCHER_ASSUME_YES=1

if bash "$SRC/install.sh" "$PANEL"; then
  set +x
  echo "=== installatie geslaagd, unit uitschakelen ==="
  # Pas nu het antwoordbestand weghalen: de gebruiker en de wifi hebben
  # aantoonbaar gewerkt, want we hebben er pakketten mee opgehaald. Eerder
  # weggooien zou de provisioning kunnen slopen als er iets misging.
  rm -f "$BOOT/custom.toml"
  systemctl disable wpscatcher-provision.service
  rm -f /etc/systemd/system/wpscatcher-provision.service
  systemctl daemon-reload
  echo "herstarten zodat SPI en wpscatcher opkomen"
  sleep 2
  reboot
else
  set +x
  echo "=== installatie MISLUKT -- zie hierboven; unit blijft aan ==="
  exit 1
fi
