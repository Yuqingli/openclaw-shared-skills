<#
.SYNOPSIS
    Auto-commit and push changes with structured commit message.
.PARAMETER RepoPath
    Path to the repository.
.PARAMETER Step
    Pipeline step (constitution, specify, plan, tasks, implement, review).
.PARAMETER Message
    Description of what changed.
.PARAMETER Prefix
    Commit prefix (default: speckit).
.PARAMETER Push
    Push to remote after commit (default: true).
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$RepoPath,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("constitution", "specify", "plan", "tasks", "implement", "review")]
    [string]$Step,
    
    [Parameter(Mandatory=$true)]
    [string]$Message,
    
    [string]$Prefix = "speckit",
    
    [bool]$Push = $true
)

$ErrorActionPreference = "Stop"
$RepoPath = Resolve-Path $RepoPath

Push-Location $RepoPath
try {
    # Check for changes
    $status = git status --porcelain 2>&1
    if (-not $status) {
        Write-Host "No changes to commit."
        @{ success = $true; committed = $false; message = "No changes" } | ConvertTo-Json
        exit 0
    }
    
    # Stage all changes
    git add -A
    
    # Build commit message
    $commitMsg = "$Prefix($Step): $Message"
    
    # Commit
    git commit -m $commitMsg
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Git commit failed"
        exit 1
    }
    
    $commitHash = git rev-parse --short HEAD
    Write-Host "📦 Committed: $commitMsg ($commitHash)"
    
    # Push
    if ($Push) {
        $branch = git branch --show-current
        git push origin $branch 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Push failed — may need to set upstream. Trying with -u..."
            git push -u origin $branch 2>&1
        }
        Write-Host "🚀 Pushed to $branch"
    }
    
    # Output JSON
    @{
        success = $true
        committed = $true
        commit_hash = $commitHash
        commit_message = $commitMsg
        branch = (git branch --show-current)
    } | ConvertTo-Json
    
} finally {
    Pop-Location
}
