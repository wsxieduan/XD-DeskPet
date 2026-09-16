# kill-pets.ps1 - kill every running deskpet process (python.exe or pythonw.exe)
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads BOM-less UTF-8 as
# ANSI/GBK, and non-ASCII comment characters can break the whole script.
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root 'pet.pid'
$killed = 0

# 1) authoritative: the pid the pet itself wrote
if (Test-Path $pidFile) {
    $raw = (Get-Content $pidFile -Raw).Trim()
    if ($raw -match '^[0-9]+$') {
        $p = Get-Process -Id ([int]$raw) -ErrorAction SilentlyContinue
        if ($p) {
            Write-Output ("kill by pid file: PID=" + $p.Id + " " + $p.ProcessName)
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            $killed++
        }
    }
}

# 2) sweep by command line
$targets = @(Get-CimInstance Win32_Process -Filter "Name LIKE '%python%'" |
    Where-Object { $_.CommandLine -like '*deskpet.py*' })
foreach ($t in $targets) {
    Write-Output ("kill by cmdline: PID=" + $t.ProcessId + " " + $t.Name)
    Stop-Process -Id $t.ProcessId -Force -ErrorAction SilentlyContinue
    $killed++
}

# 3) fallback: window title
$win = @(Get-Process pythonw, python -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -eq [char]0x684C + [char]0x5BA0 })
foreach ($p in $win) {
    Write-Output ("kill by window title: PID=" + $p.Id)
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    $killed++
}

if ($killed -eq 0) { Write-Output "no deskpet process" }
if (Test-Path $pidFile) { Remove-Item $pidFile -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 600
