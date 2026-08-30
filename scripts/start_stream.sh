#!/usr/bin/env bash

set -euo pipefail

# ============================================================
# OwlCam Raspberry Pi Camera Stream
#
# Streams:
#   Raspberry Pi Camera
#       -> rpicam-vid (H.264)
#       -> ffmpeg (MPEG-TS)
#       -> UDP over Tailscale
#
# Default destination:
#   100.116.197.91:5000
#
# This is the debugging path. It reaches exactly one machine and bypasses
# MediaMTX, so the web page has no stream while it runs. For anything other
# than a direct VLC check, prefer the owlcam-stream service and open the HLS
# URL below, which any number of viewers can watch at once.
# ============================================================


# ------------------------------------------------------------
# Configuration
# Environment variables can override these defaults.
# ------------------------------------------------------------

DEST_IP="${OWL_CAM_DEST_IP:-100.116.197.91}"
DEST_PORT="${OWL_CAM_DEST_PORT:-5000}"

WIDTH="${OWL_CAM_WIDTH:-1920}"
HEIGHT="${OWL_CAM_HEIGHT:-1080}"
FRAMERATE="${OWL_CAM_FRAMERATE:-30}"

STREAM_HOST="${OWL_CAM_STREAM_HOST:-owlcam.tail31318f.ts.net}"

CAMERA_DEVICES=(
    "/dev/media0"
    "/dev/media2"
)

force=false
assume_yes=false


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

info() {
    echo "🦉 $*"
}

warn() {
    echo "⚠️  $*"
}

error() {
    echo "❌ $*" >&2
}

usage() {
    cat <<'EOF'
Usage: start_stream.sh [--force] [--yes]

Sends the camera to one machine as MPEG-TS over UDP, for VLC. This bypasses
MediaMTX, so the web page has no stream while it runs.

  --force   Stop the owlcam-stream service and take the camera anyway.
  --yes     Do not prompt before stopping competing camera processes.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force) force=true ;;
        --yes|-y) assume_yes=true ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
    shift
done


# ------------------------------------------------------------
# Dependency checks
# ------------------------------------------------------------

check_dependencies() {

    if ! command -v rpicam-vid >/dev/null 2>&1; then
        error "rpicam-vid is not installed or not in PATH."
        exit 1
    fi

    if ! command -v ffmpeg >/dev/null 2>&1; then
        error "ffmpeg is not installed or not in PATH."
        exit 1
    fi

    if ! command -v fuser >/dev/null 2>&1; then
        warn "'fuser' is not available."
        warn "Camera ownership diagnostics will be limited."
    fi
}


# ------------------------------------------------------------
# Does the systemd service own the camera?
#
# is-active alone is not enough. It reports failure while a unit is
# 'activating', which is where a thrashing unit spends most of its time, so
# that check by itself lets this script through during exactly the situation
# the guard exists to prevent. An installed unit counts as the owner.
# ------------------------------------------------------------

service_owns_camera() {

    systemctl --user is-enabled owlcam-stream.service >/dev/null 2>&1 && return 0

    case "$(systemctl --user show owlcam-stream.service -p ActiveState --value 2>/dev/null)" in
        active|activating|reloading|deactivating) return 0 ;;
    esac

    return 1
}


# ------------------------------------------------------------
# Refuse to fight the service for the sensor
#
# Taking the camera from the service does not fail loudly. The web page just
# reports no stream on path 'owl', which is indistinguishable from the camera
# being switched off, while systemd restarts the unit every few seconds
# forever.
# ------------------------------------------------------------

check_service_conflict() {

    service_owns_camera || return 0

    if ! "${force}"; then

        cat >&2 <<EOF
❌ Refusing to start: the owlcam-stream service owns the camera.

Starting this would take the sensor, and the web page would go dark while
systemd restarts the service in a loop.

To watch in VLC without stopping the web page, open the same HLS feed the
browser uses. MediaMTX serves any number of readers at once:

  https://${STREAM_HOST}/owl/index.m3u8

Note: quitting VLC does not stop this script. UDP is fire-and-forget, so the Pi
keeps sending to a closed player and keeps holding the camera. Stop it here.

To take the camera anyway:

  ./start_stream.sh --force
EOF
        exit 1
    fi

    # Stopping the unit is not optional under --force. Killing its capture
    # without stopping the unit just triggers Restart=always, and the two
    # pipelines take turns knocking each other over.
    warn "Stopping owlcam-stream to take the camera..."
    systemctl --user stop owlcam-stream.service 2>/dev/null || true
    sleep 2
}


# ------------------------------------------------------------
# Show processes using the camera
# ------------------------------------------------------------

show_camera_owners() {

    echo
    warn "Camera appears to be in use."
    echo

    if command -v fuser >/dev/null 2>&1; then

        echo "Processes using Raspberry Pi camera devices:"
        echo

        for device in "${CAMERA_DEVICES[@]}"; do

            if [[ -e "$device" ]]; then
                echo "---- $device ----"

                # No sudo here.
                fuser -v "$device" 2>/dev/null || true

                echo
            fi

        done

    fi

    echo "Related camera processes:"
    echo

    ps -ef \
        | grep -E '[r]picam-vid|[r]picam-hello|[l]ibcamera' \
        || true

    echo
}


