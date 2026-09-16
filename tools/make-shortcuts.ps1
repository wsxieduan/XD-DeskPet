# make-shortcuts.ps1 - create the desktop shortcut for the pet console
# ASCII-only on purpose (Windows PowerShell 5.1 mangles BOM-less UTF-8 sources).
$root = Split-Path -Parent $PSScriptRoot
$pyw = (Get-Command pythonw).Source
$icon = Join-Path $root 'assets\icon.ico'
$target = Join-Path $root 'petctl.pyw'

# "桌宠控制台" = desk pet console (built from char codes, keeps this file ASCII)
$name = [string]([char]0x684C + [char]0x5BA0 + [char]0x63A7 + [char]0x5236 + [char]0x53F0) + '.lnk'
$desktop = [Environment]::GetFolderPath('Desktop')
$path = Join-Path $desktop $name

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($path)
$lnk.TargetPath = $pyw
$lnk.Arguments = '"' + $target + '"'
$lnk.WorkingDirectory = $root
$lnk.IconLocation = $icon + ',0'
$lnk.Description = 'Show or hide the desktop pet'
$lnk.Save()

Write-Output ("desktop shortcut created: " + $path)
Write-Output ("exists: " + (Test-Path $path))
