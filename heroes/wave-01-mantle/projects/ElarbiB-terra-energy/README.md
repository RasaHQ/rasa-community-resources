---
Author: Elarbi B
Wave: wave-01-mantle
Assessed on: 2026-10-13
Assessed by: Elarbi B
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
Audience: Developers building a voice + text Rasa Mantle assistant with a FastAPI backend for renewable-energy site assessment
Time: 15 min
---

# Terra — TerraEnergy

Presentation website + **Rasa Pro Mantle** conversational assistant for
assessing the solar and wind energy potential of any location worldwide
(satellite/reanalysis data: NASA POWER / PVGIS / NSRDB / ERA5 / Open-Meteo).

The Rasa agent is the project root: `agent.yml`, `integrations.yml`, `skills/`
and `references/` live here. The FastAPI backend and the Vite/React frontend
are the application layers around it.

## Demo video

▶️ [Watch the demo](https://drive.google.com/file/d/14UWx5vIus9EWtZmtdPmzimNVM0X_h4mU/view?usp=drive_link)

## Engine — Mantle

This resource is built on the **Mantle** engine shipped in
`rasa-pro==3.20.0.dev6`:

- tools use `from rasa.mantle.tools.decorator import tool, ToolContext` and
  `from rasa.mantle.tools.result import ToolResult`
  (the pre-Mantle `rasa.calm_v2.*` namespace does not exist here);
- the orchestrator LLM is a **model-group reference**
  (`llm: {model_group: orchestrator}`) — provider, model and key live on the
  `model_groups` entry, never inline under `llm:`;
- `name`, `description`, `rules`, `prompts` and `references` are **top-level
  keys** in `agent.yml`, siblings of `agent:`.

## Architecture

```
┌────────────┐   /api/*        ┌────────────┐   /webhooks/rest   ┌────────────────────────┐
│  Frontend   │ ──────────────▶ │  Backend    │ ─────────────────▶ │  Rasa Mantle agent     │
│  (Vite/React)│                │  (FastAPI)  │                    │  (rasa run, port 5005) │
└────────────┘                 └────────────┘                    └────────────────────────┘
      │  ws://localhost:8765
      ▼
┌─────────────────────┐
│  Whisper bridge     │  (Safari/WebAudio — voice_bridge.py, optional)
└─────────────────────┘
```

| Path            | Tech                    | Port  | Role                                             |
|-----------------|-------------------------|-------|--------------------------------------------------|
| `.` (root)      | Rasa Pro (Mantle)       | 5005  | Multilingual agent (EN/FR/DE/ES) served over REST |
| `backend/`      | FastAPI (Python)        | 8000  | Weather/analysis API + `/api/llm/chat` proxy→Rasa |
| `frontend/`     | Vite + React            | 5173  | Terra landing page + voice assistant (orb)        |
| `voice_bridge.py` | faster-whisper        | 8765  | Local STT (WebSocket) for the voice assistant     |

> The Rasa agent calls the backend (`http://localhost:8000/api/analysis/...`)
> through its `site_assessment` / `site_comparison` skills to fetch real data.

## Prerequisites

- **uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Python ≥ 3.11** (uv provisions it if needed)
- **Node ≥ 18** — only for the frontend
- **Rasa Pro license** (`RASA_LICENSE`) — required to run `rasa train` / `rasa run`
- **Mistral API key** (`MISTRAL_API_KEY`) — orchestrator LLM + embeddings

## Installation — one locked path

Everything Python is installed from the project root with **uv** (`uv.lock` is
committed). There is no separate `pip install -r requirements.txt` step.

```bash
# 1. agent + backend (single resolve through uv.lock)
make install              # = uv sync --prerelease=allow

# 2. credentials
make env                  # = cp .env.example .env   (then fill RASA_LICENSE + MISTRAL_API_KEY)
make verify               # pre-flight: keys, rasa.mantle import, project validation

# 3. build the agent model
make train                # = uv run rasa train
```

Optional layers:

```bash
make install-voice        # = uv sync --extra voice  (local Whisper bridge + TTS)
make frontend-install     # = npm --prefix frontend install
```

Equivalently, without `make`:

```bash
uv sync --prerelease=allow
cp .env.example .env
uv run rasa train
```

## Running (development)

Open **3 terminals** from the project root:

**Terminal 1 — Rasa agent** (port 5005):

```bash
make run                        # = uv run rasa run --enable-api --port 5005
```

**Terminal 2 — Backend** (port 8000):

```bash
make backend                    # = uv run uvicorn main:app --app-dir backend --port 8000
```

**Terminal 3 — Frontend** (port 5173):

```bash
make frontend                   # = npm --prefix frontend run dev   → http://localhost:5173
```

## Voice assistant (macOS Safari, optional)

`webkitSpeechRecognition` does not work on macOS Safari, so the frontend falls
back to the local **Whisper bridge** (`ws://localhost:8765`). Install the voice
extra first (`make install-voice`), then start it from the project root (the
Whisper model is downloaded on first run, ~2 min):

```bash
uv run python voice_bridge.py
# Check: lsof -i :8765
```

> On Chrome/Edge (native SpeechRecognition), this bridge is not required.

## Validation and tests

```bash
make validate                   # rasa.mantle.validation.validate_project on the agent
make inspect                    # talk to the agent (Rasa Inspector)
make test                       # backend pytest + frontend vitest
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
.
├── agent.yml           # Mantle agent: id/language/persona + top-level name, rules, prompts, references
├── integrations.yml    # llm.model_group + model_groups (Mistral) + REST/Inspector channels
├── skills/             # site_assessment, site_comparison (skill.md + tools.py)
├── references/         # synthetic docs used for retrieval
├── voice_engines/      # optional custom Whisper ASR / Neuphonic TTS channel engines
├── voice_bridge.py     # local WebSocket Whisper bridge (frontend voice orb)
├── scripts/            # verify_setup.py
├── backend/            # FastAPI: analysis, LLM proxy, weather, geospatial
│   ├── routers/        # API routes
│   ├── services/       # engines (solar, wind, weather, Rasa…)
│   └── tests/
└── frontend/           # Vite + React (TypeScript)
    ├── src/components/ # landing/ + assistant/
    └── public/         # assets (video, images)
```

## Troubleshooting

- **Voice assistant doesn't listen on Safari** → the Whisper bridge (port 8765)
  must be running: `lsof -i :8765`, otherwise restart `voice_bridge.py`.
- **Rasa won't respond** → check `RASA_LICENSE` (non-empty in `.env`) and that
  port 5005 is listening.
- **The agent answers without calling tools** → make sure the backend (port 8000)
  is reachable; the `site_assessment`/`site_comparison` skills depend on it.
- **Frontend build** → `npm --prefix frontend run build` (tsc must report no errors).

## Provenance and verification

- **Author:** Elarbi B. The agent, backend, frontend and reference material were
  written by the author.
- **Verified with:** `rasa-pro==3.20.0.dev6`, Python 3.11+, uv — the pin in
  `pyproject.toml`, the resolved `uv.lock` and this line all agree
  (`make validate` in the catalog enforces it).
- **CI scope:** the project declares provider keys (`MISTRAL_API_KEY`,
  `NEUPHONIC_API_KEY`, `NSRDB_API_KEY`, `CDS_API_KEY`) in
  `[tool.rasa-catalog]`, so catalog CI verifies **install and
  `validate_project`**; `rasa train` needs a `RASA_LICENSE` and runs where one
  is available.
