#!/bin/bash
# wpscatcher-autoinstall-fase1
# Fase 1 van de autoinstall -- draait via systemd.run bij de allereerste boot.
#
# Hier is er nog geen netwerk: systemd.run draait vroeg, voordat
# NetworkManager de wifi uit custom.toml heeft toegepast. Dus doen we hier
# alleen wat offline kan, en zetten we een tweede fase klaar die na
# network-online.target het echte installeren doet.
#
# Faalt er iets, dan stopt dit script niet het opstarten: alles wordt gelogd
# naar de FAT-partitie zodat je het van Windows kan lezen.

BOOT=/boot/firmware
LOG=$BOOT/wpscatcher-firstrun.log
SRC=/opt/wpscatcher-src

exec >>"$LOG" 2>&1
echo "=== fase 1: $(date -Is) ==="

set -x

mkdir -p "$SRC"
cp -v "$BOOT"/wpscatcher-payload/* "$SRC"/ || echo "LET OP: payload ontbreekt"
chmod +x "$SRC"/install.sh "$SRC"/stage2.sh 2>/dev/null

PANEL=$(cat "$BOOT/wpscatcher-panel" 2>/dev/null || echo 4in2)
echo "paneel: $PANEL"

# Fase 2 als systemd-unit: die heeft wel netwerk nodig (apt, waveshare-lib).
install -m 644 "$SRC/wpscatcher-provision.service" \
  /etc/systemd/system/wpscatcher-provision.service
systemctl enable wpscatcher-provision.service

# custom.toml NIET hier weghalen: fase 1 draait via systemd.run en dat is
# vroeg -- mogelijk voordat Raspberry Pi OS dat bestand verwerkt heeft. Het
# weghalen gebeurt in fase 2, als de gebruiker en de wifi aantoonbaar staan.

# Onze haak uit cmdline.txt halen, anders draait dit elke boot opnieuw.
sed -i 's| systemd.run=[^ ]*||g; s| systemd.run_success_action=[^ ]*||g' \
  "$BOOT/cmdline.txt"

echo "=== fase 1 klaar, herstarten voor fase 2 ==="
exit 0
