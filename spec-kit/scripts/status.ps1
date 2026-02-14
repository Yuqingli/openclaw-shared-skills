<#
.SYNOPSIS
    Show spec-kit pipeline status for a repo or all active features.
.PARAMETER RepoPath
    Path to a specific repository (optional, shows all if omitted).
.PARAMETER StatePath
    Path to spec-kit-state.json.
#>
param(
    [string]$RepoPath,
    [string]$StatePath = "$env:USERPROFILE\clawd\memory\spec-kit-state.json"
)

# Load state
if (-not (Test-Path $StatePath)) {
    Write-Host "No active spec-kit features."
    @{ success = $true; features = @() } | ConvertTo-Json -Depth 4
    exit 0
}

$state = Get-Content $StatePath | ConvertFrom-Json

if (-not $state.active_features) {
    Write-Host "No active spec-kit features."
    @{ success = $true; features = @() } | ConvertTo-Json -Depth 4
    exit 0
}

$features = @()

$state.active_features.PSObject.Properties | ForEach-Object {
    $path = $_.Name
    $feat = $_.Value
    
    # Skip if filtering by repo
    if ($RepoPath -and $path -ne (Resolve-Path $RepoPath -ErrorAction SilentlyContinue)) {
        return
    }
    
    $stepOrder = @("constitution", "specify", "plan", "tasks", "implement")
    $currentIdx = $stepOrder.IndexOf($feat.step)
    $completedCount = ($feat.steps_completed | Measure-Object).Count
    $totalSteps = $stepOrder.Count
    
    $progressBar = ""
    foreach ($s in $stepOrder) {
        if ($feat.steps_completed -contains $s) {
            $progressBar += "✅"
        } elseif ($s -eq $feat.step) {
            $progressBar += "🔄"
        } else {
            $progressBar += "⬜"
        }
        $progressBar += " "
    }
    
    Write-Host ""
    Write-Host "📁 $path"
    Write-Host "   Branch: $($feat.branch)"
    Write-Host "   Step:   $($feat.step) ($($feat.phase))"
    Write-Host "   Review: $($feat.review_mode)"
    Write-Host "   Progress: $progressBar"
    Write-Host "   Started: $($feat.started)"
    Write-Host "   Updated: $($feat.last_updated)"
    
    $features += @{
        repo_path = $path
        branch = $feat.branch
        step = $feat.step
        phase = $feat.phase
        review_mode = $feat.review_mode
        steps_completed = $feat.steps_completed
        started = $feat.started
        last_updated = $feat.last_updated
        platform = $feat.platform
    }
}

@{
    success = $true
    features = $features
} | ConvertTo-Json -Depth 4
