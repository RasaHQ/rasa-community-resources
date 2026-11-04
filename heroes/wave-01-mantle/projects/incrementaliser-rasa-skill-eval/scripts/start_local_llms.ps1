# Starts llama-server. Prefer ``uv run eval-all`` which starts one local actor at a time.
param(
    [string[]]$Ids = @("lfm-1.2b", "lfm-2.6b")
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$flat = @()
foreach ($raw in $Ids) {
    foreach ($piece in @($raw -split ",")) {
        $trimmed = $piece.Trim()
        if ($trimmed) { $flat += $trimmed }
    }
}

uv run python -m rasa_skill_eval.local_llm start @flat
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
