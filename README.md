# Basin — Developer Guide

Basin is an AES-67 multitrack recording appliance. It exposes a browser-based web interface for recording, monitoring, playback, and file management of AES-67 audio-over-IP streams. Target: **128 simultaneous channels** at 48/96 kHz, 24-bit.

---

## Architecture

```
Browser (Vue 3 SPA)
    ↕ HTTP / WebSocket
Nginx (reverse proxy)
    ↕
FastAPI (uvicorn)  ──→  PostgreSQL
    ↕                   Redis
Celery workers     ──→  (background: export, relocation)
    ↕
GStreamer pipelines ←── AES-67 multicast RTP (UDP)
    ↕
bondagit/aes67-linux-daemon  (stream discovery, PTP coordination)
    ↕
linuxptp / ptp4l  (PTP grandmaster clock sync)
```

Audio capture uses **GStreamer** directly — streams are received as multicast RTP, depayloaded, and written per-channel to WAV/AIFF/RF64 without an ALSA intermediary. The bondagit daemon handles SAP/mDNS discovery and PTP synchronization; Basin reads stream parameters from its REST API.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, uvicorn |
| ORM | SQLAlchemy 2 (async) + Alembic |
| Database | PostgreSQL 15+ |
| Task queue | Celery + Redis |
| Audio engine | GStreamer 1.24+ via GstPython (`gi.repository.Gst`) |
| AES-67 discovery | bondagit/aes67-linux-daemon |
| PTP sync | linuxptp (ptp4l) |
| Console protocol | OSC via python-osc (X32 / Wing) |
| WebRTC monitor | aiortc |
| Export transcode | FFmpeg |
| Frontend | Vue 3, Vite, TypeScript, PrimeVue, TailwindCSS, Pinia |
| Reverse proxy | Nginx |
| Process supervision | systemd |

---

## Repository Structure

```
basin/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory + lifespan
│   │   ├── config.py            # Settings (pydantic-settings, env vars)
│   │   ├── database.py          # PostgreSQL engine + session factory
│   │   ├── security.py          # JWT, password hashing, role enforcement
│   │   ├── deps.py              # FastAPI dependency functions
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # FastAPI routers (one per API section)
│   │   ├── services/
│   │   │   ├── audio/
│   │   │   │   ├── gstreamer.py         # Pipeline description builder
│   │   │   │   ├── recording_engine.py  # GStreamer session manager
│   │   │   │   ├── playback_engine.py   # Playback pipeline
│   │   │   │   ├── meter_parser.py      # Level bus message parser
│   │   │   │   ├── aes67_daemon.py      # bondagit daemon REST client
│   │   │   │   └── filename.py          # Filename pattern renderer
│   │   │   ├── console/         # X32Console, WingConsole
│   │   │   ├── storage/         # SMB, NFS, local destination managers
│   │   │   └── network.py       # Netplan interface queries/writes
│   │   └── tasks/
│   │       ├── celery_app.py    # Celery + Redis config
│   │       ├── export.py        # FFmpeg transcode task
│   │       └── relocate.py      # File relocation task
│   ├── alembic/                 # DB migrations
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       ├── 002_filename_pattern.py
│   │       └── 003_gstreamer_source.py  # Drops alsa_device, adds rtp_port
│   ├── tests/
│   │   ├── conftest.py          # pytest fixtures, test DB (basin_test)
│   │   ├── test_auth.py
│   │   ├── test_recordings.py
│   │   ├── test_sources.py
│   │   └── test_recording_engine.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.ts
│   │   ├── router/
│   │   ├── stores/              # Pinia stores
│   │   ├── api/                 # Typed Axios client
│   │   ├── views/               # One .vue file per route
│   │   └── components/          # Shared components
│   ├── vite.config.ts
│   └── package.json
├── deploy/
│   ├── setup.sh                 # First-time appliance provisioning (run as root)
│   ├── deploy.sh                # Code update + restart (run after git push)
│   ├── systemd/                 # Service unit files
│   └── nginx/basin.conf         # Nginx site config
├── scripts/
│   └── netplan-helper.sh        # Privileged helper for in-app network config
├── IMPLEMENTATION_PLAN.md       # Architecture decisions, API surface, phased build plan
└── AES-Capture-Specification.md # Original product spec (reference only)
```

