# Rimuove la stampante virtuale "CRN PDF".
param([string]$Name = "CRN PDF")
$port = Join-Path $env:ProgramData "CRN PDF Studio\spool\stampa.pdf"
if (Get-Printer -Name $Name -ErrorAction SilentlyContinue) { Remove-Printer -Name $Name }
Start-Sleep -Seconds 1
# La porta su file puo' restare registrata (Windows non sempre consente di rimuoverla):
# e' innocua e viene riutilizzata da una nuova installazione.
if (Get-PrinterPort -Name $port -ErrorAction SilentlyContinue) {
    Remove-PrinterPort -Name $port -ErrorAction SilentlyContinue
}
Write-Output "Stampante '$Name' rimossa"
