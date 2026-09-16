$out = @()
$out += "=== 本地监听的代理端口 ==="
$ports = @(10808,10809,7890,7891,7897,1080,2080,8080,20171)
$found = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort }
if ($found) { $found | ForEach-Object { $out += ("  " + $_.LocalAddress + ":" + $_.LocalPort) } } else { $out += "  (没有常见代理端口在监听)" }

$out += ""
$out += "=== 出网测试 ==="
foreach ($u in @("https://pypi.org/simple/", "https://github.com", "https://huggingface.co", "https://hf-mirror.com", "https://objects.githubusercontent.com")) {
    try {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $r = Invoke-WebRequest -Uri $u -Method Head -TimeoutSec 6 -UseBasicParsing -ErrorAction Stop
        $out += ("  OK   " + $u + "  " + $r.StatusCode + "  " + [int]$sw.ElapsedMilliseconds + "ms")
    } catch {
        $out += ("  FAIL " + $u + "  " + $_.Exception.Message.Substring(0, [Math]::Min(60, $_.Exception.Message.Length)))
    }
}
$out -join [Environment]::NewLine | Set-Content -Path 'D:\dsh\deskpet\selftest\net.txt' -Encoding UTF8
Write-Output "written"
