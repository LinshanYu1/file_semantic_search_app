#define MyAppName "Semantic File Search"
#ifndef MyAppVersion
#define MyAppVersion "0.1.0"
#endif
#define MyAppPublisher "Local"
#define MyAppExeName "SemanticFileSearch.exe"
#ifndef MyAppOutputBaseFilename
#define MyAppOutputBaseFilename "SemanticFileSearchSetup"
#endif
[Setup]
AppId={{2B7535D1-1A8B-4F63-9860-F1A13EC75691}
AppName=文件快速搜索
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Semantic File Search
DefaultGroupName=文件快速搜索
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename={#MyAppOutputBaseFilename}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=6.1sp1
PrivilegesRequired=lowest
SetupIconFile=assets\search.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："
[Files]
Source: "dist\SemanticFileSearch\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\文件快速搜索"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\文件快速搜索"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
