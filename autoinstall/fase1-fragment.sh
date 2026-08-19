# --- wpscatcher: toegevoegd door prepare-sd.ps1 -----------------------------
# Imager regelt gebruiker, wifi en ssh; wij zetten alleen onze eigen fase 2
# klaar. Bewust hier en niet via systemd.run: cmdline.txt heeft maar een haak
# en die is van Imager.
{
  echo "=== wpscatcher fase 1: $(date -Is) ==="

  # Sleutel er sowieso in zetten, ook als Imager dat al deed. Zonder werkende
  # ssh is er na fase 2 geen weg meer naar binnen over wifi: install.sh
  # maskeert NetworkManager en dan is wlan0 van wpscatcher.
  HOME_DIR=$(getent passwd '@@USER@@' | cut -d: -f6)
  if [ -n "$HOME_DIR" ]; then
    mkdir -p "$HOME_DIR/.ssh"
    grep -qxF '@@PUBKEY@@' "$HOME_DIR/.ssh/authorized_keys" 2>/dev/null       || echo '@@PUBKEY@@' >> "$HOME_DIR/.ssh/authorized_keys"
    chmod 700 "$HOME_DIR/.ssh"; chmod 600 "$HOME_DIR/.ssh/authorized_keys"
    chown -R '@@USER@@' "$HOME_DIR/.ssh"
    echo "sleutel gezet voor @@USER@@ in $HOME_DIR/.ssh/authorized_keys"
  else
    echo "LET OP: gebruiker @@USER@@ bestaat niet, sleutel niet gezet"
  fi
  systemctl enable ssh >/dev/null 2>&1
  mkdir -p /opt/wpscatcher-src
  cp -v /boot/firmware/wpscatcher-payload/* /opt/wpscatcher-src/     || echo "LET OP: payload ontbreekt"
  chmod +x /opt/wpscatcher-src/install.sh /opt/wpscatcher-src/stage2.sh
  install -m 644 /opt/wpscatcher-src/wpscatcher-provision.service     /etc/systemd/system/wpscatcher-provision.service
  systemctl enable wpscatcher-provision.service
  echo "=== fase 2 staat klaar voor de volgende boot ==="
} >> /boot/firmware/wpscatcher-firstrun.log 2>&1
# --- einde wpscatcher --------------------------------------------------------
