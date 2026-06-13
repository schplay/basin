# Basin — Implementation Plan

Version 1.0  •  June 2026

---

## 1. Architecture Decisions & Spec Revisions

The following decisions deviate from or extend the AES-Capture-Specification.md:

| Topic | Spec Says | Plan Decision | Reason |
|---|---|---|---|
| Project name | AES-Capture | **Basin** | Correct name per David |
| Database | SQLite | **PostgreSQL** | Multiple concurrent recordings require true concurrency; overbuild for scale |
| Audio engine | FFmpeg (subprocess) | **GStreamer (GstPython)** | Direct RTP multicast reception without ALSA intermediary; native `rtpjitterbuffer` for AES-67 timing; `level` element for metering; Python object-level pipeline control; proven at 128ch by voc/aes67-recorder |
| AES-67 capture path | ALSA → FFmpeg | **Multicast RTP → GStreamer pipeline** | bondagit daemon retained for SAP/SDP discovery and PTP coordination; `ravenna-alsa-lkm` kernel module not required for capture |
| Source identifier | `alsa_device` string | **`multicast_address` + `rtp_port`** | ALSA device string obsolete; GStreamer pipelines address streams by multicast IP and UDP port from daemon SDP |
| Source per recording | Single `aes67_source_id` | **Per-channel routing table** | Each channel maps independently to a source + source channel index |
| Concurrent recordings | One at a time | **Multiple concurrent**, with load display | Allowed if hardware has capacity; UI shows load vs. capacity |
| First boot | Not specified | **Browser setup wizard** (no CLI for end users) | End users never touch CLI |
| Local display | Not in spec | **Chromium kiosk** pointing at `/status` route | Shows IP, status, health on physical monitor |
| Network config | Informational | **Full in-app IP/gateway config** via netplan | Admin configures networking from browser |
| Storage extension | SMB + NFS | **SMB + NFS with plugin extension points** | v1 ships SMB/NFS; future types drop in |
| Recording lock | Proposed | **Not implemented** | Roles provide sufficient protection |
| Export location | Open | **`exports/` subdirectory within recording folder** | Human-navigable without the app |
| Testing | Not specified | **pytest: unit + integration; no frontend tests** | Right level for appliance project |

---

## 2. Revised Data Model

### 2.1 Key Change: Channel Routing

Recordings no longer have a single `aes67_source_id`. Instead, a `recording_channels` join table maps each recorded channel to a specific source and source-channel index. This supports multi-source recordings (e.g., Source A channels 1–32 + Source B channels 1–32 = a 64-channel recording) while keeping sources independently manageable.

```
recording_channels
─────────────────────────────────────────────────
id                  SERIAL PK
recording_id        INTEGER FK → recordings
channel_number      INTEGER        1-based output position; determines filename (ch01_, ch02_, ...)
source_id           INTEGER FK → aes67_sources
source_channel      INTEGER        1-based channel index within the source
channel_name        TEXT           Display name (may differ from source's channel name)
```

### 2.2 Full Schema

**users**
```
id, username (UNIQUE), password_hash, role (admin|editor|operator), is_active, created_at
```

**user_group_access**
```
user_id FK, group_id FK
```

**recording_groups**
```
id, name, parent_id FK (self-ref), filesystem_path, default_template_id FK, created_at
```

**recording_templates**
```
id, name, channel_count, channel_names (JSON array), sample_rate, bit_depth, codec, container,
channel_source_defaults (JSON: [{source_id, source_channel}] per channel position),
metadata_defaults (JSON), created_at
```

**aes67_sources**
```
id, name, network_interface, multicast_address, rtp_port, channel_count, sample_rate, bit_depth,
is_active, created_at
```
Note: `alsa_device` removed. GStreamer pipelines address streams via `multicast_address` + `rtp_port`, obtained from the bondagit daemon SDP at source creation time.

**recordings**
```
id, name, group_id FK, template_id FK (snapshot at creation),
status (pending|recording|completed|error|playback),
filesystem_path, channel_count (derived count),
sample_rate, bit_depth, codec, container,
started_at, ended_at, duration_seconds,
metadata (JSON — full metadata snapshot),
created_by FK, created_at
```
Note: `channel_count` is maintained as a denormalized column equal to the count of rows in `recording_channels` for this recording. Updated on channel configuration save.

**recording_channels** — see §2.1

**console_integrations**
```
id, name, console_type (behringer_x32|behringer_wing), ip_address, port,
network_interface, is_active, last_connected_at, created_at
```

**storage_destinations**
```
id, destination_type (local_os|local_volume|network_smb|network_nfs),
is_active, local_path, network_type, network_host, network_share,
network_interface, smb_username, smb_password_enc, smb_domain, smb_version,
nfs_version, nfs_options, mount_point,
last_speed_test_at, last_speed_test_write_mbps, last_speed_test_read_mbps,
created_at
```

**storage_relocations**
```
id, from_destination_id FK, to_destination_id FK,
scheduled_at, status (pending|in_progress|completed|failed),
files_total, files_moved, bytes_total, bytes_moved, created_at
```

