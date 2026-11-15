# CRN Manutenzione PC - controlli e interventi di manutenzione per Windows 10/11.
# Compatibile con Windows PowerShell 5.1 (incluso in Windows) e PowerShell 7.
#
# Ogni controllo è una tabella con:
#   Id, Categoria, Nome      identificazione
#   Analizza                 scriptblock in sola lettura: restituisce New-Esito
#   Correggi                 scriptblock (facoltativo): restituisce New-Intervento
#   Azione                   descrizione dell'intervento
#   Tipo                     Automatica | Lunga (finestra separata) | Apri (apre uno strumento di Windows)
#   Admin                    l'analisi richiede i privilegi di amministratore
#   AdminCorreggi            l'intervento richiede i privilegi di amministratore

$script:Versione = '1.1.0'
$script:CallbackAttesa = $null
$script:OrdineStati = @{ 'OK' = 0; 'Info' = 1; 'Attenzione' = 2; 'Problema' = 3; 'Errore' = 4 }

function Get-VersioneManutenzione { $script:Versione }

# Chiamato durante le attese lunghe: l'interfaccia grafica lo usa per restare reattiva.
function Set-CallbackAttesa {
    param([scriptblock]$Callback)
    $script:CallbackAttesa = $Callback
}

function Invoke-Attesa {
    if ($script:CallbackAttesa) { & $script:CallbackAttesa }
}

function Test-Amministratore {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal $id).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Format-Dimensione {
    param([double]$Byte)
    if ($Byte -ge 1GB) { return ('{0:N1} GB' -f ($Byte / 1GB)) }
    if ($Byte -ge 1MB) { return ('{0:N0} MB' -f ($Byte / 1MB)) }
    if ($Byte -ge 1KB) { return ('{0:N0} KB' -f ($Byte / 1KB)) }
    return ('{0:N0} byte' -f $Byte)
}

function New-Esito {
    param([string]$Stato, [string]$Dettaglio, [long]$Byte = 0)
    @{ Stato = $Stato; Dettaglio = $Dettaglio; Byte = $Byte }
}

function New-Intervento {
    param([string]$Messaggio, [long]$Byte = 0, [bool]$Riuscito = $true)
    @{ Messaggio = $Messaggio; Byte = $Byte; Riuscito = $Riuscito }
}

function Select-StatoPeggiore {
    param([string[]]$Stati)
    $peggiore = 'OK'
    foreach ($s in $Stati) {
        if ($s -and $script:OrdineStati[$s] -gt $script:OrdineStati[$peggiore]) { $peggiore = $s }
    }
    $peggiore
}

# --- File e cartelle ---------------------------------------------------------

# Elenca i file di una cartella e delle sottocartelle senza mai seguire
# collegamenti simbolici o giunzioni (che porterebbero fuori dalla cartella).
function Get-FileSicuri {
    param([string]$Cartella)
    $pila = New-Object System.Collections.Stack
    $pila.Push($Cartella)
    while ($pila.Count -gt 0) {
        $dir = $pila.Pop()
        foreach ($f in @(Get-ChildItem -LiteralPath $dir -Force -ErrorAction SilentlyContinue)) {
            if ($f.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
            if ($f.PSIsContainer) { $pila.Push($f.FullName) } else { $f }
        }
    }
}

function Get-SottocartelleSicure {
    param([string]$Cartella)
    $pila = New-Object System.Collections.Stack
    $pila.Push($Cartella)
    while ($pila.Count -gt 0) {
        $dir = $pila.Pop()
        foreach ($f in @(Get-ChildItem -LiteralPath $dir -Force -Directory -ErrorAction SilentlyContinue)) {
            if ($f.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
            $f
            $pila.Push($f.FullName)
        }
    }
}

function Get-ElementiDaPulire {
    param([string[]]$Percorso, [double]$MinOre = 0)
    $limite = (Get-Date).AddHours(-$MinOre)
    foreach ($p in $Percorso) {
        if (-not $p -or -not (Test-Path -LiteralPath $p)) { continue }
        $item = Get-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
        if (-not $item) { continue }
        if ($item.PSIsContainer) { $file = Get-FileSicuri -Cartella $item.FullName } else { $file = @($item) }
        foreach ($f in $file) { if ($f.LastWriteTime -le $limite) { $f } }
    }
}

# Dimensione in byte dei file più vecchi di MinOre ore nei percorsi indicati.
function Get-DimensioneCartella {
    param([string[]]$Percorso, [double]$MinOre = 0)
    $somma = (@(Get-ElementiDaPulire -Percorso $Percorso -MinOre $MinOre) | Measure-Object -Property Length -Sum).Sum
    if ($somma) { [long]$somma } else { [long]0 }
}

# Elimina i file più vecchi di MinOre ore (le cartelle indicate restano).
# I file in uso vengono saltati. Restituisce i byte liberati e i file saltati.
function Remove-ContenutoCartella {
    param([string[]]$Percorso, [double]$MinOre = 0)
    $liberati = [long]0
    $saltati = 0
    $eliminati = 0
    foreach ($f in @(Get-ElementiDaPulire -Percorso $Percorso -MinOre $MinOre)) {
        $dim = $f.Length
        try {
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction Stop
            $liberati += $dim
            $eliminati++
        } catch {
            $saltati++
        }
        Invoke-Attesa
    }
    # Cartelle rimaste vuote, dalla più profonda. Conta la data di creazione: quella di
    # modifica cambia appena se ne eliminano i file. Le cartelle appena create restano.
    $limite = (Get-Date).AddHours(-$MinOre)
    foreach ($p in $Percorso) {
        if (-not $p -or -not (Test-Path -LiteralPath $p -PathType Container)) { continue }
        $dirs = @(Get-SottocartelleSicure -Cartella $p | Sort-Object { $_.FullName.Length } -Descending)
        foreach ($d in $dirs) {
            if ($d.CreationTime -gt $limite) { continue }
            try { [IO.Directory]::Delete($d.FullName, $false) } catch { }
        }
    }
    [pscustomobject]@{ Byte = $liberati; Eliminati = $eliminati; Saltati = $saltati }
}

function Format-EsitoPulizia {
    param($Esito, [string]$Prefisso = 'Liberati')
    $m = "$Prefisso $(Format-Dimensione $Esito.Byte)"
    if ($Esito.Saltati -gt 0) { $m += " ($($Esito.Saltati) file in uso lasciati al loro posto)" }
    $m
}

# --- Esecuzione in background ------------------------------------------------

# Esegue uno scriptblock in un processo separato con un limite di tempo,
# mantenendo reattiva l'interfaccia durante l'attesa.
function Invoke-ConTimeout {
    param([scriptblock]$Script, [int]$Secondi = 180, [object[]]$Argomenti = @())
    $job = Start-Job -ScriptBlock $Script -ArgumentList $Argomenti
    try {
        $fine = (Get-Date).AddSeconds($Secondi)
        while ($job.State -eq 'Running' -or $job.State -eq 'NotStarted') {
            if ((Get-Date) -gt $fine) {
                Stop-Job -Job $job
                throw "nessuna risposta dopo $Secondi secondi"
            }
            Invoke-Attesa
            Start-Sleep -Milliseconds 150
        }
        Receive-Job -Job $job -ErrorAction Stop
    } finally {
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
}

# Avvia un comando lungo in una finestra di PowerShell visibile, così si vede l'avanzamento.
function Start-FinestraComando {
    param([string]$Titolo, [string]$Comando)
    $t = $Titolo -replace "'", "''"
    $script = @"
`$Host.UI.RawUI.WindowTitle = 'CRN Manutenzione PC - $t'
Write-Host '$t' -ForegroundColor Cyan
Write-Host ''
try {
$Comando
} catch {
    Write-Host `$_ -ForegroundColor Red
}
Write-Host ''
Write-Host 'Operazione terminata.' -ForegroundColor Green
Read-Host 'Premi INVIO per chiudere questa finestra'
"@
    $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
    Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $enc
}

# --- Funzioni di supporto ai controlli ----------------------------------------

function Get-InfoSistema {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    $cpu = Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue | Select-Object -First 1
    $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
    $cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction SilentlyContinue
    $sistema = 'Windows'
    if ($os) {
        $sistema = ("$($os.Caption -replace '^Microsoft ', '') $($cv.DisplayVersion)").Trim()
        $sistema += " (build $($os.BuildNumber))"
    }
    $processore = ''
    if ($cpu) { $processore = ($cpu.Name -replace '\s+', ' ').Trim() }
    $ram = ''
    if ($cs) { $ram = Format-Dimensione $cs.TotalPhysicalMemory }
    [pscustomobject]@{
        Computer       = $env:COMPUTERNAME
        Sistema        = $sistema
        Processore     = $processore
        RAM            = $ram
        Amministratore = (Test-Amministratore)
        Data           = (Get-Date)
    }
}

function Get-MotiviRiavvio {
    $motivi = @()
    if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') {
        $motivi += 'installazione di componenti di Windows'
    }
    if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') {
        $motivi += 'aggiornamenti di Windows Update'
    }
    $motivi
}

