**MULTITRACK RECORDING APPLIANCE**

Architecture & Full Project Specification

Project Codename: **AES-Capture**

Version 1.0 Draft  •  June 2026

# **1\. Executive Summary**

AES-Capture is a self-contained Ubuntu Server x86 appliance that provides professional-grade multitrack recording, monitoring, playback, and file management for AES-67 audio-over-IP networks. It exposes a browser-based web interface accessible to users on the local network and supports up to 128 simultaneous channels at initial target, with room to grow.

The system is designed around a clear separation of concerns: audio I/O is handled by the existing AES-67 ALSA driver and FFmpeg; business logic lives in a Python/FastAPI backend; a Vue 3 single-page application provides the user interface; and SQLite persists all application state. Real-time updates use WebSockets; browser audio monitoring uses WebRTC.

# **2\. Recommended Technology Stack**

## **2.1 Rationale**

Python was selected as the backend language over PHP/Laravel because the entire ecosystem of required integrations — FFmpeg subprocess management, ALSA/Linux system calls, OSC protocol libraries for console integration, network share mounting (CIFS/NFS), and filesystem operations — has mature, well-maintained Python libraries with minimal glue code required. Laravel would require significant custom bridging for nearly every integration.

## **2.2 Stack Components**

| Layer | Technology | Justification |
| :---- | :---- | :---- |
| Backend Framework | Python 3.12 \+ FastAPI | Async-native, WebSocket support built-in, excellent subprocess/OS integration, auto-generated OpenAPI docs |
| Task Queue | Celery \+ Redis | Background jobs: file moves, transcode, speed tests, scheduled relocations |
| Database | SQLite via SQLAlchemy ORM | Zero-config, sufficient for single-node appliance, file-based backup |
| Database Migrations | Alembic | Schema versioning, clean upgrade path |
| Audio Engine | FFmpeg (subprocess) | Proven AES-67 capture, wide codec support, metadata writing |
| AES-67 Driver | Existing ALSA driver | Already in place on the appliance |
| Console Protocol | python-osc (OSC/UDP) | X32 and Wing both use OSC; most stable integration method |
| Real-time Comms | WebSockets (FastAPI native) | Live level meters, recording status, log streaming |
| Browser Audio Monitor | WebRTC (via aiortc server-side) | Single-channel listen-in during recording or playback |
| Frontend Framework | Vue 3 \+ Vite | Familiar to developer, excellent reactivity for live views |
| Frontend UI | PrimeVue \+ TailwindCSS | Professional component library; audio/meter components available |
| Frontend State | Pinia | Vue 3 native store, replaces Vuex |
| Network Share Mounting | pysmb / libnfs \+ OS mount | SMB/CIFS and NFS mounting with Python control |
| Process Supervision | systemd | Services for FastAPI, Celery, Redis, WebRTC relay |
| Reverse Proxy | Nginx | Serves Vue SPA, proxies API and WebSocket connections |
| Packaging / Updates | Debian .deb or Ansible | Appliance-friendly deployment and update mechanism |

# **3\. System Architecture**

## **3.1 High-Level Component Diagram**

The following describes the major system boundaries and data flows:

Browser (Vue SPA)  ←→  Nginx  ←→  FastAPI (HTTP \+ WebSocket)  ←→  SQLite

FastAPI  ←→  FFmpeg subprocesses (capture / playback / transcode)

FastAPI  ←→  Celery workers (background jobs)  ←→  Redis

FastAPI  ←→  ALSA / AES-67 driver (audio device queries)

FastAPI  ←→  python-osc (X32 / Wing console OSC)

FastAPI  ←→  OS mounts (SMB/CIFS, NFS, local volumes)

FastAPI  ←→  aiortc WebRTC relay (browser audio monitoring)

## **3.2 Directory & File Layout**

The application lives at /opt/aes-capture/. The active storage root is configurable but follows this structure:

