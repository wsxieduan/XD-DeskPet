Get-Process -Name DeskPet -ErrorAction SilentlyContinue | Select-Object Id,StartTime | Format-Table -AutoSize
Write-Output "---- windows ----"
Get-Process -Name DeskPet -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne "" } | Select-Object Id,MainWindowTitle | Format-Table -AutoSize
Write-Output "---- shortcut ----"
$p = Join-Path ([Environment]::GetFolderPath("Desktop")) ([string]([char]0x684C + [char]0x5BA0 + [char]0x63A7 + [char]0x5236 + [char]0x53F0) + ".lnk")
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($p)
Write-Output ("target: " + $s.TargetPath + "  exists: " + (Test-Path $s.TargetPath))
