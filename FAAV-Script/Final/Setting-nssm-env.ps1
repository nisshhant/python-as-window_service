Set-ExecutionPolicy Bypass -Scope Process -Force

$AdminCheck = [System.Security.Principal.WindowsPrincipal] [System.Security.Principal.WindowsIdentity]::GetCurrent()
$AdminRole = [System.Security.Principal.WindowsBuiltInRole]::Administrator

if (-not $AdminCheck.IsInRole($AdminRole)) {
    Start-Process powershell -ArgumentList "-File `"$PSCommandPath`"" -Verb RunAs
    exit
}


# Define NSSM path
$nssmPath = "C:\nssm\nssm-2.24\win64"

# Get the current PATH
$currentPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::Machine)

# Check if it's already in PATH
if ($currentPath -notlike "*$nssmPath*") {
    # Append NSSM path
    $newPath = "$currentPath;$nssmPath"

    # Set the new PATH for the system
    [Environment]::SetEnvironmentVariable("Path", $newPath, [EnvironmentVariableTarget]::Machine)

    Write-Host "`n✅ NSSM path added to system PATH. You may need to restart your terminal or system."
} else {
    Write-Host "`nℹ️ NSSM path is already present in system PATH."
}
