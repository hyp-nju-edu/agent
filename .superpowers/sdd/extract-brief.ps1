# Extract one task's full text from the plan into a brief file.
# Usage: extract-brief.ps1 -Task N
param(
  [Parameter(Mandatory=$true)][int]$Task,
  [string]$Plan = "doc/PLAN.md",
  [string]$Out
)
if (-not $Out) { $Out = ".superpowers/sdd/task-$Task-brief.md" }
$lines = Get-Content -LiteralPath $Plan -Encoding utf8
$start = -1; $end = $lines.Count
for ($i=0; $i -lt $lines.Count; $i++) {
  if ($lines[$i] -match "^## Task\s+$Task([^0-9]|$)") { $start = $i; break }
}
if ($start -eq -1) { Write-Error "Task $Task not found"; exit 3 }
for ($j=$start+1; $j -lt $lines.Count; $j++) {
  if ($lines[$j] -match "^## Task\s+[0-9]+([^0-9]|$)") { $end = $j; break }
  if ($lines[$j] -match "^## (Self-Review|End of)") { $end = $j; break }
}
$brief = $lines[$start..($end-1)] -join "`n"
Set-Content -LiteralPath $Out -Value $brief -Encoding utf8
Write-Output "wrote $Out : $($end-$start) lines"
