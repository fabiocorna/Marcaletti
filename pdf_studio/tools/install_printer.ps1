# Installa la stampante virtuale "CRN PDF" (richiede privilegi di amministratore).
# Usa il driver "Microsoft Print To PDF" di Windows con una porta che scrive il PDF
# in una cartella condivisa; CRN PDF Studio raccoglie il file e lo apre.
param([string]$Name = "CRN PDF")
$ErrorActionPreference = "Stop"

$spool = Join-Path $env:ProgramData "CRN PDF Studio\spool"
$port = Join-Path $spool "stampa.pdf"
$driver = "Microsoft Print To PDF"

New-Item -ItemType Directory -Force -Path $spool | Out-Null
# Utenti (SID S-1-5-32-545): lettura e modifica, per spostare i PDF stampati
& icacls $spool /grant "*S-1-5-32-545:(OI)(CI)M" | Out-Null

if (-not (Get-PrinterDriver -Name $driver -ErrorAction SilentlyContinue)) {
    try {
        Enable-WindowsOptionalFeature -Online -FeatureName "Printing-PrintToPDFServices-Features" -NoRestart -All | Out-Null
    } catch { }
    if (-not (Get-PrinterDriver -Name $driver -ErrorAction SilentlyContinue)) {
        Add-PrinterDriver -Name $driver
    }
}

if (Get-Printer -Name $Name -ErrorAction SilentlyContinue) {
    Remove-Printer -Name $Name
}
if (-not (Get-PrinterPort -Name $port -ErrorAction SilentlyContinue)) {
    Add-PrinterPort -Name $port
}
Add-Printer -Name $Name -DriverName $driver -PortName $port -Comment "Crea file PDF con CRN PDF Studio"
Write-Output "Stampante '$Name' installata (porta: $port)"