**export_jobs**
```
id, recording_id FK, codec, container, channel_selection (JSON),
interleaved (BOOLEAN), output_path, status (queued|running|completed|failed|cancelled),
progress_pct, created_by FK, created_at, completed_at
```

**audit_log**
```
id, user_id FK, action (TEXT), resource_type, resource_id, detail (JSON), created_at
```

---

## 3. Project Directory Layout

### 3.1 Repository Structure

```
basin/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory, lifespan, router registration
│   │   ├── config.py                # Settings (pydantic-settings, env vars)
│   │   ├── database.py              # PostgreSQL engine, session factory
│   │   ├── models/                  # SQLAlchemy ORM models (one file per entity)
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── routers/                 # FastAPI routers (one per API section)
│   │   ├── services/
│   │   │   ├── audio/               # GStreamer pipeline builder, recorder, player, meter
│   │   │   ├── console/             # BaseConsole, X32Console, WingConsole
│   │   │   ├── storage/             # Destination manager, SMB, NFS
│   │   │   └── network.py           # Netplan read/write, interface queries
│   │   ├── tasks/
│   │   │   ├── celery_app.py        # Celery + Redis config
│   │   │   ├── relocate.py          # File relocation task
│   │   │   └── export.py            # Transcode/export task
│   │   ├── websockets/              # WS managers for levels, status, progress
│   │   └── security.py             # JWT, password hashing, role enforcement
│   ├── alembic/                     # DB migration scripts
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_recordings.py
│   │   ├── test_audio.py
│   │   └── conftest.py              # pytest fixtures, test DB, mock FFmpeg
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── main.ts
│   │   ├── router/
│   │   ├── stores/                  # Pinia stores
│   │   ├── api/                     # Typed API client (generated from OpenAPI or hand-written)
│   │   ├── views/                   # One .vue file per route
│   │   └── components/              # Shared reusable components
│   ├── vite.config.ts
│   └── package.json
├── deploy/
│   ├── setup.sh                     # First-time Ubuntu appliance provisioning
│   ├── deploy.sh                    # Git pull → migrate → restart services
│   ├── systemd/
│   │   ├── basin-api.service
│   │   ├── basin-worker.service     # Celery worker
│   │   ├── basin-beat.service       # Celery beat scheduler
│   │   └── basin-kiosk.service      # Chromium kiosk autostart
│   └── nginx/
│       └── basin.conf
├── scripts/
│   └── netplan-helper.sh            # Privileged helper called by backend via sudo for netplan writes
└── AES-Capture-Specification.md    # Original spec (for reference)
```

### 3.2 Ubuntu Appliance Layout

```
/opt/basin/                          # Application root
/opt/basin/backend/                  # FastAPI app (git clone lands here)
/opt/basin/frontend/dist/            # Built Vue SPA (served by Nginx)
/opt/basin/data/                     # Persistent non-recording data
/opt/basin/data/basin.db             # (Not used; PostgreSQL runs as system service)
/opt/basin/data/exports_temp/        # Temp dir for in-progress exports
<storage_root>/                      # Configurable; local, volume, or mount point
<storage_root>/<group>/
<storage_root>/<group>/<recording>/
<storage_root>/<group>/<recording>/ch01_<name>.wav
<storage_root>/<group>/<recording>/ch02_<name>.wav
<storage_root>/<group>/<recording>/exports/
<storage_root>/<group>/<recording>/metadata.json
/mnt/basin-storage/                  # Mount point for network destinations
/var/log/basin/                      # Application logs
```

---

## 4. System Services

| Service | Binary / Command | Managed By |
|---|---|---|
| `basin-api` | `uvicorn app.main:app` | systemd |
| `basin-worker` | `celery -A app.tasks.celery_app worker` | systemd |
| `basin-beat` | `celery -A app.tasks.celery_app beat` | systemd |
| `redis` | `redis-server` | systemd (system package) |
| `postgresql` | `postgres` | systemd (system package) |
| `nginx` | `nginx` | systemd (system package) |
| `basin-kiosk` | `chromium-browser --kiosk http://localhost/status` | systemd user service |

---

## 5. API Surface (Complete)

### Auth
```
POST   /api/auth/login
POST   /api/auth/refresh
POST   /api/auth/logout
GET    /api/auth/me
```

### Setup Wizard (unauthenticated, only active before first admin is created)
```
GET    /api/setup/status             # Is setup complete? {complete: bool}
POST   /api/setup/init               # Set admin password, hostname, initial storage path
```

### Status (unauthenticated, for kiosk display)
```
GET    /api/status                   # Hostname, IPs, service health, active recording count
```

### Users (admin only)
```
GET    /api/users
POST   /api/users
GET    /api/users/{id}
PUT    /api/users/{id}
DELETE /api/users/{id}
PUT    /api/users/{id}/groups
```

