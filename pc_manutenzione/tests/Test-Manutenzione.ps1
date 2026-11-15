# Collaudo di CRN Manutenzione PC. Uso:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tests\Test-Manutenzione.ps1
# Esce con codice diverso da zero se un controllo fallisce.
$ErrorActionPreference = 'Stop'
$radice = Split-Path -Parent $PSScriptRoot
$script:falliti = 0

function Assert-Vero {
    param([bool]$Condizione, [string]$Messaggio)
    if ($Condizione) { Write-Host "OK    $Messaggio" -ForegroundColor Green }
    else { Write-Host "FAIL  $Messaggio" -ForegroundColor Red; $script:falliti++ }
}

Write-Host "PowerShell $($PSVersionTable.PSVersion) - amministratore: $(([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrators'))"

# --- Sintassi e codifica --------------------------------------------------------
foreach ($f in Get-ChildItem -LiteralPath $radice -Recurse -File -Include *.ps1, *.psm1) {
    $tok = $null; $err = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$tok, [ref]$err)
    $dett = ($err | ForEach-Object { "$($_.Message) (riga $($_.Extent.StartLineNumber))" }) -join '; '
    Assert-Vero ($err.Count -eq 0) "sintassi di $($f.Name) $dett"
    # Windows PowerShell 5.1 legge come ANSI i file senza BOM: le lettere accentate si guasterebbero
    $b = [IO.File]::ReadAllBytes($f.FullName)
    $nonAscii = @($b | Where-Object { $_ -gt 127 }).Count -gt 0
    $bom = $b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF
    Assert-Vero ((-not $nonAscii) -or $bom) "codifica UTF-8 con BOM di $($f.Name)"
}
$bat = Get-ChildItem -LiteralPath $radice -Filter *.bat
foreach ($f in $bat) {
    $b = [IO.File]::ReadAllBytes($f.FullName)
    Assert-Vero (@($b | Where-Object { $_ -gt 127 }).Count -eq 0) "$($f.Name) solo ASCII"
}

Import-Module (Join-Path $radice 'CRNManutenzione.psm1') -Force -DisableNameChecking

# --- Elenco dei controlli -------------------------------------------------------
$controlli = @(Get-ControlliPC)
Assert-Vero ($controlli.Count -ge 20) "$($controlli.Count) controlli definiti"
$ids = @($controlli | ForEach-Object { $_.Id })
Assert-Vero (@($ids | Select-Object -Unique).Count -eq $ids.Count) 'identificativi univoci'
Assert-Vero ($ids[0] -eq 'puntoripristino') 'il punto di ripristino viene creato per primo'
foreach ($c in $controlli) {
    $ok = $c.Id -and $c.Categoria -and $c.Nome -and ($c.Analizza -is [scriptblock]) -and (@('Automatica', 'Lunga', 'Apri') -contains $c.Tipo)
    if ($c.Correggi) { $ok = $ok -and ($c.Correggi -is [scriptblock]) -and $c.Azione }
    Assert-Vero $ok "definizione di '$($c.Id)'"
}

# --- Analisi completa (sola lettura) ---------------------------------------------
$validi = 'OK', 'Info', 'Attenzione', 'Problema'
$risultati = @()
foreach ($c in $controlli) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $r = Invoke-AnalisiControllo -Controllo $c
    $sw.Stop()
    $risultati += $r
    Write-Host ("      {0,-16} {1,-10} {2,5:N1}s  {3}" -f $r.Id, $r.Stato, $sw.Elapsed.TotalSeconds, $r.Dettaglio)
    Assert-Vero ($validi -contains $r.Stato) "analisi di '$($c.Id)' senza errori"
    Assert-Vero ([bool]$r.Dettaglio) "dettaglio di '$($c.Id)' presente"
}
$p = Get-PunteggioSalute -Risultati $risultati
Assert-Vero ($p.Punteggio -ge 0 -and $p.Punteggio -le 100 -and $p.Giudizio) "punteggio $($p.Punteggio) ($($p.Giudizio))"

