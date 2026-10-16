#!/bin/bash
# Install the official NVIDIA Container Toolkit and register its Docker runtime.
# Run once on the host: sudo bash scripts/setup_nvidia_docker.sh
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
    echo "Run this script with sudo on the Docker host." >&2
    exit 1
fi

for tool in curl gpg docker nvidia-smi systemctl; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Required host program is missing: $tool" >&2
        exit 1
    fi
done
nvidia-smi --query-gpu=index,name --format=csv,noheader

# Restarting Docker must not interrupt unrelated running containers.
RUNNING_CONTAINERS=$(docker ps --format '{{.Names}}')
if [[ -n "$RUNNING_CONTAINERS" ]]; then
    echo "Stop running containers before installing (Docker will restart):" >&2
    echo "$RUNNING_CONTAINERS" >&2
    exit 1
fi

TASK_TMP=$(mktemp -d)
trap 'rm -rf "$TASK_TMP"' EXIT

# Production repository and signing key from NVIDIA's official installation guide:
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html
curl --fail --show-error --silent --location --connect-timeout 15 --max-time 120 \
    https://nvidia.github.io/libnvidia-container/gpgkey -o "$TASK_TMP/key.asc"
gpg --batch --dearmor --output "$TASK_TMP/key.gpg" "$TASK_TMP/key.asc"
curl --fail --show-error --silent --location --connect-timeout 15 --max-time 120 \
    https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    -o "$TASK_TMP/repository.list"
sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    "$TASK_TMP/repository.list" > "$TASK_TMP/signed-repository.list"
install -m 0644 "$TASK_TMP/key.gpg" /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
install -m 0644 "$TASK_TMP/signed-repository.list" /etc/apt/sources.list.d/nvidia-container-toolkit.list

apt-get update
apt-get install -y --no-install-recommends nvidia-container-toolkit

if [[ -f /etc/docker/daemon.json ]]; then
    cp -p /etc/docker/daemon.json "/etc/docker/daemon.json.before-nvidia-$(date +%Y%m%d-%H%M%S)"
fi
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

docker run --rm --gpus all \
    -e NVIDIA_DRIVER_CAPABILITIES=compute,graphics,utility,display \
    --entrypoint nvidia-smi rlai-bot:gazebo --query-gpu=index,name --format=csv,noheader
echo "NVIDIA Docker support is ready. Start the simulation with:"
echo "bash scripts/run_sim.sh --nvidia"
