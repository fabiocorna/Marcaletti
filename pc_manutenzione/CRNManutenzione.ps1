<#
.SYNOPSIS
    CRN Manutenzione PC: controlla lo stato del PC, lo pulisce, lo ripara e lo aggiorna.

.DESCRIPTION
    Senza parametri apre la finestra del programma.
    Da riga di comando:
      -Elenco                         elenca i controlli disponibili
      -Analizza [-Report file.html]   analizza il PC (sola lettura) e salva il report
      -Esegui temp,cestino,...        esegue gli interventi indicati
      -Escludi winupdate,winget       salta alcuni controlli durante l'analisi
#>
[CmdletBinding()]
param(
    [switch]$Analizza,
    [string[]]$Esegui,
    [string[]]$Escludi,
    [string]$Report,
    [switch]$Elenco,
    [string]$Collaudo
)

$ErrorActionPreference = 'Continue'
$cartella = $PSScriptRoot
$script:percorsoScript = $PSCommandPath
try { Get-ChildItem -LiteralPath $cartella -Recurse -File -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue } catch { }
Import-Module (Join-Path $cartella 'CRNManutenzione.psm1') -Force -DisableNameChecking

function Split-Elenco {
    param([string[]]$Valori)
    @($Valori | ForEach-Object { $_ -split '[,;\s]+' } | Where-Object { $_ })
}

$Escludi = Split-Elenco $Escludi
$Esegui = Split-Elenco $Esegui

# --- Riga di comando ---------------------------------------------------------

if ($Elenco) {
    Get-ControlliPC | ForEach-Object {
        [pscustomobject]@{ Id = $_.Id; Categoria = $_.Categoria; Controllo = $_.Nome; Intervento = $_.Azione }
    } | Format-Table -AutoSize | Out-String -Width 220 | Write-Host
    exit 0
}

if ($Analizza -or $Esegui.Count -gt 0) {
    $controlli = Get-ControlliPC
    if (-not (Test-Amministratore)) { Write-Host 'Nota: non sei amministratore, alcuni controlli e interventi sono limitati.' -ForegroundColor Yellow }
    if ($Esegui.Count -gt 0) {
        $sconosciuti = @($Esegui | Where-Object { $id = $_; -not ($controlli | Where-Object { $_.Id -eq $id }) })
        if ($sconosciuti.Count -gt 0) { Write-Host "Controlli sconosciuti: $($sconosciuti -join ', '). Usa -Elenco per vederli." -ForegroundColor Red; exit 2 }
        foreach ($c in @($controlli | Where-Object { $Esegui -contains $_.Id })) {
            Write-Host "Eseguo: $($c.Nome)..."
            $r = Invoke-CorrezioneControllo -Controllo $c
            $colore = 'Green'
            if (-not $r.Riuscito) { $colore = 'Yellow' }
            Write-Host "  $($r.Messaggio)" -ForegroundColor $colore
        }
    }
    if ($Analizza) {
        $ris = @(foreach ($c in @($controlli | Where-Object { $Escludi -notcontains $_.Id })) {
                Write-Host "Controllo: $($c.Nome)..."
                Invoke-AnalisiControllo -Controllo $c
            })
        $ris | Format-Table Categoria, Nome, Stato, Dettaglio -Wrap | Out-String -Width 220 | Write-Host
        $p = Get-PunteggioSalute -Risultati $ris
        Write-Host "Stato del PC: $($p.Giudizio) ($($p.Punteggio)/100) - $($p.Problemi) problemi, $($p.Avvisi) avvisi, spazio recuperabile $(Format-Dimensione $p.Recuperabile)"
        if ($Report) {
            Export-ReportManutenzione -Risultati $ris -Percorso $Report
            Write-Host "Report salvato in $Report"
        }
    }
    exit 0
}

# --- Finestra del programma ----------------------------------------------------

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
Set-CallbackAttesa { [System.Windows.Forms.Application]::DoEvents() }

