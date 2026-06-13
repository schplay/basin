#!/usr/bin/env bash
# Basin appliance first-time provisioning script.
# Run as root on a fresh Ubuntu 22.04/24.04 LTS server.
set -euo pipefail

BASIN_USER="basin"
BASIN_HOME="/opt/basin"
REPO_URL="${REPO_URL:-https://github.com/YOUR_ORG/basin.git}"
BRANCH="${BRANCH:-main}"
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 16)}"
SECRET_KEY="$(openssl rand -hex 32)"
ENCRYPTION_KEY="$(openssl rand -hex 32)"

echo "==> Installing system packages"
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3.12-dev \
    postgresql postgresql-client \
    redis-server \
    nginx \
    nodejs npm \
    git curl wget \
    build-essential cmake \
    libffi-dev libssl-dev libavahi-client-dev \
    ffmpeg \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
    python3-gst-1.0 gir1.2-gstreamer-1.0 \
    avahi-daemon avahi-utils \
    linuxptp \
    netifaces \
    xorg openbox chromium-browser \
    net-tools iproute2

echo "==> Creating basin user"
id -u $BASIN_USER &>/dev/null || useradd -r -m -d $BASIN_HOME -s /bin/bash $BASIN_USER
usermod -aG audio,video $BASIN_USER

echo "==> Setting up PostgreSQL"
systemctl enable postgresql --now
sudo -u postgres psql -c "CREATE USER basin WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE basin OWNER basin;" 2>/dev/null || true

echo "==> Configuring Redis"
sed -i 's/^supervised no/supervised systemd/' /etc/redis/redis.conf
systemctl enable redis-server --now

echo "==> Cloning repository"
if [ -d "$BASIN_HOME/repo" ]; then
    git -C "$BASIN_HOME/repo" pull origin $BRANCH
else
    git clone --branch $BRANCH "$REPO_URL" "$BASIN_HOME/repo"
fi
chown -R $BASIN_USER:$BASIN_USER "$BASIN_HOME/repo"

echo "==> Installing AES-67 daemon (aes67-linux-daemon)"
# The daemon handles SAP/mDNS discovery and PTP coordination.
# Basin reads stream parameters from its REST API; no ALSA kernel module is needed.
DRIVER_SRC="$BASIN_HOME/drivers"
mkdir -p "$DRIVER_SRC"

if [ ! -d "$DRIVER_SRC/aes67-linux-daemon" ]; then
    git clone https://github.com/bondagit/aes67-linux-daemon.git "$DRIVER_SRC/aes67-linux-daemon"
fi
cd "$DRIVER_SRC/aes67-linux-daemon"
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
make install
cd "$BASIN_HOME"

echo "==> Applying RT scheduling sysctl"
cat > /etc/sysctl.d/99-basin.conf <<'EOF'
kernel.sched_rt_runtime_us = -1
EOF
sysctl -p /etc/sysctl.d/99-basin.conf

echo "==> Verifying GStreamer Python bindings"
python3 -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; Gst.init(None); print('GStreamer', Gst.version_string())" || {
    echo "ERROR: GStreamer Python bindings not available — check python3-gst-1.0 install"
    exit 1
}

echo "==> Disabling PulseAudio system-wide"
systemctl --global disable pulseaudio.service pulseaudio.socket 2>/dev/null || true

echo "==> Setting up Python virtualenv and backend dependencies"
python3.12 -m venv "$BASIN_HOME/venv"
source "$BASIN_HOME/venv/bin/activate"
pip install --upgrade pip
pip install -r "$BASIN_HOME/repo/backend/requirements.txt"

echo "==> Building frontend"
cd "$BASIN_HOME/repo/frontend"
npm ci
npm run build

echo "==> Writing .env"
cat > "$BASIN_HOME/repo/backend/.env" <<EOF
DATABASE_URL=postgresql://basin:${DB_PASSWORD}@localhost/basin
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=${SECRET_KEY}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
STORAGE_ROOT=/mnt/basin-storage
MOCK_AUDIO=0
AES67_DAEMON_URL=http://localhost:8080
EOF
chown $BASIN_USER:$BASIN_USER "$BASIN_HOME/repo/backend/.env"
chmod 600 "$BASIN_HOME/repo/backend/.env"

echo "==> Running database migrations"
cd "$BASIN_HOME/repo/backend"
source "$BASIN_HOME/venv/bin/activate"
alembic upgrade head

echo "==> Installing systemd services"
cp "$BASIN_HOME/repo/deploy/systemd/"*.service /etc/systemd/system/
systemctl daemon-reload
for svc in basin-aes67 basin-api basin-worker basin-beat; do
    systemctl enable "$svc"
    systemctl start "$svc"
done

echo "==> Configuring Nginx"
cp "$BASIN_HOME/repo/deploy/nginx/basin.conf" /etc/nginx/sites-available/basin
ln -sf /etc/nginx/sites-available/basin /etc/nginx/sites-enabled/basin
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl enable nginx --now && systemctl reload nginx

echo "==> Installing netplan helper"
cp "$BASIN_HOME/repo/scripts/netplan-helper.sh" /usr/local/bin/basin-netplan-helper
chmod 755 /usr/local/bin/basin-netplan-helper
echo "basin ALL=(ALL) NOPASSWD: /usr/local/bin/basin-netplan-helper" > /etc/sudoers.d/basin-netplan
chmod 440 /etc/sudoers.d/basin-netplan

echo "==> Setting up kiosk display (runs on boot with X)"
systemctl enable basin-kiosk

mkdir -p /mnt/basin-storage
chown $BASIN_USER:$BASIN_USER /mnt/basin-storage

echo ""
echo "======================================================"
echo "  Basin setup complete!"
echo "  Database password: $DB_PASSWORD"
echo "  (Stored in $BASIN_HOME/repo/backend/.env)"
echo "  Access the web UI at: http://$(hostname -I | awk '{print $1}')"
echo "======================================================"
