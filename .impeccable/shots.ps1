param([string[]]$Pages, [int]$Width = 1440, [int]$Height = 1200, [int]$Budget = 9000)
# Usage: shots.ps1 -Pages "/=markets","/jobs=jobs"
$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
foreach ($p in ($Pages -join ",") -split ",") {
  $null = $p -match '^(.*)=([^=]+)$'; $url = $Matches[1]; $name = $Matches[2]
  $out = "C:\Self_analytics\.impeccable\review\$name.png"
  $proc = Start-Process -FilePath $edge -PassThru -WindowStyle Hidden -ArgumentList @(
    '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run', "--user-data-dir=$env:TEMP\sa-edge-$name",
    "--window-size=$Width,$Height", "--virtual-time-budget=$Budget", "--screenshot=$out", "http://127.0.0.1:3100$url")
  if (-not $proc.WaitForExit(40000)) { Stop-Process -Id $proc.Id -Force; "timeout $name" } else { "ok $name" }
}