### System Settings (admin only)
```
GET    /api/settings
PUT    /api/settings/auth            # Toggle password auth
PUT    /api/settings/hostname
GET    /api/settings/services        # Health of all systemd services
```

### Network (admin only)
```
GET    /api/network/interfaces       # List interfaces with status, IP, MAC
PUT    /api/network/interfaces/{name} # Write IP/gateway/netmask via netplan helper
POST   /api/network/interfaces/{name}/apply  # Apply netplan config
```

### Recording Groups
```
GET    /api/groups                   # Full nested tree
POST   /api/groups
PUT    /api/groups/{id}
DELETE /api/groups/{id}
PUT    /api/groups/{id}/access       # Assign user access
```

### Templates
```
GET    /api/templates
POST   /api/templates
GET    /api/templates/{id}
PUT    /api/templates/{id}
DELETE /api/templates/{id}
```

### AES-67 Sources
```
GET    /api/sources
POST   /api/sources
GET    /api/sources/{id}
PUT    /api/sources/{id}
DELETE /api/sources/{id}
GET    /api/sources/{id}/status      # Live: ALSA device reachable, channel count
```

### Recordings
```
GET    /api/recordings               # Filter: group_id, status, date range, search
POST   /api/recordings               # Create with channel routing
GET    /api/recordings/{id}
PUT    /api/recordings/{id}          # Update editable metadata
PUT    /api/recordings/{id}/channels # Update channel routing / names
POST   /api/recordings/{id}/start
POST   /api/recordings/{id}/stop
POST   /api/recordings/{id}/playback/start
POST   /api/recordings/{id}/playback/stop
DELETE /api/recordings/{id}
GET    /api/recordings/{id}/files    # List per-channel output files with sizes
```

### Live Recording / Playback
```
WS     /ws/recordings/{id}/levels    # Per-channel dBFS at ~4Hz
WS     /ws/recordings/{id}/status    # Status changes, error events, elapsed time
GET    /api/recordings/{id}/monitor/{channel}  # Initiate WebRTC session
```

### Console Integration
```
GET    /api/consoles
POST   /api/consoles
GET    /api/consoles/{id}
PUT    /api/consoles/{id}
DELETE /api/consoles/{id}
POST   /api/consoles/{id}/test
GET    /api/consoles/{id}/channels   # Pull channel names from console
POST   /api/consoles/{id}/channels   # Push channel names to console
```

### Storage & Destinations
```
GET    /api/storage/destinations
POST   /api/storage/destinations
GET    /api/storage/destinations/{id}
PUT    /api/storage/destinations/{id}
POST   /api/storage/destinations/{id}/activate
POST   /api/storage/destinations/{id}/test       # Speed test
GET    /api/storage/destinations/{id}/capacity
POST   /api/storage/relocations
GET    /api/storage/relocations/{id}
WS     /ws/storage/relocations/{id}              # Progress stream
```

### Transcode / Export
```
POST   /api/recordings/{id}/export
GET    /api/recordings/{id}/exports
GET    /api/exports/{job_id}
DELETE /api/exports/{job_id}
WS     /ws/exports/{job_id}                      # Progress stream
```

---

## 6. Frontend Views

| View | Route | Roles | Key Features |
|---|---|---|---|
| Setup Wizard | /setup | none (pre-auth) | Admin password, hostname, initial storage. Redirects away once setup complete. |
| Status (kiosk) | /status | none | Read-only. Hostname, all IPs, service health, active recordings. Chromium kiosk target. |
| Login | /login | all | Hidden if auth disabled |
| Dashboard | / | all | Active recordings (real-time cards), recent recordings, capacity gauge, system health |
| Sources | /sources | admin, editor | AES-67 source CRUD; live status indicators |
| Groups | /groups | admin, editor | Nested tree; drag-to-reparent; create/rename/delete |
| Templates | /templates | admin, editor | CRUD; per-channel source defaults; metadata defaults |
| New Recording | /recordings/new | admin, editor, operator | Group + template + per-channel source routing; metadata entry; console channel pull |
| Recording Detail | /recordings/:id | all (own groups) | Metadata view/edit; file list with sizes; export controls |
| Live View | /recordings/:id/live | all (own groups) | Per-channel level meters; elapsed time; stop control; single-channel WebRTC listen-in |
| Playback | /recordings/:id/playback | admin, editor, operator | Playback controls; channel mapping; level meters; listen-in |
| Consoles | /consoles | admin, editor | Console CRUD; test connectivity; channel pull/push diff |
| Storage | /settings/storage | admin | Destination CRUD; speed test results; safe-settings matrix; relocation management |
| Network | /settings/network | admin | Interface list with full IP/gateway config; apply button |
| Users | /settings/users | admin | User CRUD; role assignment; group access matrix |
| System | /settings/system | admin | Auth toggle; hostname; service health; audit log |

---

## 7. Audio Engine Details

### 7.1 Multi-Source Recording

Each AES-67 source gets one GStreamer pipeline. Channels are grouped by source from the `recording_channels` rows, and one pipeline per source handles capture and per-channel file writing.

