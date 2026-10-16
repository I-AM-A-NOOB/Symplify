; Symplify — Windows installer (Inno Setup 7).
;
; Compiled by `scripts/release.py`, which is the only thing that should ever do
; it, because that is where the four values it needs come from (the version in
; pyproject.toml, the architecture and the platform of the build that was
; actually made, and the Nuitka output directory):
;
;   ISCC.exe /DMyAppVersion=0.6.0 /DPlatform=windows /DArch=x64 ^
;            /DSourceDir=<repo>\build\main.dist /DOutputDir=<repo>\build ^
;            installer\Symplify.iss
;
; The defaults below are what the IDE compiles with. `MyAppVersion` deliberately
; has none: a setup that does not know its own version is not one to hand to
; anyone.

#ifndef MyAppVersion
  #error Pass /DMyAppVersion=<version> — scripts/release.py does it. The setup's file name, its Add/Remove entry and its file properties all come from it.
#endif
#ifndef Platform
  #define Platform "windows"
#endif
#ifndef Arch
  #define Arch "x64"
#endif
#ifndef SourceDir
  #define SourceDir "..\build\main.dist"
#endif
#ifndef OutputDir
  #define OutputDir "..\build"
#endif

#define MyAppName "Symplify"
#define MyAppExeName "symplify.exe"
#define MyAppPublisher "I-AM-A-NOOB"
#define MyAppURL "https://github.com/I-AM-A-NOOB/Symplify"

[Setup]
; The identity is stable across releases, so an upgrade replaces the previous
; installation instead of sitting next to it — and the architecture is appended
; to it, so an arm64 build could be installed on the same machine later without
; either one uninstalling the other.
AppId={{8EF6D059-DF33-474A-97FA-E30238B02DA1}-{#Arch}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
; {autopf} is Program Files for an all-users install and %LOCALAPPDATA%\Programs
; for a per-user one — the user picks which on the first page (see PrivilegesRequired).
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes

; The app keeps its settings in %APPDATA%\Symplify unless a `data` folder sits
; next to the exe (python/settings.py, `resolve_config_dir`) — so nothing here
; may create that folder: an installed copy whose Start-Menu shortcut put its
; config inside Program Files would be a bug. The portable archive is the
; download that ships the empty `data/`; this one installs the system location.
OutputDir={#OutputDir}
OutputBaseFilename=Symplify-v{#MyAppVersion}-{#Platform}-{#Arch}-setup
SetupIconFile=..\icon\Symplify.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; `dynamic` follows the user's Windows light/dark setting; `modern` is the flat
; wizard that matches it. No custom images or style files: the default artwork
; already ships dark-mode variants, and the setup's own icon is ours.
WizardStyle=modern dynamic
; A 64-bit Setup, so the dictionary size is not capped at 1 GB and the outer
; archive stays small; `ultra64` (64 MB) is 742 MB of memory while compressing,
; which is the point 7-Zip gains nothing more from on Qt binaries.
Compression=lzma2/ultra64
SolidCompression=yes

; A 64-bit installer for a 64-bit-only program (Nuitka built the exe with MSVC
; x64). 64-bit install mode too, so {autopf} is the real Program Files rather
; than the x86 one.
SetupArchitecture=x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Setup's own default is Windows 7 SP1, which Qt 6.11 cannot start on: without
; this the installer would happily install an app that cannot run.
MinVersion=10.0.17763

; Per-user by default: no UAC prompt for a calculator, and %LOCALAPPDATA%\Programs
; needs no rights. `dialog` offers the all-users install (and `/ALLUSERS` /
; `/CURRENTUSER` for a scripted one) to the people who want it.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Let Setup close a running Symplify through the Restart Manager instead of
; failing on a file in use during an upgrade.
CloseApplications=yes

VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Tasks]
; Unchecked: an installer that covers the desktop with icons is a complaint.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole Nuitka tree. `ignoreversion` on purpose: these are one build's files,
; and comparing versions across releases is how an exe ends up running next to
; the previous release's DLLs.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
