# Rimuove la stampante virtuale "CRN PDF".
param([string]$Name = "CRN PDF")
$port = Join-Path $env:ProgramData "CRN PDF Studio\spool\stampa.pdf"
if (Get-Printer -Name $Name -ErrorAction SilentlyContinue) { Remove-Printer -Name $Name }
Start-Sleep -Seconds 1
if (Get-PrinterPort -Name $port -ErrorAction SilentlyContinue) {
    try { Remove-PrinterPort -Name $port } catch { }
}
Write-Output "Stampante '$Name' rimossa"