function Get-PercorsiCacheBrowser {
    $chromium = @(
        @{ Nome = 'Google Chrome'; Processo = 'chrome'; Base = "$env:LOCALAPPDATA\Google\Chrome\User Data" },
        @{ Nome = 'Microsoft Edge'; Processo = 'msedge'; Base = "$env:LOCALAPPDATA\Microsoft\Edge\User Data" },
        @{ Nome = 'Brave'; Processo = 'brave'; Base = "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\User Data" }
    )
    foreach ($b in $chromium) {
        if (-not (Test-Path -LiteralPath $b.Base)) { continue }
        $percorsi = @()
        $profili = @(Get-ChildItem -LiteralPath $b.Base -Directory -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq 'Default' -or $_.Name -like 'Profile *' -or $_.Name -eq 'Guest Profile' })
        foreach ($pr in $profili) {
            foreach ($sub in 'Cache', 'Code Cache', 'GPUCache') { $percorsi += Join-Path $pr.FullName $sub }
        }
        foreach ($sub in 'ShaderCache', 'GrShaderCache') { $percorsi += Join-Path $b.Base $sub }
        [pscustomobject]@{ Nome = $b.Nome; Processo = $b.Processo; Percorsi = $percorsi }
    }
    $ff = "$env:LOCALAPPDATA\Mozilla\Firefox\Profiles"
    if (Test-Path -LiteralPath $ff) {
        $percorsi = @(Get-ChildItem -LiteralPath $ff -Directory -Force -ErrorAction SilentlyContinue |
            ForEach-Object { Join-Path $_.FullName 'cache2' })
        [pscustomobject]@{ Nome = 'Mozilla Firefox'; Processo = 'firefox'; Percorsi = $percorsi }
    }
}

function Get-PercorsiDump {
    @(
        "$env:LOCALAPPDATA\CrashDumps",
        "$env:LOCALAPPDATA\Microsoft\Windows\WER\ReportArchive",
        "$env:LOCALAPPDATA\Microsoft\Windows\WER\ReportQueue",
        "$env:ProgramData\Microsoft\Windows\WER\ReportArchive",
        "$env:ProgramData\Microsoft\Windows\WER\ReportQueue",
        "$env:windir\Minidump",
        "$env:windir\MEMORY.DMP",
        "$env:windir\LiveKernelReports"
    )
}

function Get-PercorsoCestinoUtente {
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    foreach ($d in @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -ErrorAction SilentlyContinue)) {
        $p = Join-Path "$($d.DeviceID)\" "`$Recycle.Bin\$sid"
        if (Test-Path -LiteralPath $p) { $p }
    }
}

# Byte occupati nel cestino dell'utente (desktop.ini del cestino escluso)
function Get-DimensioneCestino {
    $somma = (@(Get-ElementiDaPulire -Percorso @(Get-PercorsoCestinoUtente) | Where-Object { $_.Name -ne 'desktop.ini' }) |
        Measure-Object -Property Length -Sum).Sum
    if ($somma) { [long]$somma } else { [long]0 }
}

function Get-NomiAvvioDisattivati {
    $nomi = @()
    $speciali = 'PSPath', 'PSParentPath', 'PSChildName', 'PSDrive', 'PSProvider'
    foreach ($radice in 'HKCU:', 'HKLM:') {
        foreach ($k in 'Run', 'Run32', 'StartupFolder') {
            $p = "$radice\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\$k"
            $prop = Get-ItemProperty -LiteralPath $p -ErrorAction SilentlyContinue
            if (-not $prop) { continue }
            foreach ($n in $prop.PSObject.Properties) {
                if ($speciali -contains $n.Name) { continue }
                $v = $n.Value
                # Primo byte dispari = voce disattivata da Gestione attività / Impostazioni
                if ($v -is [byte[]] -and $v.Length -gt 0 -and ($v[0] -band 1)) { $nomi += $n.Name }
            }
        }
    }
    $nomi
}

function Get-ProdottiSicurezza {
    param([ValidateSet('AntiVirusProduct', 'FirewallProduct')][string]$Classe)
    $prodotti = @(Get-CimInstance -Namespace 'root/SecurityCenter2' -ClassName $Classe -ErrorAction SilentlyContinue)
    foreach ($p in $prodotti) {
        [pscustomobject]@{
            Nome   = $p.displayName
            Attivo = (([int64]$p.productState -band 0x1000) -ne 0)
        }
    }
}

# Legge l'output tabellare di "winget upgrade" e restituisce i nomi dei programmi.
# Le colonne si ricavano dalla riga di intestazione, quindi funziona in ogni lingua.
function ConvertFrom-OutputWinget {
    param([string[]]$Righe)
    $pacchetti = @()
    $pulite = @($Righe | ForEach-Object { (([string]$_) -split "`r")[-1].TrimEnd() })
    for ($i = 1; $i -lt $pulite.Count; $i++) {
        if ($pulite[$i] -notmatch '^-{10,}$') { continue }
        $intest = $pulite[$i - 1]
        $inizi = @()
        for ($c = 0; $c -lt $intest.Length; $c++) {
            if ($intest[$c] -ne ' ' -and ($c -eq 0 -or $intest[$c - 1] -eq ' ')) { $inizi += $c }
        }
        if ($inizi.Count -lt 3) { continue }
        $minLung = $inizi[$inizi.Count - 2]
        for ($j = $i + 1; $j -lt $pulite.Count; $j++) {
            $r = $pulite[$j]
            if ($r.Trim() -eq '' -or $r.Length -le $minLung -or $r -match '^-{10,}$') { break }
            $nome = $r.Substring(0, [Math]::Min($inizi[1], $r.Length)).Trim()
            if ($nome) { $pacchetti += $nome }
        }
    }
    $pacchetti
}

# --- Elenco dei controlli ----------------------------------------------------

