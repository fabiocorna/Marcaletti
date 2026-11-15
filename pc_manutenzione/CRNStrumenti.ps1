# Schede degli strumenti di CRN Manutenzione PC: analisi disco, file doppi,
# programmi installati, privacy e pulizia programmata.
# Viene caricato (dot-source) da CRNManutenzione.ps1 dopo la creazione di $schede.

function New-Lista([object[]]$Colonne, [bool]$Caselle = $false) {
    $l = New-Object System.Windows.Forms.ListView
    $l.View = 'Details'
    $l.FullRowSelect = $true
    $l.HideSelection = $false
    $l.CheckBoxes = $Caselle
    $l.Dock = 'Fill'
    $l.ShowItemToolTips = $true
    foreach ($c in $Colonne) { [void]$l.Columns.Add($c[0], $c[1]) }
    $l
}

function New-Fila([string]$Dock = 'Top') {
    $f = New-Object System.Windows.Forms.FlowLayoutPanel
    $f.Dock = $Dock
    $f.AutoSize = $true
    $f.AutoSizeMode = 'GrowAndShrink'
    $f.WrapContents = $true
    $f.Padding = New-Object System.Windows.Forms.Padding(8, 8, 8, 6)
    $f
}

function New-Etichetta([string]$Testo, [bool]$Auto = $true) {
    $e = New-Object System.Windows.Forms.Label
    $e.Text = $Testo
    $e.AutoSize = $Auto
    $e.Margin = New-Object System.Windows.Forms.Padding(0, 9, 6, 0)
    $e
}

function New-Casella([string]$Testo, [int]$Larghezza) {
    $t = New-Object System.Windows.Forms.TextBox
    $t.Text = $Testo
    $t.Width = $Larghezza
    $t.Margin = New-Object System.Windows.Forms.Padding(0, 6, 6, 0)
    $t
}

# Aggiunge alla scheda: fila in alto, lista al centro, fila in basso (nell'ordine giusto per il Dock)
function Add-Contenuto($Scheda, $Alto, $Centro, $Basso) {
    foreach ($c in @($Centro, $Basso, $Alto)) { if ($c) { $Scheda.Controls.Add($c) } }
    $Centro.BringToFront()
}

function Select-Cartella([string]$Iniziale) {
    $d = New-Object System.Windows.Forms.FolderBrowserDialog
    $d.Description = 'Scegli la cartella'
    if ($Iniziale -and (Test-Path -LiteralPath $Iniziale)) { $d.SelectedPath = $Iniziale }
    if ($d.ShowDialog($form) -eq [System.Windows.Forms.DialogResult]::OK) { return $d.SelectedPath }
    $null
}

function Show-Messaggio([string]$Testo, [string]$Titolo, [string]$Icona = 'Information') {
    [void][System.Windows.Forms.MessageBox]::Show($form, $Testo, $Titolo, 'OK', $Icona)
}

function Confirm-Domanda([string]$Testo, [string]$Titolo) {
    [System.Windows.Forms.MessageBox]::Show($form, $Testo, $Titolo, 'YesNo', 'Question') -eq [System.Windows.Forms.DialogResult]::Yes
}

# ===================== Analisi disco =====================

$tabDisco = New-Object System.Windows.Forms.TabPage 'Analisi disco'
$discoAlto = New-Fila
$txtDisco = New-Casella "$env:SystemDrive\" 420
$btnDiscoSfoglia = New-Pulsante 'Sfoglia...' 90
$btnDiscoAnalizza = New-Pulsante 'Analizza' 100
$btnDiscoSu = New-Pulsante 'Cartella superiore' 140
$discoAlto.Controls.AddRange(@((New-Etichetta 'Cartella:'), $txtDisco, $btnDiscoSfoglia, $btnDiscoAnalizza, $btnDiscoSu))
$lvDisco = New-Lista @(@('Nome', 380), @('Dimensione', 110), @('Quota', 230), @('File', 90))
$discoBasso = New-Fila 'Bottom'
$btnDiscoApri = New-Pulsante 'Apri in Esplora file' 160
$lblDisco = New-Etichetta 'Scegli una cartella (o un disco) e premi «Analizza». Doppio clic su una cartella per entrarci.'
$discoBasso.Controls.AddRange(@($btnDiscoApri, $lblDisco))
Add-Contenuto $tabDisco $discoAlto $lvDisco $discoBasso

