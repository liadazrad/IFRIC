$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$dataDir = Join-Path $root "data"
$importDir = Join-Path $root "imports\ifrs-library"
$outputPath = Join-Path $dataDir "ifrs-library.json"
$toolsDir = Join-Path $root "tools"

function Ensure-Directory {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Get-PdfToTextPath {
  Ensure-Directory -Path $toolsDir

  $pdftotext = Get-ChildItem -LiteralPath $toolsDir -Recurse -Filter "pdftotext.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1

  if ($pdftotext) {
    return $pdftotext.FullName
  }

  $zipPath = Join-Path $toolsDir "xpdf-tools-win-4.06.zip"
  if (-not (Test-Path -LiteralPath $zipPath)) {
    & curl.exe -sS -L --output $zipPath --url "https://dl.xpdfreader.com/xpdf-tools-win-4.06.zip" | Out-Null
    if ($LASTEXITCODE -ne 0) {
      throw "Failed to download Xpdf tools."
    }
  }

  Expand-Archive -LiteralPath $zipPath -DestinationPath $toolsDir -Force

  $pdftotext = Get-ChildItem -LiteralPath $toolsDir -Recurse -Filter "pdftotext.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Select-Object -First 1

  if (-not $pdftotext) {
    throw "Unable to locate pdftotext.exe."
  }

  return $pdftotext.FullName
}

function Normalize-Text {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return ""
  }

  $text = $Value.Replace([char]0x2019, "'").Replace([char]0x2018, "'").Replace([char]0x2014, "-").Replace([char]0x2013, "-")
  $text = [regex]::Replace($text, "\s+", " ").Trim()
  return $text
}

function Infer-Standard {
  param([string]$Text)
  $match = [regex]::Match($Text, '\b(IAS|IFRS)\s*(\d+)\b', 'IgnoreCase')
  if ($match.Success) {
    return "{0} {1}" -f $match.Groups[1].Value.ToUpperInvariant(), $match.Groups[2].Value
  }
  return "ללא תקן"
}

function Infer-DocType {
  param([string]$Text)
  if ($Text -match '(?i)\bexposure draft\b|\bED\b') { return "ED" }
  if ($Text -match '(?i)\bbasis for conclusions\b|\bBC\b') { return "BC" }
  return "Standard"
}

function Build-Id {
  param(
    [string]$DocType,
    [string]$Standard,
    [string]$Title
  )

  $slug = [regex]::Replace(($Title.ToLowerInvariant()), "[^a-z0-9]+", "-").Trim("-")
  $typeSlug = [regex]::Replace(($DocType.ToLowerInvariant()), "[^a-z0-9]+", "-").Trim("-")
  $standardSlug = [regex]::Replace(($Standard.ToLowerInvariant()), "[^a-z0-9]+", "-").Trim("-")
  return "$typeSlug-$standardSlug-$slug"
}

Ensure-Directory -Path $dataDir
Ensure-Directory -Path $importDir

$manifestPath = Join-Path $importDir "manifest.csv"
$manifestRows = @{}

if (Test-Path -LiteralPath $manifestPath) {
  Import-Csv -LiteralPath $manifestPath | ForEach-Object {
    $manifestRows[$_.fileName] = $_
  }
}

$pdfToTextPath = Get-PdfToTextPath
$pdfFiles = Get-ChildItem -LiteralPath $importDir -Filter "*.pdf" -File -ErrorAction SilentlyContinue
$items = New-Object System.Collections.Generic.List[object]

foreach ($pdfFile in $pdfFiles) {
  $meta = $manifestRows[$pdfFile.Name]
  $txtPath = Join-Path $importDir ([System.IO.Path]::GetFileNameWithoutExtension($pdfFile.Name) + ".txt")

  if (-not (Test-Path -LiteralPath $txtPath) -or ((Get-Item -LiteralPath $txtPath).Length -lt 20)) {
    & $pdfToTextPath -enc UTF-8 -nopgbrk $pdfFile.FullName $txtPath | Out-Null
  }

  $fullText = ""
  if (Test-Path -LiteralPath $txtPath) {
    $fullText = Normalize-Text ([System.IO.File]::ReadAllText($txtPath, [System.Text.Encoding]::UTF8))
  }

  $baseText = if ($meta -and $meta.title) { $meta.title } else { [System.IO.Path]::GetFileNameWithoutExtension($pdfFile.Name) }
  $standard = if ($meta -and $meta.standard) { $meta.standard } else { Infer-Standard -Text $baseText }
  $docType = if ($meta -and $meta.docType) { $meta.docType } else { Infer-DocType -Text $baseText }
  $title = if ($meta -and $meta.title) { $meta.title } else { $baseText.Replace("_", " ").Replace("-", " ").Trim() }
  $publishedAt = if ($meta -and $meta.publishedAt) { $meta.publishedAt } else { $pdfFile.LastWriteTime.ToString("yyyy-MM-dd") }
  $sourceUrl = if ($meta -and $meta.sourceUrl) { $meta.sourceUrl } else { "./imports/ifrs-library/$($pdfFile.Name -replace ' ', '%20')" }
  $tags = @($standard.ToLowerInvariant(), $docType.ToLowerInvariant(), "ifrs-library")
  if ($meta -and $meta.tags) {
    $tags = $meta.tags.Split("|") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  }

  $items.Add([pscustomobject]@{
    id = Build-Id -DocType $docType -Standard $standard -Title $title
    title = $title
    heTitle = if ($meta -and $meta.heTitle) { $meta.heTitle } else { $title }
    shortSummary = if ($meta -and $meta.shortSummary) { $meta.shortSummary } else { "$docType document for $standard." }
    heSummary = if ($meta -and $meta.heSummary) { $meta.heSummary } else { "$docType | $standard" }
    standard = $standard
    docType = $docType
    publishedAt = $publishedAt
    volume = "IFRS Library"
    tags = $tags
    sourceUrl = $sourceUrl
    sourceType = "IFRS Library"
    fullText = $fullText
  })
}

$json = $items | Sort-Object docType, standard, title | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText($outputPath, $json, [System.Text.UTF8Encoding]::new($false))

Write-Host "Generated ifrs-library.json with $($items.Count) documents."
