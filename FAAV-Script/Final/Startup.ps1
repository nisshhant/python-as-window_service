# Full PowerShell Script with Step-by-Step y/n Execution

# Get the directory of the current script
$basePath = $PSScriptRoot

# Dynamically construct paths to the scripts
$Downloadnssm = Join-Path $basePath "Downloading-nssm.ps1"
$envpath = Join-Path $basePath "Setting-nssm-env.ps1"

$Setupnssm = Join-Path $basePath "Running-service.ps1"
$setupService = Join-Path $basePath "Manual-setup-Service.ps1"
# Function to run script with user confirmation
function Run-Step {
    param (
        [string]$scriptPath,
        [string]$stepName
    )

    Write-Host "`n➡️ Step: $stepName"
    Write-Host "Do you want to run this script? (y/n): " -NoNewline
    $input = Read-Host
    if ($input -eq 'y') {
        Write-Host "✅ Running $stepName..."
        &  powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath
    } elseif ($input -eq 'n') {
        Write-Host "⏭️ Skipping $stepName..."
    } else {
        Write-Host "❌ Invalid input. Skipping $stepName by default."
    }
}

# Execute steps one by one
Run-Step -scriptPath $Downloadnssm -stepName "Downloading NSSM"

Run-Step -scriptPath $envpath -stepName "Setting NSSM Environment Variables"
Run-Step -scriptPath $Setupnssm -stepName "Running AUTOMATIC service sertup"

#Run-Step -scriptPath $setupService -stepName "Running Manual Service Setup MODE"


Write-Host "`n🎉 Script completed. All steps processed!"