function Get-ControlliPC {
    @(
        @{
            Id = 'puntoripristino'; Categoria = 'Protezione'; Nome = 'Punto di ripristino'
            Azione = 'Crea un punto di ripristino'; Tipo = 'Automatica'; Admin = $true; AdminCorreggi = $true
            Analizza = {
                if (-not (Get-Command Get-ComputerRestorePoint -ErrorAction SilentlyContinue)) {
                    return New-Esito 'Info' 'Il ripristino configurazione di sistema non è disponibile su questa edizione di Windows'
                }
                try { $punti = @(Get-ComputerRestorePoint -ErrorAction Stop) }
                catch { return New-Esito 'Info' 'Il ripristino configurazione di sistema non è disponibile su questo PC' }
                if ($punti.Count -eq 0) {
                    return New-Esito 'Attenzione' 'Nessun punto di ripristino: è consigliato crearne uno prima di fare interventi, per poter tornare indietro'
                }
                $date = @($punti | ForEach-Object { [Management.ManagementDateTimeConverter]::ToDateTime($_.CreationTime) } | Sort-Object)
                $ultimo = $date[-1]
                $giorni = [int]((Get-Date) - $ultimo).TotalDays
                $testo = "Ultimo punto di ripristino: $($ultimo.ToString('dd/MM/yyyy HH:mm')) ($giorni giorni fa)"
                if ($giorni -gt 30) { return New-Esito 'Attenzione' "$testo. Consigliato crearne uno nuovo prima degli interventi" }
                New-Esito 'OK' $testo
            }
            Correggi = {
                $r = Invoke-ConTimeout -Secondi 600 -Script {
                    $k = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore'
                    $vecchio = (Get-ItemProperty -Path $k -Name SystemRestorePointCreationFrequency -ErrorAction SilentlyContinue).SystemRestorePointCreationFrequency
                    # Windows crea al massimo un punto ogni 24 ore: si toglie il limite per questa volta
                    Set-ItemProperty -Path $k -Name SystemRestorePointCreationFrequency -Value 0 -Type DWord
                    $abilitato = $false
                    try {
                        $prima = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue).Count
                        try {
                            Checkpoint-Computer -Description 'CRN Manutenzione PC' -RestorePointType MODIFY_SETTINGS -ErrorAction Stop
                        } catch {
                            Enable-ComputerRestore -Drive "$env:SystemDrive\" -ErrorAction Stop
                            $abilitato = $true
                            Checkpoint-Computer -Description 'CRN Manutenzione PC' -RestorePointType MODIFY_SETTINGS -ErrorAction Stop
                        }
                        $dopo = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue).Count
                        [pscustomobject]@{ Creato = ($dopo -gt $prima); Abilitato = $abilitato }
                    } finally {
                        if ($null -eq $vecchio) {
                            Remove-ItemProperty -Path $k -Name SystemRestorePointCreationFrequency -ErrorAction SilentlyContinue
                        } else {
                            Set-ItemProperty -Path $k -Name SystemRestorePointCreationFrequency -Value $vecchio -Type DWord
                        }
                    }
                }
                $r = @($r)[-1]
                if (-not $r.Creato) { return New-Intervento 'Windows non ha creato il punto di ripristino' -Riuscito $false }
                $m = 'Punto di ripristino creato'
                if ($r.Abilitato) { $m += " (è stata attivata la Protezione sistema sull'unità $env:SystemDrive)" }
                New-Intervento $m
            }
        },
        @{
            Id = 'spazio'; Categoria = 'Disco'; Nome = 'Spazio libero sui dischi'
            Azione = ''; Tipo = 'Automatica'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                $stati = @(); $parti = @()
                foreach ($d in @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -ErrorAction Stop)) {
                    if (-not $d.Size) { continue }
                    $pct = 100.0 * $d.FreeSpace / $d.Size
                    $parti += ('{0} {1} liberi su {2} ({3:N0}%)' -f $d.DeviceID, (Format-Dimensione $d.FreeSpace), (Format-Dimensione $d.Size), $pct)
                    if ($pct -lt 10 -or ($d.DeviceID -eq $env:SystemDrive -and $d.FreeSpace -lt 5GB)) { $stati += 'Problema' }
                    elseif ($pct -lt 20) { $stati += 'Attenzione' }
                    else { $stati += 'OK' }
                }
                $stato = Select-StatoPeggiore $stati
                $testo = $parti -join '; '
                if ($stato -ne 'OK') { $testo += '. Esegui le pulizie qui sotto o sposta file grandi su un disco esterno' }
                New-Esito $stato $testo
            }
            Correggi = $null
        },
        @{
            Id = 'temp'; Categoria = 'Pulizia'; Nome = 'File temporanei'
            Azione = 'Elimina i file temporanei più vecchi di un giorno'; Tipo = 'Automatica'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                $b = Get-DimensioneCartella -Percorso @($env:TEMP, "$env:windir\Temp") -MinOre 24
                if ($b -ge 1GB) { return New-Esito 'Attenzione' "$(Format-Dimensione $b) di file temporanei da eliminare" $b }
                if ($b -gt 0) { return New-Esito 'Info' "$(Format-Dimensione $b) di file temporanei da eliminare" $b }
                New-Esito 'OK' 'Nessun file temporaneo da eliminare'
            }
            Correggi = {
                $e = Remove-ContenutoCartella -Percorso @($env:TEMP, "$env:windir\Temp") -MinOre 24
                New-Intervento (Format-EsitoPulizia $e) $e.Byte
            }
        },
        @{
            Id = 'cestino'; Categoria = 'Pulizia'; Nome = 'Cestino'
            Azione = 'Svuota il cestino'; Tipo = 'Automatica'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                $b = Get-DimensioneCestino
                if ($b -ge 1GB) { return New-Esito 'Attenzione' "Il cestino occupa $(Format-Dimensione $b)" $b }
                if ($b -gt 0) { return New-Esito 'Info' "Il cestino occupa $(Format-Dimensione $b)" $b }
                New-Esito 'OK' 'Il cestino è vuoto'
            }
            Correggi = {
                $prima = Get-DimensioneCestino
                Clear-RecycleBin -Force -ErrorAction SilentlyContinue
                $dopo = Get-DimensioneCestino
                $b = [Math]::Max([long]0, $prima - $dopo)
                New-Intervento "Cestino svuotato: liberati $(Format-Dimensione $b)" $b
            }
        },
        @{
            Id = 'browser'; Categoria = 'Pulizia'; Nome = 'Cache dei browser'
            Azione = 'Svuota la cache (cronologia e password restano)'; Tipo = 'Automatica'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                $tot = [long]0; $parti = @()
                foreach ($b in @(Get-PercorsiCacheBrowser)) {
                    $d = Get-DimensioneCartella -Percorso $b.Percorsi
                    $tot += $d
                    if ($d -gt 0) { $parti += "$($b.Nome) $(Format-Dimensione $d)" }
                }
                if ($tot -eq 0) { return New-Esito 'OK' 'Nessuna cache da svuotare' }
                $testo = "$(Format-Dimensione $tot) di cache: $($parti -join ', '). Chiudi i browser prima di pulire"
                if ($tot -ge 1GB) { return New-Esito 'Attenzione' $testo $tot }
                New-Esito 'Info' $testo $tot
            }
            Correggi = {
                $tot = [long]0; $saltati = @(); $fatti = @()
                foreach ($b in @(Get-PercorsiCacheBrowser)) {
                    if (Get-Process -Name $b.Processo -ErrorAction SilentlyContinue) { $saltati += $b.Nome; continue }
                    $e = Remove-ContenutoCartella -Percorso $b.Percorsi
                    $tot += $e.Byte
                    $fatti += $b.Nome
                }
                $m = "Liberati $(Format-Dimensione $tot)"
                if ($saltati) { $m += ". Non puliti perché aperti: $($saltati -join ', ') (chiudili e riprova)" }
                New-Intervento $m $tot ($fatti.Count -gt 0 -or $saltati.Count -eq 0)
            }
        },
        @{
            Id = 'dump'; Categoria = 'Pulizia'; Nome = 'Rapporti errori e file di dump'
            Azione = 'Elimina rapporti errori e dump'; Tipo = 'Automatica'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                $b = Get-DimensioneCartella -Percorso (Get-PercorsiDump)
                if ($b -ge 1GB) { return New-Esito 'Attenzione' "$(Format-Dimensione $b) di rapporti errori e file di dump" $b }
                if ($b -gt 0) { return New-Esito 'Info' "$(Format-Dimensione $b) di rapporti errori e file di dump" $b }
                New-Esito 'OK' 'Nessun rapporto errori da eliminare'
            }
            Correggi = {
                $e = Remove-ContenutoCartella -Percorso (Get-PercorsiDump)
                New-Intervento (Format-EsitoPulizia $e) $e.Byte
            }
        },
        @{
            Id = 'wucache'; Categoria = 'Pulizia'; Nome = 'File di installazione degli aggiornamenti'
            Azione = 'Elimina i download già installati di Windows Update'; Tipo = 'Automatica'; Admin = $true; AdminCorreggi = $true
            Analizza = {
                $b = Get-DimensioneCartella -Percorso "$env:windir\SoftwareDistribution\Download"
                if (Get-Command Get-DeliveryOptimizationPerfSnap -ErrorAction SilentlyContinue) {
                    try { $b += [long](Get-DeliveryOptimizationPerfSnap -ErrorAction Stop -WarningAction SilentlyContinue).CacheSizeBytes } catch { }
                }
                if ($b -ge 1GB) { return New-Esito 'Attenzione' "$(Format-Dimensione $b) di file degli aggiornamenti da eliminare" $b }
                if ($b -gt 0) { return New-Esito 'Info' "$(Format-Dimensione $b) di file degli aggiornamenti da eliminare" $b }
                New-Esito 'OK' 'Nessun file degli aggiornamenti da eliminare'
            }
            Correggi = {
                if (@(Get-MotiviRiavvio).Count -gt 0) {
                    return New-Intervento 'Saltato: ci sono aggiornamenti in attesa di riavvio. Riavvia il PC e riprova' -Riuscito $false
                }
                $tot = [long]0
                if (Get-Command Delete-DeliveryOptimizationCache -ErrorAction SilentlyContinue) {
                    try {
                        $do = [long](Get-DeliveryOptimizationPerfSnap -ErrorAction Stop -WarningAction SilentlyContinue).CacheSizeBytes
                        Delete-DeliveryOptimizationCache -Force -ErrorAction Stop
                        $tot += $do
                    } catch { }
                }
                $servizi = 'wuauserv', 'bits'
                $attivi = @($servizi | Where-Object { (Get-Service -Name $_ -ErrorAction SilentlyContinue).Status -eq 'Running' })
                foreach ($s in $servizi) { Stop-Service -Name $s -Force -ErrorAction SilentlyContinue }
                try {
                    $e = Remove-ContenutoCartella -Percorso "$env:windir\SoftwareDistribution\Download"
                    $tot += $e.Byte
                } finally {
                    foreach ($s in $attivi) { Start-Service -Name $s -ErrorAction SilentlyContinue }
                }
                New-Intervento "Liberati $(Format-Dimensione $tot)" $tot
            }
        },
        @{
            Id = 'componenti'; Categoria = 'Pulizia'; Nome = 'Vecchie versioni dei componenti di Windows'
            Azione = 'Pulizia dei componenti (10-30 minuti)'; Tipo = 'Lunga'; Admin = $false; AdminCorreggi = $true
            Analizza = {
                New-Esito 'Info' "Windows conserva le versioni vecchie dei file aggiornati: rimuoverle libera spazio (dopo non si possono più disinstallare gli aggiornamenti già installati)"
            }
            Correggi = {
                Start-FinestraComando 'Pulizia dei componenti di Windows' 'DISM.exe /Online /Cleanup-Image /StartComponentCleanup'
                New-Intervento 'Avviata in una finestra separata: può richiedere da 10 a 30 minuti'
            }
        },
        @{
            Id = 'winupdate'; Categoria = 'Aggiornamenti'; Nome = 'Aggiornamenti di Windows'
            Azione = 'Apre Windows Update'; Tipo = 'Apri'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                try {
                    $r = Invoke-ConTimeout -Secondi 240 -Script {
                        $sessione = New-Object -ComObject Microsoft.Update.Session
                        $ricerca = $sessione.CreateUpdateSearcher()
                        $esito = $ricerca.Search("IsInstalled=0 and IsHidden=0 and Type='Software'")
                        $titoli = @()
                        foreach ($u in $esito.Updates) { $titoli += [string]$u.Title }
                        [pscustomobject]@{ Titoli = ($titoli -join "`n") }
                    }
                } catch {
                    return New-Esito 'Info' "Impossibile verificare gli aggiornamenti ($($_.Exception.Message)). Controlla la connessione a Internet"
                }
                $titoli = @(([string](@($r)[-1].Titoli)) -split "`n" | Where-Object { $_ })
                $motivi = @(Get-MotiviRiavvio)
                if ($titoli.Count -eq 0) {
                    if ($motivi.Count -gt 0) { return New-Esito 'Attenzione' 'Gli aggiornamenti sono stati scaricati: riavvia il PC per completarne l''installazione' }
                    return New-Esito 'OK' 'Windows è aggiornato'
                }
                $elenco = ($titoli | Select-Object -First 5) -join '; '
                if ($titoli.Count -gt 5) { $elenco += '; ...' }
                New-Esito 'Attenzione' "$($titoli.Count) aggiornamenti da installare: $elenco"
            }
            Correggi = {
                Start-Process 'ms-settings:windowsupdate'
                New-Intervento 'Aperto Windows Update: premi «Scarica e installa» o «Cerca aggiornamenti»'
            }
        },
        @{
            Id = 'winget'; Categoria = 'Aggiornamenti'; Nome = 'Aggiornamenti dei programmi'
            Azione = 'Aggiorna tutti i programmi (chiudili prima)'; Tipo = 'Lunga'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
                    return New-Esito 'Info' 'Per controllare i programmi serve «Programma di installazione app» (winget), gratuito nel Microsoft Store'
                }
                try {
                    $righe = Invoke-ConTimeout -Secondi 240 -Script {
                        try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
                        & winget upgrade --accept-source-agreements 2>&1 | ForEach-Object { [string]$_ }
                    }
                } catch {
                    return New-Esito 'Info' "Impossibile controllare gli aggiornamenti dei programmi ($($_.Exception.Message))"
                }
                $nomi = @(ConvertFrom-OutputWinget -Righe @($righe))
                if ($nomi.Count -eq 0) { return New-Esito 'OK' 'Tutti i programmi gestiti da winget sono aggiornati' }
                $elenco = ($nomi | Select-Object -First 8) -join ', '
                if ($nomi.Count -gt 8) { $elenco += ', ...' }
                New-Esito 'Attenzione' "$($nomi.Count) programmi da aggiornare: $elenco"
            }
            Correggi = {
                if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
                    return New-Intervento 'winget non è installato: installa «Programma di installazione app» dal Microsoft Store' -Riuscito $false
                }
                Start-FinestraComando 'Aggiornamento dei programmi' 'winget upgrade --all --silent --accept-source-agreements --accept-package-agreements'
                New-Intervento 'Aggiornamento avviato in una finestra separata'
            }
        },
        @{
            Id = 'antivirus'; Categoria = 'Sicurezza'; Nome = 'Antivirus'
            Azione = 'Aggiorna le definizioni e fa una scansione rapida'; Tipo = 'Lunga'; Admin = $false; AdminCorreggi = $true
            Analizza = {
                $s = $null
                if (Get-Command Get-MpComputerStatus -ErrorAction SilentlyContinue) {
                    try { $s = Get-MpComputerStatus -ErrorAction Stop } catch { $s = $null }
                }
                if (-not $s -or -not $s.AntivirusEnabled) {
                    $altri = @(Get-ProdottiSicurezza -Classe AntiVirusProduct | Where-Object { $_.Nome -notmatch 'Defender' })
                    $attivi = @($altri | Where-Object { $_.Attivo })
                    if ($attivi.Count -gt 0) { return New-Esito 'OK' "Antivirus attivo: $(($attivi | ForEach-Object { $_.Nome }) -join ', ')" }
                    if ($altri.Count -gt 0) { return New-Esito 'Problema' "L'antivirus $(($altri | ForEach-Object { $_.Nome }) -join ', ') risulta disattivato" }
                    if (-not $s) { return New-Esito 'Info' 'Impossibile leggere lo stato dell''antivirus su questo PC' }
                    return New-Esito 'Problema' 'Microsoft Defender è disattivato e non c''è un altro antivirus attivo'
                }
                $stati = @(); $parti = @()
                if ($s.RealTimeProtectionEnabled) { $parti += 'Microsoft Defender attivo' }
                else { $stati += 'Problema'; $parti += 'Protezione in tempo reale DISATTIVATA' }
                $eta = [int]$s.AntivirusSignatureAge
                if ($eta -ge 3) { $stati += 'Attenzione'; $parti += "definizioni vecchie di $eta giorni" }
                else { $parti += 'definizioni aggiornate' }
                $scan = [long]$s.QuickScanAge
                if ($scan -gt 14) {
                    $stati += 'Attenzione'
                    if ($scan -gt 3650) { $parti += 'nessuna scansione eseguita' } else { $parti += "ultima scansione $scan giorni fa" }
                } else { $parti += "ultima scansione $scan giorni fa" }
                New-Esito (Select-StatoPeggiore $stati) ($parti -join ', ')
            }
            Correggi = {
                $s = $null
                if (Get-Command Get-MpComputerStatus -ErrorAction SilentlyContinue) {
                    try { $s = Get-MpComputerStatus -ErrorAction Stop } catch { }
                }
                if (-not $s -or -not $s.AntivirusEnabled) {
                    return New-Intervento 'L''antivirus non è Microsoft Defender: aggiornalo e avvia la scansione dal suo programma' -Riuscito $false
                }
                if (-not $s.RealTimeProtectionEnabled) {
                    try { Set-MpPreference -DisableRealtimeMonitoring $false -ErrorAction Stop } catch { }
                }
                Start-FinestraComando 'Aggiornamento e scansione antivirus' @'
Write-Host 'Aggiorno le definizioni dei virus...'
Update-MpSignature
Write-Host 'Scansione rapida in corso (qualche minuto)...'
Start-MpScan -ScanType QuickScan
$minacce = @(Get-MpThreatDetection | Where-Object { $_.InitialDetectionTime -gt (Get-Date).AddHours(-1) })
if ($minacce.Count -gt 0) {
    Write-Host "Minacce trovate: $($minacce.Count). Microsoft Defender le ha gestite; dettagli in Sicurezza di Windows." -ForegroundColor Yellow
} else {
    Write-Host 'Nessuna minaccia trovata.' -ForegroundColor Green
}
'@
                $m = 'Aggiornamento e scansione avviati in una finestra separata'
                if (-not $s.RealTimeProtectionEnabled) { $m = 'Riattivata la protezione in tempo reale. ' + $m }
                New-Intervento $m
            }
        },
        @{
            Id = 'firewall'; Categoria = 'Sicurezza'; Nome = 'Firewall'
            Azione = 'Attiva il firewall di Windows'; Tipo = 'Automatica'; Admin = $false; AdminCorreggi = $true
            Analizza = {
                $altri = @(Get-ProdottiSicurezza -Classe FirewallProduct | Where-Object { $_.Attivo })
                if ($altri.Count -gt 0) { return New-Esito 'OK' "Firewall attivo: $(($altri | ForEach-Object { $_.Nome }) -join ', ')" }
                $profili = @(Get-NetFirewallProfile -ErrorAction Stop)
                $spenti = @($profili | Where-Object { -not $_.Enabled } | ForEach-Object { [string]$_.Name })
                if ($spenti.Count -gt 0) { return New-Esito 'Problema' "Firewall di Windows disattivato per le reti: $($spenti -join ', ')" }
                New-Esito 'OK' 'Firewall di Windows attivo su tutte le reti'
            }
            Correggi = {
                Set-NetFirewallProfile -Profile Domain, Public, Private -Enabled True -ErrorAction Stop
                New-Intervento 'Firewall di Windows attivato'
            }
        },
        @{
            Id = 'integrita'; Categoria = 'Sistema'; Nome = 'Integrità dei file di Windows'
            Azione = 'Verifica e ripara i file di sistema (DISM + SFC)'; Tipo = 'Lunga'; Admin = $true; AdminCorreggi = $true
            Analizza = {
                if (-not (Get-Command Repair-WindowsImage -ErrorAction SilentlyContinue)) {
                    return New-Esito 'Info' 'Verifica non disponibile su questo PC'
                }
                $r = Repair-WindowsImage -Online -CheckHealth -ErrorAction Stop
                switch ([string]$r.ImageHealthState) {
                    'Healthy' { return New-Esito 'OK' 'Nessun danno noto ai file di Windows. Se il PC dà errori strani puoi comunque eseguire la verifica completa' }
                    'Repairable' { return New-Esito 'Problema' 'I file di Windows risultano danneggiati ma riparabili' }
                    default { return New-Esito 'Problema' "Stato dei file di Windows: $($r.ImageHealthState)" }
                }
            }
            Correggi = {
                Start-FinestraComando 'Riparazione dei file di sistema' @'
Write-Host 'Fase 1 di 2: controllo e riparazione dell''immagine di Windows (DISM)...'
DISM.exe /Online /Cleanup-Image /RestoreHealth
Write-Host ''
Write-Host 'Fase 2 di 2: verifica dei file di sistema (SFC)...'
sfc.exe /scannow
Write-Host ''
Write-Host 'Se sono stati riparati dei file, riavvia il PC.' -ForegroundColor Yellow
'@
                New-Intervento 'Verifica avviata in una finestra separata: può richiedere 15-40 minuti'
            }
        },
        @{
            Id = 'riavvio'; Categoria = 'Sistema'; Nome = 'Riavvio in sospeso'
            Azione = ''; Tipo = 'Automatica'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                $motivi = @(Get-MotiviRiavvio)
                if ($motivi.Count -gt 0) { return New-Esito 'Attenzione' "Riavvia il PC per completare: $($motivi -join ', ')" }
                New-Esito 'OK' 'Nessun riavvio richiesto'
            }
            Correggi = $null
        },
        @{
            Id = 'acceso'; Categoria = 'Sistema'; Nome = 'Tempo dall''ultimo riavvio'
            Azione = ''; Tipo = 'Automatica'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
                $giorni = [int][Math]::Floor(((Get-Date) - $os.LastBootUpTime).TotalDays)
                $testo = "Ultimo riavvio: $($os.LastBootUpTime.ToString('dd/MM/yyyy HH:mm'))"
                if ($giorni -ge 7) {
                    return New-Esito 'Attenzione' "$testo ($giorni giorni fa). Riavvia il PC: «Arresta il sistema» non basta per via dell'avvio rapido"
                }
                New-Esito 'OK' $testo
            }
            Correggi = $null
        },
        @{
            Id = 'errori'; Categoria = 'Sistema'; Nome = 'Errori di sistema (ultimi 7 giorni)'
            Azione = 'Apre il Visualizzatore eventi'; Tipo = 'Apri'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                $da = (Get-Date).AddDays(-7)
                $ev = @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; Level = 1, 2; StartTime = $da } -MaxEvents 3000 -ErrorAction SilentlyContinue)
                $bsod = @($ev | Where-Object { $_.Id -eq 1001 -and $_.ProviderName -eq 'Microsoft-Windows-WER-SystemErrorReporting' }).Count
                $spegn = @($ev | Where-Object { $_.Id -eq 41 -and $_.ProviderName -eq 'Microsoft-Windows-Kernel-Power' }).Count
                $origini = ($ev | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 3 |
                    ForEach-Object { "$($_.Name -replace '^Microsoft-Windows-', '') ($($_.Count))" }) -join ', '
                $testo = "$($ev.Count) errori registrati"
                if ($origini) { $testo += "; più frequenti: $origini" }
                if ($bsod -gt 0) { return New-Esito 'Problema' "$bsod arresti anomali (schermata blu). $testo" }
                if ($spegn -gt 0) { return New-Esito 'Attenzione' "$spegn spegnimenti imprevisti (corrente o blocco). $testo" }
                if ($ev.Count -ge 100) { return New-Esito 'Attenzione' $testo }
                New-Esito 'OK' $testo
            }
            Correggi = {
                Start-Process 'eventvwr.msc'
                New-Intervento 'Aperto il Visualizzatore eventi (Registri di Windows > Sistema)'
            }
        },
        @{
            Id = 'dispositivi'; Categoria = 'Sistema'; Nome = 'Dispositivi e driver'
            Azione = 'Apre Gestione dispositivi'; Tipo = 'Apri'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                if (-not (Get-Command Get-PnpDevice -ErrorAction SilentlyContinue)) { return New-Esito 'Info' 'Verifica non disponibile su questo PC' }
                $guasti = @(Get-PnpDevice -PresentOnly -ErrorAction Stop | Where-Object { $_.Status -eq 'Error' -or $_.Status -eq 'Degraded' })
                if ($guasti.Count -eq 0) { return New-Esito 'OK' 'Tutti i dispositivi funzionano' }
                $nomi = @($guasti | ForEach-Object { if ($_.FriendlyName) { $_.FriendlyName } else { $_.InstanceId } } | Select-Object -Unique)
                New-Esito 'Attenzione' "$($nomi.Count) dispositivi con problemi: $(($nomi | Select-Object -First 5) -join ', '). Installa gli aggiornamenti facoltativi dei driver da Windows Update o dal sito del produttore"
            }
            Correggi = {
                Start-Process 'devmgmt.msc'
                New-Intervento 'Aperta Gestione dispositivi: i dispositivi con problemi hanno un triangolo giallo'
            }
        },
        @{
            Id = 'dischi'; Categoria = 'Disco'; Nome = 'Salute dei dischi'
            Azione = 'Ripara il file system delle unità con errori'; Tipo = 'Lunga'; Admin = $false; AdminCorreggi = $true
            Analizza = {
                $stati = @(); $parti = @()
                foreach ($d in @(Get-PhysicalDisk -ErrorAction Stop)) {
                    $tipo = [string]$d.MediaType
                    if ($tipo -ne 'SSD' -and $tipo -ne 'HDD') { $tipo = 'disco' }
                    $nome = "$(([string]$d.FriendlyName).Trim()) ($tipo, $(Format-Dimensione $d.Size))"
                    $note = @()
                    switch ([string]$d.HealthStatus) {
                        'Healthy' { $stati += 'OK'; $note += 'integro' }
                        'Warning' { $stati += 'Attenzione'; $note += 'segnala anomalie: fai un backup' }
                        'Unhealthy' { $stati += 'Problema'; $note += 'GUASTO: fai subito un backup e sostituiscilo' }
                        default { $note += "stato $($d.HealthStatus)" }
                    }
                    try {
                        $rc = $d | Get-StorageReliabilityCounter -ErrorAction Stop
                        if ($rc.Wear -ge 90) { $stati += 'Problema'; $note += "usura $($rc.Wear)%" }
                        elseif ($rc.Wear -ge 70) { $stati += 'Attenzione'; $note += "usura $($rc.Wear)%" }
                        if ($rc.Temperature -ge 60) { $stati += 'Attenzione'; $note += "temperatura $($rc.Temperature) °C" }
                    } catch { }
                    $parti += "$nome $($note -join ', ')"
                }
                foreach ($v in @(Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.DriveLetter -and $_.DriveType -eq 'Fixed' })) {
                    if ([string]$v.HealthStatus -ne 'Healthy') {
                        $stati += 'Attenzione'
                        $parti += "unità $($v.DriveLetter): il file system va riparato"
                    }
                }
                if ($parti.Count -eq 0) { return New-Esito 'Info' 'Nessun disco rilevato' }
                New-Esito (Select-StatoPeggiore $stati) ($parti -join '; ')
            }
            Correggi = {
                $vol = @(Get-Volume -ErrorAction Stop | Where-Object { $_.DriveLetter -and $_.DriveType -eq 'Fixed' -and [string]$_.HealthStatus -ne 'Healthy' })
                if ($vol.Count -eq 0) {
                    return New-Intervento 'Il file system delle unità è a posto. Se un disco segnala guasti, fai un backup e fallo sostituire'
                }
                $lettere = ($vol | ForEach-Object { "'$($_.DriveLetter)'" }) -join ','
                Start-FinestraComando 'Riparazione delle unità' @"
foreach (`$l in @($lettere)) {
    Write-Host "Controllo dell'unità `${l}:..."
    Repair-Volume -DriveLetter `$l -Scan
    Write-Host "Riparazione dell'unità `${l}:..."
    Repair-Volume -DriveLetter `$l -SpotFix
}
Write-Host 'Se Windows lo chiede, riavvia il PC per completare la riparazione.' -ForegroundColor Yellow
"@
                New-Intervento 'Riparazione avviata in una finestra separata'
            }
        },
        @{
            Id = 'ottimizza'; Categoria = 'Disco'; Nome = 'Ottimizzazione delle unità'
            Azione = 'Ottimizza le unità (TRIM per SSD, deframmentazione per HDD)'; Tipo = 'Lunga'; Admin = $false; AdminCorreggi = $true
            Analizza = {
                $t = Get-ScheduledTask -TaskPath '\Microsoft\Windows\Defrag\' -TaskName 'ScheduledDefrag' -ErrorAction SilentlyContinue
                if (-not $t) { return New-Esito 'Info' 'Ottimizzazione automatica non trovata: puoi ottimizzare le unità manualmente' }
                $ultima = ''
                try {
                    $info = $t | Get-ScheduledTaskInfo -ErrorAction Stop
                    if ($info.LastRunTime -and $info.LastRunTime.Year -gt 2000) { $ultima = " (ultima esecuzione: $($info.LastRunTime.ToString('dd/MM/yyyy')))" }
                } catch { }
                if ([string]$t.State -eq 'Disabled') { return New-Esito 'Attenzione' "L'ottimizzazione automatica delle unità è disattivata$ultima" }
                New-Esito 'OK' "Windows ottimizza le unità automaticamente$ultima"
            }
            Correggi = {
                $t = Get-ScheduledTask -TaskPath '\Microsoft\Windows\Defrag\' -TaskName 'ScheduledDefrag' -ErrorAction SilentlyContinue
                if ($t -and [string]$t.State -eq 'Disabled') { $t | Enable-ScheduledTask -ErrorAction SilentlyContinue | Out-Null }
                Start-FinestraComando 'Ottimizzazione delle unità' @'
foreach ($v in @(Get-Volume | Where-Object { $_.DriveLetter -and $_.DriveType -eq 'Fixed' -and $_.FileSystem -eq 'NTFS' })) {
    Write-Host "Ottimizzo l'unità $($v.DriveLetter):..."
    Optimize-Volume -DriveLetter $v.DriveLetter -Verbose
}
'@
                New-Intervento 'Ottimizzazione avviata in una finestra separata'
            }
        },
        @{
            Id = 'memoria'; Categoria = 'Prestazioni'; Nome = 'Memoria (RAM)'
            Azione = ''; Tipo = 'Automatica'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
                $totale = [double]$os.TotalVisibleMemorySize * 1KB
                $uso = 100.0 * (1 - [double]$os.FreePhysicalMemory / [double]$os.TotalVisibleMemorySize)
                $top = @(Get-Process -ErrorAction SilentlyContinue | Group-Object ProcessName | ForEach-Object {
                        [pscustomobject]@{ Nome = $_.Name; Byte = ($_.Group | Measure-Object WorkingSet64 -Sum).Sum }
                    } | Sort-Object Byte -Descending | Select-Object -First 4 | ForEach-Object { "$($_.Nome) $(Format-Dimensione $_.Byte)" })
                $testo = ('In uso il {0:N0}% di {1}. Programmi che ne usano di più: {2}' -f $uso, (Format-Dimensione $totale), ($top -join ', '))
                if ($totale -lt 3.5GB) { return New-Esito 'Attenzione' "$testo. La RAM è poca per Windows di oggi: valuta di aggiungerne" }
                if ($uso -ge 90) { return New-Esito 'Attenzione' "$testo. Chiudi i programmi che non usi" }
                New-Esito 'OK' $testo
            }
            Correggi = $null
        },
        @{
            Id = 'avvio'; Categoria = 'Prestazioni'; Nome = 'Programmi all''avvio'
            Azione = 'Apre le app di avvio'; Tipo = 'Apri'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                $disatt = @(Get-NomiAvvioDisattivati)
                $voci = @(Get-CimInstance Win32_StartupCommand -ErrorAction Stop | Where-Object {
                        -not ($disatt -contains $_.Name -or $disatt -contains "$($_.Name).lnk" -or $disatt -contains [string]$_.Caption)
                    })
                $nomi = @($voci | ForEach-Object { $_.Name } | Select-Object -Unique)
                $testo = "$($nomi.Count) programmi partono con Windows"
                if ($nomi.Count -gt 0) { $testo += ": $(($nomi | Select-Object -First 8) -join ', ')" }
                if ($nomi.Count -gt 8) { $testo += ', ...' }
                if ($nomi.Count -ge 12) { return New-Esito 'Attenzione' "$testo. Disattiva quelli che non ti servono per un avvio più veloce" }
                New-Esito 'OK' $testo
            }
            Correggi = {
                Start-Process 'ms-settings:startupapps'
                New-Intervento 'Aperte le app di avvio: disattiva quelle che non ti servono'
            }
        },
        @{
            Id = 'rete'; Categoria = 'Rete'; Nome = 'Connessione a Internet'
            Azione = 'Svuota la cache DNS'; Tipo = 'Automatica'; Admin = $false; AdminCorreggi = $false
            Analizza = {
                try {
                    $r = Invoke-WebRequest -Uri 'http://www.msftconnecttest.com/connecttest.txt' -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
                    if ([string]$r.Content -match 'Microsoft Connect Test') { return New-Esito 'OK' 'Connessione a Internet funzionante' }
                    return New-Esito 'Attenzione' 'Accesso a Internet limitato (rete con pagina di accesso o proxy)'
                } catch {
                    try {
                        [void][Net.Dns]::GetHostAddresses('www.microsoft.com')
                        return New-Esito 'Attenzione' 'I nomi dei siti vengono risolti ma il collegamento di prova non risponde'
                    } catch {
                        return New-Esito 'Problema' 'Nessuna connessione a Internet'
                    }
                }
            }
            Correggi = {
                Clear-DnsClientCache -ErrorAction SilentlyContinue
                New-Intervento 'Cache DNS svuotata. Se il problema continua, riavvia il router e il PC'
            }
        }
    )
}

# --- Esecuzione dei controlli -------------------------------------------------

function Get-UltimoEsito {
    param([object[]]$Output, [string]$Chiave)
    @($Output | Where-Object { $_ -is [hashtable] -and $_.ContainsKey($Chiave) }) | Select-Object -Last 1
}

function Invoke-AnalisiControllo {
    param([Parameter(Mandatory = $true)][hashtable]$Controllo)
    $e = $null
    if ($Controllo.Admin -and -not (Test-Amministratore)) {
        $e = New-Esito 'Info' 'Avvia il programma come amministratore per questo controllo'
    } else {
        try {
            $e = Get-UltimoEsito -Output @(& $Controllo.Analizza) -Chiave 'Stato'
            if (-not $e) { $e = New-Esito 'Errore' 'Il controllo non ha restituito un risultato' }
        } catch {
            $e = New-Esito 'Errore' "Controllo non riuscito: $($_.Exception.Message)"
        }
    }
    [pscustomobject]@{
        Id         = $Controllo.Id
        Categoria  = $Controllo.Categoria
        Nome       = $Controllo.Nome
        Stato      = $e.Stato
        Dettaglio  = $e.Dettaglio
        Byte       = [long]$e.Byte
        Azione     = $Controllo.Azione
        Tipo       = $Controllo.Tipo
        HaAzione   = [bool]$Controllo.Correggi
        Consigliato = (Test-InterventoConsigliato -Controllo $Controllo -Stato $e.Stato -Byte ([long]$e.Byte))
    }
}

# Interventi da selezionare in automatico dopo l'analisi.
function Test-InterventoConsigliato {
    param([hashtable]$Controllo, [string]$Stato, [long]$Byte)
    if (-not $Controllo.Correggi -or $Controllo.Tipo -eq 'Apri') { return $false }
    if ($Controllo.AdminCorreggi -and -not (Test-Amministratore)) { return $false }
    if ($Stato -eq 'Problema' -or $Stato -eq 'Attenzione') { return $true }
    ($Controllo.Categoria -eq 'Pulizia' -and $Byte -ge 1MB)
}

function Invoke-CorrezioneControllo {
    param([Parameter(Mandatory = $true)][hashtable]$Controllo)
    $r = $null
    if (-not $Controllo.Correggi) {
        $r = New-Intervento 'Nessun intervento automatico disponibile' -Riuscito $false
    } elseif ($Controllo.AdminCorreggi -and -not (Test-Amministratore)) {
        $r = New-Intervento 'Serve avviare il programma come amministratore' -Riuscito $false
    } else {
        try {
            $r = Get-UltimoEsito -Output @(& $Controllo.Correggi) -Chiave 'Messaggio'
            if (-not $r) { $r = New-Intervento 'Fatto' }
        } catch {
            $r = New-Intervento "Non riuscito: $($_.Exception.Message)" -Riuscito $false
        }
    }
    [pscustomobject]@{
        Id        = $Controllo.Id
        Nome      = $Controllo.Nome
        Riuscito  = [bool]$r.Riuscito
        Messaggio = $r.Messaggio
        Byte      = [long]$r.Byte
    }
}

function Get-PunteggioSalute {
    param([object[]]$Risultati)
    $problemi = @($Risultati | Where-Object { $_.Stato -eq 'Problema' }).Count
    $avvisi = @($Risultati | Where-Object { $_.Stato -eq 'Attenzione' }).Count
    $byte = [long](($Risultati | Measure-Object -Property Byte -Sum).Sum)
    $punti = [Math]::Max(0, 100 - 15 * $problemi - 5 * $avvisi)
    if ($punti -ge 90) { $giudizio = 'Ottimo' }
    elseif ($punti -ge 75) { $giudizio = 'Buono' }
    elseif ($punti -ge 50) { $giudizio = 'Da sistemare' }
    else { $giudizio = 'Critico' }
    [pscustomobject]@{ Punteggio = $punti; Giudizio = $giudizio; Problemi = $problemi; Avvisi = $avvisi; Recuperabile = $byte }
}

function Export-ReportManutenzione {
    param([Parameter(Mandatory = $true)][object[]]$Risultati, [Parameter(Mandatory = $true)][string]$Percorso, $Info = $null)
    if (-not $Info) { $Info = Get-InfoSistema }
    $h = { param($t) [System.Net.WebUtility]::HtmlEncode([string]$t) }
    $p = Get-PunteggioSalute -Risultati $Risultati
    $colori = @{ OK = '#e2f4e4'; Info = '#eef3fb'; Attenzione = '#fff3cd'; Problema = '#f8d7da'; Errore = '#e6e6e6' }
    $righe = foreach ($r in $Risultati) {
        $c = $colori[$r.Stato]
        "<tr style=""background:$c""><td>$(& $h $r.Categoria)</td><td><b>$(& $h $r.Nome)</b></td><td>$(& $h $r.Stato)</td><td>$(& $h $r.Dettaglio)</td></tr>"
    }
    $html = @"
<!doctype html>
<html lang="it"><head><meta charset="utf-8"><title>Report manutenzione PC - $(& $h $Info.Computer)</title>
<style>
body{font-family:'Segoe UI',Arial,sans-serif;margin:24px;color:#222;background:#fff}
h1{margin:0 0 4px;font-size:24px}.sub{color:#555;margin-bottom:16px}
.voto{font-size:20px;margin:12px 0}table{border-collapse:collapse;width:100%}
td,th{border:1px solid #ccc;padding:6px 8px;text-align:left;vertical-align:top;font-size:14px}
th{background:#1f3a5f;color:#fff}
</style></head><body>
<h1>Report manutenzione PC</h1>
<div class="sub">$(& $h $Info.Computer) &middot; $(& $h $Info.Sistema) &middot; $(& $h $Info.Processore) &middot; RAM $(& $h $Info.RAM)<br>
Generato il $(& $h ($Info.Data.ToString('dd/MM/yyyy HH:mm'))) da CRN Manutenzione PC $script:Versione</div>
<div class="voto">Stato del PC: <b>$(& $h $p.Giudizio)</b> ($($p.Punteggio)/100) &middot; $($p.Problemi) problemi, $($p.Avvisi) avvisi &middot; spazio recuperabile: $(& $h (Format-Dimensione $p.Recuperabile))</div>
<table><tr><th>Categoria</th><th>Controllo</th><th>Stato</th><th>Dettaglio</th></tr>
$($righe -join "`n")
</table></body></html>
"@
    $dir = Split-Path -Parent $Percorso
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [IO.File]::WriteAllText($Percorso, $html, (New-Object Text.UTF8Encoding $true))
}

# --- Strumenti: analisi del disco e file doppi ---------------------------------

# Cartelle mai esaminate nella ricerca dei file doppi: contengono file di programmi
# e di Windows che devono restare dove sono anche se identici.
$script:CartelleEscluseDoppi = @('AppData', 'Windows', 'Program Files', 'Program Files (x86)', 'ProgramData',
    '$Recycle.Bin', 'System Volume Information', '$WINDOWS.~BT', '$Windows.~WS', 'node_modules', '.git')

function Initialize-CrnDisco {
    if ('CrnDisco' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Collections.Generic;
using System.Security.Cryptography;

public static class CrnDisco
{
    private static FileSystemInfo[] Figli(DirectoryInfo d)
    {
        try { return d.GetFileSystemInfos(); }
        catch { return new FileSystemInfo[0]; }
    }

    // Byte e numero di file di una cartella; non segue collegamenti e giunzioni.
    public static long[] Misura(string percorso)
    {
        long byteTot = 0, file = 0;
        Stack<DirectoryInfo> pila = new Stack<DirectoryInfo>();
        pila.Push(new DirectoryInfo(percorso));
        while (pila.Count > 0)
        {
            foreach (FileSystemInfo f in Figli(pila.Pop()))
            {
                if ((f.Attributes & FileAttributes.ReparsePoint) != 0) continue;
                DirectoryInfo sub = f as DirectoryInfo;
                if (sub != null) { pila.Push(sub); continue; }
                FileInfo fi = f as FileInfo;
                if (fi != null) { byteTot += fi.Length; file++; }
            }
        }
        return new long[] { byteTot, file };
    }

    // File di almeno minByte, escluse le cartelle con i nomi indicati.
    public static List<FileInfo> ElencaFile(string percorso, long minByte, string[] escluse)
    {
        HashSet<string> nomi = new HashSet<string>(escluse ?? new string[0], StringComparer.OrdinalIgnoreCase);
        List<FileInfo> elenco = new List<FileInfo>();
        Stack<DirectoryInfo> pila = new Stack<DirectoryInfo>();
        pila.Push(new DirectoryInfo(percorso));
        while (pila.Count > 0)
        {
            foreach (FileSystemInfo f in Figli(pila.Pop()))
            {
                if ((f.Attributes & FileAttributes.ReparsePoint) != 0) continue;
                DirectoryInfo sub = f as DirectoryInfo;
                if (sub != null) { if (!nomi.Contains(sub.Name)) pila.Push(sub); continue; }
                FileInfo fi = f as FileInfo;
                if (fi != null && fi.Length >= minByte) elenco.Add(fi);
            }
        }
        return elenco;
    }

    // SHA-256 dei primi maxByte byte del file (tutto il file se maxByte <= 0).
    public static string Impronta(string percorso, long maxByte)
    {
        using (FileStream fs = new FileStream(percorso, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
        using (SHA256 sha = SHA256.Create())
        {
            byte[] buf = new byte[81920];
            long rimasti = maxByte <= 0 ? long.MaxValue : maxByte;
            int letti;
            while (rimasti > 0 && (letti = fs.Read(buf, 0, (int)Math.Min(buf.Length, rimasti))) > 0)
            {
                sha.TransformBlock(buf, 0, letti, null, 0);
                rimasti -= letti;
            }
            sha.TransformFinalBlock(new byte[0], 0, 0);
            return BitConverter.ToString(sha.Hash).Replace("-", "");
        }
    }
}
'@
}

# Quanto occupa ogni sottocartella di una cartella (dalla più grande).
function Get-OccupazioneCartella {
    param([Parameter(Mandatory = $true)][string]$Percorso, [scriptblock]$Avanzamento)
    Initialize-CrnDisco
    $dir = New-Object IO.DirectoryInfo $Percorso
    if (-not $dir.Exists) { throw "La cartella «$Percorso» non esiste" }
    try { $figli = $dir.GetFileSystemInfos() } catch { throw "Accesso negato alla cartella «$Percorso»" }
    $voci = @()
    $byteFile = [long]0
    $numFile = 0
    foreach ($f in $figli) {
        if ($f.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        if ($f -is [IO.DirectoryInfo]) {
            if ($Avanzamento) { & $Avanzamento $f.Name }
            Invoke-Attesa
            $m = [CrnDisco]::Misura($f.FullName)
            $voci += [pscustomobject]@{ Nome = $f.Name; Percorso = $f.FullName; Cartella = $true; Byte = [long]$m[0]; File = [long]$m[1] }
        } else {
            $byteFile += $f.Length
            $numFile++
        }
    }
    if ($numFile -gt 0) {
        $voci += [pscustomobject]@{ Nome = '(file in questa cartella)'; Percorso = $dir.FullName; Cartella = $false; Byte = $byteFile; File = [long]$numFile }
    }
    $tot = [double](($voci | Measure-Object -Property Byte -Sum).Sum)
    foreach ($v in @($voci | Sort-Object Byte -Descending)) {
        $pct = 0.0
        if ($tot -gt 0) { $pct = 100.0 * $v.Byte / $tot }
        $v | Add-Member -NotePropertyName Percentuale -NotePropertyValue $pct -PassThru
    }
}

# Gruppi di file identici (stessa dimensione e stessa impronta SHA-256), dal più "sprecone".
function Find-FileDoppi {
    param([Parameter(Mandatory = $true)][string]$Percorso, [long]$MinByte = 1MB, [scriptblock]$Avanzamento)
    Initialize-CrnDisco
    if (-not (Test-Path -LiteralPath $Percorso -PathType Container)) { throw "La cartella «$Percorso» non esiste" }
    $file = [CrnDisco]::ElencaFile($Percorso, [Math]::Max([long]1, $MinByte), [string[]]$script:CartelleEscluseDoppi)
    $perDim = @($file | Group-Object -Property Length | Where-Object { $_.Count -gt 1 })
    $gruppi = @()
    $i = 0
    foreach ($g in $perDim) {
        $i++
        if ($Avanzamento) { & $Avanzamento $i $perDim.Count }
        Invoke-Attesa
        $dim = [long]$g.Name
        # Prima un confronto veloce sui primi 64 KB, poi sull'intero file
        $parziali = @(foreach ($f in $g.Group) {
                try { [pscustomobject]@{ F = $f; H = [CrnDisco]::Impronta($f.FullName, 65536) } } catch { }
            })
        foreach ($pg in @($parziali | Group-Object -Property H | Where-Object { $_.Count -gt 1 })) {
            if ($dim -le 65536) {
                $insiemi = @(, @($pg.Group | ForEach-Object { $_.F }))
            } else {
                $completi = @(foreach ($x in $pg.Group) {
                        Invoke-Attesa
                        try { [pscustomobject]@{ F = $x.F; H = [CrnDisco]::Impronta($x.F.FullName, 0) } } catch { }
                    })
                $insiemi = @(foreach ($cg in @($completi | Group-Object -Property H | Where-Object { $_.Count -gt 1 })) {
                        , @($cg.Group | ForEach-Object { $_.F })
                    })
            }
            foreach ($ins in $insiemi) {
                $ordinati = @($ins | Sort-Object CreationTime, FullName)
                $gruppi += [pscustomobject]@{
                    Dimensione = $dim
                    File       = $ordinati
                    Sprecati   = [long]($dim * ($ordinati.Count - 1))
                }
            }
        }
    }
    $gruppi | Sort-Object Sprecati -Descending
}

# Sposta i file nel cestino (si possono recuperare).
function Remove-FileNelCestino {
    param([string[]]$Percorso)
    Add-Type -AssemblyName Microsoft.VisualBasic
    $spostati = @()
    $errori = @()
    foreach ($p in $Percorso) {
        try {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p,
                [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
                [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
            $spostati += $p
        } catch {
            $errori += "${p}: $($_.Exception.Message)"
        }
    }
    [pscustomobject]@{ Spostati = $spostati; Errori = $errori }
}

# --- Strumenti: programmi installati ---------------------------------------------

function Get-ProgrammiInstallati {
    $chiavi = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    $visti = @{}
    foreach ($k in $chiavi) {
        foreach ($p in @(Get-ItemProperty -Path $k -ErrorAction SilentlyContinue)) {
            $nome = ([string]$p.DisplayName).Trim()
            $dis = ([string]$p.UninstallString).Trim()
            if (-not $nome -or -not $dis) { continue }
            if ($p.SystemComponent -eq 1 -or $p.ParentKeyName -or [string]$p.ReleaseType -match 'Update|Hotfix') { continue }
            $chiave = "$nome|$($p.DisplayVersion)"
            if ($visti.ContainsKey($chiave)) { continue }
            $visti[$chiave] = $true
            $data = $null
            if ([string]$p.InstallDate -match '^\d{8}$') {
                try { $data = [datetime]::ParseExact([string]$p.InstallDate, 'yyyyMMdd', [Globalization.CultureInfo]::InvariantCulture) } catch { }
            }
            $kb = 0.0
            try { $kb = [double]$p.EstimatedSize } catch { }
            [pscustomobject]@{
                Nome        = $nome
                Editore     = ([string]$p.Publisher).Trim()
                Versione    = [string]$p.DisplayVersion
                Byte        = [long]($kb * 1KB)
                Installato  = $data
                Disinstalla = $dis
            }
        }
    }
}

# Rende eseguibile il comando di disinstallazione (alcuni programmi lo registrano senza virgolette).
function Get-ComandoDisinstallazione {
    param([string]$Comando)
    $c = $Comando.Trim()
    if ($c -match '^(?i)msiexec(\.exe)?\s') { return ($c -replace '(?i)/I\s*\{', '/X{') }
    if ($c.StartsWith('"')) { return $c }
    if (Test-Path -LiteralPath $c -PathType Leaf) { return "`"$c`"" }
    if ($c -match '^(?<exe>.+?\.exe)(?<arg>\s.*)?$' -and (Test-Path -LiteralPath $Matches.exe -PathType Leaf)) {
        return "`"$($Matches.exe)`"$($Matches.arg)"
    }
    $c
}

function Start-DisinstallaProgramma {
    param([Parameter(Mandatory = $true)]$Programma)
    $cmd = Get-ComandoDisinstallazione $Programma.Disinstalla
    Start-Process -FilePath $env:ComSpec -ArgumentList '/c', "`"$cmd`"" -WindowStyle Hidden
}

# --- Strumenti: privacy ----------------------------------------------------------

function Get-ProfiliBrowser {
    $chromium = @(
        @{ Nome = 'Google Chrome'; Processo = 'chrome'; Base = "$env:LOCALAPPDATA\Google\Chrome\User Data" },
        @{ Nome = 'Microsoft Edge'; Processo = 'msedge'; Base = "$env:LOCALAPPDATA\Microsoft\Edge\User Data" },
        @{ Nome = 'Brave'; Processo = 'brave'; Base = "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\User Data" }
    )
    foreach ($b in $chromium) {
        if (-not (Test-Path -LiteralPath $b.Base)) { continue }
        $profili = @(Get-ChildItem -LiteralPath $b.Base -Directory -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq 'Default' -or $_.Name -like 'Profile *' } | ForEach-Object { $_.FullName })
        if ($profili.Count -gt 0) { [pscustomobject]@{ Nome = $b.Nome; Processo = $b.Processo; Tipo = 'Chromium'; Profili = $profili } }
    }
    $ff = "$env:APPDATA\Mozilla\Firefox\Profiles"
    if (Test-Path -LiteralPath $ff) {
        $profili = @(Get-ChildItem -LiteralPath $ff -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
        if ($profili.Count -gt 0) { [pscustomobject]@{ Nome = 'Mozilla Firefox'; Processo = 'firefox'; Tipo = 'Firefox'; Profili = $profili } }
    }
}

function New-VocePrivacy {
    param([string]$Id, [string]$Nome, [string]$Descrizione, [string]$Processo, [string[]]$Percorsi = @(), [string[]]$Registro = @())
    [pscustomobject]@{
        Id = $Id; Nome = $Nome; Descrizione = $Descrizione; Processo = $Processo
        Percorsi = $Percorsi; Registro = $Registro
        Byte = (Get-DimensioneCartella -Percorso $Percorsi)
    }
}

function Get-VociPrivacy {
    foreach ($b in @(Get-ProfiliBrowser)) {
        $p = $b.Profili
        if ($b.Tipo -eq 'Chromium') {
            $cookie = foreach ($x in $p) { foreach ($f in 'Network\Cookies', 'Network\Cookies-journal', 'Cookies', 'Cookies-journal') { Join-Path $x $f } }
            $storia = foreach ($x in $p) { foreach ($f in 'History', 'History-journal', 'Visited Links', 'Top Sites', 'Top Sites-journal', 'Shortcuts', 'Shortcuts-journal') { Join-Path $x $f } }
            New-VocePrivacy "$($b.Processo)-cookie" "$($b.Nome): cookie" 'Ti scollega da tutti i siti: dovrai rifare l''accesso' $b.Processo @($cookie)
            New-VocePrivacy "$($b.Processo)-cronologia" "$($b.Nome): cronologia" 'Siti visitati e pagine suggerite (preferiti e password restano)' $b.Processo @($storia)
        } else {
            $cookie = foreach ($x in $p) { foreach ($f in 'cookies.sqlite', 'cookies.sqlite-wal', 'cookies.sqlite-shm') { Join-Path $x $f } }
            $moduli = foreach ($x in $p) { foreach ($f in 'formhistory.sqlite', 'formhistory.sqlite-wal', 'formhistory.sqlite-shm') { Join-Path $x $f } }
            New-VocePrivacy 'firefox-cookie' "$($b.Nome): cookie" 'Ti scollega da tutti i siti: dovrai rifare l''accesso' $b.Processo @($cookie)
            New-VocePrivacy 'firefox-moduli' "$($b.Nome): testo dei moduli" 'Testi suggeriti nei campi dei siti (la cronologia di Firefox si cancella da Firefox con Ctrl+Maiusc+Canc)' $b.Processo @($moduli)
        }
    }
    New-VocePrivacy 'win-recenti' 'Windows: file recenti' 'Elenco dei file aperti di recente in Esplora file e nelle jump list (i file restano)' '' @("$env:APPDATA\Microsoft\Windows\Recent")
    New-VocePrivacy 'win-esegui' 'Windows: cronologia di «Esegui»' 'Comandi digitati nella finestra Esegui (Win+R)' '' @() @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU')
    New-VocePrivacy 'win-ricerche' 'Windows: ricerche in Esplora file' 'Parole cercate nella casella di ricerca di Esplora file' '' @() @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\WordWheelQuery')
}

function Clear-VocePrivacy {
    param([Parameter(Mandatory = $true)]$Voce)
    if ($Voce.Processo -and (Get-Process -Name $Voce.Processo -ErrorAction SilentlyContinue)) {
        return [pscustomobject]@{ Riuscito = $false; Messaggio = "$($Voce.Nome): chiudi il browser e riprova"; Byte = [long]0 }
    }
    $e = Remove-ContenutoCartella -Percorso $Voce.Percorsi
    foreach ($k in $Voce.Registro) {
        if (Test-Path -LiteralPath $k) {
            Remove-Item -LiteralPath $k -Recurse -Force -ErrorAction SilentlyContinue
            New-Item -Path $k -Force | Out-Null
        }
    }
    [pscustomobject]@{ Riuscito = ($e.Saltati -eq 0); Messaggio = "$($Voce.Nome): $(Format-EsitoPulizia $e 'cancellati')"; Byte = $e.Byte }
}

# --- Strumenti: pulizia programmata ---------------------------------------------

$script:NomeAttivita = 'CRN Manutenzione PC - pulizia settimanale'
$script:InterventiProgrammabili = @('temp', 'cestino', 'browser', 'dump', 'wucache')
$script:GiorniSettimana = @(
    @{ Nome = 'lunedì'; Valore = 'Monday'; Bit = 2 }, @{ Nome = 'martedì'; Valore = 'Tuesday'; Bit = 4 },
    @{ Nome = 'mercoledì'; Valore = 'Wednesday'; Bit = 8 }, @{ Nome = 'giovedì'; Valore = 'Thursday'; Bit = 16 },
    @{ Nome = 'venerdì'; Valore = 'Friday'; Bit = 32 }, @{ Nome = 'sabato'; Valore = 'Saturday'; Bit = 64 },
    @{ Nome = 'domenica'; Valore = 'Sunday'; Bit = 1 }
)

function Get-GiorniSettimana { $script:GiorniSettimana }
function Get-InterventiProgrammabili { $script:InterventiProgrammabili }

function Get-PercorsoLog {
    Join-Path $env:LOCALAPPDATA 'CRN Manutenzione PC\pulizia.log'
}

function Write-LogManutenzione {
    param([string]$Percorso, [string]$Testo)
    $dir = Split-Path -Parent $Percorso
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Add-Content -LiteralPath $Percorso -Value "$((Get-Date).ToString('yyyy-MM-dd HH:mm'))  $Testo" -Encoding UTF8
}

function Get-PuliziaProgrammata {
    $t = Get-ScheduledTask -TaskName $script:NomeAttivita -ErrorAction SilentlyContinue
    if (-not $t) { return $null }
    $info = $t | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue
    $trig = @($t.Triggers)[0]
    $arg = [string](@($t.Actions)[0].Arguments)
    $interventi = @()
    if ($arg -match '-Esegui\s+(\S+)') { $interventi = @($Matches[1] -split ',') }
    $giorno = ''
    $ora = ''
    if ($trig) {
        $maschera = [int]$trig.DaysOfWeek
        $giorno = (@($script:GiorniSettimana | Where-Object { $maschera -band $_.Bit } | ForEach-Object { $_.Nome })) -join ', '
        try { $ora = ([datetime]$trig.StartBoundary).ToString('HH:mm') } catch { }
    }
    $ultima = $null
    if ($info -and $info.LastRunTime -and $info.LastRunTime.Year -gt 2000) { $ultima = $info.LastRunTime }
    $prossima = $null
    if ($info -and $info.NextRunTime) { $prossima = $info.NextRunTime }
    [pscustomobject]@{
        Attiva           = ([string]$t.State -ne 'Disabled')
        Giorno           = $giorno
        Ora              = $ora
        Interventi       = $interventi
        UltimaEsecuzione = $ultima
        Prossima         = $prossima
    }
}

function Set-PuliziaProgrammata {
    param(
        [ValidateSet('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')][string]$Giorno = 'Sunday',
        [string]$Ora = '12:00',
        [Parameter(Mandatory = $true)][string[]]$Interventi,
        [Parameter(Mandatory = $true)][string]$Script
    )
    $non = @($Interventi | Where-Object { $script:InterventiProgrammabili -notcontains $_ })
    if ($non.Count -gt 0) { throw "Interventi non programmabili: $($non -join ', ')" }
    if ($Interventi.Count -eq 0) { throw 'Scegli almeno un intervento' }
    if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) { throw "Programma non trovato: $Script" }
    $alle = [datetime]::ParseExact($Ora, 'HH:mm', [Globalization.CultureInfo]::InvariantCulture)
    $arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`" -Esegui $($Interventi -join ',') -Log `"$(Get-PercorsoLog)`""
    $azione = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Giorno -At $alle
    $livello = 'Limited'
    if (Test-Amministratore) { $livello = 'Highest' }
    $utente = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $principale = New-ScheduledTaskPrincipal -UserId $utente -LogonType Interactive -RunLevel $livello
    $imp = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName $script:NomeAttivita -Action $azione -Trigger $trigger -Principal $principale -Settings $imp `
        -Description 'Pulizia automatica creata da CRN Manutenzione PC' -Force | Out-Null
    Get-PuliziaProgrammata
}

function Remove-PuliziaProgrammata {
    if (Get-ScheduledTask -TaskName $script:NomeAttivita -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $script:NomeAttivita -Confirm:$false
    }
}

function Start-PuliziaProgrammata {
    Start-ScheduledTask -TaskName $script:NomeAttivita
}

Export-ModuleMember -Function *
