<#
.SYNOPSIS
Maakt een verse Raspberry Pi OS-kaart klaar zodat wpscatcher zichzelf
installeert bij de eerste boot. Geen Imager-menu's, geen ssh-sessie.

.DESCRIPTION
Schrijf eerst een kale "Raspberry Pi OS Lite" op de kaart met Imager --
zonder enige aanpassing, het tandwiel mag je overslaan. Voor een Zero WH
moet dat de 32-bit versie zijn (ARMv6).

Daarna dit script op de boot-partitie loslaten. Het zet er neer:

  custom.toml          antwoordbestand: hostname, gebruiker, ssh-sleutel, wifi
  firstrun.sh          fase 1, draait offline bij de eerste boot
  wpscatcher-payload/  de broncode
  wpscatcher-panel     welk scherm er op dit toestel zit

Bij de eerste boot maakt fase 1 de gebruiker aan en zet fase 2 klaar; die
haalt na netwerk de pakketten op en draait install.sh. Daarna herstart het
toestel en draait wpscatcher.

.EXAMPLE
Zonder -Drive zoekt hij de kaart zelf: de schijf die zowel config.txt als
cmdline.txt heeft. Vindt hij er geen of meerdere, dan stopt hij en moet je
-Drive E: erbij zetten.

.\prepare-sd.ps1 -Panel 2in13 -Hostname wpscatcher-klein `
    -User david -PubKeyFile C:\Users\david\.ssh\id_ed25519.pub `
    -WifiSsid MijnThuisnet -WifiPassword geheim123
#>