$script:controlli = Get-ControlliPC
$script:mappa = @{}
foreach ($c in $script:controlli) { $script:mappa[$c.Id] = $c }
$script:risultati = @{}
$script:righe = @{}
$script:occupato = $false
$script:info = Get-InfoSistema

$coloriStato = @{
    'OK'         = [System.Drawing.Color]::FromArgb(226, 244, 228)
    'Info'       = [System.Drawing.Color]::FromArgb(238, 243, 251)
    'Attenzione' = [System.Drawing.Color]::FromArgb(255, 243, 205)
    'Problema'   = [System.Drawing.Color]::FromArgb(248, 215, 218)
    'Errore'     = [System.Drawing.Color]::FromArgb(230, 230, 230)
}
$etichetteStato = @{ 'OK' = '✔ OK'; 'Info' = 'ℹ Info'; 'Attenzione' = '⚠ Attenzione'; 'Problema' = '✖ Problema'; 'Errore' = '✖ Errore' }

$form = New-Object System.Windows.Forms.Form
$form.Text = "CRN Manutenzione PC $(Get-VersioneManutenzione)"
$form.Size = New-Object System.Drawing.Size(1180, 720)
$form.MinimumSize = New-Object System.Drawing.Size(820, 480)
$form.StartPosition = 'CenterScreen'
$form.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$form.Icon = [System.Drawing.SystemIcons]::Shield

# Intestazione
$intest = New-Object System.Windows.Forms.Panel
$intest.Dock = 'Top'
$intest.Height = 96
$intest.BackColor = [System.Drawing.Color]::FromArgb(31, 58, 95)
$intest.ForeColor = [System.Drawing.Color]::White

$lblTitolo = New-Object System.Windows.Forms.Label
$lblTitolo.Text = 'Stato del PC'
$lblTitolo.Font = New-Object System.Drawing.Font('Segoe UI', 16, [System.Drawing.FontStyle]::Bold)
$lblTitolo.AutoSize = $true
$lblTitolo.Location = New-Object System.Drawing.Point(16, 8)

$lblPunteggio = New-Object System.Windows.Forms.Label
$lblPunteggio.Text = 'Premi «Analizza il PC» per controllare il computer. L''analisi non modifica nulla.'
$lblPunteggio.Font = New-Object System.Drawing.Font('Segoe UI', 11)
$lblPunteggio.AutoSize = $true
$lblPunteggio.Location = New-Object System.Drawing.Point(18, 44)

$lblInfo = New-Object System.Windows.Forms.Label
$testoInfo = "$($script:info.Computer)  ·  $($script:info.Sistema)  ·  $($script:info.Processore)  ·  RAM $($script:info.RAM)"
if (-not $script:info.Amministratore) { $testoInfo += '  ·  ⚠ Non sei amministratore: alcuni controlli sono limitati' }
$lblInfo.Text = $testoInfo
$lblInfo.AutoSize = $true
$lblInfo.ForeColor = [System.Drawing.Color]::FromArgb(200, 214, 235)
$lblInfo.Location = New-Object System.Drawing.Point(19, 72)

$intest.Controls.AddRange(@($lblTitolo, $lblPunteggio, $lblInfo))

# Elenco dei controlli
$lv = New-Object System.Windows.Forms.ListView
$lv.View = 'Details'
$lv.CheckBoxes = $true
$lv.FullRowSelect = $true
$lv.HideSelection = $false
$lv.ShowItemToolTips = $true
$lv.Dock = 'Fill'
[void]$lv.Columns.Add('Controllo', 250)
[void]$lv.Columns.Add('Stato', 105)
[void]$lv.Columns.Add('Dettaglio', 520)
[void]$lv.Columns.Add('Intervento proposto', 260)