**Pipeline structure (per source, e.g. 32ch L24 at 48 kHz):**

```
udpsrc multicast-group=239.69.0.1 port=5004 multicast-iface=eth0
  caps="application/x-rtp, media=audio, encoding-name=L24, channels=32, clock-rate=48000"
  → rtpjitterbuffer latency=20 do-lost=true
  → rtpL24depay
  → audio/x-raw, format=S24BE, channels=32, rate=48000
  → audioconvert
  → deinterleave name=split
      split.src_0 → queue → audioconvert → audio/x-raw,format=S24LE → wavenc → filesink location=ch01_Kick.wav
      split.src_1 → queue → audioconvert → audio/x-raw,format=S24LE → wavenc → filesink location=ch02_Snare.wav
      ...
```

Only the channels selected in `recording_channels` for that source get a filesink branch; unused source channels are discarded via `fakesink`. AES-67 sources share a PTP grandmaster, so multi-source recordings are sample-accurate.

The pipeline is built as a Python object using `gi.repository.Gst` (GstPython) and managed through GStreamer state transitions (`PLAYING` → `EOS` → `NULL`) rather than subprocess lifecycle management.

**RF64 / large-file support:** `wavenc` in GStreamer writes standard WAV by default. RF64 auto-promotion is handled by a thin post-processing step using the `mutagen` library when the file exceeds 4 GB (same as the FFmpeg `-rf64 auto` flag). AIFF output uses `aiffenc`.

### 7.2 Level Metering

Metering branches off the same pipeline via a `tee` element inserted after `audioconvert`, avoiding a separate process:

```
... audioconvert → tee name=t
  t.src_0 → deinterleave → filesinks   (recording branch)
  t.src_1 → level name=lvl interval=250000000 post-messages=true → fakesink sync=false
```

The `level` element posts `GstMessage` objects on the pipeline bus every 250 ms (~4 Hz), containing per-channel RMS and peak values as a `GValueArray`. The Python bus watch callback reads these messages, maps channel indices to `recording_channels` channel numbers, and updates the in-memory `RecordingSession.meter_data` list for WebSocket broadcast.

One pipeline per active source handles both recording and metering, reference-counted across concurrent recordings that share the same source.

### 7.3 Capacity / Load Display

The dashboard shows a real-time capacity gauge computed as:

```
required_bandwidth = Σ(recording.channel_count × recording.sample_rate × recording.bit_depth/8)
                     for all active recordings
available_bandwidth = active_destination.last_speed_test_write_mbps × 1e6
load_pct = required_bandwidth / available_bandwidth
```

Color coding: green < 70%, yellow 70–90%, red > 90%. A warning is shown when creating a new recording that would exceed 90%.

---

## 8. Key Service Implementations

### 8.1 Console Abstraction

```python
class BaseConsole(ABC):
    async def test_connection(self) -> bool: ...
    async def pull_channel_names(self, count: int) -> list[str]: ...
    async def push_channel_names(self, names: list[str]) -> None: ...

class X32Console(BaseConsole): ...  # /ch/01/config/name through /ch/32/config/name
class WingConsole(BaseConsole): ... # /ch/<n>/name
```

### 8.2 Storage Destination Abstraction

```python
class BaseDestination(ABC):
    async def test_connection(self) -> bool: ...
    async def mount(self) -> None: ...
    async def unmount(self) -> None: ...
    async def get_capacity(self) -> dict: ...

class LocalOSDestination(BaseDestination): ...
class SMBDestination(BaseDestination): ...
class NFSDestination(BaseDestination): ...
```

### 8.3 Network Configuration (Privileged)

In-app network config writes netplan YAML. Because FastAPI runs as `basin` user, a small Bash helper (`/usr/local/bin/basin-netplan-helper`) runs via sudoers with a narrow permission:

```
basin ALL=(ALL) NOPASSWD: /usr/local/bin/basin-netplan-helper
```

The helper accepts a JSON payload on stdin describing the interface config, validates it, writes `/etc/netplan/99-basin.yaml`, and calls `netplan apply`. The FastAPI service never has unrestricted sudo.

### 8.4 AES-67 Capture Stack

**Architecture:**

```
Network (multicast RTP/AES-67)
        ↓
  aes67-linux-daemon        ← GPL v3 userspace daemon; SAP/mDNS discovery,
        ↓                     PTP sync (via linuxptp), stream metadata, REST API :8080
  GStreamer pipeline        ← udpsrc → rtpjitterbuffer → rtpL24depay → deinterleave → filesinks
```

The `ravenna-alsa-lkm` kernel module is **not required**. GStreamer reads multicast RTP directly from the network stack; no ALSA device is created or used for capture. The bondagit daemon remains responsible for:
- SAP/mDNS stream advertisement/discovery
- PTP clock synchronization (via `linuxptp` / `ptp4l`)
- Providing stream SDP metadata (multicast address, port, encoding, channel count) via its REST API

**Build and install steps (handled by `deploy/setup.sh`):**

