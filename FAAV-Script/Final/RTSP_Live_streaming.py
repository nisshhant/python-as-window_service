from Module_Checker import *
import cv2 
import av
import threading
import time
import logging
import asyncio
import hashlib
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from collections import deque
import uvicorn
from contextlib import asynccontextmanager
import subprocess
import platform
import multiprocessing
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global stream management
stream_data = {}
stream_lock = threading.Lock()

def ping_host(rtsp_url: str, timeout=1) -> bool:
    try:
        parsed_url = urlparse(rtsp_url)
        host = parsed_url.hostname
        if not host:
            return False

        ping_count = "1"
        system = platform.system().lower()
        if system == "windows":
            command = ["ping", "-n", ping_count, "-w", str(timeout * 1000), host]
        else:
            command = ["ping", "-c", ping_count, "-W", str(timeout), host]

        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Ping failed: {e}")
        return False

def get_stream_id(rtsp_url: str) -> str:
    return f"stream_{hashlib.md5(rtsp_url.encode()).hexdigest()}"

class FrameManager:
    def _init_(self, maxlen=5):
        self.buffer = deque(maxlen=maxlen)
        self.lock = threading.Lock()
        self.new_frame_event = threading.Event()
        self.last_frame_time = 0
        self.active = True

    def add_frame(self, frame):
        with self.lock:
            self.buffer.append(frame)
            self.new_frame_event.set()
            self.last_frame_time = time.time()

    def get_frame(self, timeout=1.0):
        if not self.new_frame_event.wait(timeout):
            return None
        with self.lock:
            if self.buffer:
                frame = self.buffer[-1]
                self.new_frame_event.clear()
                return frame
            return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    with stream_lock:
        for stream_id in list(stream_data.keys()):
            stop_stream_internal(stream_id)

app = FastAPI(lifespan=lifespan)

def capture_frames(stream_id, rtsp_url):
    reconnect_attempts = 0
    max_reconnect_attempts = 5

    while stream_data.get(stream_id, {}).get("running", False) and reconnect_attempts < max_reconnect_attempts:
        try:
            container = av.open(rtsp_url, options={
                "rtsp_transport": "tcp",
                "buffer_size": "1024000",
                "max_delay": "500000",
                "stimeout": "5000000"
            })

            with stream_lock:
                if stream_id in stream_data:
                    stream_data[stream_id]["container"] = container
                    reconnect_attempts = 0

            stream = container.streams.video[0]
            stream.thread_type = "AUTO"

            try:
                for frame in container.decode(video=0):
                    if not stream_data.get(stream_id, {}).get("running", False):
                        break
                    try:
                        img = frame.to_ndarray(format="bgr24")
                        if stream_id in stream_data:
                            stream_data[stream_id]["frame_manager"].add_frame(img)
                    except Exception as e:
                        logger.error(f"Frame decode/convert error: {e}")
            except av.AVError as e:
                logger.warning(f"Decoder crashed or stream interrupted: {e}")
            except Exception as e:
                logger.error(f"Unexpected decoding error: {e}")

        except av.error.FFmpegError as e:
            reconnect_attempts += 1
            logger.warning(f"FFmpeg error (attempt {reconnect_attempts}/{max_reconnect_attempts}): {e}")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            break
        finally:
            if 'container' in locals():
                try:
                    container.close()
                except Exception:
                    pass

    with stream_lock:
        if stream_id in stream_data:
            stream_data[stream_id]["running"] = False
            logger.info(f"Capture thread ended for {stream_id}")

async def generate_frames(stream_id):
    last_frame_time = 0
    retry_count = 0
    max_retries = 10

    while stream_id in stream_data and stream_data[stream_id]["running"] and retry_count < max_retries:
        frame = stream_data[stream_id]["frame_manager"].get_frame(timeout=0.5)
        if frame is None:
            retry_count += 1
            logger.warning(f"No frame for {stream_id} (attempt {retry_count}/{max_retries})")
            await asyncio.sleep(0.1)
            continue

        retry_count = 0
        current_time = time.time()
        if current_time - last_frame_time >= 0.033:
            try:
                _, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                frame_bytes = jpeg.tobytes()
                last_frame_time = current_time
                yield frame_bytes
            except Exception as e:
                logger.error(f"Frame encoding error: {e}")
                continue

    logger.info(f"Generator stopped for {stream_id}")

