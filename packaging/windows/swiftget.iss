; Installer Windows untuk SwiftGet (Inno Setup 6). Dibangun lewat packaging/build.py
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6F1B7A52-3C4E-4D2B-9A57-5E0C1D8B7A31}
AppName=SwiftGet
AppVersion={#AppVersion}
AppVerName=SwiftGet {#AppVersion}
AppPublisher=SwiftGet
DefaultDirName={autopf}\SwiftGet
DefaultGroupName=SwiftGet
DisableProgramGroupPage=yes
OutputBaseFilename=SwiftGet-Setup-{#AppVersion}
SetupIconFile=..\..\assets\icon.ico
UninstallDisplayIcon={app}\SwiftGet.exe
UninstallDisplayName=SwiftGet
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=force
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Start SwiftGet when I sign in (runs in the background so the browser extension stays connected)"; GroupDescription: "Startup:"

[Files]
Source: "..\..\dist\SwiftGet\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\SwiftGet"; Filename: "{app}\SwiftGet.exe"
Name: "{autodesktop}\SwiftGet"; Filename: "{app}\SwiftGet.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SwiftGet"; \
  ValueData: """{app}\SwiftGet.exe"" --background"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\SwiftGet.exe"; Description: "{cm:LaunchProgram,SwiftGet}"; Flags: nowait postinstall skipifsilent
