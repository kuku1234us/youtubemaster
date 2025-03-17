; YouTubeMaster Installer Script
!include "MUI2.nsh"

; General Settings
Name "YouTubeMaster"
OutFile "YouTubeMaster-Setup.exe"
InstallDir "$PROGRAMFILES\YouTubeMaster"
InstallDirRegKey HKLM "Software\YouTubeMaster" "Install_Dir"
RequestExecutionLevel admin

; Interface Settings
!define MUI_ABORTWARNING
!define MUI_ICON "assets\app.ico"
!define MUI_UNICON "assets\app.ico"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Languages
!insertmacro MUI_LANGUAGE "English"

; Installer Sections
Section "Install"
  SetOutPath "$INSTDIR"
  
  ; Copy application files
  File "dist\YouTubeMaster.exe"
  File "dist\config.yaml"
  File "dist\.env"
  
  ; Create folders and copy resources
  CreateDirectory "$INSTDIR\assets"
  SetOutPath "$INSTDIR\assets"
  File /r "assets\*.*"
  
  ; Create Start Menu shortcuts
  CreateDirectory "$SMPROGRAMS\YouTubeMaster"
  CreateShortcut "$SMPROGRAMS\YouTubeMaster\YouTubeMaster.lnk" "$INSTDIR\YouTubeMaster.exe" "" "$INSTDIR\assets\app.ico"
  CreateShortcut "$SMPROGRAMS\YouTubeMaster\Uninstall.lnk" "$INSTDIR\uninstall.exe"
  CreateShortcut "$DESKTOP\YouTubeMaster.lnk" "$INSTDIR\YouTubeMaster.exe" "" "$INSTDIR\assets\app.ico"
  
  ; Write uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  ; Registry entries for Add/Remove Programs
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YouTubeMaster" "DisplayName" "YouTubeMaster"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YouTubeMaster" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YouTubeMaster" "DisplayIcon" "$INSTDIR\assets\app.ico"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YouTubeMaster" "Publisher" "YouTubeMaster"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YouTubeMaster" "DisplayVersion" "1.0.0"
  
  ; Associate with .ico files for testing
  WriteRegStr HKCR ".ytm" "" "YouTubeMaster.downloader"
  WriteRegStr HKCR "YouTubeMaster.downloader" "" "YouTube Master Download"
  WriteRegStr HKCR "YouTubeMaster.downloader\DefaultIcon" "" "$INSTDIR\assets\app.ico"
  WriteRegStr HKCR "YouTubeMaster.downloader\shell\open\command" "" '"$INSTDIR\YouTubeMaster.exe" "%1"'
SectionEnd

; Uninstaller Section
Section "Uninstall"
  ; Remove application files
  Delete "$INSTDIR\YouTubeMaster.exe"
  Delete "$INSTDIR\config.yaml"
  Delete "$INSTDIR\.env"
  
  ; Remove resources
  RMDir /r "$INSTDIR\assets"
  
  ; Remove Start Menu shortcuts
  Delete "$SMPROGRAMS\YouTubeMaster\YouTubeMaster.lnk"
  Delete "$SMPROGRAMS\YouTubeMaster\Uninstall.lnk"
  RMDir "$SMPROGRAMS\YouTubeMaster"
  Delete "$DESKTOP\YouTubeMaster.lnk"
  
  ; Remove uninstaller
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
  
  ; Remove registry entries
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\YouTubeMaster"
  DeleteRegKey HKLM "Software\YouTubeMaster"
  
  ; Remove file associations
  DeleteRegKey HKCR ".ytm"
  DeleteRegKey HKCR "YouTubeMaster.downloader"
SectionEnd 