| Path | Description |
| :---- | :---- |
| /opt/aes-capture/ | Application root |
| /opt/aes-capture/backend/ | FastAPI application code |
| /opt/aes-capture/frontend/dist/ | Built Vue SPA (served by Nginx) |
| /opt/aes-capture/data/aes\_capture.db | SQLite database |
| /opt/aes-capture/data/config.json | Appliance-level settings (storage path, auth mode) |
| \<storage\_root\>/ | Configured storage root (local, volume, or network mount point) |
| \<storage\_root\>/\<group\>/ | Filesystem directory per recording group (nested for subgroups) |
| \<storage\_root\>/\<group\>/\<recording\_name\>/ | Directory per recording |
| \<storage\_root\>/\<group\>/\<recording\_name\>/ch01\_\<name\>.wav | Per-channel audio file |
| \<storage\_root\>/\<group\>/\<recording\_name\>/metadata.json | Sidecar metadata for the recording |

The filesystem structure mirrors the group hierarchy exactly. Renaming or moving a group in the UI renames or moves the corresponding directory. This ensures files on disk are always human-navigable without the application.

# **4\. Data Model**

## **4.1 Users**

| Field | Type | Notes |
| :---- | :---- | :---- |
| id | INTEGER PK |  |
| username | TEXT UNIQUE |  |
| password\_hash | TEXT | bcrypt; NULL if auth disabled |
| role | TEXT | admin | editor | operator |
| is\_active | BOOLEAN |  |
| created\_at | DATETIME |  |

## **4.2 User Group Assignments**

Admins have implicit access to all groups. Editors and operators are explicitly assigned to groups via a join table: user\_group\_access (user\_id, group\_id). Assignment to a parent group does not automatically grant access to child groups — each must be assigned explicitly, or the UI can offer a 'grant all children' shortcut.

## **4.3 Recording Groups**

| Field | Type | Notes |
| :---- | :---- | :---- |
| id | INTEGER PK |  |
| name | TEXT |  |
| parent\_id | INTEGER FK | NULL for top-level; self-referential for nesting |
| filesystem\_path | TEXT | Full relative path from storage root; kept in sync |
| default\_template\_id | INTEGER FK | Optional; auto-assigned template for new recordings |
| created\_at | DATETIME |  |

## **4.4 Recording Templates**

| Field | Type | Notes |
| :---- | :---- | :---- |
| id | INTEGER PK |  |
| name | TEXT | Template display name |
| channel\_count | INTEGER | e.g. 32, 64, 128 |
| channel\_names | JSON | Array of strings; e.g. \['Kick', 'Snare', ...\] |
| sample\_rate | INTEGER | e.g. 48000, 96000 |
| bit\_depth | INTEGER | e.g. 24, 32 |
| codec | TEXT | pcm\_s24le | pcm\_s32le | flac |
| container | TEXT | wav | bwf | flac |
| aes67\_source\_id | INTEGER FK | Default AES-67 source |
| metadata\_defaults | JSON | Pre-filled metadata fields (artist, project, etc.) |
| created\_at | DATETIME |  |

## **4.5 AES-67 Sources**

| Field | Type | Notes |
| :---- | :---- | :---- |
| id | INTEGER PK |  |
| name | TEXT | User-assigned friendly name |
| network\_interface | TEXT | e.g. eth0, eth1 |
| multicast\_address | TEXT | AES-67 stream multicast IP |
| channel\_count | INTEGER | Channels in this stream |
| sample\_rate | INTEGER |  |
| bit\_depth | INTEGER |  |
| alsa\_device | TEXT | Resolved ALSA device string |
| is\_active | BOOLEAN |  |
| created\_at | DATETIME |  |

## **4.6 Recordings**

| Field | Type | Notes |
| :---- | :---- | :---- |
| id | INTEGER PK |  |
| name | TEXT | Recording session name |
| group\_id | INTEGER FK | Owning group |
| template\_id | INTEGER FK | Template used (snapshot at creation time) |
| aes67\_source\_id | INTEGER FK | Source used |
| status | TEXT | pending | recording | completed | error | playback |
| filesystem\_path | TEXT | Full path to recording directory |
| channel\_count | INTEGER |  |
| channel\_names | JSON | Array; may differ from template if console-updated |
| sample\_rate | INTEGER |  |
| bit\_depth | INTEGER |  |
| codec | TEXT |  |
| container | TEXT |  |
| started\_at | DATETIME |  |
| ended\_at | DATETIME |  |
| duration\_seconds | FLOAT |  |
| metadata | JSON | Full metadata snapshot written to files |
| created\_by | INTEGER FK | User who created it |
| created\_at | DATETIME |  |