```bash
# 1. GStreamer runtime and Python bindings
apt-get install -y \
  gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
  python3-gst-1.0 gir1.2-gstreamer-1.0

# 2. PTP synchronization (required for multi-source timing)
apt-get install -y linuxptp
# ptp4l configured to lock to AES-67 grandmaster on the audio NIC

# 3. avahi for mDNS discovery
apt-get install -y avahi-daemon

# 4. Build and install the bondagit daemon (discovery + PTP coordination only)
apt-get install -y build-essential git cmake
git clone https://github.com/bondagit/aes67-linux-daemon.git /opt/basin/drivers/aes67-linux-daemon
cd /opt/basin/drivers/aes67-linux-daemon
mkdir build && cd build
cmake .. && make -j$(nproc)
make install   # installs to /usr/local/bin/aes67-daemon

# 5. Real-time scheduling for GStreamer threads
echo "kernel.sched_rt_runtime_us = -1" >> /etc/sysctl.d/99-basin.conf
sysctl -p /etc/sysctl.d/99-basin.conf
```

**systemd service `basin-aes67.service`:**

```ini
[Unit]
Description=Basin AES-67 Daemon
After=network.target
Before=basin-api.service

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/aes67-daemon -c /opt/basin/data/aes67-daemon.conf
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Stream parameters stored in `aes67_sources`:**

At source creation, Basin queries the daemon's REST API for the stream's SDP and stores `multicast_address` (e.g. `239.69.0.1`) and `rtp_port` (e.g. `5004`) directly. The GStreamer `udpsrc` element uses these to subscribe to the multicast group. No ALSA device string is needed.

**Channel count target:**

128 channels is the v1 target, achieved via multiple concurrent GStreamer pipelines (one per AES-67 source). Each pipeline handles one source's channel count independently. GStreamer's element-level concurrency model scales without the 64-channel daemon sink limit that applied to the ALSA path.

**GPL compliance:**

Include in the appliance (e.g., on `/opt/basin/drivers/sources/` or a bundled USB/URL):
- Source of `aes67-linux-daemon` at the exact commit built
- A written offer: "The source code for GPL components is available at /opt/basin/drivers/sources/ or by written request to [contact]"

---

### 8.5 WebRTC Monitor (aiortc)

A single aiortc `RTCPeerConnection` is maintained per user session. On channel selection:
1. Browser sends SDP offer to `GET /api/recordings/{id}/monitor/{channel}`
2. Backend resolves the channel's source (`multicast_address`, `rtp_port`, `source_channel`)
3. A lightweight GStreamer pipeline taps the source's live RTP feed for the selected channel, converts to Opus, and feeds into an aiortc audio track
4. SDP answer returned; browser plays via Web Audio API

Only one channel per user at a time; selecting a new channel sends a new offer which replaces the previous connection.

---

## 9. Phased Build Plan (Revised)

### Phase 1 — Foundation (Weeks 1–4)

**Infra & Deployment**
- Ubuntu appliance provisioning script (`deploy/setup.sh`):
  - System packages: PostgreSQL, Redis, Nginx, Python 3.12, Node.js, build-essential, linux-headers, git, linuxptp, avahi-daemon
  - Build and install `ravenna-alsa-lkm` kernel module (from bondagit/ravenna-alsa-lkm)
  - Build and install `aes67-linux-daemon` (from bondagit/aes67-linux-daemon)
  - Write sysctl `kernel.sched_rt_runtime_us = -1` for RT scheduling
  - Disable PulseAudio globally
- systemd service files for all Basin processes: `basin-api`, `basin-worker`, `basin-beat`, `basin-aes67`
- Chromium kiosk service targeting `/status`
- Git-based deployment script (`deploy/deploy.sh`): `git pull` → Alembic migrate → `npm run build` → `systemctl restart basin-api basin-worker basin-beat` (does NOT restart `basin-aes67` on routine deploys)
- Nginx config: serve Vue `dist/`, proxy `/api/` and `/ws/` to uvicorn

**Backend Scaffold**
- FastAPI app factory with lifespan (startup/shutdown hooks)
- PostgreSQL + SQLAlchemy + Alembic (all models, first migration)
- pydantic-settings config (env vars: `POSTGRES_DSN`, `REDIS_URL`, `STORAGE_ROOT`, etc.)
- Celery + Redis setup

**Auth & Users**
- JWT login (httpOnly cookie), refresh token rotation, logout (token revocation via Redis)
- Three roles: admin, editor, operator
- Role enforcement dependency (`require_role(...)`)
- User CRUD endpoints (admin only)

**Setup Wizard**
- `/api/setup/status` and `/api/setup/init` endpoints (active only before first admin exists)
- Vue wizard view at `/setup`: set hostname, admin password, initial local storage path
- Redirect to `/login` on completion

**Status Endpoint**
- `/api/status`: hostname, all network interface IPs, PostgreSQL OK, Redis OK, active recording count
- Vue `/status` view: clean read-only display for kiosk

**Vue SPA Scaffold**
- Vite + Vue 3 + Pinia + PrimeVue + TailwindCSS
- Vue Router with auth guard (redirect to `/setup` → `/login` → `/ `)
- Axios instance with 401 interceptor (auto-refresh token)
- Navigation shell component (sidebar/topbar)
- Login view

**Deliverable**: Appliance can be provisioned from scratch and accessed via browser. Login works. Status page shows on kiosk monitor.

---

### Phase 2 — AES-67 Sources & Storage Foundation (Weeks 5–7)

**AES-67 Sources**
- Source CRUD API + Vue view
- ALSA device string stored as `alsa_device` (e.g. `hw:AES67_Studio,0`); resolved from aes67-daemon REST API at source creation time
- Connectivity test: query aes67-daemon REST API for stream status; if stream active, attempt `apcm_open` via ctypes or parse `aplay -l` output to confirm device presence and channel count
- Live status indicator: poll aes67-daemon `/api/source/{id}` endpoint every 5s; display stream lock status and detected sample rate
- The `aes67_sources.alsa_device` field is what FFmpeg receives; never hardcode device strings

**Storage Destinations (Local only)**
- `local_os` and `local_volume` destination types
- Directory creation and validation
- Capacity display (disk usage via `shutil.disk_usage`)
- Speed test (write + read 512MB temp file, store results)
- Safe-settings capacity matrix (channels × sample rates vs. measured throughput)

**Network Interfaces (Admin)**
- `/api/network/interfaces` — read all interfaces via `netifaces`/`ip link`
- Vue Network view: show interface, status, IP, MAC
- Full IP/gateway config via netplan helper (write + apply)

**Deliverable**: Admin can configure network and storage from the browser.

---

### Phase 3 — Groups, Templates & Recording Creation (Weeks 8–10)

**Recording Groups**
- Nested group CRUD with filesystem directory sync
- Group move/rename: renames filesystem directory tree (safely, with rollback on failure)
- User access assignment (`user_group_access`)
- Vue Groups view: tree with drag-to-reparent, context menu for create/rename/delete

**Templates**
- Template CRUD with `channel_names`, `channel_source_defaults`, `metadata_defaults`
- Vue Templates view: channel name editor (scrollable table for 128 channels)

**Recording Creation**
- `POST /api/recordings` with full channel routing payload
- Validates: all referenced sources exist and are active; channel numbers contiguous from 1; source channels within source's channel count
- Creates recording directory on storage destination
- Vue "New Recording" view:
  - Select group, template (auto-populates channels)
  - Channel routing table: each row shows channel number, name, source dropdown, source channel
  - "Pull from console" button (if console configured) — populates channel names
  - Metadata form
  - Preview of file paths that will be created

**Deliverable**: Recordings can be created and configured end-to-end.

---

### Phase 4 — Core Recording Engine (Weeks 11–14)

**GStreamer Recording Engine**
- `GstPipeline` wrapper: build pipeline from source parameters, set to PLAYING, handle bus messages (EOS, ERROR), set to NULL on stop
- `Recorder` service: constructs per-source GStreamer pipelines from `recording_channels`, manages pipeline lifecycle
- BWF metadata written by `wavenc` capsfilter + post-stop `mutagen` BEXT chunk injection
- Post-stop: write `metadata.json` sidecar, update `ended_at` and `duration_seconds`

**Level Metering**
- `level` element in each recording pipeline posts bus messages at ~4 Hz
- Bus watch callback in Python updates `RecordingSession.meter_data` in-memory; one pipeline per active source shared across concurrent recordings using that source
- Parsed dBFS values published to Redis pub/sub
- WebSocket endpoint `/ws/recordings/{id}/levels` subscribes to Redis, filters to recording's channels, sends JSON at ~4Hz

**Recording Start/Stop API**
- `POST /api/recordings/{id}/start`: validates not already recording; sets pipeline state to PLAYING; sets status → `recording`
- `POST /api/recordings/{id}/stop`: sends EOS event to pipeline; waits for EOS message; sets state to NULL; sets status → `completed`
- Error handling: GStreamer ERROR bus message → status → `error`; broadcast error event via WebSocket
- Concurrent recording limit: warn at >90% storage bandwidth; hard block if pipeline fails to reach PLAYING state

**Live View**
- Vue `/recordings/:id/live` view:
  - Per-channel VU meter bars (dBFS, peak hold)
  - Elapsed time counter
  - Stop button
  - Status badge (recording / error)

**Deliverable**: Full record/stop cycle works on hardware. Level meters display live in browser.

---

### Phase 5 — Playback & WebRTC Monitoring (Weeks 15–17)

**Playback**
- GStreamer playback pipeline: `filesrc → wavparse → interleave → udpsink` to re-emit as AES-67 RTP, or `alsasink` for local monitor output (config selectable)
- Channel re-mapping UI before playback start
- `POST /api/recordings/{id}/playback/start` / `/stop`
- Status `playback` added to recording FSM

**WebRTC Single-Channel Listen-In**
- aiortc server integrated into FastAPI lifespan
- `/api/recordings/{id}/monitor/{channel}` — SDP offer/answer flow
- ALSA source channel → Opus RTP track via aiortc
- Vue listen-in button on Live View and Playback view

**Metadata Editing**
- `PUT /api/recordings/{id}` for post-recording metadata edits
- FFmpeg/mutagen tag write-back for WAV/BWF (update BEXT chunk and ID3 without re-encoding)
- Vue Recording Detail: editable metadata form with save button

**Dashboard**
- Active recordings cards (real-time via WebSocket): name, group, elapsed, channels, status
- Recent recordings list (last 20 completed)
- Storage capacity bar
- Service health badges

**Deliverable**: Full playback and monitoring flow complete.

---

### Phase 6 — Console Integration (Weeks 18–20)

**Console Abstraction Layer**
- `BaseConsole` abstract class
- `X32Console`: OSC pull `/ch/01/config/name` → `/ch/32/config/name`; OSC push same addresses
- `WingConsole`: OSC pull `/ch/<n>/name`; OSC push same

**Console Management**
- Console CRUD + connectivity test endpoints
- Vue Consoles view: add/edit/remove consoles, test button with result toast

**Channel Pull Integration**
- "Pull from console" in New Recording view and Recording Detail view
- Fetches channel names, applies to matching channel rows

**Channel Push**
- Diff view: current recording channel names vs. current console channel names
- Confirm dialog; write to console via OSC SET messages

**Deliverable**: X32 and Wing channel names sync in both directions.

---

### Phase 7 — Network Storage (Weeks 21–23)

**SMB/CIFS Destinations**
- OS mount via `mount.cifs` subprocess; credentials stored AES-256-encrypted in DB
- Unmount on destination deactivation
- `SMBDestination` implementing `BaseDestination`

**NFS Destinations**
- OS mount via `mount.nfs` subprocess; version and options configurable
- `NFSDestination` implementing `BaseDestination`

**File Relocation**
- Celery task: iterate recording directories; copy with `shutil.copy2`; verify MD5; delete originals
- Scheduled relocation via Celery ETA (Celery beat triggers at `scheduled_at`)
- WebSocket progress stream `/ws/storage/relocations/{id}`
- Vue Storage view: relocation wizard, schedule picker (up to 7 days), live progress bar

**Deliverable**: Files can be moved to and from network shares automatically.

---

### Phase 8 — Export & Polish (Weeks 24–26)

**Transcode / Export**
- Celery export tasks: FFmpeg transcode to MP3, AAC, Opus, FLAC, PCM
- Channel selection (subset of channels) and interleaved option
- Output placed in `<recording_dir>/exports/<job_id>_<filename>`
- WebSocket progress stream
- Vue export UI in Recording Detail view

**Audit Log**
- `audit_log` table populated on: recording start/stop, user CRUD, settings changes, file deletion
- Vue System view: sortable/filterable audit log table (admin only)

**System Settings**
- Service health monitor (query `systemctl is-active` for each Basin service)
- Appliance info (OS version, disk layout, Python version, Basin version from git tag)
- Auth toggle with confirmation dialog

**End-to-End Testing & Performance**
- pytest integration tests covering full recording lifecycle
- Load test: 64ch at 96kHz on hardware; verify no dropped audio, no DB contention
- Verify WebSocket broadcast latency at 64ch metering

**Documentation**
- API reference auto-generated from FastAPI OpenAPI (`/docs`, `/redoc`)
- Deployment guide (README in `deploy/`)

**Deliverable**: Feature-complete v1.0. All spec functionality implemented.

---

## 10. Development Workflow

### Local Development (Windows)

Code is written on Windows and deployed to the physical appliance for all testing. There is no local backend runtime — the appliance is the test environment.

**Frontend-only iteration** (no appliance needed):
- `npm run dev` in `frontend/` starts the Vite dev server on port 5173
- API calls proxy to the appliance over the local network — set the appliance IP in `vite.config.ts`:
  ```ts
  proxy: {
    '/api': { target: 'http://<appliance-ip>', changeOrigin: true },
    '/ws':  { target: 'ws://<appliance-ip>', ws: true, changeOrigin: true },
  }
  ```
- This lets frontend changes be tested instantly against the real backend running on the appliance

**Full-stack changes** (backend code, models, migrations):
1. Commit and push to git
2. SSH to appliance and run `./deploy/deploy.sh`
3. Test in browser or via SSH

### Deployment to Appliance

```bash
# On appliance (one-time setup)
curl -sSL https://raw.githubusercontent.com/.../basin/setup.sh | bash

