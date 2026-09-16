# churn.ps1 - count distinct conhost processes seen over N seconds (prints one integer)
$secs = [int]$args[0]
$seen = @{}
$end = (Get-Date).AddSeconds($secs)
while ((Get-Date) -lt $end) {
    Get-Process conhost -ErrorAction SilentlyContinue | ForEach-Object { $seen[$_.Id] = 1 }
    Start-Sleep -Milliseconds 40
}
Write-Output $seen.Keys.Count
