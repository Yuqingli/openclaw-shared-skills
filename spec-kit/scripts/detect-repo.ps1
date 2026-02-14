<#
.SYNOPSIS
    Detect repo type and load/create spec-kit config.
.PARAMETER RepoPath
    Path to the repository.
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$RepoPath
)

$ErrorActionPreference = "Stop"
$RepoPath = Resolve-Path $RepoPath

# Verify git repo
if (-not (Test-Path "$RepoPath\.git")) {
    @{ success = $false; error = "Not a git repository: $RepoPath" } | ConvertTo-Json
    exit 1
}

Push-Location $RepoPath
try {
    # Get remote URL
    $remote = git remote get-url origin 2>$null
    
    # Detect platform
    $platform = "unknown"
    $org = ""
    $project = ""
    $repoName = ""
    
    if ($remote -match "github\.com[:/]([^/]+)/([^/.]+)") {
        $platform = "github"
        $org = $Matches[1]
        $repoName = $Matches[2]
    }
    elseif ($remote -match "(\w+)\.visualstudio\.com/([^/_]+)/_git/(.+)") {
        $platform = "ado"
        $org = $Matches[1]
        $project = [System.Uri]::UnescapeDataString($Matches[2])
        $repoName = $Matches[3]
    }
    elseif ($remote -match "dev\.azure\.com/([^/]+)/([^/]+)/_git/(.+)") {
        $platform = "ado"
        $org = $Matches[1]
        $project = [System.Uri]::UnescapeDataString($Matches[2])
        $repoName = $Matches[3]
    }
    
    # Check for existing config
    $configPath = Join-Path $RepoPath "spec-kit-config.json"
    $config = $null
    if (Test-Path $configPath) {
        $config = Get-Content $configPath | ConvertFrom-Json
    }
    
    # Check if spec-kit is initialized
    $specKitInit = (Test-Path "$RepoPath\scripts\powershell") -or (Test-Path "$RepoPath\.claude\commands")
    
    # Detect available agents
    $agents = @()
    if (Get-Command claude -ErrorAction SilentlyContinue) { $agents += "claude" }
    if (Get-Command codex -ErrorAction SilentlyContinue) { $agents += "codex" }
    if (Get-Command gemini -ErrorAction SilentlyContinue) { $agents += "gemini" }
    
    # Current branch
    $branch = git branch --show-current 2>$null
    
    # Check for active feature
    $featureDir = $null
    if (Test-Path "$RepoPath\specs") {
        $features = Get-ChildItem "$RepoPath\specs" -Directory | Sort-Object Name -Descending
        if ($features) {
            $featureDir = $features[0].Name
        }
    }

    @{
        success = $true
        repo_path = $RepoPath
        platform = $platform
        org = $org
        project = $project
        repo_name = $repoName
        remote = $remote
        branch = $branch
        speckit_initialized = $specKitInit
        has_config = ($null -ne $config)
        config = $config
        available_agents = $agents
        latest_feature = $featureDir
    } | ConvertTo-Json -Depth 3

} finally {
    Pop-Location
}