## **4.7 Recording Metadata Fields (JSON Schema)**

The metadata JSON stored on a recording and written to audio file tags includes the following fields:

| Field | Editable Post-Record | Maps To | Notes |
| :---- | :---- | :---- | :---- |
| title | Yes | TITLE / TIT2 | Recording session name by default |
| artist | Yes | ARTIST / TPE1 |  |
| album\_artist | Yes | ALBUMARTIST / TPE2 |  |
| album | Yes | ALBUM / TALB |  |
| project | Yes | COMMENT / custom | Production/project name |
| venue | Yes | custom (TOPE/TIT3) |  |
| event\_date | Yes | DATE / TDRC |  |
| track\_number | Yes | TRACK / TRCK | Channel track number within session |
| channel\_name | Yes | custom / TIT3 | Per-channel name |
| comment | Yes | COMMENT / COMM |  |
| engineer | Yes | custom | Recording engineer name |
| copyright | Yes | COPYRIGHT / TCOP |  |
| isrc | Yes | TSRC |  |
| bwf\_description | Yes | BWF BEXT Description | BWF files only |
| bwf\_originator | Yes | BWF BEXT Originator | Default: appliance hostname |
| bwf\_originator\_ref | No | BWF BEXT OriginatorReference | Auto-generated UUID |
| bwf\_origination\_date | No | BWF BEXT OriginationDate | Auto: recording start date |
| bwf\_origination\_time | No | BWF BEXT OriginationTime | Auto: recording start time |
| bwf\_time\_reference | No | BWF BEXT TimeReference | Sample offset from midnight |
| sample\_rate | No | File header |  |
| bit\_depth | No | File header |  |
| channel\_count | No | File header |  |
| codec | No | File header |  |
| appliance\_hostname | No | custom | Auto-captured |
| aes67\_source\_name | No | custom | Auto-captured |
| recording\_uuid | No | custom | Auto-generated per session |

## **4.8 Console Integrations**

| Field | Type | Notes |
| :---- | :---- | :---- |
| id | INTEGER PK |  |
| name | TEXT | User-assigned name |
| console\_type | TEXT | behringer\_x32 | behringer\_wing | (future types) |
| ip\_address | TEXT |  |
| port | INTEGER | Default 10023 for X32/Wing |
| network\_interface | TEXT | Optional bind interface |
| is\_active | BOOLEAN |  |
| last\_connected\_at | DATETIME |  |
| created\_at | DATETIME |  |

## **4.9 Storage Destinations**

| Field | Type | Notes |
| :---- | :---- | :---- |
| id | INTEGER PK | Active destination; only one row treated as active at a time |
| destination\_type | TEXT | local\_os | local\_volume | network |
| is\_active | BOOLEAN | Only one can be true |
| local\_path | TEXT | For local\_os and local\_volume |
| network\_type | TEXT | smb | nfs | (future: sftp, s3) |
| network\_host | TEXT |  |
| network\_share | TEXT | Share path or export path |
| network\_interface | TEXT | Bind NIC for network destination |
| smb\_username | TEXT |  |
| smb\_password\_enc | TEXT | Encrypted at rest |
| smb\_domain | TEXT |  |
| smb\_version | TEXT | 2.0 | 2.1 | 3.0 | auto |
| nfs\_version | TEXT | 3 | 4 | 4.1 |
| nfs\_options | TEXT | Additional mount options |
| mount\_point | TEXT | Where the app mounts the share: /mnt/aes-capture-storage |
| last\_speed\_test\_at | DATETIME |  |
| last\_speed\_test\_write\_mbps | FLOAT |  |
| last\_speed\_test\_read\_mbps | FLOAT |  |
| created\_at | DATETIME |  |

## **4.10 Scheduled File Relocations**

