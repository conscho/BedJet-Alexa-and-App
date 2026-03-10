"""BedJet Hub Server - REST API + WebSocket for multi-user access."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bedjet_ble import BedjetBLE
from bedjet_protocol import BedjetMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bedjet = BedjetBLE()
connected_websockets: set[WebSocket] = set()


def broadcast_status(status):
    """Broadcast status to all connected WebSocket clients."""
    data = json.dumps({"type": "status", "data": status.to_dict()})
    stale = set()
    for ws in connected_websockets:
        try:
            asyncio.create_task(ws.send_text(data))
        except Exception:
            stale.add(ws)
    connected_websockets.difference_update(stale)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect to BedJet on startup, disconnect on shutdown."""
    bedjet.add_status_callback(broadcast_status)

    bedjet_address = os.environ.get("BEDJET_ADDRESS")
    try:
        await bedjet.connect(address=bedjet_address)
    except Exception as e:
        logger.warning(f"Could not connect to BedJet on startup: {e}")
        logger.info("Use POST /connect to connect manually")

    yield

    await bedjet.disconnect()


app = FastAPI(
    title="BedJet Controller Hub",
    description="Multi-user BedJet V3 controller via BLE bridge",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---

class SetTemperatureRequest(BaseModel):
    temperature_f: float = Field(..., ge=66, le=109, description="Temperature in Fahrenheit")


class SetFanRequest(BaseModel):
    percent: int = Field(..., ge=5, le=100, description="Fan speed percentage (5-100)")


class SetRuntimeRequest(BaseModel):
    hours: int = Field(..., ge=0, le=10)
    minutes: int = Field(..., ge=0, le=59)


class ConnectRequest(BaseModel):
    address: str | None = Field(None, description="BLE address (auto-scan if omitted)")


class SetModeRequest(BaseModel):
    mode: str = Field(..., description="Mode: off, heat, cool, turbo, dry, extended_heat, m1, m2, m3")


# --- REST Endpoints ---

@app.get("/status")
async def get_status():
    """Get current BedJet status."""
    return bedjet.status.to_dict()


@app.post("/connect")
async def connect(req: ConnectRequest = ConnectRequest()):
    """Connect to BedJet device."""
    try:
        await bedjet.connect(address=req.address)
        return {"status": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/disconnect")
async def disconnect():
    """Disconnect from BedJet device."""
    await bedjet.disconnect()
    return {"status": "disconnected"}


@app.get("/scan")
async def scan_devices():
    """Scan for BedJet BLE devices."""
    try:
        devices = await bedjet.scan()
        return {
            "devices": [
                {"name": d.name, "address": d.address}
                for d in devices
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mode")
async def set_mode(req: SetModeRequest):
    """Set BedJet operating mode."""
    mode_map = {
        "off": bedjet.turn_off,
        "heat": bedjet.set_mode_heat,
        "cool": bedjet.set_mode_cool,
        "turbo": bedjet.set_mode_turbo,
        "dry": bedjet.set_mode_dry,
        "extended_heat": bedjet.set_mode_extended_heat,
    }

    # Handle presets
    if req.mode in ("m1", "m2", "m3"):
        preset_num = int(req.mode[1])
        try:
            await bedjet.set_preset(preset_num)
            return {"status": "ok", "mode": req.mode}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    handler = mode_map.get(req.mode)
    if not handler:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {req.mode}. Valid: {', '.join(list(mode_map.keys()) + ['m1', 'm2', 'm3'])}"
        )

    try:
        await handler()
        return {"status": "ok", "mode": req.mode}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/temperature")
async def set_temperature(req: SetTemperatureRequest):
    """Set target temperature."""
    try:
        await bedjet.set_temperature(req.temperature_f)
        return {"status": "ok", "temperature_f": req.temperature_f}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/fan")
async def set_fan(req: SetFanRequest):
    """Set fan speed."""
    try:
        await bedjet.set_fan_speed(req.percent)
        return {"status": "ok", "fan_percent": req.percent}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/runtime")
async def set_runtime(req: SetRuntimeRequest):
    """Set remaining runtime."""
    try:
        await bedjet.set_runtime(req.hours, req.minutes)
        return {"status": "ok", "hours": req.hours, "minutes": req.minutes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket for real-time status updates."""
    await ws.accept()
    connected_websockets.add(ws)
    logger.info(f"WebSocket client connected ({len(connected_websockets)} total)")

    # Send current status immediately
    try:
        await ws.send_text(json.dumps({
            "type": "status",
            "data": bedjet.status.to_dict(),
        }))
    except Exception:
        pass

    try:
        while True:
            # Listen for commands from the WebSocket client
            text = await ws.receive_text()
            try:
                msg = json.loads(text)
                await _handle_ws_command(msg)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
            except Exception as e:
                await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
    except WebSocketDisconnect:
        pass
    finally:
        connected_websockets.discard(ws)
        logger.info(f"WebSocket client disconnected ({len(connected_websockets)} total)")


async def _handle_ws_command(msg: dict):
    """Handle a command received via WebSocket."""
    cmd = msg.get("command")
    if cmd == "set_mode":
        mode = msg.get("mode", "off")
        req = SetModeRequest(mode=mode)
        await set_mode(req)
    elif cmd == "set_temperature":
        temp = msg.get("temperature_f", 72)
        await bedjet.set_temperature(temp)
    elif cmd == "set_fan":
        percent = msg.get("percent", 50)
        await bedjet.set_fan_speed(percent)
    elif cmd == "set_runtime":
        hours = msg.get("hours", 0)
        minutes = msg.get("minutes", 0)
        await bedjet.set_runtime(hours, minutes)


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8265"))
    uvicorn.run(app, host=host, port=port)