def stop_stream_internal(stream_id):
    if stream_id in stream_data:
        logger.info(f"Stopping stream {stream_id}")
        stream_data[stream_id]["running"] = False

        thread = stream_data[stream_id].get("thread")
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
            if thread.is_alive():
                logger.warning(f"Capture thread for {stream_id} didn't terminate cleanly")

        container = stream_data[stream_id].get("container")
        if container:
            try:
                container.close()
            except Exception:
                pass

        del stream_data[stream_id]

@app.get("/start_stream")
async def start_stream(rtsp_url: str):
    if not rtsp_url:
        raise HTTPException(status_code=400, detail="RTSP URL required")

    if not ping_host(rtsp_url):
        raise HTTPException(status_code=400, detail="Camera is not reachable on the network")

    stream_id = get_stream_id(rtsp_url)

    with stream_lock:
        if stream_id in stream_data:
            return {
                "status": "exists",
                "message": "Stream already running",
                "stream_id": stream_id,
                "clients": stream_data[stream_id]["clients"]
            }

        stream_data[stream_id] = {
            "rtsp_url": rtsp_url,
            "clients": 0,
            "frame_manager": FrameManager(maxlen=3),
            "running": True,
            "container": None
        }

        thread = threading.Thread(
            target=capture_frames,
            args=(stream_id, rtsp_url),
            daemon=True
        )
        stream_data[stream_id]["thread"] = thread
        thread.start()

    await asyncio.sleep(3)
    if not stream_data[stream_id]["frame_manager"].buffer:
        stop_stream_internal(stream_id)
        raise HTTPException(status_code=500, detail="Failed to connect to camera stream after network check")

    logger.info(f"Started new stream {stream_id}")
    return {
        "status": "success",
        "message": "New stream started",
        "stream_id": stream_id
    }

@app.websocket("/ws/video_feed")
async def websocket_video_feed(websocket: WebSocket, rtsp_url: str):
    await websocket.accept()
    stream_id = get_stream_id(rtsp_url)

    with stream_lock:
        if stream_id not in stream_data:
            await websocket.close(code=1008)
            return
        stream_data[stream_id]["clients"] += 1

    logger.info(f"WebSocket client connected: {stream_id}")

    try:
        async for frame_bytes in generate_frames(stream_id):
            await websocket.send_bytes(frame_bytes)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {stream_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        with stream_lock:
            if stream_id in stream_data:
                stream_data[stream_id]["clients"] -= 1
                logger.info(f"Client left {stream_id} (remaining: {stream_data[stream_id]['clients']})")
                if stream_data[stream_id]["clients"] == 0:
                    await asyncio.sleep(10)
                    if stream_data.get(stream_id, {}).get("clients", 0) == 0:
                        stop_stream_internal(stream_id)

@app.get("/stop_stream")
async def stop_stream(rtsp_url: str):
    if not rtsp_url:
        raise HTTPException(status_code=400, detail="RTSP URL required")

    stream_id = get_stream_id(rtsp_url)
    stop_stream_internal(stream_id)
    return {
        "status": "success",
        "message": f"Stream {stream_id} stopped"
    }

@app.get("/stream_info")
async def stream_info(rtsp_url: str = None):
    with stream_lock:
        if rtsp_url:
            stream_id = get_stream_id(rtsp_url)
            if stream_id in stream_data:
                return {
                    "stream_id": stream_id,
                    "status": "running" if stream_data[stream_id]["running"] else "stopped",
                    "clients": stream_data[stream_id]["clients"],
                    "rtsp_url": stream_data[stream_id]["rtsp_url"]
                }
            return {"status": "not_found"}

        return {
            "streams": [
                {
                    "stream_id": sid,
                    "rtsp_url": data["rtsp_url"],
                    "clients": data["clients"],
                    "status": "running" if data["running"] else "stopped"
                }
                for sid, data in stream_data.items()
            ]
        }



#if _name_ == "_main_":
#    uvicorn.run(app, host="0.0.0.0", port=5000)

def run_http():
    uvicorn.run(app, host="0.0.0.0", port=4000)

def run_https():
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5443,
        ssl_certfile="server.crt",
        ssl_keyfile="server.key"
    )

if __name__ == "__main__":
    try:
        multiprocessing.set_start_method("spawn")  # Required for Windows
        p1 = multiprocessing.Process(target=run_http)
        p2 = multiprocessing.Process(target=run_https)
        
        p1.start()
        p2.start()
        
        p1.join()
        p2.join()
    except Exception as ex:
        print(ex)
    
