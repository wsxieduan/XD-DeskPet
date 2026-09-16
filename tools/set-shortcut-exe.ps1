# set-shortcut-exe.ps1 - point the desktop shortcut at the packaged exe
# ASCII-only (Windows PowerShell 5.1 mangles BOM-less UTF-8 sources).
param([string]$ExeDir = "D:\dsh\deskpet\dist\DeskPet")

$exe = Join-Path $ExeDir "DeskPet.exe"
if (-not (Test-Path $exe)) { Write-Output ("missing: " + $exe); exit 1 }

# "桌宠控制台" = desk pet console, built from char codes
$name = [string]([char]0x684C + [char]0x5BA0 + [char]0x63A7 + [char]0x5236 + [char]0x53F0) + ".lnk"
$path = Join-Path ([Environment]::GetFolderPath("Desktop")) $name

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($path)
$lnk.TargetPath = $exe
$lnk.Arguments = ""
$lnk.WorkingDirectory = $ExeDir
$lnk.IconLocation = $exe + ",0"
$lnk.Description = "DeskPet console"
$lnk.Save()
Write-Output ("shortcut -> " + $path)
Write-Output ("target   -> " + $exe)
Write-Output ("exists   -> " + (Test-Path $path))