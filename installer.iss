[Setup]
AppName=Video2Notes
AppVersion=1.0
DefaultDirName={autopf}\Video2Notes
DefaultGroupName=Video2Notes
OutputDir=installer_output
OutputBaseFilename=Video2Notes-Setup
Compression=lzma2
SolidCompression=yes
; Installs just for the current user, so Windows does not ask for admin rights
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\note.exe
SetupIconFile=icon.ico

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"

[Files]
Source: "dist\note\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Video2Notes"; Filename: "{app}\note.exe"
Name: "{autodesktop}\Video2Notes"; Filename: "{app}\note.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\note.exe"; Description: "Open Video2Notes now"; Flags: nowait postinstall skipifsilent