# --- Report -----------------------------------------------------------------------
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("crn-test-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
$rep = Join-Path $tmp 'report.html'
Export-ReportManutenzione -Risultati $risultati -Percorso $rep
$html = [IO.File]::ReadAllText($rep)
Assert-Vero ($html -match 'Report manutenzione PC' -and $html -match 'Cestino' -and $html -match 'Antivirus') 'report HTML con tutti i controlli'

# --- Pulizia sicura delle cartelle --------------------------------------------------
$prova = Join-Path $tmp 'pulizia'
New-Item -ItemType Directory -Path "$prova\sub\profonda" -Force | Out-Null
New-Item -ItemType Directory -Path "$prova\nuova" -Force | Out-Null
$vecchi = @("$prova\a.tmp", "$prova\sub\b.log", "$prova\sub\profonda\c.dat")
foreach ($v in $vecchi) { [IO.File]::WriteAllBytes($v, (New-Object byte[] 1000)) }
[IO.File]::WriteAllBytes("$prova\recente.tmp", (New-Object byte[] 500))
[IO.File]::WriteAllBytes("$prova\nuova\recente2.tmp", (New-Object byte[] 500))
$solaLettura = "$prova\sub\solalettura.tmp"
[IO.File]::WriteAllBytes($solaLettura, (New-Object byte[] 1000))
(Get-Item $solaLettura).Attributes = 'ReadOnly'
$vecchi += $solaLettura
$data = (Get-Date).AddDays(-3)
foreach ($v in $vecchi) { (Get-Item $v).LastWriteTime = $data }
(Get-Item "$prova\sub\profonda").CreationTime = $data
(Get-Item "$prova\sub").CreationTime = $data

# Una giunzione verso una cartella esterna non deve essere seguita
$esterna = Join-Path $tmp 'esterna'
New-Item -ItemType Directory -Path $esterna | Out-Null
[IO.File]::WriteAllBytes("$esterna\prezioso.doc", (New-Object byte[] 1000))
(Get-Item "$esterna\prezioso.doc").LastWriteTime = $data
cmd /c mklink /J "$prova\collegamento" "$esterna" | Out-Null
Assert-Vero (Test-Path "$prova\collegamento\prezioso.doc") 'giunzione di prova creata'

# Un file aperto (bloccato) va saltato senza errori
$bloccato = "$prova\bloccato.tmp"
[IO.File]::WriteAllBytes($bloccato, (New-Object byte[] 1000))
(Get-Item $bloccato).LastWriteTime = $data
$fs = [IO.File]::Open($bloccato, 'Open', 'Read', 'None')
try {
    $dim = Get-DimensioneCartella -Percorso $prova -MinOre 24
    Assert-Vero ($dim -eq 5000) "dimensione dei file vecchi = $dim (attesi 5000)"
    $e = Remove-ContenutoCartella -Percorso $prova -MinOre 24
} finally {
    $fs.Close()
}
Assert-Vero ($e.Byte -eq 4000) "byte liberati = $($e.Byte) (attesi 4000)"
Assert-Vero ($e.Saltati -eq 1) "file in uso saltati = $($e.Saltati) (atteso 1)"
foreach ($v in $vecchi) { Assert-Vero (-not (Test-Path -LiteralPath $v)) "eliminato $(Split-Path -Leaf $v)" }
Assert-Vero (Test-Path "$prova\recente.tmp") 'file recente conservato'
Assert-Vero (Test-Path "$prova\nuova\recente2.tmp") 'file recente in sottocartella conservato'
Assert-Vero (-not (Test-Path "$prova\sub")) 'cartelle vecchie rimaste vuote eliminate'
Assert-Vero (Test-Path $prova) 'la cartella di partenza resta'
Assert-Vero (Test-Path "$esterna\prezioso.doc") 'i file raggiunti tramite giunzione non vengono toccati'
Assert-Vero ((Get-DimensioneCartella -Percorso "$prova\non-esiste") -eq 0) 'percorso inesistente = 0 byte'
Assert-Vero ((Get-DimensioneCartella -Percorso @($null, '')) -eq 0) 'percorso vuoto ignorato'

# --- Lettura dell'output di winget ----------------------------------------------------
$f1 = '{0,-26}{1,-24}{2,-12}{3,-12}{4}'
$f2 = '{0,-16}{1,-19}{2,-10}{3,-13}{4}'
$campione = @(
    ("   - `r   \ `r" + ($f1 -f 'Name', 'Id', 'Version', 'Available', 'Source')),
    ('-' * 80),
    ($f1 -f 'Mozilla Firefox (x64 it)', 'Mozilla.Firefox', '120.0', '121.0', 'winget'),
    ($f1 -f '7-Zip 22.01 (x64)', '7zip.7zip', '22.01', '23.01', 'winget'),
    ($f1 -f 'Notepad++ (64-bit x64)', 'Notepad++.Notepad++', '8.5.8', '8.6', 'winget'),
    '3 upgrades available.',
    '',
    'The following packages have an upgrade available, but require explicit targeting for upgrade:',
    ($f2 -f 'Nome', 'ID', 'Versione', 'Disponibile', 'Origine'),
    ('-' * 64),
    ($f2 -f 'Discord', 'Discord.Discord', '1.0.9', '1.0.10', 'winget')
)
$nomi = @(ConvertFrom-OutputWinget -Righe $campione)
Assert-Vero ($nomi.Count -eq 4) "winget: $($nomi.Count) programmi letti (attesi 4): $($nomi -join ' | ')"
Assert-Vero ($nomi[0] -eq 'Mozilla Firefox (x64 it)' -and $nomi[3] -eq 'Discord') 'winget: nomi corretti'
Assert-Vero (@(ConvertFrom-OutputWinget -Righe @('No installed package found matching input criteria.')).Count -eq 0) 'winget: nessun aggiornamento'

# --- Interventi innocui ----------------------------------------------------------------
foreach ($id in 'temp', 'dump', 'cestino', 'rete') {
    $c = $controlli | Where-Object { $_.Id -eq $id }
    $r = Invoke-CorrezioneControllo -Controllo $c
    Write-Host "      $id -> $($r.Messaggio)"
    Assert-Vero ($r.Riuscito) "intervento '$id'"
}
$r = Invoke-CorrezioneControllo -Controllo ($controlli | Where-Object { $_.Id -eq 'spazio' })
Assert-Vero (-not $r.Riuscito) 'controllo senza intervento rifiutato'

# --- Riga di comando ---------------------------------------------------------------------
$ps = (Get-Process -Id $PID).Path
$repCli = Join-Path $tmp 'cli.html'
& $ps -NoProfile -ExecutionPolicy Bypass -File (Join-Path $radice 'CRNManutenzione.ps1') -Analizza -Escludi 'winupdate,winget' -Report $repCli | Out-Host
Assert-Vero ($LASTEXITCODE -eq 0 -and (Test-Path $repCli)) 'riga di comando: -Analizza -Report'
& $ps -NoProfile -ExecutionPolicy Bypass -File (Join-Path $radice 'CRNManutenzione.ps1') -Elenco | Out-Host
Assert-Vero ($LASTEXITCODE -eq 0) 'riga di comando: -Elenco'
& $ps -NoProfile -ExecutionPolicy Bypass -File (Join-Path $radice 'CRNManutenzione.ps1') -Esegui 'inesistente' | Out-Host
Assert-Vero ($LASTEXITCODE -eq 2) 'riga di comando: id sconosciuto rifiutato'

Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue

if ($script:falliti -gt 0) { Write-Host "$script:falliti verifiche fallite" -ForegroundColor Red; exit 1 }
Write-Host 'Tutte le verifiche sono riuscite' -ForegroundColor Green
exit 0
