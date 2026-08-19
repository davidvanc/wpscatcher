# --- wpscatcher: toegevoegd door prepare-sd.ps1 -----------------------------
# Imager regelt gebruiker, wifi en ssh; wij zetten alleen onze eigen fase 2
# klaar. Bewust hier en niet via systemd.run: cmdline.txt heeft maar een haak
# en die is van Imager.
{
  echo "=== wpscatcher fase 1: $(date -Is) ==="
  mkdir -p /opt/wpscatcher-src
  cp -v /boot/firmware/wpscatcher-payload/* /opt/wpscatcher-src/     || echo "LET OP: payload ontbreekt"
  chmod +x /opt/wpscatcher-src/install.sh /opt/wpscatcher-src/stage2.sh
  install -m 644 /opt/wpscatcher-src/wpscatcher-provision.service     /etc/systemd/system/wpscatcher-provision.service
  systemctl enable wpscatcher-provision.service
  echo "=== fase 2 staat klaar voor de volgende boot ==="
} >> /boot/firmware/wpscatcher-firstrun.log 2>&1
# --- einde wpscatcher --------------------------------------------------------
