$ErrorActionPreference = "Continue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root "frontend"
$ports = @(8002, 8000, 5175, 5173)
$stopped = New-Object System.Collections.Generic.HashSet[int]

function Stop-Pid([int]$ProcessId, [string]$Reason) {
  if ($ProcessId -le 0 -or $stopped.Contains($ProcessId)) { return }
  try {
    $proc = Get-Process -Id $ProcessId -ErrorAction Stop
    Write-Host "Stopping PID $ProcessId ($($proc.ProcessName)) - $Reason"
    Stop-Process -Id $ProcessId -Force -ErrorAction Stop
    [void]$stopped.Add($ProcessId)
  } catch {
    # already exited
  }
}

Write-Host "[1/3] Stopping listeners on ports: $($ports -join ', ')..."
foreach ($port in $ports) {
  $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  foreach ($conn in @($conns)) {
    Stop-Pid -ProcessId $conn.OwningProcess -Reason "port $port"
  }
}

Write-Host "[2/3] Stopping project backend/frontend processes..."
$rootNorm = $root.Replace('\', '/').ToLowerInvariant()
$frontendNorm = $frontend.Replace('\', '/').ToLowerInvariant()

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine } |
  ForEach-Object {
    $cmd = $_.CommandLine
    $cmdNorm = $cmd.Replace('\', '/').ToLowerInvariant()
    $isBackend = ($cmd -match 'run_api\.py') -and (
      $cmdNorm.Contains($rootNorm) -or $cmd -match 'API_PORT[\s=:''"]*8002'
    )
    $isFrontend = ($cmd -match 'vite|npm run dev') -and (
      $cmdNorm.Contains($frontendNorm) -or $cmdNorm.Contains($rootNorm)
    )
    $isStarterShell = ($_.Name -match 'powershell|pwsh|cmd') -and (
      ($cmd -match 'run_api\.py' -and $cmdNorm.Contains($rootNorm)) -or
      ($cmd -match 'npm run dev' -and $cmdNorm.Contains($frontendNorm))
    )
    if ($isBackend -or $isFrontend -or $isStarterShell) {
      Stop-Pid -ProcessId $_.ProcessId -Reason $_.Name
    }
  }

Write-Host "[3/3] Rechecking ports..."
$stillUp = @()
foreach ($port in $ports) {
  $left = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($left) { $stillUp += $port }
}

Write-Host ""
if ($stopped.Count -eq 0 -and $stillUp.Count -eq 0) {
  Write-Host "Nothing to stop. Services were not running."
} elseif ($stillUp.Count -gt 0) {
  Write-Host "Stopped $($stopped.Count) process(es), but ports still in use: $($stillUp -join ', ')"
  exit 1
} else {
  Write-Host "Stopped $($stopped.Count) process(es). Backend/frontend are down."
}