| Field | Type | Notes |
| :---- | :---- | :---- |
| id | INTEGER PK |  |
| from\_destination\_id | INTEGER FK |  |
| to\_destination\_id | INTEGER FK |  |
| scheduled\_at | DATETIME | When to execute; NULL means immediate/background |
| status | TEXT | pending | in\_progress | completed | failed |
| files\_total | INTEGER |  |
| files\_moved | INTEGER | Progress counter |
| created\_at | DATETIME |  |

# **5\. API Surface (FastAPI Routers)**

## **5.1 Authentication**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| POST | /api/auth/login | Returns JWT access token \+ refresh token |
| POST | /api/auth/refresh | Refresh access token |
| POST | /api/auth/logout | Invalidate refresh token |
| GET | /api/auth/me | Current user info |

## **5.2 Users (Admin only)**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| GET | /api/users | List users |
| POST | /api/users | Create user |
| PUT | /api/users/{id} | Update user |
| DELETE | /api/users/{id} | Deactivate user |
| PUT | /api/users/{id}/groups | Assign group access |
| PUT | /api/settings/auth | Toggle password auth on/off |

## **5.3 Recording Groups**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| GET | /api/groups | Full tree of groups (nested) |
| POST | /api/groups | Create group |
| PUT | /api/groups/{id} | Rename / reparent group (syncs filesystem) |
| DELETE | /api/groups/{id} | Delete group (must be empty or cascade option) |

## **5.4 Templates**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| GET | /api/templates | List templates |
| POST | /api/templates | Create template |
| PUT | /api/templates/{id} | Update template |
| DELETE | /api/templates/{id} | Delete template |

## **5.5 AES-67 Sources**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| GET | /api/sources | List configured AES-67 sources |
| POST | /api/sources | Add source |
| PUT | /api/sources/{id} | Update source |
| DELETE | /api/sources/{id} | Remove source |
| GET | /api/sources/{id}/status | Live status: connected, channel count detected |

## **5.6 Recordings**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| GET | /api/recordings | List recordings (filterable by group, status, date) |
| POST | /api/recordings | Create recording (sets up session, does not start) |
| GET | /api/recordings/{id} | Get recording detail |
| PUT | /api/recordings/{id} | Update editable metadata fields |
| POST | /api/recordings/{id}/start | Begin capture via FFmpeg |
| POST | /api/recordings/{id}/stop | Stop capture, finalize files |
| POST | /api/recordings/{id}/playback/start | Begin playback |
| POST | /api/recordings/{id}/playback/stop | Stop playback |
| DELETE | /api/recordings/{id} | Delete recording and files |

## **5.7 Live Recording / Playback**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| WS | /ws/recordings/{id}/levels | WebSocket: per-channel dBFS level updates (\~4/sec) |
| WS | /ws/recordings/{id}/status | WebSocket: status changes, error events, elapsed time |
| GET | /api/recordings/{id}/monitor/{channel} | Initiate WebRTC session for single-channel browser listen-in |

## **5.8 Console Integration**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| GET | /api/consoles | List configured consoles |
| POST | /api/consoles | Add console |
| PUT | /api/consoles/{id} | Update console config |
| DELETE | /api/consoles/{id} | Remove console |
| POST | /api/consoles/{id}/test | Test OSC connectivity |
| GET | /api/consoles/{id}/channels | Pull channel names from console |
| POST | /api/consoles/{id}/channels | Push channel names to console |

## **5.9 Storage & Destinations**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| GET | /api/storage/destinations | List destination configurations |
| POST | /api/storage/destinations | Add destination |
| PUT | /api/storage/destinations/{id} | Update destination |
| POST | /api/storage/destinations/{id}/activate | Set as active (triggers relocation prompt) |
| POST | /api/storage/destinations/{id}/test | Run read/write speed test |
| GET | /api/storage/destinations/{id}/capacity | Available disk space |
| POST | /api/storage/relocations | Schedule or trigger file relocation |
| GET | /api/storage/relocations/{id} | Relocation job status |
| GET | /api/network/interfaces | List system network interfaces with status |

