# De Pi klaarzetten

Wat er op de kaart moet staan voordat `install.sh` iets zinnigs kan doen.

## 1. Het juiste image — dit is de valkuil

**Voor een Raspberry Pi Zero WH (de originele, niet de 2): neem de 32-bit
versie.** Dat bord heeft een BCM2835 met ARM1176-kern, dat is ARMv6. Het
64-bit image draait daar niet op — je krijgt een kaart die simpelweg niet
boot, zonder bruikbare foutmelding.

In Raspberry Pi Imager: **Raspberry Pi OS (32-bit) Lite** — de gewone, op
Bookworm gebaseerde versie. Niet de 64-bit, niet de Desktop-versie, en ook
niet de **Legacy**-variant. Die Legacy is Bullseye: daar mount de
bootpartitie op `/boot` in plaats van `/boot/firmware` en wordt
`custom.toml` niet verwerkt, dus de [autoinstall](autoinstall/) installeert
er stilletjes niets. Ook `install.sh` en dit stappenplan gaan uit van
Bookworm.

Voor een Zero 2 W geldt hetzelfde, alleen mag het daar ook de 64-bit
Bookworm zijn; die is ARMv8 en slikt allebei.

Lite volstaat: dit toestel heeft geen desktop nodig en elke minder
geïnstalleerde package is minder dat kapot kan.

## 2. Alles vooraf instellen in Imager

Klik het tandwiel (of Ctrl+Shift+X) vóór het schrijven. Daar zet je in één
keer alles wat anders geknoei op een blind systeem wordt:

| Instelling | Waarde |
|---|---|
| Hostname | `wpscatcher-klein` / `wpscatcher-groot` — twee toestellen, geef ze aparte namen |
| Gebruiker | je eigen naam, geen `pi` |
| SSH | **aanzetten, met public key** |
| Wifi | tijdelijk je thuisnetwerk (zie waarschuwing hieronder) |
| Locale | Europe/Brussels, toetsenbord be |

### Public key in plaats van een wachtwoord

Imager plakt de sleutel meteen in `~/.ssh/authorized_keys` en zet
wachtwoordlogin uit. Heb je een PuTTY-sleutel (`.ppk`), open die dan in
PuTTYgen: het vak bovenaan bevat de OpenSSH-vorm die je in Imager plakt
(de regel die met `ssh-rsa` of `ssh-ed25519` begint).

### Waarschuwing over die wifi-instelling

Die thuiswifi werkt **alleen tot je `install.sh` draait**. Daarna is wlan0
van wpscatcher en verdwijnt die verbinding. Gebruik hem dus om te
installeren en te testen, niet als je vaste weg naar binnen.

## 3. sudo zonder wachtwoord

Raspberry Pi OS zet dit meestal al klaar voor de eerste gebruiker. Nakijken:

```bash
sudo -n true && echo "ok, geen wachtwoord nodig"
```

Zo niet, zelf zetten (vervang `david` door je gebruikersnaam):

```bash
echo "david ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/010_nopasswd
sudo chmod 440 /etc/sudoers.d/010_nopasswd
```

Schrijf sudoers-regels altijd in een apart bestand onder `/etc/sudoers.d/`,
nooit rechtstreeks in `/etc/sudoers` — een typfout daar sluit je buiten.

## 4. USB gadget mode: je vaste weg naar binnen

Zodra wpscatcher wlan0 overneemt is dit de enige betrouwbare toegang. Eén
usb-kabel van je laptop naar de Pi geeft stroom én netwerk.

Op de SD-kaart, in de boot-partitie (op Windows zichtbaar zodra je de kaart
insteekt):

`config.txt` — regel toevoegen onderaan:

```
dtoverlay=dwc2
```

`cmdline.txt` — het is één lange regel; voeg direct na `rootwait` toe, met
spaties eromheen en **geen** nieuwe regel:

```
modules-load=dwc2,g_ether
```

Steek de kabel daarna in de **USB**-poort van de Zero, niet in **PWR**. Op de
Zero zijn dat twee identieke micro-usb-poorten; alleen de middelste voert
data. Verkeerde poort = de Pi start wel op maar er gebeurt niets.

```bash
ssh david@wpscatcher-klein.local
```

Reageert `.local` niet, dan mist avahi:

```bash
sudo apt install -y avahi-daemon
```

Op Windows moet er soms nog een RNDIS-stuurprogramma bij voor het virtuele
netwerkapparaat. Dat is het vervelendste stukje van deze opzet; lukt het
niet, gebruik dan de seriële console hieronder.

## 5. Terugvaloptie: seriële console

Werkt altijd, ook als het netwerk stuk is en zelfs als het opstarten
halverwege vastloopt. Je hebt een usb-naar-serieel-adapter (3,3 V) nodig, een
paar euro.

In `config.txt`:

```
enable_uart=1
```

Drie draadjes tussen adapter en de GPIO-header van de Pi: GND op pin 6, de
RX van de adapter op pin 8 (TXD), de TX van de adapter op pin 10 (RXD).
Kruislings dus. Daarna met PuTTY op de COM-poort, 115200 baud.

Sluit **nooit** de 5 V of 3,3 V van de adapter aan als de Pi al gevoed is.

## 6. Volgorde

1. Kaart schrijven met Imager, alles hierboven ingesteld
2. Booten, via wifi inloggen met je sleutel
3. `sudo apt update && sudo apt full-upgrade`
4. Repo halen, `sudo bash install.sh 2in13` (of `4in2`)
5. Rebooten — SPI heeft dat nodig, en wpscatcher neemt wlan0 over
6. Vanaf nu binnengeraken via usb gadget of serieel

Meekijken met wat het toestel doet:

```bash
journalctl -u wpscatcher -f
```
