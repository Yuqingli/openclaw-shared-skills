<#
.SYNOPSIS
    Run build and test commands for a repo. Returns JSON result.
.PARAMETER RepoPath
    Path to the repository.
.PARAMETER ConfigPath
    Path to spec-kit-config.json (optional, defaults to RepoPath/spec-kit-config.json).
.PARAMETER SkipBuild
    Skip the build step.
.PARAMETER SkipTest
    Skip the test step.
.PARAMETER SkipLint
    Skip the lint step.
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$RepoPath,
    
    [string]$ConfigPath,
    
    [switch]$SkipBuild,
    [switch]$SkipTest,
    [switch]$SkipLint
)

$ErrorActionPreference = "Stop"
$RepoPath = Resolve-Path $RepoPath

# Load config
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $RepoPath "spec-kit-config.json"
}

if (-not (Test-Path $ConfigPath)) {
    Write-Error "No spec-kit-config.json found at $ConfigPath"
    exit 1
}

$config = Get-Content $ConfigPath | ConvertFrom-Json

$results = @{
    build = @{ status = "skipped"; output = "" }
    test = @{ status = "skipped"; output = "" }
    lint = @{ status = "skipped"; output = "" }
    overall = "pass"
}

Push-Location $RepoPath
try {
    # Build
    if (-not $SkipBuild -and $config.build_cmd) {
        Write-Host "🏗️ Running build: $($config.build_cmd)"
        $buildOutput = Invoke-Expression $config.build_cmd 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) {
            $results.build.status = "pass"
            Write-Host "  ✅ Build passed"
        } else {
            $results.build.status = "fail"
            $results.overall = "fail"
            Write-Host "  ❌ Build failed"
        }
        $results.build.output = $buildOutput
    }
    
    # Test
    if (-not $SkipTest -and $config.test_cmd) {
        Write-Host "🧪 Running tests: $($config.test_cmd)"
        $testOutput = Invoke-Expression $config.test_cmd 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) {
            $results.test.status = "pass"
            Write-Host "  ✅ Tests passed"
        } else {
            $results.test.status = "fail"
            $results.overall = "fail"
            Write-Host "  ❌ Tests failed"
        }
        $results.test.output = $testOutput
    }
    
    # Lint
    if (-not $SkipLint -and $config.lint_cmd) {
        Write-Host "🔍 Running lint: $($config.lint_cmd)"
        $lintOutput = Invoke-Expression $config.lint_cmd 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) {
            $results.lint.status = "pass"
            Write-Host "  ✅ Lint passed"
        } else {
            $results.lint.status = "fail"
            $results.overall = "fail"
            Write-Host "  ❌ Lint failed"
        }
        $results.lint.output = $lintOutput
    }
    
} finally {
    Pop-Location
}

# Output JSON
$results | ConvertTo-Json -Depth 3
