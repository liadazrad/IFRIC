$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$trackerPath = Join-Path $root "data\ifric-tracker.json"
$changelogPath = Join-Path $root "data\ifric-changelog.json"
$ifricPath = Join-Path $root "data\ifric.json"
$today = (Get-Date).ToString("yyyy-MM-dd")

function Normalize-TopicTitle {
  param([string]$Value)

  $text = if ($null -eq $Value) { "" } else { $Value.ToLowerInvariant() }
  return ($text -replace "\([^)]*\)", "" -replace "[^a-z0-9\s]", " " -replace "\s+", " ").Trim()
}

if (-not (Test-Path -LiteralPath $trackerPath)) {
  throw "Missing tracker file: $trackerPath"
}

if (-not (Test-Path -LiteralPath $ifricPath)) {
  throw "Missing IFRIC decisions file: $ifricPath"
}

$tracker = Get-Content -LiteralPath $trackerPath -Raw | ConvertFrom-Json
$ifric = Get-Content -LiteralPath $ifricPath -Raw | ConvertFrom-Json

$decisionIndex = @{}
foreach ($decision in $ifric) {
  $key = "{0}|{1}" -f $decision.standard, (Normalize-TopicTitle $decision.title)
  $decisionIndex[$key] = $decision
}

foreach ($item in $tracker.items) {
  $item.lastCheckedAt = $today

  $key = "{0}|{1}" -f $item.standard, (Normalize-TopicTitle $item.topicTitleEn)
  if ($decisionIndex.ContainsKey($key)) {
    $decision = $decisionIndex[$key]

    $item.finalAgendaDecisionUrl = $decision.sourceUrl
    $item.sourceUrl = $decision.sourceUrl
    $item.lastChangedAt = if ([string]::IsNullOrWhiteSpace($item.lastChangedAt)) { $decision.publishedAt } else { $item.lastChangedAt }

    $hasFinalPaper = @($item.relatedPapers) | Where-Object { $_.relationshipType -eq "final_agenda_decision" }
    if (-not $hasFinalPaper) {
      $item.relatedPapers += [pscustomobject]@{
        documentTitle = "Final agenda decision"
        apNumber = ""
        documentType = "Final agenda decision"
        documentUrl = $decision.sourceUrl
        meetingDate = $decision.publishedAt
        sourcePageUrl = "https://www.ifrs.org/supporting-implementation/how-we-help-support-consistent-application/#agenda-decisions"
        relationshipType = "final_agenda_decision"
        confidenceScore = 0.99
        needsReview = $false
      }
    }
  }
}

$tracker.generatedAt = $today
$tracker.items = @(
  $tracker.items |
    Sort-Object @{ Expression = { [datetime]$_.lastChangedAt }; Descending = $true }, topicTitleEn
)

$existingChanges = @()
if (Test-Path -LiteralPath $changelogPath) {
  $existingChanges = (Get-Content -LiteralPath $changelogPath -Raw | ConvertFrom-Json).items
}

$changelog = [pscustomobject]@{
  generatedAt = $today
  items = @(
    $existingChanges |
      Sort-Object @{ Expression = { [datetime]$_.changedAt }; Descending = $true }, topicTitleEn
  )
}

[System.IO.File]::WriteAllText($trackerPath, ($tracker | ConvertTo-Json -Depth 100), [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText($changelogPath, ($changelog | ConvertTo-Json -Depth 100), [System.Text.UTF8Encoding]::new($false))

Write-Host "Updated IFRIC tracker and changelog."
