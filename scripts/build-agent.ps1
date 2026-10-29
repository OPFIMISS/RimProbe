param(
    [Parameter(Mandatory = $true)][ValidateSet('1.6', '1.7')][string]$Version,
    [string]$GamePath,
    [string]$ManagedPath,
    [Parameter(Mandatory = $true)][string]$HarmonyAssembly
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$harmony = (Resolve-Path -LiteralPath $HarmonyAssembly).Path
$project = Join-Path $root "agent/$Version/RimProbe.Agent.$Version.csproj"
$buildArguments = @('build', $project, '-c', 'Release', "-p:HarmonyAssembly=$harmony")
if ($GamePath) {
    $game = (Resolve-Path -LiteralPath $GamePath).Path
    $versionText = (Get-Content -LiteralPath (Join-Path $game 'Version.txt') -Raw).Trim()
    if (-not $versionText.StartsWith("$Version.")) {
        throw "Requested $Version but GamePath contains $versionText"
    }
    $buildArguments += "-p:GamePath=$game"
}
if ($Version -eq '1.6') {
    if (-not $ManagedPath) {
        if (-not $GamePath) { throw '1.6 requires GamePath or an explicit archived ManagedPath.' }
        $ManagedPath = Join-Path $game 'RimWorldWin64_Data/Managed'
    }
    $managed = (Resolve-Path -LiteralPath $ManagedPath).Path
    $buildArguments += "-p:ManagedPath=$managed"
    $engine = Join-Path $managed 'UnityEngine.CoreModule.dll'
} else {
    if (-not $GamePath) { throw '1.7 requires GamePath.' }
    $managed = $game
    $engine = Join-Path $managed 'UnityStubs.dll'
}
$gameAssembly = Join-Path $managed 'Assembly-CSharp.dll'
$identity = [Reflection.AssemblyName]::GetAssemblyName($gameAssembly)
if (-not $identity.Version.ToString().StartsWith("$Version.")) {
    throw "Reference DLL is $($identity.Version), not $Version. Refusing mixed-version build."
}
& dotnet @buildArguments
if ($LASTEXITCODE -ne 0) { throw 'Agent build failed.' }
$assembly = Join-Path $root "mod/$Version/Assemblies/RimProbe.Agent.dll"
$evidence = [ordered]@{
    built_at = [DateTimeOffset]::UtcNow.ToString('O')
    target_version = $Version
    target_framework = $(if ($Version -eq '1.6') { 'net472' } else { 'net10.0' })
    game_assembly = $gameAssembly
    reference_assembly_version = $identity.Version.ToString()
    game_sha256 = (Get-FileHash -LiteralPath $gameAssembly -Algorithm SHA256).Hash
    engine_sha256 = (Get-FileHash -LiteralPath $engine -Algorithm SHA256).Hash
    harmony_path = $harmony
    harmony_sha256 = (Get-FileHash -LiteralPath $harmony -Algorithm SHA256).Hash
    agent_sha256 = (Get-FileHash -LiteralPath $assembly -Algorithm SHA256).Hash
    in_game_verified = $false
}
$evidence | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root "build-evidence-$Version.json") -Encoding UTF8
Write-Output "Build evidence for $Version recorded. Compilation does not prove in-game correctness."
