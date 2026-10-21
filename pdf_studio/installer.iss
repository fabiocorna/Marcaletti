; Script Inno Setup per l'installer di CRN PDF Studio.
; Prima eseguire build_windows.bat, poi compilare questo file con Inno Setup 6.

#define AppName "CRN PDF Studio"
#define AppVersion "1.3.0"
#define AppExe "CRNPDFStudio.exe"

[Setup]
AppId={{6C0B1B7E-3B7A-4E43-9B7E-2D6B8D1C5F10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=CRN Studio
DefaultDirName={autopf}\CRN PDF Studio
DefaultGroupName={#AppName}
OutputDir=dist
OutputBaseFilename=CRNPDFStudio-Setup-{#AppVersion}
SetupIconFile=assets\pdfstudio.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
; La stampante virtuale richiede i privilegi di amministratore
PrivilegesRequired=admin
UsePreviousAppDir=no
CloseApplications=yes

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assocpdf"; Description: "Usa CRN PDF Studio per aprire i file PDF"; GroupDescription: "Associazioni file:"; Flags: unchecked
Name: "assocp7m"; Description: "Usa CRN PDF Studio per aprire i file firmati .p7m"; GroupDescription: "Associazioni file:"
Name: "printer"; Description: "Installa la stampante virtuale «CRN PDF» (crea PDF da qualsiasi programma)"; GroupDescription: "Stampante PDF:"
Name: "startup"; Description: "Avvia con Windows per ricevere le stampe"; GroupDescription: "Stampante PDF:"

[InstallDelete]
; Versioni precedenti, pubblicate con il nome "PDF Studio"
Type: filesandordirs; Name: "{commonpf}\PDF Studio"
Type: filesandordirs; Name: "{userpf}\PDF Studio"
Type: filesandordirs; Name: "{commonprograms}\PDF Studio"
Type: filesandordirs; Name: "{userprograms}\PDF Studio"
Type: files; Name: "{commondesktop}\PDF Studio.lnk"
Type: files; Name: "{userdesktop}\PDF Studio.lnk"

[Files]
Source: "dist\CRNPDFStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "tools\*.ps1"; DestDir: "{app}\tools"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Disinstalla {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Voce "Apri con" e associazione facoltativa dei .pdf
Root: HKA; Subkey: "Software\Classes\PDFStudio.Document"; ValueType: string; ValueName: ""; ValueData: "Documento PDF"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\PDFStudio.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"
Root: HKA; Subkey: "Software\Classes\PDFStudio.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PDFStudio.Document"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.pdf"; ValueType: string; ValueName: ""; ValueData: "PDFStudio.Document"; Tasks: assocpdf; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.p7m\OpenWithProgids"; ValueType: string; ValueName: "PDFStudio.Document"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.p7m"; ValueType: string; ValueName: ""; ValueData: "PDFStudio.Document"; Tasks: assocp7m; Flags: uninsdeletevalue

Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "CRN PDF Studio"; ValueData: """{app}\{#AppExe}"" --background"; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\tools\install_printer.ps1"""; StatusMsg: "Installazione della stampante «CRN PDF»…"; Flags: runhidden waituntilterminated; Tasks: printer
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "ChiudiApp"
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\tools\uninstall_printer.ps1"""; Flags: runhidden waituntilterminated; RunOnceId: "RimuoviStampante"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Code: Integer;
begin
  { Chiude il programma se è aperto (anche nell'area di notifica) }
  Exec('taskkill.exe', '/F /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Exec('taskkill.exe', '/F /IM PDFStudio.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Result := '';
end;
