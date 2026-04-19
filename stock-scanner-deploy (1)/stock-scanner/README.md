# Stock Scanner — Single Repo, Deploy on Render

Real yfinance data · 170 stocks · VWAP + Volume · 5-min auto-refresh

## Repo structure (upload ALL of this to your ONE GitHub repo)

```
your-repo/
├── app.py               ← Flask server + yfinance scraper + API
├── requirements.txt     ← Python deps
├── render.yaml          ← Render auto-config
└── static/
    └── index.html       ← React dashboard (served by Flask at /)
```

---

## Deploy on Render (3 steps)

### 1. Push all files to your GitHub repo
Upload every file exactly as-is, keeping the `static/` folder.

### 2. Create a Web Service on Render
- Go to https://render.com → New → Web Service
- Connect your GitHub repo
- Render will auto-detect `render.yaml` and fill everything in
- If it doesn't auto-fill, use:
  - **Environment**: Python
  - **Build command**: `pip install -r requirements.txt`
  - **Start command**: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1`
  - **Plan**: Free

### 3. Click "Create Web Service" — done!

Your live URL will be: `https://stock-scanner.onrender.com` (or similar)
Open it in a browser — the dashboard loads automatically.

---

## What happens after deploy

1. On startup the backend immediately starts fetching all 170 stocks via yfinance
2. First load takes ~60–90 seconds (batched download of 170 tickers)
3. After that, data refreshes every **5 minutes** automatically
4. The dashboard polls the API and updates its display every 5 minutes
5. You can hit "⟳ Refresh Now" to pull latest data immediately

## API endpoints (also available)

| URL | What it returns |
|-----|----------------|
| `/` | The React dashboard |
| `/api/stocks` | All 170 stocks — price, VWAP, volume, change%, signal |
| `/api/stocks/AAPL` | Single stock detail |
| `/api/sectors` | Per-sector aggregates |
| `/api/health` | Server status + last fetch time |

## Keep it awake (free tier tip)

Render free services sleep after 15 min of no traffic.
Set up a free pinger at https://uptimerobot.com to hit your URL every 5 min.