## **5.10 Transcode / Export**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| POST | /api/recordings/{id}/export | Queue transcode job (specify codec, container, channel selection) |
| GET | /api/recordings/{id}/exports | List export jobs for a recording |
| GET | /api/exports/{job\_id} | Export job status and progress |
| DELETE | /api/exports/{job\_id} | Cancel or delete export |

# **6\. Frontend Application (Vue 3 SPA)**

## **6.1 Page / View Inventory**

| View | Route | Roles | Key Features |
| :---- | :---- | :---- | :---- |
| Login | /login | All | Username/password; hidden if auth disabled |
| Dashboard | / | All | Active recordings, recent recordings, system health summary |
| Sources | /sources | Admin, Editor | Manage AES-67 sources; live status indicators |
| Groups | /groups | Admin, Editor | Tree view; drag-to-reparent; create/rename/delete |
| Templates | /templates | Admin, Editor | CRUD; channel name editor; metadata defaults |
| New Recording | /recordings/new | Admin, Editor, Operator | Select group, template, source; enter metadata; console channel pull |
| Recording Detail | /recordings/:id | All (own groups) | Metadata view/edit; file list; export controls |
| Live View | /recordings/:id/live | All (own groups) | Channel level meters; status; elapsed time; single-channel listen-in |
| Playback | /recordings/:id/playback | Admin, Editor, Operator | Playback controls; channel mapping; level meters; listen-in |
| Consoles | /consoles | Admin, Editor | Add/manage consoles; test connectivity |
| Storage | /settings/storage | Admin | Destination config; speed test; relocation management |
| Network | /settings/network | Admin | Interface list; per-interface config |
| Users | /settings/users | Admin | User CRUD; role assignment; group access |
| System | /settings/system | Admin | Auth toggle; hostname; appliance info; service health |

## **6.2 Real-time Strategy**

The following views require WebSocket connections:

* Live View (/recordings/:id/live): level meters at \~4 updates/sec, status changes, error toasts

* Dashboard: active recording cards update in real time; no polling needed

* Relocation jobs: progress counter streamed via WebSocket

* Export jobs: progress streamed via WebSocket

All other views use standard HTTP REST calls. Vue Query (TanStack Query for Vue) is recommended for caching, background refetch, and loading states.

## **6.3 Browser Audio Monitoring (WebRTC)**

A single-channel listen-in button is present on the Live View and Playback view. When activated:

* The browser sends a WebRTC offer to /api/recordings/{id}/monitor/{channel}

* The backend (aiortc) creates a peer connection and pipes the selected ALSA channel into an RTP audio track

* The browser plays the received audio stream through the Web Audio API at the user's local volume

* Only one channel at a time per user session is allowed; selecting a new channel tears down the previous connection

* No mixing or processing is applied server-side; latency of \~200-500ms is acceptable

# **7\. Audio Engine**

## **7.1 Recording**

Each recording session spawns a single FFmpeg process that reads from the AES-67 ALSA device and writes N output files (one per channel). A Python wrapper class manages process lifecycle, monitors stderr for error conditions, and periodically samples output file sizes to derive approximate write rates for level estimation.

Example FFmpeg invocation for a 32-channel BWF recording at 24-bit/48kHz:

ffmpeg \-f alsa \-i hw:AES67,0 \-filter\_complex "channelsplit=channel\_layout=32c\[c0\]\[c1\]...\[c31\]" \-map \[c0\] \-c:a pcm\_s24le \-rf64 auto ch01\_Kick.wav \-map \[c1\] ...

Metadata (BEXT chunk for BWF, ID3/Vorbis comment for other formats) is passed via FFmpeg \-metadata flags at start time. Post-recording, metadata that was edited by the user is written back using FFmpeg \-metadata remux or mutagen for non-destructive tag editing.

## **7.2 Level Metering**

FFmpeg's loudnorm/volumedetect or astats filters can emit per-channel levels. For live metering, the recommended approach is to run a secondary lightweight FFmpeg instance per source (or reuse the capture process with tee muxer) that outputs dBFS values to stdout at \~4Hz via the astats filter with metadata\_block\_size. The backend parses this stream and broadcasts values over the WebSocket channel.

## **7.3 Playback**

