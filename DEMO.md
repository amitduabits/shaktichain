# Demo walkthrough

Shakti-Chain ships a working V2G marketplace demo: a React dashboard, a FastAPI market engine, and a McAfee double-auction clearing loop. The current demo is a **simulation of energy trading**, not a live DISCOM interconnection.

## What a visitor should see

1. Login page with **Enter Demo** (no wallet required). Register to pick a role (EV owner, fleet, aggregator, CPO, DISCOM).
2. Role home: EV owner sees SOC and **Place order**. Other roles have their own home.
3. Market: buy and sell in INR/kWh (not shown for DISCOM).
4. Auction round viewer: sealed bids, clearing price, matched volume.
5. Settlement: stake, unstake, claim rewards (demo ledger).
6. Demo-only **View as** switcher: fleet vehicles, DISCOM feeders, CPO sites, admin reset.
7. DISCOM/admin Reports: city-calibrated simulation (disabled on Pages; needs the local API).

## Public demo

https://amitduabits.github.io/shaktichain/demo/

Click **Enter Demo**. Buy, sell, stake, and reset run in the browser. No wallet and no backend required.

## Fastest local start

From the repository root:

```bash
cd v2g-marketplace
docker compose up --build
```

Then open:

| Surface | URL |
|---|---|
| Marketplace UI | http://localhost |
| API | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |

Demo flags:

- Frontend: `VITE_DEMO_ONLY=true`
- Backend: `ENABLE_DEMO_LOGIN=true` (or `ENVIRONMENT=development`)

On the login page, click **Enter Demo**. Place a buy order, a sell order, then watch the round clear. Use **Reset Demo Data** to return to the seeded ledger.

## Manual start (no Docker)

Terminal 1 — API:

```bash
cd v2g-marketplace
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
set PYTHONPATH=%CD%;%CD%\backend   # PowerShell: $env:PYTHONPATH="$PWD;$PWD\backend"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2 — UI:

```bash
cd v2g-marketplace/frontend
npm install
# .env.development: VITE_API_URL=http://localhost:8000
#                   VITE_DEMO_ONLY=true
npm run dev
```

Open the Vite URL (typically http://localhost:5173).

## Suggested 8-minute industry script

| Minute | Role view | Action |
|---|---|---|
| 0–1 | EV owner | Enter Demo, home, Place order |
| 1–3 | EV owner | Buy + sell, round viewer |
| 3–4 | Fleet | View as Fleet, bulk bid / vehicles |
| 4–5 | DISCOM | View as DISCOM, feeders, no order ticket |
| 5–6 | EV owner | Settlement: stake |
| 6–8 | DISCOM/admin | City sim note (or run if the API is up) |

## What this demo is not

- It does not control a physical bidirectional charger.
- It does not settle against a live DISCOM billing system.
- It does not replace a regulatory sandbox or a CERC/SERC filing.
- Voltage regulation and transformer thermal limits are out of scope; a post-clearing feeder hosting-capacity wrapper is the only grid constraint currently enforced.

Those items are the subject of a DISCOM or CPO pilot, not of this software demonstration.
