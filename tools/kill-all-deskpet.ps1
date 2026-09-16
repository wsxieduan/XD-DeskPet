# kill-all-deskpet.ps1 - kill EVERY DeskPet process (exe or python source run).
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads BOM-less UTF-8 as
# ANSI/GBK, and non-ASCII comment characters can break the whole script.
$killed = 0

# 1) every process literally named DeskPet (that is the packaged exe)
$exes = @(Get-Process -Name DeskPet -ErrorAction SilentlyContinue)
foreach ($p in $exes) {
    Write-Output ("kill exe: PID=" + $p.Id + " " + $p.Path)
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    $killed++
}

# 2) source runs (python / pythonw) whose command line mentions deskpet.py or petctl.py
$targets = @(Get-CimInstance Win32_Process -Filter "Name LIKE '%python%'" |
    Where-Object { $_.CommandLine -like '*deskpet.py*' -or $_.CommandLine -like '*petctl.py*' })
foreach ($t in $targets) {
    Write-Output ("kill python: PID=" + $t.ProcessId + " " + $t.Name)
    Stop-Process -Id $t.ProcessId -Force -ErrorAction SilentlyContinue
    $killed++
}

if ($killed -eq 0) { Write-Output "no deskpet process" } else { Write-Output ("killed " + $killed) }
Start-Sleep -Milliseconds 900