---

## Local Development (Windows)

Code is written on Windows. **The appliance is the test environment** — there is no local backend runtime. See [Appliance Setup](#appliance-setup) to provision one.

### Frontend-only iteration

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs at `http://localhost:5173`. Set the appliance IP in `vite.config.ts` so API calls proxy to the real backend:

```ts
// frontend/vite.config.ts
proxy: {
  '/api': { target: 'http://<appliance-ip>', changeOrigin: true },
  '/ws':  { target: 'ws://<appliance-ip>', ws: true, changeOrigin: true },
}
```

Frontend changes are hot-reloaded instantly; the backend on the appliance handles all API calls.

### Full-stack changes

```bash
git add <files>
git commit -m "..."
git push origin main
# Then SSH to the appliance:
ssh basin@<appliance-ip>
cd /opt/basin && sudo ./repo/deploy/deploy.sh
```

### Type checking

```bash
cd frontend
npx vue-tsc --noEmit
```

---

## Appliance Setup

### Hardware requirements

- x86_64 machine (mini-PC or server)
- Ubuntu Server 22.04 or 24.04 LTS (no desktop environment needed)
- Network interface on the AES-67 VLAN/subnet (multicast routing required)
- Sufficient storage for recordings (local NVMe recommended; NFS/SMB supported)

### First-time provisioning

Run as root on a fresh Ubuntu install:

```bash
# Set your git repo URL
export REPO_URL=https://github.com/YOUR_ORG/basin.git
export DB_PASSWORD=your-strong-password   # optional; auto-generated if omitted

curl -sSL https://raw.githubusercontent.com/YOUR_ORG/basin/main/deploy/setup.sh | bash
```

Or clone first and run locally:

```bash
git clone https://github.com/YOUR_ORG/basin.git /opt/basin/repo
sudo bash /opt/basin/repo/deploy/setup.sh
```

`setup.sh` performs in order:

1. Installs system packages: Python 3.12, PostgreSQL, Redis, Nginx, Node.js, GStreamer, FFmpeg, linuxptp, avahi
2. Creates the `basin` system user
3. Sets up PostgreSQL (`basin` user + database)
4. Clones the repo to `/opt/basin/repo`
5. Builds and installs the bondagit/aes67-linux-daemon
6. Sets RT scheduling sysctl (`kernel.sched_rt_runtime_us = -1`)
7. Creates the Python venv and installs backend dependencies
8. Builds the Vue frontend
9. Writes `/opt/basin/repo/backend/.env` with generated keys
10. Runs Alembic migrations
11. Installs and starts systemd services
12. Configures Nginx
13. Installs the netplan helper with scoped `sudoers` entry

At the end it prints the appliance IP and generated database password.

### After provisioning

Navigate to `http://<appliance-ip>` in a browser. The setup wizard will appear on first access; set a hostname, admin password, and initial storage path. After that, log in with the admin account.

---

## Day-to-day Deployment

After pushing code changes to `main`:

```bash
ssh root@<appliance-ip>
cd /opt/basin && ./repo/deploy/deploy.sh
```

`deploy.sh` does:
- `git pull origin main`
- `pip install -r requirements.txt`
- `alembic upgrade head`
- `npm ci && npm run build`
- `systemctl restart basin-api basin-worker basin-beat`

The AES-67 daemon (`basin-aes67`) is **not** restarted on routine deploys — it manages live streams and PTP state independently.

---

## Environment Variables

File: `/opt/basin/repo/backend/.env` (generated by `setup.sh`, owner `basin`, mode `600`)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://basin:basin@localhost/basin` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for Celery + token revocation |
| `SECRET_KEY` | *(generated)* | JWT signing key — 32-byte hex |
| `ENCRYPTION_KEY` | *(generated)* | AES key for SMB credential storage — 32-byte hex |
| `STORAGE_ROOT` | `/mnt/basin-storage` | Default recording storage root |
| `MOCK_AUDIO` | `0` | Set to `1` to run without GStreamer/hardware (dev/test mode) |
| `AES67_DAEMON_URL` | `http://localhost:8080` | bondagit daemon REST API base URL |

Generate new keys:

```bash
openssl rand -hex 32   # SECRET_KEY
openssl rand -hex 32   # ENCRYPTION_KEY
```

---

## Systemd Services

| Service | Command | Notes |
|---|---|---|
| `basin-api` | `uvicorn app.main:app --host 127.0.0.1 --port 8000` | FastAPI backend |
| `basin-worker` | `celery -A app.tasks.celery_app worker` | Background jobs (export, relocation) |
| `basin-beat` | `celery -A app.tasks.celery_app beat` | Scheduled task trigger |
| `basin-aes67` | `aes67-daemon -c /opt/basin/data/aes67-daemon.conf` | AES-67 stream discovery + PTP |
| `basin-kiosk` | `chromium-browser --kiosk http://localhost/status` | Local HDMI kiosk display |

```bash
# View live logs
journalctl -u basin-api -f
journalctl -u basin-worker -f
journalctl -u basin-aes67 -f

# Restart a service
systemctl restart basin-api

# Check all Basin service health
systemctl status basin-api basin-worker basin-beat basin-aes67
```

---

## Running Tests

Tests run against a real PostgreSQL database (`basin_test`) — no mocks. The `MOCK_AUDIO=1` setting bypasses GStreamer for audio tests, so the test suite does not require an AES-67 network or hardware.

### Setup (once per machine)

```bash
# Create test database
sudo -u postgres psql -c "CREATE DATABASE basin_test OWNER basin;"
```

### Run

```bash
cd backend
source /opt/basin/venv/bin/activate
MOCK_AUDIO=1 pytest tests/ -v
```

Coverage report:

```bash
MOCK_AUDIO=1 pytest tests/ --cov=app --cov-report=term-missing
```

The test DB URL is hardcoded in `tests/conftest.py` as `postgresql+asyncpg://basin:basin@localhost/basin_test`. Schema is created fresh each test session via `Base.metadata.create_all`.

---

## AES-67 / GStreamer Details

### How capture works

Basin does **not** use ALSA for capture. Each AES-67 source is a GStreamer pipeline that subscribes to a multicast UDP group directly:

```
udpsrc multicast-group=<ip> port=<port> multicast-iface=<nic>
  → rtpjitterbuffer latency=20ms
  → rtpL24depay  (or rtpL16depay)
  → audioconvert
  → tee
      branch A → deinterleave → per-channel wavenc → filesink
      branch B → level (4 Hz) → fakesink  (metering via bus messages)
```

The pipeline is built as a string in `services/audio/gstreamer.py` and launched via `Gst.parse_launch()`. The Python bus watch receives `GstMessage` objects for level data and errors — no stdout parsing.

### bondagit daemon

The daemon (`basin-aes67.service`) provides:
- **SAP/mDNS discovery** — detects AES-67 streams on the network
- **PTP coordination** — manages PTP slave clocks via linuxptp
- **REST API** at `http://localhost:8080` — Basin queries `/api/sources` to get `multicast_address`, `rtp_port`, channel count, and sample rate when you add a source in the UI

Config file: `/opt/basin/data/aes67-daemon.conf`

### PTP configuration

Multi-source recordings require all sources to share a PTP grandmaster clock. Check PTP sync status:

```bash
ptp4l -i eth0 -s   # run as slave on the AES-67 NIC
pmc -u -b 0 'GET CURRENT_DATA_SET'   # check offset from master
```

If the appliance is not PTP-locked, `get_source_status()` will return `ptp_locked: false` and the UI will show a warning on the Sources page.

### Adding GStreamer plugins

GStreamer plugins are installed from apt as part of `setup.sh`:

```bash
gstreamer1.0-plugins-base   # audioconvert, deinterleave, level, wavenc
gstreamer1.0-plugins-good   # udpsrc, rtpjitterbuffer, rtpL24depay
gstreamer1.0-plugins-bad    # rtpL16depay, aiffenc
python3-gst-1.0             # GstPython bindings (gi.repository.Gst)
```

Verify GStreamer is working:

```bash
python3 -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; Gst.init(None); print(Gst.version_string())"
```

Test a multicast receive pipeline manually:

```bash
gst-launch-1.0 udpsrc multicast-group=239.69.0.1 port=5004 multicast-iface=eth0 \
  caps="application/x-rtp,media=audio,encoding-name=L24,channels=32,clock-rate=48000" \
  ! rtpjitterbuffer latency=20 ! rtpL24depay \
  ! audio/x-raw,format=S24BE,channels=32,rate=48000 \
  ! audioconvert ! fakesink
```

### MOCK_AUDIO mode

When `MOCK_AUDIO=1`, the backend skips all GStreamer and daemon calls:
- Source status always returns `stream_active: true, ptp_locked: true`
- Recording sessions run a synthetic meter task (sine wave + gaussian noise per channel)
- Playback sessions run a no-op timer

Use this mode for all backend development and testing on Windows or on a machine without AES-67 hardware.

---

## Database Migrations

```bash
cd /opt/basin/repo/backend
source /opt/basin/venv/bin/activate

# Apply all pending migrations
alembic upgrade head

# Check current revision
alembic current

# Generate a new migration after changing a model
alembic revision --autogenerate -m "describe the change"

# Roll back one step
alembic downgrade -1
```

Migrations live in `backend/alembic/versions/`. Never edit an already-deployed migration; create a new one.

---

## API Reference

FastAPI generates interactive docs automatically:

- **Swagger UI**: `http://<appliance-ip>/api/docs`
- **ReDoc**: `http://<appliance-ip>/api/redoc`

All endpoints require a JWT bearer token (obtained from `POST /api/auth/login`) except `/api/setup/*`, `/api/status`, and the docs pages.

---

## Roles

| Role | Can do |
|---|---|
| `admin` | Everything: system settings, users, all groups, storage, consoles |
| `editor` | Groups, templates, recordings in assigned groups; no system settings |
| `operator` | Create and start/stop recordings in assigned groups; no template or settings access |

---

## Troubleshooting

**`basin-api` fails to start — `asyncpg` connection refused**
PostgreSQL is not running or credentials are wrong. Check:
```bash
systemctl status postgresql
psql -U basin -d basin -c '\conninfo'
```

**GStreamer pipeline fails to play — no data from source**
- Verify multicast routing on the AES-67 NIC: `ip maddr show dev eth0`
- Check the source is visible to the daemon: `curl http://localhost:8080/api/sources`
- Run the manual `gst-launch-1.0` test above to isolate the issue

**PTP not locking**
- Confirm `ptp4l` is running and the AES-67 grandmaster is visible on the network
- Check NIC timestamping support: `ethtool -T eth0` (look for `hardware-transmit` and `hardware-receive`)
- Some consumer NICs lack hardware PTP support; use software timestamping as fallback (`ptp4l -i eth0 -s -S`)

**Celery workers not processing jobs**
```bash
systemctl status basin-worker
journalctl -u basin-worker -n 50
redis-cli ping   # should return PONG
```

**Frontend proxy errors in dev (CORS / 404 on `/api`)**
Confirm `vite.config.ts` proxy target matches the appliance IP and the appliance is reachable from your dev machine.

**`MOCK_AUDIO` is set but recording still tries to open a pipeline**
The `mock_audio` setting is read at import time via `@lru_cache`. In tests, patch via `monkeypatch.setattr(settings, "mock_audio", True)` rather than setting the env var after import.
