#!/usr/bin/env bash
# 🌩️ ULTIMATE WEATHER RADAR TERMINAL
# The most powerful terminal-based weather radar viewer

# Copied from https://gist.github.com/craigderington/c30f7237be9499b6af60f855435e5d0b but I had to make some changes for my
# MacOS to work

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

# Radar lookup: returns "CODE|Name|URL" for a given key
get_radar_entry() {
    case "$1" in
        c) echo "CONUS|National View|https://radar.weather.gov/ridge/standard/CONUS_loop.gif" ;;
        n) echo "NORTHEAST|Northeast US|https://radar.weather.gov/ridge/standard/NORTHEAST_loop.gif" ;;
        s) echo "SOUTHEAST|Southeast US|https://radar.weather.gov/ridge/standard/SOUTHEAST_loop.gif" ;;
        w) echo "CENTGRLAKES|Great Lakes|https://radar.weather.gov/ridge/standard/CENTGRLAKES_loop.gif" ;;
        p) echo "PACNORTHWEST|Pacific NW|https://radar.weather.gov/ridge/standard/PACNORTHWEST_loop.gif" ;;
        1) echo "KMLB|Melbourne FL|https://radar.weather.gov/ridge/standard/KMLB_loop.gif" ;;
        2) echo "KAMX|Miami FL|https://radar.weather.gov/ridge/standard/KAMX_loop.gif" ;;
        3) echo "KJAX|Jacksonville FL|https://radar.weather.gov/ridge/standard/KJAX_loop.gif" ;;
        4) echo "KATL|Atlanta GA|https://radar.weather.gov/ridge/standard/KFFC_loop.gif" ;;
        5) echo "KNYC|New York City|https://radar.weather.gov/ridge/standard/KOKX_loop.gif" ;;
        6) echo "KCHI|Chicago IL|https://radar.weather.gov/ridge/standard/KLOT_loop.gif" ;;
        7) echo "KDFW|Dallas TX|https://radar.weather.gov/ridge/standard/KFWS_loop.gif" ;;
        8) echo "KDEN|Denver CO|https://radar.weather.gov/ridge/standard/KFTG_loop.gif" ;;
        9) echo "KSEA|Seattle WA|https://radar.weather.gov/ridge/standard/KATX_loop.gif" ;;
        0) echo "KLAX|Los Angeles CA|https://radar.weather.gov/ridge/standard/KSOX_loop.gif" ;;
    esac
}

CURRENT="s"
TEMP="/tmp/radar.gif"
WEATHER_DATA="/tmp/radar_weather.json"
STATUS_FILE="/tmp/radar_status.txt"
MPV_PID=""
AUTO_REFRESH_PID=""

# Terminal colors
C_RESET=$'\e[0m'
C_BOLD=$'\e[1m'
C_DIM=$'\e[2m'
C_RED=$'\e[31m'
C_GREEN=$'\e[32m'
C_YELLOW=$'\e[33m'
C_BLUE=$'\e[34m'
C_MAGENTA=$'\e[35m'
C_CYAN=$'\e[36m'
C_WHITE=$'\e[37m'
C_BG_BLUE=$'\e[44m'
C_BG_BLACK=$'\e[40m'

# ============================================================================
# TERMINAL MANAGEMENT
# ============================================================================

setup_terminal() {
    tput civis 2>/dev/null || true
    stty -echo 2>/dev/null || true
    clear
}

cleanup_terminal() {
    tput cnorm 2>/dev/null || true
    stty echo 2>/dev/null || true
    [[ -n "$MPV_PID" ]] && kill "$MPV_PID" 2>/dev/null || true
    [[ -n "$AUTO_REFRESH_PID" ]] && kill "$AUTO_REFRESH_PID" 2>/dev/null || true
    rm -f "$TEMP" "$WEATHER_DATA" "$STATUS_FILE" "$TEMP.new"
    clear
}

trap cleanup_terminal EXIT INT TERM

# ============================================================================
# RENDERER DETECTION
# ============================================================================

