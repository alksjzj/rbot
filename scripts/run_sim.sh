#!/bin/bash
# scripts/run_sim.sh
# Launches rbot in Gazebo Harmonic (inside Docker).
#
# Usage:
#   bash scripts/run_sim.sh                           # Gazebo GUI
#   bash scripts/run_sim.sh --rviz                    # Gazebo GUI + RViz (gazebo_live)
#   bash scripts/run_sim.sh --headless                # Gazebo server-only (no GUI)
#   bash scripts/run_sim.sh --headless --rviz         # Headless sim + RViz
#   bash scripts/run_sim.sh --rviz-nav                # Gazebo + Nav2 + navigation RViz
#   bash scripts/run_sim.sh --headless --rviz-nav     # Headless sim + Nav2 + navigation RViz
#   bash scripts/run_sim.sh --headless --rviz-mapping # Headless mapping sim + mapping RViz
#   bash scripts/run_sim.sh --rviz-nav --map /ros2_ws/maps/my_map.yaml
#   bash scripts/run_sim.sh --nvidia                  # require NVIDIA rendering
#   bash scripts/run_sim.sh --no-nvidia               # use base Intel/AMD config
#
# Additional ROS launch args can follow, e.g.:
#   bash scripts/run_sim.sh --rviz world:=empty_world
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse --rviz, --rviz-nav, --rviz-mapping, and --headless flags
RVIZ=false
RVIZ_NAV=false
RVIZ_MAPPING=false
HEADLESS=false
NVIDIA_MODE=auto
MAP_YAML="/ros2_ws/maps/my_map.yaml"
ROSARGS=()
while [[ $# -gt 0 ]]; do
    arg="$1"
    if [[ "$arg" == "--rviz" ]]; then
        RVIZ=true
    elif [[ "$arg" == "--rviz-nav" ]]; then
        RVIZ_NAV=true
    elif [[ "$arg" == "--rviz-mapping" ]]; then
        RVIZ_MAPPING=true
    elif [[ "$arg" == "--headless" ]]; then
        HEADLESS=true
    elif [[ "$arg" == "--nvidia" ]]; then
        NVIDIA_MODE=required
    elif [[ "$arg" == "--no-nvidia" ]]; then
        NVIDIA_MODE=disabled
    elif [[ "$arg" == "--map" ]]; then
        shift
        if [[ $# -eq 0 ]]; then
            echo "ERROR: --map requires a map YAML path" >&2
            exit 2
        fi
        MAP_YAML="$1"
    else
        ROSARGS+=("$arg")
    fi
    shift
done

COMPOSE_FILES=(-f "$WS_ROOT/docker/docker-compose.yml")
NVIDIA_ENABLED=false
if [[ "$NVIDIA_MODE" != "disabled" ]]; then
    NVIDIA_RUNTIME=$(docker info --format '{{if index .Runtimes "nvidia"}}ready{{end}}')
    if [[ "$NVIDIA_RUNTIME" == "ready" ]]; then
        COMPOSE_FILES+=(-f "$WS_ROOT/docker/docker-compose.nvidia.yml")
        NVIDIA_ENABLED=true
    elif [[ "$NVIDIA_MODE" == "required" ]]; then
        echo "ERROR: NVIDIA Docker runtime is not configured." >&2
        echo "Run: sudo bash $SCRIPT_DIR/setup_nvidia_docker.sh" >&2
        exit 2
    elif command -v nvidia-smi >/dev/null 2>&1; then
        echo "WARNING: NVIDIA driver found, but Docker GPU support is missing." >&2
        echo "Run: sudo bash $SCRIPT_DIR/setup_nvidia_docker.sh" >&2
    fi
fi

# Build the list of docker compose services to start
SERVICES=(sim)
if [[ "$RVIZ" == "true" ]]; then
    SERVICES=(sim rviz)
fi
if [[ "$RVIZ_NAV" == "true" ]]; then
    SERVICES=(sim nav rviz_nav)
fi
if [[ "$RVIZ_MAPPING" == "true" ]]; then
    SERVICES=(sim_mapping rviz_mapping)
fi

GUI_REQUIRED=false
if [[ "$HEADLESS" == "false" ]] || [[ "$RVIZ" == "true" ]] || [[ "$RVIZ_NAV" == "true" ]] || [[ "$RVIZ_MAPPING" == "true" ]]; then
    GUI_REQUIRED=true
fi

if [[ "$GUI_REQUIRED" == "true" ]]; then
    export XAUTHORITY="${XAUTHORITY:-/tmp/.docker.xauth}"
    if [[ -d "$XAUTHORITY" ]]; then
        rm -rf "$XAUTHORITY"
    fi
    touch "$XAUTHORITY"
    if command -v xauth >/dev/null 2>&1; then
        xauth nlist "$DISPLAY" 2>/dev/null | sed -e 's/^..../ffff/' | xauth -f "$XAUTHORITY" nmerge - 2>/dev/null || true
    fi
    chmod 600 "$XAUTHORITY"
    xhost +local:docker 2>/dev/null || true
fi

# Export launch flags — docker-compose.yml reads these from the host env.
# Extra launch args are standard name:=value tokens and should not contain whitespace.
export RLAI_GZ_HEADLESS="$HEADLESS"
export RLAI_MAP_YAML="$MAP_YAML"
RLAI_EXTRA_ARGS="${ROSARGS[*]}"
export RLAI_EXTRA_ARGS

echo "==> Launching rbot simulation (Gazebo Harmonic)"
echo "    RViz:         $RVIZ"
echo "    RViz nav:     $RVIZ_NAV"
echo "    RViz mapping: $RVIZ_MAPPING"
echo "    Headless:     $HEADLESS"
echo "    NVIDIA GPU:   $NVIDIA_ENABLED"
echo "    Map YAML:     $MAP_YAML"
echo "    Extra args:   ${RLAI_EXTRA_ARGS:-none}"
exec docker compose "${COMPOSE_FILES[@]}" up "${SERVICES[@]}"