# ------------------------------------------------------------
# Check for known rpicam processes
# ------------------------------------------------------------

known_rpicam_processes_running() {

    pgrep -x "rpicam-vid" >/dev/null 2>&1 \
        || pgrep -x "rpicam-hello" >/dev/null 2>&1
}


# ------------------------------------------------------------
# Check whether camera devices are busy
# ------------------------------------------------------------

camera_is_busy() {

    # If fuser isn't installed, fall back to the process check.
    if ! command -v fuser >/dev/null 2>&1; then

        if known_rpicam_processes_running; then
            return 0
        fi

        return 1
    fi

    for device in "${CAMERA_DEVICES[@]}"; do

        if [[ -e "$device" ]]; then

            # No sudo here.
            if fuser "$device" >/dev/null 2>&1; then
                return 0
            fi

        fi

    done

    return 1
}


# ------------------------------------------------------------
# Kill competing rpicam processes
# ------------------------------------------------------------

kill_competing_rpicam_processes() {

    echo
    warn "Stopping competing Raspberry Pi camera processes..."

    # Matching on the exact process name rather than the full command line, so
    # the pattern cannot match this script or the shell that launched it.
    pkill -TERM -x "rpicam-vid" 2>/dev/null || true
    pkill -TERM -x "rpicam-hello" 2>/dev/null || true

    sleep 2

    # Force kill anything that survived.
    if pgrep -x "rpicam-vid" >/dev/null 2>&1; then
        warn "rpicam-vid did not stop cleanly. Sending SIGKILL..."
        pkill -KILL -x "rpicam-vid" 2>/dev/null || true
    fi

    if pgrep -x "rpicam-hello" >/dev/null 2>&1; then
        warn "rpicam-hello did not stop cleanly. Sending SIGKILL..."
        pkill -KILL -x "rpicam-hello" 2>/dev/null || true
    fi

    sleep 1
}


# ------------------------------------------------------------
# Resolve camera conflicts
# ------------------------------------------------------------

resolve_camera_conflict() {

    if camera_is_busy || known_rpicam_processes_running; then

        show_camera_owners

        if known_rpicam_processes_running; then

            echo "OwlCam found one or more competing camera processes:"
            echo
            echo "  rpicam-vid"
            echo "  rpicam-hello"
            echo

            answer=Y

            # Prompting without a terminal blocks forever under nohup, in a
            # unit, or over a piped SSH command.
            if "${assume_yes}" || [[ ! -t 0 ]]; then
                info "Assuming yes (no terminal attached or --yes given)."
            else
                read -r -p "Kill competing rpicam processes and retry? [Y/n] " answer
                answer="${answer:-Y}"
            fi

            case "$answer" in

                [Yy]|[Yy][Ee][Ss])

                    kill_competing_rpicam_processes

                    info "Checking camera again..."

                    sleep 1

                    if camera_is_busy || known_rpicam_processes_running; then

                        echo
                        error "Camera is STILL being used by another process."

                        show_camera_owners

                        error "Not starting OwlCam."
                        exit 1

                    fi

                    info "Camera is now available."
                    ;;

                *)

                    warn "Leaving existing camera processes running."
                    warn "OwlCam stream was not started."
                    exit 0
                    ;;

            esac

        else

            error "Camera appears busy, but the owner does not appear to be"
            error "rpicam-vid or rpicam-hello."
            echo

            show_camera_owners

            error "Not killing an unknown process automatically."
            exit 1

        fi

    fi
}


# ------------------------------------------------------------
# Start OwlCam stream
# ------------------------------------------------------------

start_stream() {

    echo
    echo "============================================================"
    echo "                  🦉 OWLCAM STREAM"
    echo "============================================================"
    echo
    echo " Resolution : ${WIDTH}x${HEIGHT}"
    echo " Framerate  : ${FRAMERATE} FPS"
    echo " Codec      : H.264"
    echo " Transport  : MPEG-TS / UDP"
    echo " Destination: udp://${DEST_IP}:${DEST_PORT}"
    echo
    warn "The web page has no stream while this runs."
    echo
    echo " Press Ctrl+C to stop."
    echo

    rpicam-vid \
        -t 0 \
        -n \
        --width "${WIDTH}" \
        --height "${HEIGHT}" \
        --framerate "${FRAMERATE}" \
        --inline \
        --codec h264 \
        -o - \
    | ffmpeg \
        -f h264 \
        -framerate "${FRAMERATE}" \
        -i - \
        -c:v copy \
        -fflags +genpts \
        -muxdelay 0 \
        -f mpegts \
        "udp://${DEST_IP}:${DEST_PORT}?pkt_size=1316"
}


# ------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------

cleanup() {

    echo
    info "OwlCam stream stopped."

    if "${force}"; then
        warn "owlcam-stream is still stopped. Restart the web page feed with:"
        warn "  systemctl --user start owlcam-stream"
    fi
}

trap cleanup EXIT


# ============================================================
# Main
# ============================================================

check_dependencies

check_service_conflict

resolve_camera_conflict

info "Camera is available."
info "Starting stream..."

start_stream
