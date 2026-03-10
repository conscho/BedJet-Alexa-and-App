# BedJet Controller

A multi-user BedJet V3 controller with native iOS app and Alexa integration.

## Architecture

The BedJet V3 hardware only allows **one BLE connection at a time**. This project solves the multi-user problem with a hub-based architecture:

```
┌─────────────┐     BLE      ┌──────────────┐    WiFi     ┌──────────────┐
│  BedJet V3  │◄────────────►│  Hub Server  │◄───────────►│  iOS App #1  │
│  (Hardware) │              │ (Raspberry Pi)│◄───────────►│  iOS App #2  │
└─────────────┘              │              │◄───────────►│  Alexa Skill │
                             └──────────────┘             └──────────────┘
```

- **Hub Server** (`hub/`): Python server that maintains the BLE connection and exposes REST API + WebSocket
- **iOS App** (`ios/`): Native SwiftUI app for iPhone
- **Alexa Skill** (`alexa/`): AWS Lambda function for voice control

## Components

### Hub Server (Raspberry Pi)

Python server using `bleak` for BLE and `FastAPI` for the web API.

```bash
cd hub
pip install -r requirements.txt
python server.py
```

### iOS App

Native SwiftUI app. Open `ios/BedJetController/BedJetController.xcodeproj` in Xcode.

### Alexa Skill

AWS Lambda function. See `alexa/README.md` for deployment instructions.

## BedJet BLE Protocol

| UUID | Purpose |
|------|---------|
| `00001000-bed0-0080-aa55-4265644a6574` | Service |
| `00002000-bed0-0080-aa55-4265644a6574` | Status (notify/read) |
| `00002001-bed0-0080-aa55-4265644a6574` | Device Name (read) |
| `00002004-bed0-0080-aa55-4265644a6574` | Command (write) |

### Modes

| Mode | Value | Description |
|------|-------|-------------|
| Standby | 0 | Off |
| Heat | 1 | Heat (max 4 hrs) |
| Turbo | 2 | High heat, limited duration |
| Extended Heat | 3 | Heat (max 10 hrs) |
| Cool | 4 | Fan only |
| Dry | 5 | High speed, no heat |

### Temperature

- Stored as steps: 1 step = 0.5°C
- Valid range: 66°F - 109°F (19°C - 43°C)

### Fan Speed

- 20 steps (0-19), each step = 5% (5% to 100%)