function Start-AnalisiDisco([string]$Percorso) {
    if (-not $Percorso -or -not (Test-Path -LiteralPath $Percorso -PathType Container)) {
        $lblDisco.Text = 'La cartella indicata non esiste'
        return
    }
    $txtDisco.Text = $Percorso
    Set-Occupato $true
    $lvDisco.BeginUpdate()
    $lvDisco.Items.Clear()
    $lvDisco.EndUpdate()
    try {
        $voci = @(Get-OccupazioneCartella -Percorso $Percorso -Avanzamento { param($n) $lblStato.Text = "Misuro «$n»..." })
        $lvDisco.BeginUpdate()
        foreach ($v in $voci) {
            $nome = $v.Nome
            if ($v.Cartella) { $nome = "▸ $nome" }
            $it = New-Object System.Windows.Forms.ListViewItem($nome)
            [void]$it.SubItems.Add((Format-Dimensione $v.Byte))
            $barre = [int][Math]::Round($v.Percentuale / 5)
            [void]$it.SubItems.Add(('{0} {1:N1}%' -f ('█' * $barre), $v.Percentuale))
            [void]$it.SubItems.Add(('{0:N0}' -f $v.File))
            $it.Tag = $v
            [void]$lvDisco.Items.Add($it)
        }
        $lvDisco.EndUpdate()
        $tot = [long](($voci | Measure-Object -Property Byte -Sum).Sum)
        $lblDisco.Text = "Totale: $(Format-Dimensione $tot). Doppio clic su una cartella per entrarci."
        $lblStato.Text = "Analisi di $Percorso completata"
    } catch {
        $lblDisco.Text = "Errore: $($_.Exception.Message)"
    } finally {
        Set-Occupato $false
    }
}