detect_renderer() {
    # Inside tmux the kitty graphics protocol isn't forwarded — use default mpv GUI window
    if [[ -n "${TMUX:-}" ]]; then
        echo ""
        return
    fi
    if [[ -n "${KITTY_WINDOW_ID:-}" ]] || [[ "${TERM:-}" == "xterm-kitty" ]]; then
        echo "kitty"
    elif [[ -n "${GHOSTTY_RESOURCES_DIR:-}" ]] || [[ "${TERM_PROGRAM:-}" == "ghostty" ]]; then
        echo "kitty"
    else
        echo "tct"
    fi
}

VO=$(detect_renderer)

# ============================================================================
# STATUS BAR & UI
# ============================================================================

get_radar_info() {
    local key="$1"
    get_radar_entry "$key" | cut -d'|' -f1,2
}

get_radar_url() {
    local key="$1"
    get_radar_entry "$key" | cut -d'|' -f3
}

draw_header() {
    local radar_code radar_name timestamp
    radar_code=$(get_radar_info "$CURRENT" | cut -d'|' -f1)
    radar_name=$(get_radar_info "$CURRENT" | cut -d'|' -f2)
    timestamp=$(date '+%Y-%m-%d %H:%M:%S %Z')

    echo -e "${C_BG_BLUE}${C_WHITE}${C_BOLD}"
    echo -e "╔════════════════════════════════════════════════════════════════════════════════╗"
    echo -e "║  ⚡ WEATHER RADAR TERMINAL ⚡                    $timestamp  ║"
    echo -e "╠════════════════════════════════════════════════════════════════════════════════╣"

    local line_length=80
    local current_length=$((14 + ${#radar_code} + 3 + ${#radar_name}))
    local spaces_needed=$((line_length - current_length - 1))
    printf "║  📡 Station: ${C_YELLOW}%s${C_WHITE}${C_BG_BLUE} - %-${spaces_needed}s║\n" "$radar_code" "$radar_name"
    echo -e "╠════════════════════════════════════════════════════════════════════════════════╣${C_RESET}"
}

draw_controls() {
    echo -e "${C_CYAN}${C_BOLD}"
    echo "╔══════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                              🎮 CONTROLS                                         ║"
    echo "╠══════════════════════════════════════════════════════════════════════════════════╣"
    echo "║  ${C_YELLOW}REGIONS:${C_CYAN} [c]ONUS [n]ortheast [s]outheast [w]great lakes [p]acific NW    ║"
    echo "║  ${C_YELLOW}CITIES:${C_CYAN}  [1]Melbourne [2]Miami [3]Jacksonville [4]Atlanta [5]NYC        ║"
    echo "║           [6]Chicago [7]Dallas [8]Denver [9]Seattle [0]Los Angeles          ║"
    echo "║  ${C_YELLOW}OTHER:${C_CYAN}   [r]efresh now  [h]elp  [q]uit                                  ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════════╝${C_RESET}"
}

show_loading() {
    local message="${1:-Loading radar data...}"
    echo -e "${C_YELLOW}⏳ $message${C_RESET}"
}

show_success() {
    local message="${1:-Success!}"
    echo -e "${C_GREEN}✓ $message${C_RESET}"
}

show_error() {
    local message="${1:-Error occurred}"
    echo -e "${C_RED}✗ $message${C_RESET}"
}

show_info() {
    local message="$1"
    echo -e "${C_BLUE}ℹ $message${C_RESET}"
}

update_status() {
    tput sc 2>/dev/null || true
    tput cup 0 0 2>/dev/null || true
    draw_header
    tput rc 2>/dev/null || true
}

# ============================================================================
# RADAR DATA MANAGEMENT
# ============================================================================

download_radar() {
    local url radar_name
    url=$(get_radar_url "$CURRENT")
    radar_name=$(get_radar_info "$CURRENT" | cut -d'|' -f2)

    show_loading "Downloading $radar_name radar..."

    if wget -q --timeout=10 -O "$TEMP" "$url" 2>/dev/null; then
        show_success "Radar data updated"
        return 0
    else
        show_error "Failed to download radar data"
        return 1
    fi
}

# ============================================================================
# MPV PLAYER MANAGEMENT
# ============================================================================

start_mpv() {
    local args=(--loop=inf --no-config --no-osc --no-osd-bar --really-quiet --msg-level=all=no)
    [[ -n "$VO" ]] && args=(--vo="$VO" "${args[@]}")

    mpv "${args[@]}" "$TEMP" </dev/null &>/dev/null &
    MPV_PID=$!
    disown "$MPV_PID" 2>/dev/null || true  # suppress "Abort trap" messages from bash
    sleep 0.5

    # If mpv died immediately, fall back to the system default viewer (Preview on macOS)
    if ! kill -0 "$MPV_PID" 2>/dev/null; then
        MPV_PID=""
        open -g "$TEMP" 2>/dev/null || true
    fi
}

restart_mpv() {
    if [[ -n "$MPV_PID" ]]; then
        kill "$MPV_PID" 2>/dev/null || true
        wait "$MPV_PID" 2>/dev/null || true
    fi
    start_mpv
}

# ============================================================================
# AUTO-REFRESH BACKGROUND TASK
# ============================================================================

start_auto_refresh() {
    (
        while true; do
            sleep 120

            url=$(get_radar_url "$CURRENT")
            if wget -q --timeout=10 -O "$TEMP.new" "$url" 2>/dev/null; then
                mv "$TEMP.new" "$TEMP"
            else
                rm -f "$TEMP.new"
            fi
        done
    ) &

    AUTO_REFRESH_PID=$!
}

# ============================================================================
# MAIN APPLICATION FLOW
# ============================================================================

show_welcome() {
    clear
    echo -e "${C_CYAN}${C_BOLD}"
    echo "╔══════════════════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                                  ║"
    echo "║                    ⚡ ULTIMATE WEATHER RADAR TERMINAL ⚡                         ║"
    echo "║                                                                                  ║"
    echo "║                      Live NOAA Weather Radar Viewer                              ║"
    echo "║                                                                                  ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${C_RESET}\n"

    show_info "Renderer: ${VO:-default (mpv GUI window)}"
    show_info "Starting with Southeast US radar..."
    echo ""
}

read_key() {
    if [ -n "${ZSH_VERSION:-}" ]; then
        IFS= read -rsk1 key
    else
        IFS= read -rsn1 key
    fi
}

main() {
    setup_terminal
    show_welcome

    if ! download_radar; then
        show_error "Failed to initialize. Check your internet connection."
        sleep 3
        exit 1
    fi

    start_mpv
    start_auto_refresh

    echo ""
    draw_controls
    echo ""
    show_info "Radar is now playing. Use the controls above to switch views."
    echo ""

    while true; do
        read_key

        case "$key" in
            c|n|s|w|p|1|2|3|4|5|6|7|8|9|0)
                if [[ -n "$(get_radar_entry "$key")" ]]; then
                    CURRENT="$key"
                    local radar_name
                    radar_name=$(get_radar_info "$CURRENT" | cut -d'|' -f2)
                    echo ""
                    show_info "Switching to $radar_name..."

                    if download_radar; then
                        restart_mpv
                        [[ -n "$AUTO_REFRESH_PID" ]] && kill "$AUTO_REFRESH_PID" 2>/dev/null || true
                        start_auto_refresh
                    fi
                fi
                ;;
            r|R)
                echo ""
                show_info "Manual refresh requested..."
                if download_radar; then
                    restart_mpv
                fi
                ;;
            h|H|\?)
                echo ""
                draw_controls
                echo ""
                ;;
            q|Q)
                echo ""
                show_info "Shutting down radar viewer..."
                cleanup_terminal
                exit 0
                ;;
        esac
    done
}

# ============================================================================
# ENTRY POINT
# ============================================================================

main