[CmdletBinding()]
param(
    [string]$Drive,
    [Parameter(Mandatory)][ValidateSet('2in13', '2in13v3', '2in9', '4in2', '7in5')]
    [string]$Panel,
    [Parameter(Mandatory)][string]$Hostname,
    [Parameter(Mandatory)][string]$User,
    [Parameter(Mandatory)][string]$PubKeyFile,
    [Parameter(Mandatory)][string]$WifiSsid,
    [Parameter(Mandatory)][string]$WifiPassword,
    [string]$Password = 'wpscatcher',
    [string]$Country = 'BE',
    [string]$Timezone = 'Europe/Brussels',
    [string]$Keymap = 'be',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
function Find-BootPartitie {
    # De boot-partitie van een Pi-kaart is FAT en krijgt een letter; de rootfs
    # is ext4 en die ziet Windows niet. Herkenbaar aan de twee bestanden die
    # er altijd op staan.
    Get-Volume -ErrorAction SilentlyContinue |
        Where-Object { $_.DriveLetter } |
        ForEach-Object {
            $pad = "$($_.DriveLetter):"
            if ((Test-Path (Join-Path $pad 'config.txt')) -and
                (Test-Path (Join-Path $pad 'cmdline.txt'))) {
                [pscustomobject]@{
                    Pad       = $pad
                    Label     = $_.FileSystemLabel
                    Verwissel = ($_.DriveType -eq 'Removable')
                }
            }
        }
}

if ($Drive) {
    $boot = $Drive.TrimEnd('\')
    if (-not (Test-Path $boot) -and $boot -notmatch ':$') { $boot = "$boot`:" }
} else {
    $kandidaten = @(Find-BootPartitie)
    if ($kandidaten.Count -eq 0) {
        throw "Geen Pi-bootpartitie gevonden. Zit de kaart erin en is hij al met Imager beschreven? Anders -Drive zelf opgeven."
    }
    if ($kandidaten.Count -gt 1) {
        Write-Host "Meerdere kandidaten:"
        $kandidaten | ForEach-Object { Write-Host "  $($_.Pad)  $($_.Label)" }
        throw "Kies er zelf een met -Drive."
    }
    $boot = $kandidaten[0].Pad
    Write-Host "Kaart gevonden : $boot  ($($kandidaten[0].Label))"
    if (-not $kandidaten[0].Verwissel) {
        Write-Host "LET OP: dit is geen verwisselbare schijf." -ForegroundColor Yellow
    }
}

function Write-Lf($path, $text) {
    # Alles hier wordt op Linux gelezen: LF afdwingen, geen BOM.
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($path, ($text -replace "`r`n", "`n"), $utf8)
}

function Toml($value) { '"' + ($value -replace '\\', '\\' -replace '"', '\"') + '"' }

# -- controleren dat dit echt een Pi-bootpartitie is -------------------------

$cmdline = Join-Path $boot 'cmdline.txt'
$configTxt = Join-Path $boot 'config.txt'
foreach ($needed in $cmdline, $configTxt) {
    if (-not (Test-Path $needed)) {
        throw "$needed niet gevonden. Is $boot de boot-partitie van een verse Raspberry Pi OS-kaart?"
    }
}
if (-not (Test-Path $PubKeyFile)) { throw "Publieke sleutel niet gevonden: $PubKeyFile" }
$pubkey = (Get-Content $PubKeyFile -Raw).Trim()
if ($pubkey -notmatch '^(ssh-|ecdsa-)') {
    throw "Dat ziet er niet uit als een OpenSSH publieke sleutel: $PubKeyFile"
}
if ((Get-Content $cmdline -Raw) -match 'systemd\.run=') {
    throw "cmdline.txt heeft al een systemd.run-haak. Schrijf de kaart opnieuw met een kale image."
}

Write-Host "Kaart      : $boot"
Write-Host "Toestel    : $Hostname (paneel $Panel)"
Write-Host "Gebruiker  : $User, ssh met sleutel $(Split-Path -Leaf $PubKeyFile)"
Write-Host "Wifi       : $WifiSsid (alleen nodig om te installeren)"
if (-not $Force) {
    $answer = Read-Host "Doorgaan? [j/N]"
    if ($answer -notmatch '^[jJ]') { Write-Host 'Afgebroken.'; return }
}

# -- antwoordbestand ---------------------------------------------------------

$toml = @"
# Aangemaakt door prepare-sd.ps1 -- wordt bij de eerste boot verwerkt en
# daarna door firstrun.sh van de kaart gehaald (staat hier leesbaar in).
config_version = 1

[system]
hostname = $(Toml $Hostname)

[user]
name = $(Toml $User)
password = $(Toml $Password)
password_encrypted = false

[ssh]
enabled = true
password_authentication = false
authorized_keys = [ $(Toml $pubkey) ]

[wlan]
ssid = $(Toml $WifiSsid)
password = $(Toml $WifiPassword)
password_encrypted = false
hidden = false
country = $(Toml $Country)

[locale]
keymap = $(Toml $Keymap)
timezone = $(Toml $Timezone)
"@
Write-Lf (Join-Path $boot 'custom.toml') $toml

# -- broncode en paneelkeuze -------------------------------------------------

$payload = Join-Path $boot 'wpscatcher-payload'
if (Test-Path $payload) { Remove-Item $payload -Recurse -Force }
New-Item -ItemType Directory -Path $payload | Out-Null

$files = @('wpscatcher.py', 'wps.py', 'screens.py', 'display.py',
           'config.ini', 'wpscatcher.service', 'usb0-vast-ip.service',
           'install.sh')
foreach ($f in $files) { Copy-Item (Join-Path $repo $f) $payload }
Copy-Item (Join-Path $PSScriptRoot 'stage2.sh') $payload
Copy-Item (Join-Path $PSScriptRoot 'wpscatcher-provision.service') $payload

Write-Lf (Join-Path $boot 'wpscatcher-panel') "$Panel`n"
Copy-Item (Join-Path $PSScriptRoot 'firstrun.sh') (Join-Path $boot 'firstrun.sh')

# -- config.txt: SPI voor het scherm, dwc2 voor usb gadget -------------------

# Expliciet een [all]-kop: aan het einde van config.txt kan je zonder dat in
# een [cm4]/[cm5]/[pi5]-sectie belanden, en die gelden niet voor een Zero.
# Dan gebeurt er stilletjes niets.
$cfg = (Get-Content $configTxt -Raw).TrimEnd() + "`n`n[all]`n"
foreach ($line in 'dtparam=spi=on', 'dtoverlay=dwc2,dr_mode=peripheral') {
    if ($cfg -notmatch [regex]::Escape($line)) {
        $cfg += "$line`n"
        Write-Host "config.txt  + $line"
    }
}
Write-Lf $configTxt $cfg

# -- cmdline.txt: gadget-modules en de haak naar fase 1 ----------------------

$cmd = (Get-Content $cmdline -Raw).Trim()
if ($cmd -notmatch 'modules-load=') { $cmd += ' modules-load=dwc2,g_ether' }
$cmd += ' systemd.run=/boot/firmware/firstrun.sh systemd.run_success_action=reboot'
# cmdline.txt moet één regel blijven, zonder afsluitende newline
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($cmdline, $cmd, $utf8)

Write-Host ''
Write-Host 'Klaar. Kaart uitwerpen, in de Pi, stroom erop.'
Write-Host 'Twee keer herstarten en dan draait wpscatcher.'
Write-Host ''
Write-Host 'Meekijken kan van Windows: steek de kaart terug en lees'
Write-Host '  wpscatcher-firstrun.log   (fase 1)'
Write-Host '  wpscatcher-install.log    (fase 2, apt en install.sh)'