$btnDiscoAnalizza.Add_Click({ Start-AnalisiDisco $txtDisco.Text.Trim() })
$txtDisco.Add_KeyDown({ param($s, $e) if ($e.KeyCode -eq 'Enter') { Start-AnalisiDisco $txtDisco.Text.Trim() } })
$btnDiscoSfoglia.Add_Click({ $c = Select-Cartella $txtDisco.Text; if ($c) { Start-AnalisiDisco $c } })
$btnDiscoSu.Add_Click({
        $su = Split-Path -Parent $txtDisco.Text.TrimEnd('\')
        if ($su) { if ($su.Length -eq 2) { $su += '\' }; Start-AnalisiDisco $su }
    })
$lvDisco.Add_DoubleClick({
        if ($lvDisco.SelectedItems.Count -eq 0) { return }
        $v = $lvDisco.SelectedItems[0].Tag
        if ($v.Cartella) { Start-AnalisiDisco $v.Percorso }
    })
$btnDiscoApri.Add_Click({
        $p = $txtDisco.Text
        if ($lvDisco.SelectedItems.Count -gt 0) { $p = $lvDisco.SelectedItems[0].Tag.Percorso }
        if (Test-Path -LiteralPath $p) { Start-Process explorer.exe -ArgumentList "`"$p`"" }
    })

# ===================== File doppi =====================

$tabDoppi = New-Object System.Windows.Forms.TabPage 'File doppi'
$doppiAlto = New-Fila
$txtDoppi = New-Casella $env:USERPROFILE 380
$btnDoppiSfoglia = New-Pulsante 'Sfoglia...' 90
$numDoppi = New-Object System.Windows.Forms.NumericUpDown
$numDoppi.Minimum = 0
$numDoppi.Maximum = 100000
$numDoppi.Value = 1
$numDoppi.Width = 70
$numDoppi.Margin = New-Object System.Windows.Forms.Padding(0, 6, 6, 0)
$btnDoppiCerca = New-Pulsante 'Cerca doppioni' 130
$doppiAlto.Controls.AddRange(@((New-Etichetta 'Cartella:'), $txtDoppi, $btnDoppiSfoglia, (New-Etichetta 'Dimensione minima (MB):'), $numDoppi, $btnDoppiCerca))
$lvDoppi = New-Lista @(@('Nome', 260), @('Cartella', 470), @('Dimensione', 100), @('Modificato', 130)) $true
$doppiBasso = New-Fila 'Bottom'
$btnDoppiCopie = New-Pulsante 'Seleziona le copie' 150
$btnDoppiNessuno = New-Pulsante 'Deseleziona tutto' 130
$btnDoppiCestino = New-Pulsante 'Sposta selezionati nel cestino' 220
$btnDoppiApri = New-Pulsante 'Apri cartella' 110
$lblDoppi = New-Etichetta 'Cerca file identici (stesso contenuto). Le cartelle dei programmi e di Windows vengono saltate.'
$doppiBasso.Controls.AddRange(@($btnDoppiCopie, $btnDoppiNessuno, $btnDoppiCestino, $btnDoppiApri, $lblDoppi))
Add-Contenuto $tabDoppi $doppiAlto $lvDoppi $doppiBasso

function Start-RicercaDoppi([string]$Percorso) {
    if (-not $Percorso -or -not (Test-Path -LiteralPath $Percorso -PathType Container)) {
        $lblDoppi.Text = 'La cartella indicata non esiste'
        return
    }
    Set-Occupato $true
    $lvDoppi.BeginUpdate(); $lvDoppi.Items.Clear(); $lvDoppi.Groups.Clear(); $lvDoppi.EndUpdate()
    try {
        $lblStato.Text = "Elenco i file di $Percorso..."
        [System.Windows.Forms.Application]::DoEvents()
        $min = [long]([double]$numDoppi.Value * 1MB)
        $gruppi = @(Find-FileDoppi -Percorso $Percorso -MinByte $min -Avanzamento {
                param($i, $n)
                if ($i % 20 -eq 0 -or $i -eq $n) { $lblStato.Text = "Confronto i file: $i gruppi di $n..." }
            })
        $mostrati = @($gruppi | Select-Object -First 500)
        $lvDoppi.BeginUpdate()
        $n = 0
        foreach ($g in $mostrati) {
            $n++
            $gr = New-Object System.Windows.Forms.ListViewGroup("g$n", "$($g.File.Count) copie identiche da $(Format-Dimensione $g.Dimensione) — si liberano $(Format-Dimensione $g.Sprecati)")
            [void]$lvDoppi.Groups.Add($gr)
            foreach ($f in $g.File) {
                $it = New-Object System.Windows.Forms.ListViewItem($f.Name)
                [void]$it.SubItems.Add($f.DirectoryName)
                [void]$it.SubItems.Add((Format-Dimensione $f.Length))
                [void]$it.SubItems.Add($f.LastWriteTime.ToString('dd/MM/yyyy HH:mm'))
                $it.Tag = $f.FullName
                $it.Group = $gr
                $it.ToolTipText = $f.FullName
                [void]$lvDoppi.Items.Add($it)
            }
        }
        $lvDoppi.EndUpdate()
        $spreco = [long](($gruppi | Measure-Object -Property Sprecati -Sum).Sum)
        if ($gruppi.Count -eq 0) {
            $lblDoppi.Text = 'Nessun file doppio trovato.'
        } else {
            $t = "$($gruppi.Count) gruppi di doppioni: eliminando le copie si liberano $(Format-Dimensione $spreco)."
            if ($gruppi.Count -gt 500) { $t += ' Sono mostrati i 500 gruppi più grandi.' }
            $lblDoppi.Text = "$t «Seleziona le copie» tiene il file più vecchio di ogni gruppo."
        }
        $lblStato.Text = 'Ricerca dei doppioni completata'
    } catch {
        $lblDoppi.Text = "Errore: $($_.Exception.Message)"
    } finally {
        Set-Occupato $false
    }
}

$btnDoppiCerca.Add_Click({ Start-RicercaDoppi $txtDoppi.Text.Trim() })
$btnDoppiSfoglia.Add_Click({ $c = Select-Cartella $txtDoppi.Text; if ($c) { $txtDoppi.Text = $c } })
$btnDoppiCopie.Add_Click({
        foreach ($g in $lvDoppi.Groups) {
            $primo = $true
            foreach ($it in $g.Items) { $it.Checked = -not $primo; $primo = $false }
        }
    })
$btnDoppiNessuno.Add_Click({ foreach ($it in $lvDoppi.Items) { $it.Checked = $false } })
$btnDoppiApri.Add_Click({
        if ($lvDoppi.SelectedItems.Count -eq 0) { return }
        Start-Process explorer.exe -ArgumentList "/select,`"$($lvDoppi.SelectedItems[0].Tag)`""
    })
$btnDoppiCestino.Add_Click({
        $scelti = @($lvDoppi.CheckedItems | ForEach-Object { $_ })
        if ($scelti.Count -eq 0) { Show-Messaggio 'Seleziona i file da spostare nel cestino.' 'File doppi'; return }
        foreach ($g in $lvDoppi.Groups) {
            $tutti = $g.Items.Count -gt 0
            foreach ($it in $g.Items) { if (-not $it.Checked) { $tutti = $false } }
            if ($tutti) {
                Show-Messaggio "Hai selezionato tutte le copie di «$($g.Items[0].Text)»: lasciane almeno una." 'File doppi' 'Warning'
                return
            }
        }
        if (-not (Confirm-Domanda "Spostare $($scelti.Count) file nel cestino?`n`nSe serve, potrai recuperarli dal cestino." 'File doppi')) { return }
        Set-Occupato $true
        try {
            $r = Remove-FileNelCestino -Percorso @($scelti | ForEach-Object { [string]$_.Tag })
            foreach ($it in $scelti) { if ($r.Spostati -contains [string]$it.Tag) { $lvDoppi.Items.Remove($it) } }
            $m = "$($r.Spostati.Count) file spostati nel cestino."
            if ($r.Errori.Count -gt 0) { $m += "`n`nNon spostati:`n" + (($r.Errori | Select-Object -First 10) -join "`n") }
            Show-Messaggio $m 'File doppi'
        } finally {
            Set-Occupato $false
        }
    })

# ===================== Programmi installati =====================

$tabProg = New-Object System.Windows.Forms.TabPage 'Programmi'
$progAlto = New-Fila
$txtProg = New-Casella '' 300
$btnProgAggiorna = New-Pulsante 'Aggiorna elenco' 130
$lblProg = New-Etichetta ''
$progAlto.Controls.AddRange(@((New-Etichetta 'Cerca:'), $txtProg, $btnProgAggiorna, $lblProg))
$lvProg = New-Lista @(@('Programma', 340), @('Editore', 220), @('Versione', 120), @('Dimensione', 100), @('Installato il', 100))
$progBasso = New-Fila 'Bottom'
$btnProgDisinstalla = New-Pulsante 'Disinstalla' 120
$btnProgApp = New-Pulsante 'App installate di Windows' 190
$progBasso.Controls.AddRange(@($btnProgDisinstalla, $btnProgApp,
        (New-Etichetta 'Clic sul titolo di una colonna per ordinare (ad esempio per dimensione). Le app del Microsoft Store si gestiscono da «App installate».')))
Add-Contenuto $tabProg $progAlto $lvProg $progBasso

$script:progDati = $null
$script:progOrdine = 'Nome'
$script:progDiscendente = $false

function Show-Programmi {
    if ($null -eq $script:progDati) { return }
    $filtro = $txtProg.Text.Trim()
    $dati = @($script:progDati | Where-Object { -not $filtro -or $_.Nome -like "*$filtro*" -or $_.Editore -like "*$filtro*" })
    $dati = @($dati | Sort-Object -Property $script:progOrdine -Descending:$script:progDiscendente)
    $lvProg.BeginUpdate()
    $lvProg.Items.Clear()
    foreach ($p in $dati) {
        $it = New-Object System.Windows.Forms.ListViewItem($p.Nome)
        [void]$it.SubItems.Add($p.Editore)
        [void]$it.SubItems.Add($p.Versione)
        $dim = ''
        if ($p.Byte -gt 0) { $dim = Format-Dimensione $p.Byte }
        [void]$it.SubItems.Add($dim)
        $data = ''
        if ($p.Installato) { $data = $p.Installato.ToString('dd/MM/yyyy') }
        [void]$it.SubItems.Add($data)
        $it.Tag = $p
        [void]$lvProg.Items.Add($it)
    }
    $lvProg.EndUpdate()
    $tot = [long](($dati | Measure-Object -Property Byte -Sum).Sum)
    $lblProg.Text = "$($dati.Count) programmi · $(Format-Dimensione $tot) dichiarati"
}

function Update-Programmi {
    $lblStato.Text = 'Leggo i programmi installati...'
    [System.Windows.Forms.Application]::DoEvents()
    $script:progDati = @(Get-ProgrammiInstallati)
    Show-Programmi
    $lblStato.Text = 'Pronto'
}

$lvProg.Add_ColumnClick({
        param($s, $e)
        $campo = @('Nome', 'Editore', 'Versione', 'Byte', 'Installato')[$e.Column]
        if ($script:progOrdine -eq $campo) { $script:progDiscendente = -not $script:progDiscendente }
        else { $script:progOrdine = $campo; $script:progDiscendente = ($campo -eq 'Byte' -or $campo -eq 'Installato') }
        Show-Programmi
    })
$txtProg.Add_TextChanged({ Show-Programmi })
$btnProgAggiorna.Add_Click({ Update-Programmi })
$btnProgApp.Add_Click({ Start-Process 'ms-settings:appsfeatures' })
$btnProgDisinstalla.Add_Click({
        if ($lvProg.SelectedItems.Count -eq 0) { Show-Messaggio 'Seleziona il programma da disinstallare.' 'Programmi'; return }
        $p = $lvProg.SelectedItems[0].Tag
        if (-not (Confirm-Domanda "Disinstallare «$($p.Nome)»?`n`nSi aprirà il programma di disinstallazione: segui le sue istruzioni. Al termine premi «Aggiorna elenco»." 'Disinstalla')) { return }
        try { Start-DisinstallaProgramma -Programma $p }
        catch { Show-Messaggio "Impossibile avviare la disinstallazione: $($_.Exception.Message)" 'Disinstalla' 'Warning' }
    })

# ===================== Privacy =====================

$tabPrivacy = New-Object System.Windows.Forms.TabPage 'Privacy'
$privacyAlto = New-Fila
$privacyAlto.Controls.Add((New-Etichetta 'Cancella le tracce lasciate da browser e Windows. Attenzione: cancellare i cookie ti scollega dai siti. Chiudi i browser prima di procedere.'))
$lvPrivacy = New-Lista @(@('Voce', 300), @('Cosa cancella', 560), @('Dimensione', 100)) $true
$privacyBasso = New-Fila 'Bottom'
$btnPrivacyCancella = New-Pulsante 'Cancella selezionati' 160
$btnPrivacyAggiorna = New-Pulsante 'Aggiorna' 100
$privacyBasso.Controls.AddRange(@($btnPrivacyCancella, $btnPrivacyAggiorna))
Add-Contenuto $tabPrivacy $privacyAlto $lvPrivacy $privacyBasso
$script:privacyCaricata = $false

function Update-Privacy {
    $lblStato.Text = 'Controllo le tracce di navigazione...'
    [System.Windows.Forms.Application]::DoEvents()
    $voci = @(Get-VociPrivacy)
    $lvPrivacy.BeginUpdate()
    $lvPrivacy.Items.Clear()
    foreach ($v in $voci) {
        $it = New-Object System.Windows.Forms.ListViewItem($v.Nome)
        [void]$it.SubItems.Add($v.Descrizione)
        $dim = ''
        if ($v.Byte -gt 0) { $dim = Format-Dimensione $v.Byte }
        [void]$it.SubItems.Add($dim)
        $it.Tag = $v
        [void]$lvPrivacy.Items.Add($it)
    }
    $lvPrivacy.EndUpdate()
    $script:privacyCaricata = $true
    $lblStato.Text = 'Pronto'
}

$btnPrivacyAggiorna.Add_Click({ Update-Privacy })
$btnPrivacyCancella.Add_Click({
        $scelti = @($lvPrivacy.CheckedItems | ForEach-Object { $_.Tag })
        if ($scelti.Count -eq 0) { Show-Messaggio 'Seleziona cosa cancellare.' 'Privacy'; return }
        $elenco = ($scelti | ForEach-Object { "•  $($_.Nome)" }) -join "`n"
        if (-not (Confirm-Domanda "Cancellare definitivamente:`n`n$elenco" 'Privacy')) { return }
        Set-Occupato $true
        try {
            $esiti = @($scelti | ForEach-Object { $r = Clear-VocePrivacy -Voce $_; $s = '✔'; if (-not $r.Riuscito) { $s = '⚠' }; "$s  $($r.Messaggio)" })
        } finally {
            Set-Occupato $false
        }
        Update-Privacy
        Show-Messaggio ($esiti -join "`n") 'Privacy'
    })

# ===================== Pulizia programmata =====================

$tabPiano = New-Object System.Windows.Forms.TabPage 'Pulizia automatica'
$piano = New-Object System.Windows.Forms.TableLayoutPanel
$piano.Dock = 'Fill'
$piano.Padding = New-Object System.Windows.Forms.Padding(16)
$piano.ColumnCount = 1
$piano.AutoScroll = $true

$lblPianoStato = New-Etichetta 'Pulizia automatica: non attiva'
$lblPianoStato.Font = New-Object System.Drawing.Font('Segoe UI', 11, [System.Drawing.FontStyle]::Bold)

$filaQuando = New-Fila
$cmbGiorno = New-Object System.Windows.Forms.ComboBox
$cmbGiorno.DropDownStyle = 'DropDownList'
$cmbGiorno.Width = 120
$cmbGiorno.Margin = New-Object System.Windows.Forms.Padding(0, 6, 12, 0)
foreach ($g in Get-GiorniSettimana) { [void]$cmbGiorno.Items.Add($g.Nome) }
$cmbGiorno.SelectedIndex = 6
$oraPiano = New-Object System.Windows.Forms.DateTimePicker
$oraPiano.Format = 'Custom'
$oraPiano.CustomFormat = 'HH:mm'
$oraPiano.ShowUpDown = $true
$oraPiano.Width = 70
$oraPiano.Margin = New-Object System.Windows.Forms.Padding(0, 6, 12, 0)
$oraPiano.Value = [datetime]::Today.AddHours(12)
$filaQuando.Controls.AddRange(@((New-Etichetta 'Ogni settimana, il giorno'), $cmbGiorno, (New-Etichetta 'alle ore'), $oraPiano))

$chkPiano = New-Object System.Windows.Forms.CheckedListBox
$chkPiano.CheckOnClick = $true
$chkPiano.Width = 520
$chkPiano.Height = 110
$script:pianoIds = @(Get-InterventiProgrammabili)
foreach ($id in $script:pianoIds) {
    $c = $script:mappa[$id]
    $i = $chkPiano.Items.Add("$($c.Nome): $($c.Azione)")
    $chkPiano.SetItemChecked($i, ($id -ne 'cestino'))
}

$filaPiano = New-Fila
$btnPianoAttiva = New-Pulsante 'Attiva / aggiorna' 140
$btnPianoDisattiva = New-Pulsante 'Disattiva' 100
$btnPianoOra = New-Pulsante 'Esegui adesso' 120
$btnPianoLog = New-Pulsante 'Apri il registro' 130
$filaPiano.Controls.AddRange(@($btnPianoAttiva, $btnPianoDisattiva, $btnPianoOra, $btnPianoLog))

$lblPianoNota = New-Etichetta "La pulizia parte in silenzio quando sei collegato al PC (se il PC è spento, appena lo riaccendi). Il programma deve restare nella cartella:`n$cartella"
$lblPianoNota.MaximumSize = New-Object System.Drawing.Size(900, 0)

$piano.Controls.AddRange(@($lblPianoStato, $filaQuando, (New-Etichetta 'Interventi da eseguire:'), $chkPiano, $filaPiano, $lblPianoNota))
$tabPiano.Controls.Add($piano)

function Update-Pianificazione {
    $p = $null
    try { $p = Get-PuliziaProgrammata } catch { }
    if (-not $p) {
        $lblPianoStato.Text = 'Pulizia automatica: non attiva'
        $btnPianoDisattiva.Enabled = $false
        $btnPianoOra.Enabled = $false
        return
    }
    $t = "Pulizia automatica: attiva ogni $($p.Giorno) alle $($p.Ora)"
    if (-not $p.Attiva) { $t = 'Pulizia automatica: disattivata in Utilità di pianificazione' }
    if ($p.UltimaEsecuzione) { $t += "  ·  ultima: $($p.UltimaEsecuzione.ToString('dd/MM/yyyy HH:mm'))" }
    $lblPianoStato.Text = $t
    $btnPianoDisattiva.Enabled = $true
    $btnPianoOra.Enabled = $true
    $giorni = @(Get-GiorniSettimana)
    for ($i = 0; $i -lt $giorni.Count; $i++) { if ($p.Giorno -eq $giorni[$i].Nome) { $cmbGiorno.SelectedIndex = $i } }
    if ($p.Ora) { $oraPiano.Value = [datetime]::Today.Add([timespan]::Parse($p.Ora)) }
    for ($i = 0; $i -lt $script:pianoIds.Count; $i++) { $chkPiano.SetItemChecked($i, ($p.Interventi -contains $script:pianoIds[$i])) }
}

$btnPianoAttiva.Add_Click({
        $ids = @(for ($i = 0; $i -lt $script:pianoIds.Count; $i++) { if ($chkPiano.GetItemChecked($i)) { $script:pianoIds[$i] } })
        if ($ids.Count -eq 0) { Show-Messaggio 'Scegli almeno un intervento.' 'Pulizia automatica'; return }
        try {
            $giorno = (Get-GiorniSettimana)[$cmbGiorno.SelectedIndex].Valore
            [void](Set-PuliziaProgrammata -Giorno $giorno -Ora $oraPiano.Value.ToString('HH:mm') -Interventi $ids -Script $script:percorsoScript)
            Update-Pianificazione
            Show-Messaggio "Pulizia automatica attivata: ogni $($cmbGiorno.Text) alle $($oraPiano.Value.ToString('HH:mm'))." 'Pulizia automatica'
        } catch {
            Show-Messaggio "Impossibile attivare la pulizia automatica: $($_.Exception.Message)" 'Pulizia automatica' 'Warning'
        }
    })
$btnPianoDisattiva.Add_Click({
        try { Remove-PuliziaProgrammata } catch { Show-Messaggio $_.Exception.Message 'Pulizia automatica' 'Warning' }
        Update-Pianificazione
    })
$btnPianoOra.Add_Click({
        try {
            Start-PuliziaProgrammata
            Show-Messaggio 'Pulizia avviata in background. Fra un minuto puoi vedere l''esito con «Apri il registro».' 'Pulizia automatica'
        } catch { Show-Messaggio $_.Exception.Message 'Pulizia automatica' 'Warning' }
    })
$btnPianoLog.Add_Click({
        $log = Get-PercorsoLog
        if (Test-Path -LiteralPath $log) { Start-Process notepad.exe -ArgumentList "`"$log`"" }
        else { Show-Messaggio 'La pulizia automatica non è ancora stata eseguita.' 'Pulizia automatica' }
    })

# ===================== Schede =====================

foreach ($t in @($tabDisco, $tabDoppi, $tabProg, $tabPrivacy, $tabPiano)) { [void]$schede.TabPages.Add($t) }

# Le schede si riempiono la prima volta che si aprono
$schede.Add_SelectedIndexChanged({
        if ($schede.SelectedTab -eq $tabProg -and $null -eq $script:progDati) { Update-Programmi }
        elseif ($schede.SelectedTab -eq $tabPrivacy -and -not $script:privacyCaricata) { Update-Privacy }
        elseif ($schede.SelectedTab -eq $tabPiano) { Update-Pianificazione }
    })
