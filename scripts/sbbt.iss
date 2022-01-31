; Script generated by the Inno Setup Script Wizard.
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

#define MyAppName "SBBTracker"
#define MyAppVersion "4.0.5"
#define MyAppPublisher "SBBTracker"
#define MyAppURL "sbbtracker.com"
#define MyAppExeName "SBBTracker.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{3F68BBDC-1D58-4C60-A34B-C0E37211C022}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
;AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=../LICENSE
; Uncomment the following line to run in non administrative install mode (install for current user only.)
;PrivilegesRequired=lowest
OutputBaseFilename=SBBTracker_installer
SetupIconFile=..\assets\sbbt.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\SBBTracker\*"; DestDir: "{app}\bin\"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\cards\*"; DestDir: "{app}\cards\"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\*"; DestDir: "{app}\assets\"; Flags: ignoreversion recursesubdirs createallsubdirs

; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\bin\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\bin\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\bin\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall

[Code]
procedure CurUninstallStepChanged (CurUninstallStep: TUninstallStep);
var
   mres : integer;
begin
  case CurUninstallStep of                   
    usPostUninstall:
      begin
        mres := MsgBox('Do you want delete ALL saved data (settings and match history)?', mbConfirmation, MB_YESNO or MB_DEFBUTTON2)
        if mres = IDYES then
          DelTree(ExpandConstant('{%USERPROFILE}\Documents\SBBTracker'), True, True, True);
     end;
 end;
end;