$gruppi = @{}
foreach ($c in $script:controlli) {
    if (-not $gruppi.ContainsKey($c.Categoria)) {
        $g = New-Object System.Windows.Forms.ListViewGroup($c.Categoria, $c.Categoria)
        [void]$lv.Groups.Add($g)
        $gruppi[$c.Categoria] = $g
    }
    $azione = '—'
    if ($c.Correggi) {
        $azione = $c.Azione
        if ($c.Tipo -eq 'Lunga') { $azione += ' · finestra separata' }
    }
    $item = New-Object System.Windows.Forms.ListViewItem($c.Nome)
    [void]$item.SubItems.Add('')
    [void]$item.SubItems.Add('Non ancora analizzato')
    [void]$item.SubItems.Add($azione)
    $item.Tag = $c.Id
    $item.Group = $gruppi[$c.Categoria]
    if (-not $c.Correggi) { $item.ForeColor = [System.Drawing.Color]::FromArgb(70, 70, 70) }
    [void]$lv.Items.Add($item)
    $script:righe[$c.Id] = $item
}

# Solo i controlli con un intervento si possono selezionare
$lv.Add_ItemCheck({
        param($s, $e)
        $id = $lv.Items[$e.Index].Tag
        if (-not $script:mappa[$id].Correggi) { $e.NewValue = [System.Windows.Forms.CheckState]::Unchecked }
    })

$lv.Add_DoubleClick({
        if ($lv.SelectedItems.Count -eq 0) { return }
        $it = $lv.SelectedItems[0]
        $c = $script:mappa[$it.Tag]
        $testo = "$($it.SubItems[2].Text)"
        if ($c.Correggi) { $testo += "`n`nIntervento proposto: $($c.Azione)" }
        [void][System.Windows.Forms.MessageBox]::Show($form, $testo, $c.Nome, 'OK', 'Information')
    })

# Pulsanti
$barra = New-Object System.Windows.Forms.FlowLayoutPanel
$barra.Dock = 'Bottom'
$barra.Height = 52
$barra.Padding = New-Object System.Windows.Forms.Padding(10, 8, 10, 6)
$barra.FlowDirection = 'LeftToRight'

function New-Pulsante([string]$Testo, [int]$Larghezza = 160) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $Testo
    $b.Width = $Larghezza
    $b.Height = 34
    $b.Margin = New-Object System.Windows.Forms.Padding(0, 0, 8, 0)
    $b
}

$btnAnalizza = New-Pulsante 'Analizza il PC' 170
$btnAnalizza.Font = New-Object System.Drawing.Font('Segoe UI', 9, [System.Drawing.FontStyle]::Bold)
$btnEsegui = New-Pulsante 'Esegui interventi selezionati' 230
$btnEsegui.Enabled = $false
$btnTutti = New-Pulsante 'Seleziona consigliati' 150
$btnNessuno = New-Pulsante 'Deseleziona tutto' 130
$btnReport = New-Pulsante 'Salva report' 120
$btnAdmin = New-Pulsante 'Riavvia come amministratore' 220
$btnAdmin.Visible = -not $script:info.Amministratore
$barra.Controls.AddRange(@($btnAnalizza, $btnEsegui, $btnTutti, $btnNessuno, $btnReport, $btnAdmin))

# Barra di stato
$stato = New-Object System.Windows.Forms.StatusStrip
$lblStato = New-Object System.Windows.Forms.ToolStripStatusLabel
$lblStato.Spring = $true
$lblStato.TextAlign = 'MiddleLeft'
$lblStato.Text = 'Pronto'
$prog = New-Object System.Windows.Forms.ToolStripProgressBar
$prog.Width = 220
[void]$stato.Items.Add($lblStato)
[void]$stato.Items.Add($prog)

$form.Controls.Add($lv)
$form.Controls.Add($barra)
$form.Controls.Add($stato)
$form.Controls.Add($intest)
$lv.BringToFront()

function Update-Riga($r) {
    $item = $script:righe[$r.Id]
    $item.SubItems[1].Text = $etichetteStato[$r.Stato]
    $item.SubItems[2].Text = $r.Dettaglio
    $item.ToolTipText = $r.Dettaglio
    $item.BackColor = $coloriStato[$r.Stato]
    $item.Checked = [bool]$r.Consigliato
}

