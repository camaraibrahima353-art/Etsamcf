#!/usr/bin/env bash
# Installation sur un VPS Ubuntu 24.04 (2 vCPU / 4 Go suffisent ; aucun GPU requis). À lancer en root.
set -euo pipefail
apt-get update -q && apt-get install -y -q git python3-venv ffmpeg espeak-ng fonts-inter
id studio >/dev/null 2>&1 || useradd --system --create-home --home-dir /opt/studio-home studio
[ -d /opt/studio/.git ] || git clone https://github.com/camaraibrahima353-art/Etsamcf.git /opt/studio
cd /opt/studio
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m piper.download_voices fr_FR-siwis-medium --download-dir models || true
[ -f .env ] || { cp .env.example .env; chmod 600 .env; }
chown -R studio:studio /opt/studio
cp deploy/systemd/studio.service deploy/systemd/studio.timer deploy/systemd/studio-dashboard.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now studio.timer studio-dashboard.service
systemctl list-timers studio.timer --no-pager
echo "Renseigner /opt/studio/.env puis : sudo -u studio /opt/studio/.venv/bin/python -m studio run"
echo "Tableau de bord : ssh -L 8765:127.0.0.1:8765 <vps> puis http://127.0.0.1:8765"