# Each code change
git push origin main
# SSH to appliance:
cd /opt/basin && ./deploy/deploy.sh
# deploy.sh does:
#   git pull
#   pip install -r requirements.txt
#   alembic upgrade head
#   npm run build (in frontend/)
#   systemctl restart basin-api basin-worker basin-beat
```

### Environment Variables (`.env` on appliance)

```
DATABASE_URL=postgresql://basin:secret@localhost/basin
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<generated 32-byte hex>
ENCRYPTION_KEY=<generated 32-byte hex, for SMB credentials>
STORAGE_ROOT=/mnt/basin-storage
MOCK_AUDIO=0
```

---

## 11. Open Items (Decisions Deferred to Later Phase)

| # | Question | Impact |
|---|---|---|
| ~~A~~ | ~~AES-67 ALSA driver~~| ~~Resolved: Path 1 — bondagit/aes67-linux-daemon + Merging RAVENNA LKM (GPL v3). See §8.4.~~ |
| B | SFTP and S3 storage destinations | Phase 7 extension |
| C | AES-67 output / re-transmission from appliance | New feature, post-v1 |
| D | Wing OSC subscription model (`/xremote`) for live channel name sync | Phase 6 enhancement |
| E | Multi-site / multi-appliance support | Post-v1 |
| F | 128-channel operation | v1 target; GStreamer pipeline-per-source model supports this without daemon channel limits |
| G | Future: SMPTE ST 2110 / OMT video recording — see §12 | Post-v1 feature investigation |

---

## 12. Future Feature: Video Recording (SMPTE ST 2110 / OMT)

### Background

SMPTE ST 2110 is a suite of SMPTE standards for professional media transport over IP:
- **ST 2110-20** — Uncompressed video (the primary target for video recording)
- **ST 2110-30** — PCM audio (essentially AES-67; already implemented)
- **ST 2110-40** — Ancillary data (captions, timecode, etc.)

**OMT** is to be investigated — the exact standard or vendor protocol the user intends is not yet defined. Candidates include NDI (NewTek/Vizrt), SRT (Haivision), IPMX (AIMS alliance, an IP Media Experience standard built on ST 2110), or another protocol. This needs clarification before any implementation work begins.

### Why This Is Non-Trivial

| Dimension | Audio (current) | Video (future) |
|---|---|---|
| Bandwidth | ~18 MB/s at 64ch/96kHz/24-bit | ~7 GB/s for 1080p60 uncompressed; even 1080p60 ProRes is ~250 MB/s |
| Capture path | ALSA → FFmpeg | Requires kernel-level video capture or hardware NIC offload |
| Storage format | WAV / BWF / FLAC per channel | MXF, MOV, or MKV container; codec TBD |
| Sync | PTP-clocked ALSA device | ST 2110-10 PTP + ST 2110-20 video timing; must lock video to audio |
| Driver | ravenna-alsa-lkm (existing) | No mature open-source ST 2110-20 capture driver for Linux ALSA/V4L2 |
| Processing | FFmpeg ALSA input, well understood | FFmpeg has limited ST 2110 RTP input support; hardware support very limited |

### Investigation Items (Pre-Implementation Research Required)

1. **Clarify "OMT"** — determine the exact protocol/standard. If it is NDI, SRT, or another protocol, the capture path differs significantly from ST 2110-20.

2. **Driver / capture path** — identify a viable Linux capture path for the target protocol:
   - ST 2110-20: investigate `rtp://` FFmpeg input with `format=rawvideo`; investigate whether the existing AES-67 daemon has a video extension; research NVIDIA Rivermax SDK (commercial, high-performance ST 2110 on Mellanox NICs)
   - NDI: `libndi` (NewTek SDK, free but proprietary) with FFmpeg `ffndi` or native support
   - SRT: `libsrt` in FFmpeg — well supported, would capture a compressed stream