function Set-Occupato([bool]$Valore) {
    $script:occupato = $Valore
    foreach ($b in @($btnAnalizza, $btnTutti, $btnNessuno, $btnReport, $btnAdmin)) { $b.Enabled = -not $Valore }
    $btnEsegui.Enabled = (-not $Valore) -and ($script:risultati.Count -gt 0)
    if ($Valore) { $form.Cursor = [System.Windows.Forms.Cursors]::WaitCursor } else { $form.Cursor = [System.Windows.Forms.Cursors]::Default }
}

function Update-Punteggio {
    $p = Get-PunteggioSalute -Risultati @($script:risultati.Values)
    $lblTitolo.Text = "Stato del PC: $($p.Giudizio) ($($p.Punteggio)/100)"
    $testo = "$($p.Problemi) problemi, $($p.Avvisi) avvisi"
    if ($p.Recuperabile -gt 0) { $testo += "  ·  spazio da liberare: $(Format-Dimensione $p.Recuperabile)" }
    $testo += '  ·  Gli interventi consigliati sono già selezionati'
    $lblPunteggio.Text = $testo
}

function Start-Analisi([string[]]$Ids, [string[]]$Escludi = @()) {
    Set-Occupato $true
    try {
        $elenco = @($script:controlli | Where-Object { (-not $Ids -or $Ids -contains $_.Id) -and $Escludi -notcontains $_.Id })
        $i = 0
        foreach ($c in $elenco) {
            $i++
            $lblStato.Text = "Controllo in corso: $($c.Nome) ($i di $($elenco.Count))..."
            $prog.Value = [int](100 * ($i - 1) / $elenco.Count)
            $script:righe[$c.Id].SubItems[1].Text = '… in corso'
            $script:righe[$c.Id].EnsureVisible()
            [System.Windows.Forms.Application]::DoEvents()
            $r = Invoke-AnalisiControllo -Controllo $c
            $script:risultati[$c.Id] = $r
            Update-Riga $r
            [System.Windows.Forms.Application]::DoEvents()
        }
        $prog.Value = 100
        Update-Punteggio
        $lblStato.Text = "Analisi completata alle $((Get-Date).ToString('HH:mm')). Doppio clic su una riga per i dettagli."
    } finally {
        Set-Occupato $false
    }
}

function Start-Interventi {
    $ids = @($lv.CheckedItems | ForEach-Object { [string]$_.Tag })
    $scelti = @($script:controlli | Where-Object { $ids -contains $_.Id })
    if ($scelti.Count -eq 0) {
        [void][System.Windows.Forms.MessageBox]::Show($form, 'Seleziona almeno un intervento nella colonna di sinistra.', 'Nessun intervento', 'OK', 'Information')
        return
    }
    $testo = "Verranno eseguiti questi interventi:`n`n" + (($scelti | ForEach-Object { "•  $($_.Azione)" }) -join "`n")
    $testo += "`n`nI file eliminati non potranno essere recuperati (cronologia, password e documenti non vengono toccati). Continuare?"
    $ok = [System.Windows.Forms.MessageBox]::Show($form, $testo, 'Conferma interventi', 'YesNo', 'Question')
    if ($ok -ne [System.Windows.Forms.DialogResult]::Yes) { return }

    Set-Occupato $true
    $esiti = @()
    $liberati = [long]0
    try {
        $i = 0
        foreach ($c in $scelti) {
            $i++
            $lblStato.Text = "Intervento in corso: $($c.Azione) ($i di $($scelti.Count))..."
            $prog.Value = [int](100 * ($i - 1) / $scelti.Count)
            $script:righe[$c.Id].SubItems[1].Text = '… in corso'
            [System.Windows.Forms.Application]::DoEvents()
            $r = Invoke-CorrezioneControllo -Controllo $c
            $liberati += $r.Byte
            $segno = '✔'
            if (-not $r.Riuscito) { $segno = '⚠' }
            $esiti += "$segno  $($c.Nome): $($r.Messaggio)"
            $script:righe[$c.Id].Checked = $false
        }
        $prog.Value = 100
    } finally {
        Set-Occupato $false
    }
    # Nuova analisi dei controlli corretti subito (quelli in finestra separata finiscono dopo)
    $daRivedere = @($scelti | Where-Object { $_.Tipo -eq 'Automatica' } | ForEach-Object { $_.Id })
    if ($daRivedere.Count -gt 0) { Start-Analisi -Ids $daRivedere }
    foreach ($id in @($scelti | ForEach-Object { $_.Id })) { $script:righe[$id].Checked = $false }

    $msg = "Interventi completati.`n`n" + ($esiti -join "`n")
    if ($liberati -gt 0) { $msg += "`n`nSpazio liberato in totale: $(Format-Dimensione $liberati)" }
    if (@($scelti | Where-Object { $_.Tipo -eq 'Lunga' }).Count -gt 0) {
        $msg += "`n`nAlcuni interventi continuano in finestre separate: lasciale lavorare fino alla fine, poi premi «Analizza il PC» per ricontrollare."
    }
    $lblStato.Text = 'Interventi completati'
    [void][System.Windows.Forms.MessageBox]::Show($form, $msg, 'Interventi completati', 'OK', 'Information')
}

