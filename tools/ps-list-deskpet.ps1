Get-Process -Name DeskPet -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,Path,StartTime | Format-List
Write-Output "---- count ----"
(Get-Process -Name DeskPet -ErrorAction SilentlyContinue | Measure-Object).Count
