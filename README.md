# wpscatcher

Verbindt bij het opstarten via WPS met een router en toont de verkregen
wifi-gegevens als QR-code op een e-ink schermpje. Twee schermen, meer niet.

```
       ┌──────────────────┐              ┌──────────────────┐
       │  WPS zoeken      │   gelukt     │   ███ ██  ███    │
       │  druk op de knop │  ─────────▶  │   ██ ████ █ █    │
       │        poging 3  │              │   MijnNetwerk    │
       │                  │              │   w4chtw00rd     │
       └──────────────────┘              └──────────────────┘
              ▲                                    │
              └──────── verbinding weg ────────────┘
```

![WPS zoeken](docs/scherm-zoeken.png)
![verbonden](docs/scherm-qr.png)

Het wachtwoord staat er in mono voluit bij: scannen is de snelle weg,
overtypen de weg die altijd werkt — een laptop of desktop zonder camera kan
niet scannen. Wil je het wachtwoord niet leesbaar op het scherm, zet dan
`show_password = no` in `config.ini`.

Dat kost de QR bijna niets. Gemeten met `test_render.py`:

| Paneel | met wachtwoord | zonder | winst |
|---|---|---|---|
| 2,13" 250×122 | 3 px/module | 3 px/module | geen |
| 2,9" 296×128 | 3 px/module | 3 px/module | geen |
| 4,2" 400×300 | 6 px/module | 7 px/module | 1 px/module |
| 7,5" 800×480 | 13 px/module | 13 px/module | geen |

Op de smalle panelen wordt de QR begrensd door de schermhoogte en niet door
de tekstkolom, dus daar is het gratis.

E-ink houdt zijn beeld vast zonder stroom: een uitgeschakeld toestel toont het
wachtwoord dus gewoon verder. Daarom wist wpscatcher bij een nette stop
(`systemctl stop`, afsluiten) het scherm. Uit te zetten met
`clear_on_stop = no`.

## Hoe het werkt

Het toestel draait zijn **eigen `wpa_supplicant`**, niet NetworkManager — NM
kan geen WPS. Met `update_config=1` schrijft de supplicant het resultaat van
een geslaagde `wps_pbc` weg als `psk="hetwachtwoord"`, letterlijk leesbaar.
Dat plaintext wachtwoord is precies wat een wifi-QR nodig heeft; uit de
32-byte hash die sommige stacks bewaren valt geen QR te maken.

De lus is simpel: scherm 1 tonen → `wps_pbc` → maximaal 130 s wachten →
gelukt? credentials uitlezen en scherm 2 tonen → niet gelukt? `wps_cancel`,
even wachten, opnieuw. Valt de verbinding later weg, dan begint hij opnieuw
bij scherm 1.

E-ink wordt alleen bij een echte toestandswissel ververst, nooit op een timer,
en gaat na elke refresh weer slapen. Dat scheelt slijtage en stroom.

## Hardware

| Onderdeel | Keuze | Waarom |
|---|---|---|
| Bord | Raspberry Pi Zero 2 **WH** | de H = header al gesoldeerd |
| Scherm | Waveshare 4,2" e-Paper Module, **zwart-wit**, 400×300 | zie hieronder |
| Kaart | microSD 8 GB+ | Raspberry Pi OS **Lite** (Bookworm) |
| Voeding | usb of powerbank | |

**Neem geen driekleuren-paneel** (zwart/wit/rood of /geel). Die verversen in
15–20 s tegen 2–4 s voor zwart-wit, en je wint er niets mee.

**Neem geen kleiner paneel dan 4,2" als het niet moet.** Een wifi-QR is
byte-mode en komt bij een gewoon wachtwoord op 33–37 modules uit. Gemeten
met `test_render.py`:

| Paneel | px per module | oordeel |
|---|---|---|
| 2,13" 250×122 | 2–3 | leest, maar bij een lang wachtwoord wordt het krap |
| 2,9" 296×128 | 3 | werkt |
| 4,2" 400×300 | 5–6 | comfortabel |
| 7,5" 800×480 | 11–13 | ruim |

Onder de 3 px per module wordt scannen onbetrouwbaar.

Op de smalle panelen zet de layout de QR links en de tekst rechts; op 4,2" en
vierkanter staat de tekst onder de QR. Dat gaat automatisch.

## Installeren op de Zero

```bash
sudo bash install.sh
```

Daarna in `/etc/wpscatcher/config.ini` het juiste paneel zetten — één regel,
`panel = 2in13`, `2in9`, `4in2` of `7in5`. Driver, rotatie en schermmaat
komen daar samen uit, zodat die niet uit de pas kunnen lopen. Herstarten (SPI
heeft een reboot nodig) en meekijken met:

```bash
journalctl -u wpscatcher -f
```

Let op: het script **maskeert NetworkManager**. Daarna beheert wpscatcher
wlan0 zelf. Zorg dat je een andere weg naar binnen hebt (scherm+toetsenbord of
usb-ethernet) voor het geval er iets misloopt — het vraagt eerst om bevestiging.

## Testen zonder hardware

Zonder e-ink valt `display.py` terug op PNG's in `preview/`, dus de hele
layout is op een pc te controleren:

```bash
python wpscatcher.py --simulate -c config.ini
```

Met `--panel 2in9` render je een ander paneel zonder de config aan te raken,
handig om twee toestellen naast elkaar te vergelijken.

```bash
python test_render.py
```

Die laatste rendert elk paneelformaat en **leest de QR weer uit de gerenderde
afbeelding terug**, inclusief lastige gevallen als `wacht"woord\met;tekens`.
Als de payload-escaping breekt, valt dat daar door de mand.

```bash
python test_wps.py
```

Controleert het uitlezen van `wpa_supplicant.conf`: gewone passphrase,
hex-PSK, aanhalingstekens in het wachtwoord, hex-encoded ssid, verborgen
netwerk, meerdere netwerkblokken, en een lege config.

```bash
python test_scan.py
```

Bootst na hoe een telefooncamera de QR ziet: e-ink-grijswaarden in plaats van
papierwit, op ware fysieke schaal, met oplopende onscherpte tot het decoderen
stukloopt. Geen absolute garantie, wel een eerlijke vergelijking tussen
panelen — de 4,2" verdraagt ruim tweemaal zoveel onscherpte als de 2,9".

Het enige dat écht hardware nodig heeft is `wps_pbc` zelf en de SPI-driver.

## Bestanden

| | |
|---|---|
| `wpscatcher.py` | hoofdlus en toestandsmachine |
| `wps.py` | wpa_supplicant aansturen en credentials teruglezen |
| `screens.py` | de twee schermen renderen naar een 1-bit afbeelding |
| `display.py` | e-ink, of PNG als er geen paneel is |
| `install.sh` | opzet op de Zero |
| `config.ini` | instellingen |

## Wat er nog mis kan gaan

- **WPS staat uit op de router.** Veel ISP-routers schakelen het standaard uit
  sinds de Pixie-Dust-aanvallen, en WPA3 ondersteunt het helemaal niet. Dit is
  geen bug in wpscatcher; er is dan simpelweg niets om mee te verbinden.
- **De router geeft een hex-PSK.** Dan logt wpscatcher een waarschuwing en
  zet hij die hex-sleutel in de QR. Android accepteert dat meestal, iOS niet
  altijd. Bij een gewone consumentenrouter gebeurt dit zelden.
- **PBC vereist een fysieke knopdruk** binnen 120 s. De "zoeken"-lus is dus
  wachten, geen zoeken — er gebeurt niets tot iemand die knop indrukt.
