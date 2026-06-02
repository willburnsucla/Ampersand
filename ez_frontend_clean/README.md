# Ampersand Frontend

Minimal Vite + React frontend for the Ampersand prototype.

## Setup

```bash
pnpm install
pnpm run dev
```

## Build

```bash
pnpm run build
```

## Running with the backend

The frontend needs the mock backend running first. Open two terminals:

**Terminal 1 — backend** (from repo root):

```bash
export PATH="$HOME/.local/bin:$PATH"
cd backend
AMPERSAND_BACKEND_MODE=mock uv run uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend** (from `ez_frontend_clean/`):

```bash
pnpm dev
```

Then open `http://localhost:5173`.

> If `uv: command not found`, run `curl -LsSf https://astral.sh/uv/install.sh | sh` first, then add `export PATH="$HOME/.local/bin:$PATH"` to your `~/.zshrc`.Sonnet 4.6 LowClaude is AI and can make mistakes. Please double-check responses.