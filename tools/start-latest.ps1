$exe = "D:\dsh\deskpet\dist\DeskPet\DeskPet.exe"
Start-Process -FilePath $exe -WorkingDirectory "D:\dsh\deskpet\dist\DeskPet"
Start-Sleep -Seconds 3
Start-Process -FilePath $exe -ArgumentList "--pet","--id","pet1" -WorkingDirectory "D:\dsh\deskpet\dist\DeskPet"
Start-Sleep -Seconds 5
Get-Process -Name DeskPet -ErrorAction SilentlyContinue | Select-Object Id,StartTime | Format-Table -AutoSize
Write-Output "---- 窗口 ----"
Get-Process -Name DeskPet -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne "" } | Select-Object Id,MainWindowTitle | Format-Table -AutoSize