Playback is handled by an FFmpeg process that reads the per-channel files and routes each to the corresponding output channel on the AES-67 ALSA device. Channel mapping is preserved from the original recording's channel\_names and channel\_count. The user may re-map channels in the UI before initiating playback.

## **7.4 Transcode / Export**

Export jobs are queued in Celery and executed as FFmpeg transcode processes. Supported output codecs for export: PCM (various bit depths), FLAC, MP3 (libmp3lame), AAC (libfdk\_aac or native), Opus. Output can be individual channel files or an interleaved multitrack file (user's choice).

# **8\. Console Integration**

## **8.1 Protocol**

Both the Behringer X32 and Behringer Wing use OSC (Open Sound Control) over UDP. The python-osc library (pythonosc) provides a clean async-compatible client. The appliance initiates all communication — there is no need to open inbound ports for console-to-appliance communication unless the user enables live name sync in the future.

## **8.2 X32 Channel Name Pull**

Channel names are read from OSC addresses /ch/01/config/name through /ch/32/config/name. A single burst of 32 requests is sent and responses are collected with a configurable timeout (default 2 seconds). Auxiliary, bus, and matrix channels are available via /auxin/, /bus/, /mtx/ namespaces and may be added as optional pulls.

## **8.3 Wing Channel Name Pull**

The Wing uses a similar OSC structure but with a different address schema. Channel names are at /ch/\<n\>/name. The Wing also supports a subscription model (/xremote) for live updates, but for the initial implementation user-initiated pull is sufficient and more predictable.

## **8.4 Channel Name Push**

Writing names back to the console uses the same OSC addresses with SET messages. The UI presents a diff view showing current recording channel names vs. console channel names before committing a push, to prevent accidental overwrites.

## **8.5 Console Abstraction**

Console implementations are structured as Python classes inheriting from a BaseConsole abstract class with methods: test\_connection(), pull\_channel\_names(count) \-\> List\[str\], push\_channel\_names(names: List\[str\]). Adding a new console type (e.g., Yamaha CL) requires only a new class implementing this interface, plus a new entry in the console\_type enum.

# **9\. Storage Subsystem**

## **9.1 Destination Types**

| Type | Implementation | Notes |
| :---- | :---- | :---- |
| local\_os | Direct filesystem path (e.g. /home/aes-capture/recordings) | No mounting needed; simplest option |
| local\_volume | Separately mounted volume at a configured path (e.g. /mnt/recordings) | Admin mounts the drive; app just uses the path |
| network\_smb | pysmb for connection test; OS mount via /etc/fstab or mount command at runtime | Credentials stored encrypted in DB |
| network\_nfs | libnfs for connection test; OS mount via mount command | NFS version selectable |

## **9.2 Speed Test**

The speed test writes a configurable-size temp file (default 512MB) to the destination using buffered sequential writes, then reads it back, measuring wall-clock time. Results are stored in the destination record. After a test, the UI shows a Safe Recording Settings panel:

The minimum required write throughput is calculated as: channels × sample\_rate × (bit\_depth/8) × 1.2 (20% safety margin). The UI renders a matrix of channel counts vs. sample rates with green/yellow/red indicators based on the measured throughput.

## **9.3 File Relocation**

When a destination change is committed with relocation requested, a Celery task is created. The task iterates all recording directories, copies files to the new destination preserving the group/recording directory hierarchy, verifies checksums (MD5), and only deletes originals after verification. Progress is streamed to the UI via WebSocket.

If the user scheduled the move for a future time (up to 7 days), the Celery beat scheduler triggers the task at the specified datetime. The scheduled\_at field on the StorageRelocation record is used as the ETA for the Celery task.

# **10\. User & Permission System**

## **10.1 Roles**

| Role | Capabilities |
| :---- | :---- |
| admin | Full system access: all settings, all groups, user management, storage config, console config |
| editor | Manage groups, templates, recordings, and metadata within assigned groups; cannot access system settings or user management |
| operator | Create new recordings and start/stop recording in assigned groups; initiate playback of existing recordings; cannot edit templates, groups, or system settings |

## **10.2 Default Admin Account**

On first boot, a default admin user is created with username 'admin' and a generated or fixed default password displayed once in the setup wizard. The UI forces a password change on first login. Password authentication can be disabled entirely in system settings (useful for closed networks), which bypasses the login screen and grants all users admin-equivalent access — this option itself is protected by a confirmation dialog warning of security implications.

## **10.3 JWT Authentication**

FastAPI uses short-lived JWTs (15 min) with refresh tokens (7 days). Tokens are stored in httpOnly cookies (not localStorage) to prevent XSS theft. The /api/auth/refresh endpoint is called automatically by the Vue axios interceptor when a 401 is received.

# **11\. Phased Build Plan**

## **Phase 1 — Foundation (Weeks 1–4)**

* Ubuntu appliance setup: Python env, FastAPI scaffold, SQLite \+ Alembic, Nginx, systemd services

* User auth: JWT login, three roles, default admin, auth toggle

* AES-67 source management: CRUD, ALSA device mapping, basic connectivity test

* Storage destination: local\_os type only; directory creation; basic capacity display

* Vue SPA scaffold: Vite \+ Vue 3 \+ Pinia \+ PrimeVue \+ TailwindCSS; login page; nav shell

## **Phase 2 — Core Recording (Weeks 5–9)**

* Groups: CRUD, nesting, filesystem directory sync, user access assignment

* Templates: CRUD with channel names and metadata defaults

* Recording creation: group \+ template \+ source selection, metadata entry form

* FFmpeg capture: process wrapper, per-channel file output, BWF metadata writing

* Live View: WebSocket level meters, status, elapsed time, stop/start controls

* Recording list and detail views

## **Phase 3 — Playback & Monitoring (Weeks 10–13)**

* Playback: FFmpeg playback process, channel mapping UI, playback controls

* WebRTC single-channel listen-in: aiortc server, browser client, channel selector

* Metadata editing: editable fields post-recording, FFmpeg/mutagen tag write-back

* Dashboard: active recordings widget, recent recordings, system health

## **Phase 4 — Storage & Network (Weeks 14–17)**

* Storage: SMB/CIFS and NFS destination types, mount management, credential storage

* Speed test tool and safe settings matrix

* File relocation: immediate and scheduled, Celery task, WebSocket progress

* Network interface management view

## **Phase 5 — Console Integration (Weeks 18–21)**

* Console abstraction layer: BaseConsole class, X32 implementation, Wing implementation

* Console management UI: add/configure/test consoles

* Channel name pull: user-initiated from New Recording and Recording Detail views

* Channel name push: diff view, confirm, write to console

## **Phase 6 — Export & Polish (Weeks 22–25)**

* Transcode/export: Celery jobs, MP3/AAC/Opus output, interleaved option, progress UI

* Audit log: who started/stopped recordings, changed settings

* System settings: hostname, service health, appliance info page

* End-to-end testing, performance profiling at 128ch/96kHz

* Documentation: user manual, API reference (auto-generated from FastAPI OpenAPI)

# **12\. Remaining Open Questions**

| \# | Question | Impact |
| :---- | :---- | :---- |
| 1 | Should the appliance expose a setup wizard on first boot (no users configured) or is manual CLI setup acceptable for initial configuration? | UX — affects Phase 1 scope |
| 2 | Is SFTP or S3/object storage needed for network destinations beyond SMB and NFS? | Phase 4 scope |
| 3 | Should the export feature place output files in a separate exports/ subdirectory within the recording folder, or in a user-specified location? | Data model minor addition |
| 4 | For the network interface management view, is full IP/netmask/gateway configuration in-app required, or is it informational only (showing interface state)? | Significant scope difference |
| 5 | Should recordings be lockable (prevent deletion/editing) once completed, perhaps by admin only? | Permission model addition |
| 6 | Is there a need to stream AES-67 audio to the network (i.e., re-transmit or monitor without a physical speaker), or is browser WebRTC listen-in sufficient for all monitoring needs? | Potential AES-67 output feature |
| 7 | What is the expected concurrent user count? (SQLite performs well up to \~20-30 concurrent writes; beyond that PostgreSQL should be considered.) | Tech stack confirmation |

