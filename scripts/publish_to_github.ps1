# Publish this skill with git only (no gh).
# Prerequisite: create an empty repo on GitHub first, e.g.
#   https://github.com/new  -> name: jianying-template-video-remix
#
# Usage (from repo root):
#   .\scripts\publish_to_github.ps1
#   .\scripts\publish_to_github.ps1 -GitHubUser uniquets -RepoName jianying-template-video-remix

param(
    [string]$GitHubUser = "uniquets",
    [string]$RepoName = "jianying-template-video-remix",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git not found on PATH. Install Git for Windows first."
}

$remoteUrl = "https://github.com/$GitHubUser/$RepoName.git"

if (-not (Test-Path .git)) {
    git init -b $Branch
}

$currentRemote = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    git remote add origin $remoteUrl
} elseif ($currentRemote -ne $remoteUrl) {
    git remote set-url origin $remoteUrl
}

git add -A
$status = git status --porcelain
if ($status) {
    git commit -m @"
Publish jianying-template-video-remix skill

- Classify BGM vs voiceover/dub in template analysis
- Short single-line subtitles; no TTS atempo time-stretch
- Fallback BGM when template has no valid music track
- Fix DEFAULT_FALLBACK_PROFILE import in remix_draft
"@
} else {
    Write-Host "No file changes to commit."
}

git branch -M $Branch
Write-Host "Pushing to $remoteUrl (branch $Branch) ..."
Write-Host "If push fails with 'repository not found', create an empty repo first:"
Write-Host "  https://github.com/new?name=$RepoName"
git push -u origin $Branch
Write-Host "Done: https://github.com/$GitHubUser/$RepoName"
