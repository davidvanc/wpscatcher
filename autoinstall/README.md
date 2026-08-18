# Autoinstall

Kaart erin, script draaien, kaart in de Pi, stroom erop. Daarna hoef je er
niet meer aan te komen — geen Imager-tandwiel, geen ssh-sessie, geen
`install.sh` met de hand.

## Gebruik

1. Schrijf een **kale** Raspberry Pi OS Lite op de kaart met Imager. Sla het
   tandwiel over; dit script doet die instellingen zelf. Voor een **Zero WH
   moet dat de 32-bit versie zijn** — dat bord is ARMv6 en boot niet van een
   64-bit image. Neem de gewone Bookworm- of Trixie-versie, **niet de Legacy-variant**:
   die is Bullseye, en daar bestaat `/boot/firmware` niet en wordt
   `custom.toml` niet verwerkt — de autoinstall doet er stilletjes niets.

2. Draai het script. De kaart hoef je niet aan te wijzen — hij zoekt zelf de
   schijf die zowel `config.txt` als `cmdline.txt` heeft, want dat is de
   boot-partitie van een Pi-kaart. De ext4-rootfs krijgt op Windows toch geen
   letter. Vindt hij er geen of meerdere, dan stopt hij en noemt hij de
   kandidaten; voeg dan `-Drive E:` toe.

```powershell
.\prepare-sd.ps1 -Panel 2in13 -Hostname wpscatcher-klein -User david -PubKeyFile C:\Users\david\.ssh\id_ed25519.pub -WifiSsid MijnThuisnet -WifiPassword geheim123
```

3. Kaart uitwerpen, in de Pi, stroom erop. Twee herstarts later draait
   wpscatcher.

Voor het tweede toestel hetzelfde met `-Panel 4in2 -Hostname wpscatcher-groot`.

## Wat er gebeurt

```
prepare-sd.ps1        (Windows)   schrijft custom.toml, firstrun.sh,
                                  broncode en paneelkeuze op de kaart
        │
        ▼
eerste boot           fase 1      custom.toml maakt gebruiker + wifi aan;
  (geen netwerk)      firstrun.sh kopieert de broncode naar /opt, zet fase 2
                                  klaar, wist custom.toml en de cmdline-haak
        │
        ▼
tweede boot           fase 2      wacht op netwerk, apt, waveshare-driver,
  (wel netwerk)       stage2.sh   install.sh <paneel>, schakelt zichzelf uit
        │
        ▼
derde boot                        wpscatcher draait
```

De splitsing in twee fasen is nodig omdat `systemd.run` vroeg draait, nog
voordat NetworkManager de wifi uit `custom.toml` heeft toegepast. Fase 1 doet
daarom alleen wat offline kan; fase 2 hangt aan `network-online.target`.

Lukt het netwerk in fase 2 niet, dan schakelt die unit zichzelf **niet** uit:
de volgende boot probeert het gewoon opnieuw. Zo verlies je geen kaart aan
een router die net even traag was.

## Meekijken zonder ssh

Beide fasen loggen naar de FAT-partitie, dus je leest ze van Windows door de
kaart terug in je pc te steken:

| Bestand | Wat |
|---|---|
| `wpscatcher-firstrun.log` | fase 1 |
| `wpscatcher-install.log` | fase 2: apt, waveshare, install.sh |

## Over die wifi

Die is er alleen om te kúnnen installeren — pakketten en de waveshare-driver
moeten ergens vandaan komen. Zodra `install.sh` klaar is, maskeert het
NetworkManager en is wlan0 van wpscatcher. Je thuisnetwerk is dan weg.

Daarom zet `prepare-sd.ps1` meteen ook **usb gadget mode** aan (`dwc2` in
`config.txt`, `g_ether` in `cmdline.txt`). Eén usb-kabel naar de USB-poort
van de Zero — niet PWR — geeft stroom én netwerk:

```bash
ssh david@wpscatcher-klein.local
```

## Wachtwoorden op de kaart

`custom.toml` bevat je wifi-wachtwoord en het console-wachtwoord in leesbare
vorm; dat is nu eenmaal hoe dat antwoordbestand werkt. Fase 1 verwijdert het
daarom van de kaart zodra het verwerkt is. Ssh staat sowieso op alleen-sleutel
(`password_authentication = false`), dus dat console-wachtwoord is enkel voor
als je ooit met een scherm en toetsenbord aan het bord staat.

## Veiligheidsrails

Het script weigert te draaien als:

- de opgegeven schijf geen `config.txt` en `cmdline.txt` heeft — dan is het
  niet de boot-partitie van een Pi-kaart
- `cmdline.txt` al een `systemd.run`-haak heeft — dan is de kaart al
  voorbereid, of Imager heeft er zijn eigen script op gezet
- het opgegeven bestand geen OpenSSH publieke sleutel blijkt
