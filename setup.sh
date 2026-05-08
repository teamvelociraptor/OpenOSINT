#!/usr/bin/env bash
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
RESET='\033[0m'
BOLD='\033[1m'

print_banner() {
    echo -e "${CYAN}"
    echo ' ██████╗ ██████╗ ███████╗███╗   ██╗ ██████╗ ███████╗██╗███╗   ██╗████████╗'
    echo '██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝'
    echo '██║   ██║██████╔╝█████╗  ██╔██╗ ██║██║   ██║███████╗██║██╔██╗ ██║   ██║   '
    echo '██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║██║   ██║╚════██║██║██║╚██╗██║   ██║   '
    echo '╚██████╔╝██║     ███████╗██║ ╚████║╚██████╔╝███████║██║██║ ╚████║   ██║   '
    echo ' ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝  '
    echo -e "${RESET}"
    echo -e "${BOLD}  AI-Powered Open Source Intelligence Agent${RESET}"
    echo -e "  ${CYAN}https://github.com/openosint/openosint${RESET}"
    echo ""
}

step() { echo -e "${CYAN}  ›${RESET} $1"; }
ok()   { echo -e "${GREEN}  ✓${RESET} $1"; }
warn() { echo -e "${YELLOW}  !${RESET} $1"; }
fail() { echo -e "${RED}  ✗${RESET} $1"; exit 1; }

print_banner

# ── Python version check ──────────────────────────────────────────────
step "Checking Python version..."
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MAJOR=${VER%%.*}; MINOR=${VER##*.}
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON_CMD=$cmd
            break
        fi
    fi
done
[ -z "$PYTHON_CMD" ] && fail "Python 3.10+ is required. Install it from https://python.org"
ok "Found Python $VER ($PYTHON_CMD)"

# ── Virtual environment ───────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    step "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
    ok "Created .venv"
else
    ok "Virtual environment already exists"
fi

source .venv/bin/activate

# ── Install dependencies ──────────────────────────────────────────────
step "Installing dependencies..."
pip install --upgrade pip -q
pip install -e ".[dev]" -q
ok "Dependencies installed"

# ── Environment file ──────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    step "Creating .env from template..."
    cp .env.example .env
    warn "Edit .env and set your ANTHROPIC_API_KEY before running"
else
    ok ".env already exists"
fi

# ── Done ──────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  Installation complete!${RESET}"
echo ""
echo -e "  ${BOLD}Quick start:${RESET}"
echo -e "    ${CYAN}source .venv/bin/activate${RESET}"
echo -e "    ${CYAN}openosint${RESET}                          # interactive mode"
echo -e "    ${CYAN}openosint investigate john@example.com${RESET}  # one-shot"
echo ""
echo -e "  ${BOLD}Set your API key:${RESET}"
echo -e "    export ANTHROPIC_API_KEY=sk-ant-..."
echo "    # or edit .env"
echo ""
