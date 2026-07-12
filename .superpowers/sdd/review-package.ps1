# Generate a review package (commit list + stat + full diff) to a file.
# Usage: review-package.ps1 -Base <sha> -Head <sha>
param(
  [Parameter(Mandatory=$true)][string]$Base,
  [Parameter(Mandatory=$true)][string]$Head,
  [string]$Out
)
if (-not $Out) { $Out = ".superpowers/sdd/review-$Base-$Head.diff" }
$log = git log --oneline "$Base..$Head" 2>&1 | Out-String
$stat = git diff --stat "$Base..$Head" 2>&1 | Out-String
$diff = git diff -U10 "$Base..$Head" 2>&1 | Out-String
$content = "## Commits`n`n$log`n## Stat`n`n$stat`n## Diff`n`n$diff"
Set-Content -LiteralPath $Out -Value $content -Encoding utf8
Write-Output $Out
