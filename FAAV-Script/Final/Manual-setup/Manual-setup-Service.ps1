﻿# Get the current script folder (where this .ps1 is located)
$AdminCheck = [System.Security.Principal.WindowsPrincipal] [System.Security.Principal.WindowsIdentity]::GetCurrent()
$AdminRole = [System.Security.Principal.WindowsBuiltInRole]::Administrator

if (-not $AdminCheck.IsInRole($AdminRole)) {
    Start-Process powershell -ArgumentList "-File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$scriptFolder = Split-Path -Path $MyInvocation.MyCommand.Path -Parent

# Paths
$venvFolder = Join-Path $scriptFolder "env-service"
$venvPython = Join-Path $venvFolder "Scripts\python.exe"
$nssmPath = "C:\nssm\nssm-2.24\win64\nssm.exe"

$apiScript = Read-Host "Path of file(.py) : "

$requirements = Read-Host "Enter the requirement.txt file"
$serviceName =  Read-Host "Enter name of the Service : "

# If venv doesn't exist, create it
if (-Not (Test-Path $venvPython)) {
    Write-Host "🔧 Virtual environment not found. Creating one at $venvFolder ..."
    & python -m venv $venvFolder

    if (-Not (Test-Path $venvPython)) {
        Write-Host "❌ Failed to create virtual environment."
        exit 1
    }

    Write-Host "✅ Virtual environment created."

    # Optional: install requirements if file exists
    if (Test-Path $requirements) {
        Write-Host "📦 Installing dependencies from requirements.txt ..."
        & $venvPython -m pip install --upgrade pip
        & $venvPython -m pip install -r $requirements
    } else {
        Write-Host "⚠️ No requirements.txt found, skipping dependency installation."
    }
} else {
    Write-Host "✅ Found existing virtual environment: $venvPython"
}

& $nssmPath install $serviceName $venvPython $apiScript
& $nssmPath set $serviceName AppDirectory $scriptFolder
& $nssmPath set $serviceName AppStdout "$scriptFolder\logs\stdout.log"
& $nssmPath set $serviceName AppStderr "$scriptFolder\logs\stderr.log"
& $nssmPath set $serviceName Start SERVICE_AUTO_START

# Start the service
Start-Service $serviceName

Write-Host "`n🎉 Service '$serviceName' installed and started successfully using virtual environment!"