function Save-Report {
    if ($script:risultati.Count -eq 0) {
        [void][System.Windows.Forms.MessageBox]::Show($form, 'Esegui prima l''analisi del PC.', 'Salva report', 'OK', 'Information')
        return
    }
    $dlg = New-Object System.Windows.Forms.SaveFileDialog
    $dlg.Filter = 'Pagina web (*.html)|*.html'
    $dlg.FileName = "Report PC $($script:info.Computer) $((Get-Date).ToString('yyyy-MM-dd')).html"
    $dlg.InitialDirectory = [Environment]::GetFolderPath('MyDocuments')
    if ($dlg.ShowDialog($form) -ne [System.Windows.Forms.DialogResult]::OK) { return }
    $ris = @($script:controlli | Where-Object { $script:risultati.ContainsKey($_.Id) } | ForEach-Object { $script:risultati[$_.Id] })
    Export-ReportManutenzione -Risultati $ris -Percorso $dlg.FileName -Info $script:info
    Start-Process $dlg.FileName
}

$btnAnalizza.Add_Click({ Start-Analisi })
$btnEsegui.Add_Click({ Start-Interventi })
$btnReport.Add_Click({ Save-Report })
$btnTutti.Add_Click({
        foreach ($it in $lv.Items) {
            $r = $script:risultati[[string]$it.Tag]
            $it.Checked = ($r -and $r.Consigliato)
        }
    })
$btnNessuno.Add_Click({ foreach ($it in $lv.Items) { $it.Checked = $false } })
$btnAdmin.Add_Click({
        try {
            Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', "`"$script:percorsoScript`"" -ErrorAction Stop
            $form.Close()
        } catch {
            [void][System.Windows.Forms.MessageBox]::Show($form, 'Avvio come amministratore annullato.', 'Amministratore', 'OK', 'Information')
        }
    })
$form.Add_FormClosing({
        param($s, $e)
        if ($script:occupato) {
            $e.Cancel = $true
            [void][System.Windows.Forms.MessageBox]::Show($form, 'Attendi la fine dell''operazione in corso.', 'Operazione in corso', 'OK', 'Warning')
        }
    })

if ($Collaudo) {
    # Collaudo automatico: apre la finestra, analizza (salvo i controlli lenti), salva il report e chiude
    $form.Add_Shown({
            try {
                Start-Analisi -Escludi @('winupdate', 'winget')
                $ris = @($script:risultati.Values)
                Export-ReportManutenzione -Risultati $ris -Percorso $Collaudo -Info $script:info
            } catch {
                Set-Content -LiteralPath "$Collaudo.errore.txt" -Value $_.ToString() -Encoding UTF8
            }
            $form.Close()
        })
}

try {
    [void]$form.ShowDialog()
} catch {
    [void][System.Windows.Forms.MessageBox]::Show("Errore imprevisto: $($_.Exception.Message)", 'CRN Manutenzione PC', 'OK', 'Error')
    exit 1
}
if ($Collaudo -and (Test-Path -LiteralPath "$Collaudo.errore.txt")) { exit 1 }
exit 0
