# Stops the Tdarr node while iRacing is running; starts it otherwise (incl. at boot).
$iracing = 'iRacingSim64DX11','iRacingSim64DX12','iRacingSim64','iRacingUI'
$nodeProcs = 'Tdarr_Node','Tdarr_Node_Rust','ffmpeg','ffprobe'
$log = 'C:\logs\tdarr-watch.log'
function Log($m){ "$(Get-Date -Format s) $m" | Add-Content $log }
function NodeUp { [bool](Get-Process -Name Tdarr_Node -ErrorAction SilentlyContinue) }
$wasRacing = $false
Log 'watcher started'
while ($true) {
  $racing = [bool](Get-Process -Name $iracing -ErrorAction SilentlyContinue)
  if ($racing) {
    if ((NodeUp) -or (Get-Process -Name ffmpeg -ErrorAction SilentlyContinue)) {
      Log 'iRacing running: stopping Tdarr node'
      Get-Process -Name $nodeProcs -ErrorAction SilentlyContinue | Stop-Process -Force
    }
  } else {
    if ($wasRacing) { Log 'iRacing closed: waiting 60s'; Start-Sleep 60; if (Get-Process -Name $iracing -ErrorAction SilentlyContinue) { continue } }
    if (-not (NodeUp)) {
      Log 'starting Tdarr node'
      Start-Process -FilePath 'C:\Tdarr_Node\run-tdarr-node.cmd' -WindowStyle Hidden
      Start-Sleep 30
    }
  }
  $wasRacing = $racing
  Start-Sleep 10
}
