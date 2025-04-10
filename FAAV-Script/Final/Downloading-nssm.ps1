# Ensure script runs in its own directory
$destinationPath = Join-Path -Path $PSScriptRoot -ChildPath "nssm"

# Download and extract NSSM into the same folder as the script
Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "$PSScriptRoot\nssm.zip"
Expand-Archive -Path "$PSScriptRoot\nssm.zip" -DestinationPath $destinationPath -Force

Write-Output "NSSM extracted to: $destinationPath"
