---
Author: Elarbi B
Wave: wave-01-mantle
Assessed on: 2026-09-15
Assessed by: ElarbiB
Verified with: rasa-pro 3.19.0.dev6, Python 3.11+, uv
Audience: Developers building a voice-enabled Rasa assistant with a FastAPI backend for renewable-energy site assessment
Time: 10 min
---

# Terra — TerraEnergy

Presentation website + Rasa conversational assistant for assessing solar and wind
energy potential (satellite data: NASA POWER / PVGIS / NSRDB / ERA5).

## Demo video

▶️ [Watch the demo](https://drive.google.com/file/d/14UWx5vIus9EWtZmtdPmzimNVM0X_h4mU/view?usp=drive_link)

## Architecture

```
┌────────────┐   /api/*        ┌────────────┐   /webhook REST   ┌──────────────────────┐
│  Frontend   │ ──────────────▶ │  Backend    │ ───────────────▶ │  Agent Rasa (Mantle) │
│  (Vite/React)│                │  (FastAPI)  │                  │  (port 5005)         │
└────────────┘                 └────────────┘                  └──────────────────────┘
      │  ws://localhost:8765
      ▼
┌─────────────────────┐
│  Whisper bridge     │  (Safari/WebAudio — voice_bridge.py)
└─────────────────────┘
```

| Service         | Tech                | Port  | Role                                             |
|-----------------|---------------------|-------|--------------------------------------------------|
| `frontend/`     | Vite + React        | 5173  | Terra landing page + voice assistant (orb)       |
| `backend/`      | FastAPI (Python)    | 8000  | Weather/analysis API + `/api/llm/chat` proxy→Rasa |
| `rasa-agent/`   | Rasa Pro (CALM v2)  | 5005  | Multilingual agent (turns served over REST)      |
| `voice_bridge/` | faster-whisper      | 8765  | Local STT (WebSocket) for the voice assistant    |

> The Rasa agent itself calls the backend (`http://localhost:8000/api/analysis/...`)
> through its `site_assessment` / `site_comparison` skills to fetch real data.

## Prerequisites

- **Node ≥ 18** (frontend)
- **Python ≥ 3.11** (backend + Rasa agent)
- **Rasa Pro license** (`RASA_LICENSE`) — required to run `rasa run`
- **Mistral API key** (`MISTRAL_API_KEY`) — LLM + embeddings

## Installation

### 1. Rasa agent (`rasa-agent/`)

```bash
cd rasa-agent
python3 -m venv .venv
.venv/bin/pip install rasa-pro==3.19.0.dev6 httpx
# Dependencies for the local voice (Whisper) bridge — optional but recommended:
.venv/bin/pip install faster-whisper pyttsx3 websockets numpy
cp .env.example .env    # fill in RASA_LICENSE + MISTRAL_API_KEY
```

### 2. Backend (`backend/`)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env    # RASA_REST_URL=http://localhost:5005
```

### 3. Frontend (`frontend/`)

```bash
cd frontend
npm install
```

### 4. Environment variables

The backend loads the `.env` file **at the project root** (`backend/config.py`).
Copy the provided example if needed:

```bash
cp .env.example .env    # root: shared keys (MISTRAL, RASA_LICENSE, NASA…)
```

## Running (development)

Open **3 terminals**:

**Terminal 1 — Rasa agent** (port 5005):

```bash
cd rasa-agent
set -a && source .env && set +a
.venv/bin/rasa run --port 5005 --enable-api
```

**Terminal 2 — Backend** (port 8000):

```bash
cd backend
set -a && source .env && set +a
.venv/bin/uvicorn main:app --port 8000
```

**Terminal 3 — Frontend** (port 5173):

```bash
cd frontend
npm run dev
# → http://localhost:5173
```

## Voice assistant (macOS Safari)

`webkitSpeechRecognition` does not work on macOS Safari, so the frontend falls back
to the **local Whisper bridge** (`ws://localhost:8765`). Start it from `rasa-agent/`
(the model is downloaded on first run, ~2 min):

```bash
cd rasa-agent
set -a && source .env && set +a
nohup .venv/bin/python voice_bridge.py > /tmp/voice_bridge.log 2>&1 &
# Check: lsof -i :8765
```

> On Chrome/Edge (native SpeechRecognition), this bridge is not required.

## Production

The backend is not a static server: serve the frontend build separately.

```bash
cd frontend && npm run build        # → frontend/dist
cd ../backend && source ../.env
.venv/bin/uvicorn main:app --port 8000
# Serve frontend/dist with a static server (or: vite preview inside frontend/)
```

## Tests

```bash
# Backend (pytest)
cd backend && .venv/bin/python -m pytest

# Frontend (vitest)
cd frontend && npm test
```

## API (backend)

| Method | Route                       | Description                                |
|--------|-----------------------------|--------------------------------------------|
| `GET`  | `/health`                   | Service status                             |
| `POST` | `/api/llm/chat`             | Chat → proxy to the Rasa agent             |
| `POST` | `/api/analysis/site`        | Solar + wind analysis for a location       |
| `POST` | `/api/analysis/compare`     | Multi-site comparison                      |
| `POST` | `/api/geospatial/geocode`   | Address geocoding                          |
| `POST` | `/api/geospatial/parcel`    | Cadastral parcel lookup                    |
| `POST` | `/api/equipment/propose`    | System sizing (kWp, inverters…)            |
| `GET`  | `/api/weather/sources`      | Available weather providers                |
| `POST` | `/api/weather/fetch`        | Weather data fetching/fusion               |
| `POST` | `/api/nasa/...`             | Raw NASA POWER data                        |

## Structure

```
rasa/
├── backend/            # FastAPI: analysis, LLM proxy, weather, geospatial
│   ├── routers/        # API routes
│   ├── services/       # engines (solar, wind, weather, Rasa…)
│   └── tests/
├── frontend/           # Vite + React (TypeScript)
│   ├── src/components/ # landing/ + assistant/
│   └── public/         # assets (video, images)
└── rasa-agent/         # Rasa Pro agent
    ├── agent.yml       # persona + rules + prompt
    ├── integrations.yml# Mistral LLM + voice channels
    ├── skills/         # site_assessment, site_comparison
    ├── references/     # docs used for retrieval
    ├── voice_engines/  # Whisper ASR / Neuphonic TTS
    └── voice_bridge.py # WebSocket Whisper bridge (local ASR)
```

## Troubleshooting

- **Voice assistant doesn't listen on Safari** → the Whisper bridge (port 8765)
  must be running: `lsof -i :8765`, otherwise restart `voice_bridge.py`.
- **Rasa won't respond** → check `RASA_LICENSE` (non-empty in `.env`) and that
  port 5005 is listening.
- **The agent answers without calling tools** → make sure the backend (port 8000)
  is reachable; the `site_assessment`/`site_comparison` skills depend on it.
- **Frontend build** → `npm run build` (tsc must report no errors).