3. **Storage throughput** — video recording will require a much faster storage destination than audio. A NVMe local volume or high-bandwidth NFS/iSCSI target would likely be mandatory. The speed test tool would need video-appropriate benchmark sizes (5–10 GB test files).

4. **Data model extension** — a video-capable recording session would add:
   - `video_source_id` FK to a new `video_sources` table
   - `video_codec`, `video_container`, `video_resolution`, `video_framerate`
   - A `video_file_path` per recording (one video file + N audio channel files)

5. **UI additions** — a video recording session would add:
   - Video source selector (separate from AES-67 audio sources)
   - Resolution / framerate / codec picker
   - Video preview thumbnail (if feasible without excessive CPU cost)
   - Combined AV playback (synchronized audio + video) — significantly more complex than audio-only playback

6. **Sync / timecode** — AV sync between the audio (AES-67, PTP-clocked) and video (ST 2110-20 or OMT, also PTP-ideally) must be maintained. Both should share the same PTP grandmaster clock. If the video source does not use PTP, a timecode-based sync strategy is needed.

### Recommended Approach When Ready

1. Decide on exact protocol(s) to support first.
2. Run a standalone proof-of-concept on the appliance hardware: capture one video stream with FFmpeg alone and write to disk at target resolution/framerate. Measure sustained write throughput.
3. If proof-of-concept succeeds, scope a Phase 9 milestone covering driver integration, data model extension, and UI additions.
4. Audio recording (Phases 1–8) is completely independent and should ship first.
