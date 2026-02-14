<#
.SYNOPSIS
    Initialize spec-kit in a repository.
.PARAMETER RepoPath
    Path to the repository.
.PARAMETER Agent
    AI agent to configure (claude, codex, gemini, copilot). Default: claude.
.PARAMETER Force
    Force re-initialization if spec-kit already set up.
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$RepoPath,
    
    [ValidateSet("claude", "codex", "gemini", "copilot")]
    [string]$Agent = "claude",
    
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Resolve path
$RepoPath = Resolve-Path $RepoPath

# Check if repo exists
if (-not (Test-Path "$RepoPath\.git")) {
    Write-Error "Not a git repository: $RepoPath"
    exit 1
}

# Check if spec-kit already initialized
$specKitMarkers = @(".claude/commands", ".gemini/commands", "scripts/bash", "scripts/powershell")
$alreadyInit = $false
foreach ($marker in $specKitMarkers) {
    if (Test-Path "$RepoPath\$marker") {
        $alreadyInit = $true
        break
    }
}

if ($alreadyInit -and -not $Force) {
    Write-Host "spec-kit already initialized in $RepoPath. Use -Force to re-initialize."
    exit 0
}

# Check specify CLI is installed
$specifyCli = Get-Command specify -ErrorAction SilentlyContinue
if (-not $specifyCli) {
    Write-Host "Installing specify-cli..."
    uv tool install specify-cli --from "git+https://github.com/github/spec-kit.git"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install specify-cli"
        exit 1
    }
}

# Detect platform from remote
$remote = git -C $RepoPath remote get-url origin 2>$null
$platform = "github"
if ($remote -match "visualstudio\.com|dev\.azure\.com") {
    $platform = "ado"
}

# Initialize spec-kit
Push-Location $RepoPath
try {
    $initArgs = @("init", ".", "--ai", $Agent, "--script", "ps")
    if ($Force) { $initArgs += "--force" }
    
    Write-Host "Initializing spec-kit in $RepoPath (agent: $Agent, platform: $platform)..."
    & specify @initArgs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "specify init failed"
        exit 1
    }
    
    # Create/update spec-kit-config.json if it doesn't exist
    $configPath = Join-Path $RepoPath "spec-kit-config.json"
    if (-not (Test-Path $configPath)) {
        $config = @{
            platform = $platform
            build_cmd = ""
            test_cmd = ""
            lint_cmd = ""
            review_mode = "full"
            commit_prefix = "speckit"
        } | ConvertTo-Json -Depth 2
        
        Set-Content -Path $configPath -Value $config
        Write-Host "Created spec-kit-config.json — please configure build_cmd and test_cmd."
    }
    
    Write-Host "✅ spec-kit initialized successfully"
    Write-Host "   Platform: $platform"
    Write-Host "   Agent: $Agent"
    Write-Host "   Config: $configPath"
    
} finally {
    Pop-Location
}

# Output JSON for bot consumption
@{
    success = $true
    repo_path = $RepoPath
    platform = $platform
    agent = $Agent
    config_path = (Join-Path $RepoPath "spec-kit-config.json")
} | ConvertTo-Json
