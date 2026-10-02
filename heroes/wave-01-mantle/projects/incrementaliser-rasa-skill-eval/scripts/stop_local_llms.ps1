# Stops llama-server processes for local Layer B actor ports.
param(
    [string[]]$Ids = @()
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if ($Ids.Count -eq 0) {
    uv run python -m rasa_skill_eval.local_llm stop
} else {
    uv run python -m rasa_skill_eval.local_llm stop @Ids
}
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
