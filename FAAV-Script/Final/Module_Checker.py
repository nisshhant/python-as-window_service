import sys
import subprocess

#========================Function=========================
def install_library(package_name):
    """Installs a missing Python library."""
    try:
        print(f"{package_name} module not found. Installing {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"{package_name} module installed successfully.")
    except Exception as e:
        print(f"Error installing {package_name}: {e}")



#========================Library=========================
try:
    from watchdog.observers import Observer
except ModuleNotFoundError:
    install_library("watchdog")
    from watchdog.observers import Observer

#========================Library=========================
try:
    import uvicorn
except ModuleNotFoundError:
    install_library("uvicorn")
    import uvicorn
#========================Library=========================
try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
except ModuleNotFoundError:
    install_library("fastapi")
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

#========================Library=========================
try:
    import av
except ModuleNotFoundError:
    install_library("av")
    import av


#========================Library=========================
try:
    import cv2
except ModuleNotFoundError:
    install_library("opencv-python")
    import cv2

