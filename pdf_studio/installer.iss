; Script Inno Setup per l'installer di PDF Studio.
; Prima eseguire build_windows.bat, poi compilare questo file con Inno Setup 6.

#define AppName "PDF Studio"
#define AppVersion "1.1.0"
#define AppExe "PDFStudio.exe"

[Setup]
AppId={{6C0B1B7E-3B7A-4E43-9B7E-2D6B8D1C5F10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=PDF Studio
DefaultDirName={autopf}\PDF Studio
DefaultGroupName={#AppName}
OutputDir=dist
OutputBaseFilename=PDFStudio-Setup-{#AppVersion}
SetupIconFile=assets\pdfstudio.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assocpdf"; Description: "Usa PDF Studio per aprire i file PDF"; GroupDescription: "Associazioni file:"; Flags: unchecked
Name: "assocp7m"; Description: "Usa PDF Studio per aprire i file firmati .p7m"; GroupDescription: "Associazioni file:"

[Files]
Source: "dist\PDFStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

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

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
