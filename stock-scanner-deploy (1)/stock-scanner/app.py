"""
Stock Scanner — Single Repo Deploy on Render
=============================================
• Flask serves the React frontend at  GET /
• Flask serves the live API at        GET /api/stocks  etc.
• Background thread fetches yfinance every 5 minutes

Render settings (ONE repo, ONE service):
  Build command : pip install -r requirements.txt
  Start command : gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1
"""

import os, json, time, threading, logging
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

# ── logging ───────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── config ────────────────────────────────────────────────────
REFRESH_INTERVAL = 300   # seconds  (5 min)
BATCH_SIZE       = 10    # tickers per yf.download call
REQUEST_TIMEOUT  = 25

# ── 170 stock definitions ─────────────────────────────────────
TICKER_META = [
    # TECHNOLOGY HIGH
    ("AAPL","Apple Inc.","Technology","HIGH"),
    ("MSFT","Microsoft Corp.","Technology","HIGH"),
    ("NVDA","NVIDIA Corp.","Technology","HIGH"),
    ("GOOGL","Alphabet Inc.","Technology","HIGH"),
    ("META","Meta Platforms","Technology","HIGH"),
    ("AMD","Advanced Micro Devices","Technology","HIGH"),
    ("INTC","Intel Corp.","Technology","HIGH"),
    ("CRM","Salesforce Inc.","Technology","HIGH"),
    ("ORCL","Oracle Corp.","Technology","HIGH"),
    ("CSCO","Cisco Systems","Technology","HIGH"),
    ("IBM","IBM Corp.","Technology","HIGH"),
    ("QCOM","Qualcomm Inc.","Technology","HIGH"),
    ("TXN","Texas Instruments","Technology","HIGH"),
    ("AVGO","Broadcom Inc.","Technology","HIGH"),
    ("AMAT","Applied Materials","Technology","HIGH"),
    ("MU","Micron Technology","Technology","HIGH"),
    ("LRCX","Lam Research","Technology","HIGH"),
    ("KLAC","KLA Corp.","Technology","HIGH"),
    # TECHNOLOGY AVG
    ("PLTR","Palantir Technologies","Technology","AVG"),
    ("SNOW","Snowflake Inc.","Technology","AVG"),
    ("MDB","MongoDB Inc.","Technology","AVG"),
    ("DDOG","Datadog Inc.","Technology","AVG"),
    ("NET","Cloudflare Inc.","Technology","AVG"),
    ("ZS","Zscaler Inc.","Technology","AVG"),
    ("OKTA","Okta Inc.","Technology","AVG"),
    ("TWLO","Twilio Inc.","Technology","AVG"),
    ("U","Unity Software","Technology","AVG"),
    ("AI","C3.ai Inc.","Technology","AVG"),
    ("PATH","UiPath Inc.","Technology","AVG"),
    ("GTLB","GitLab Inc.","Technology","AVG"),
    ("SOUN","SoundHound AI","Technology","AVG"),
    # CONSUMER HIGH
    ("AMZN","Amazon.com Inc.","Consumer","HIGH"),
    ("TSLA","Tesla Inc.","Consumer","HIGH"),
    ("NFLX","Netflix Inc.","Consumer","HIGH"),
    ("BKNG","Booking Holdings","Consumer","HIGH"),
    ("MCD","McDonald's Corp.","Consumer","HIGH"),
    ("SBUX","Starbucks Corp.","Consumer","HIGH"),
    ("NKE","Nike Inc.","Consumer","HIGH"),
    ("HD","Home Depot Inc.","Consumer","HIGH"),
    ("WMT","Walmart Inc.","Consumer","HIGH"),
    ("TGT","Target Corp.","Consumer","HIGH"),
    ("COST","Costco Wholesale","Consumer","HIGH"),
    ("LOW","Lowe's Companies","Consumer","HIGH"),
    ("GM","General Motors","Consumer","HIGH"),
    ("F","Ford Motor Co.","Consumer","HIGH"),
    # CONSUMER AVG
    ("UBER","Uber Technologies","Consumer","AVG"),
    ("LYFT","Lyft Inc.","Consumer","AVG"),
    ("ABNB","Airbnb Inc.","Consumer","AVG"),
    ("DASH","DoorDash Inc.","Consumer","AVG"),
    ("SHOP","Shopify Inc.","Consumer","AVG"),
    ("ETSY","Etsy Inc.","Consumer","AVG"),
    ("RIVN","Rivian Automotive","Consumer","AVG"),
    ("LCID","Lucid Group","Consumer","AVG"),
    ("CHWY","Chewy Inc.","Consumer","AVG"),
    ("W","Wayfair Inc.","Consumer","AVG"),
    # FINANCIALS HIGH
    ("JPM","JPMorgan Chase","Financials","HIGH"),
    ("BAC","Bank of America","Financials","HIGH"),
    ("WFC","Wells Fargo","Financials","HIGH"),
    ("GS","Goldman Sachs","Financials","HIGH"),
    ("MS","Morgan Stanley","Financials","HIGH"),
    ("V","Visa Inc.","Financials","HIGH"),
    ("MA","Mastercard Inc.","Financials","HIGH"),
    ("AXP","American Express","Financials","HIGH"),
    ("BLK","BlackRock Inc.","Financials","HIGH"),
    ("C","Citigroup Inc.","Financials","HIGH"),
    ("USB","U.S. Bancorp","Financials","HIGH"),
    ("SCHW","Charles Schwab","Financials","HIGH"),
    # FINANCIALS AVG
    ("PYPL","PayPal Holdings","Financials","AVG"),
    ("SQ","Block Inc.","Financials","AVG"),
    ("COIN","Coinbase Global","Financials","AVG"),
    ("SOFI","SoFi Technologies","Financials","AVG"),
    ("HOOD","Robinhood Markets","Financials","AVG"),
    ("AFRM","Affirm Holdings","Financials","AVG"),
    ("UPST","Upstart Holdings","Financials","AVG"),
    ("NU","Nu Holdings","Financials","AVG"),
    # HEALTHCARE HIGH
    ("JNJ","Johnson & Johnson","Healthcare","HIGH"),
    ("UNH","UnitedHealth Group","Healthcare","HIGH"),
    ("PFE","Pfizer Inc.","Healthcare","HIGH"),
    ("ABBV","AbbVie Inc.","Healthcare","HIGH"),
    ("MRK","Merck & Co.","Healthcare","HIGH"),
    ("LLY","Eli Lilly & Co.","Healthcare","HIGH"),
    ("BMY","Bristol-Myers Squibb","Healthcare","HIGH"),
    ("GILD","Gilead Sciences","Healthcare","HIGH"),
    ("AMGN","Amgen Inc.","Healthcare","HIGH"),
    ("CVS","CVS Health Corp.","Healthcare","HIGH"),
    # HEALTHCARE AVG
    ("MRNA","Moderna Inc.","Healthcare","AVG"),
    ("BNTX","BioNTech SE","Healthcare","AVG"),
    ("NVAX","Novavax Inc.","Healthcare","AVG"),
    ("TDOC","Teladoc Health","Healthcare","AVG"),
    ("HIMS","Hims & Hers Health","Healthcare","AVG"),
    ("RXRX","Recursion Pharma","Healthcare","AVG"),
    # ENERGY HIGH
    ("XOM","ExxonMobil Corp.","Energy","HIGH"),
    ("CVX","Chevron Corp.","Energy","HIGH"),
    ("COP","ConocoPhillips","Energy","HIGH"),
    ("SLB","SLB (Schlumberger)","Energy","HIGH"),
    ("EOG","EOG Resources","Energy","HIGH"),
    ("PSX","Phillips 66","Energy","HIGH"),
    ("MPC","Marathon Petroleum","Energy","HIGH"),
    # ENERGY AVG
    ("OXY","Occidental Petroleum","Energy","AVG"),
    ("DVN","Devon Energy","Energy","AVG"),
    ("FANG","Diamondback Energy","Energy","AVG"),
    ("AR","Antero Resources","Energy","AVG"),
    ("PLUG","Plug Power Inc.","Energy","AVG"),
    ("ENPH","Enphase Energy","Energy","AVG"),
    ("FSLR","First Solar Inc.","Energy","AVG"),
    ("BLNK","Blink Charging","Energy","AVG"),
    ("CHPT","ChargePoint Holdings","Energy","AVG"),
    # INDUSTRIALS HIGH
    ("BA","Boeing Co.","Industrials","HIGH"),
    ("CAT","Caterpillar Inc.","Industrials","HIGH"),
    ("HON","Honeywell Intl.","Industrials","HIGH"),
    ("GE","GE Aerospace","Industrials","HIGH"),
    ("LMT","Lockheed Martin","Industrials","HIGH"),
    ("RTX","RTX Corp.","Industrials","HIGH"),
    ("UPS","United Parcel Service","Industrials","HIGH"),
    ("FDX","FedEx Corp.","Industrials","HIGH"),
    ("DE","Deere & Company","Industrials","HIGH"),
    ("MMM","3M Company","Industrials","HIGH"),
    # INDUSTRIALS AVG
    ("AAL","American Airlines","Industrials","AVG"),
    ("UAL","United Airlines","Industrials","AVG"),
    ("DAL","Delta Air Lines","Industrials","AVG"),
    ("CCL","Carnival Corp.","Industrials","AVG"),
    ("RCL","Royal Caribbean","Industrials","AVG"),
    ("NCLH","Norwegian Cruise","Industrials","AVG"),
    # COMMUNICATION HIGH
    ("DIS","Walt Disney Co.","Communication","HIGH"),
    ("CMCSA","Comcast Corp.","Communication","HIGH"),
    ("T","AT&T Inc.","Communication","HIGH"),
    ("VZ","Verizon Communications","Communication","HIGH"),
    ("TMUS","T-Mobile US","Communication","HIGH"),
    # COMMUNICATION AVG
    ("SNAP","Snap Inc.","Communication","AVG"),
    ("PINS","Pinterest Inc.","Communication","AVG"),
    ("RDDT","Reddit Inc.","Communication","AVG"),
    ("SPOT","Spotify Technology","Communication","AVG"),
    ("WBD","Warner Bros. Discovery","Communication","AVG"),
    ("PARA","Paramount Global","Communication","AVG"),
    # MATERIALS HIGH
    ("NEM","Newmont Corp.","Materials","HIGH"),
    ("FCX","Freeport-McMoRan","Materials","HIGH"),
    ("LIN","Linde plc","Materials","HIGH"),
    ("APD","Air Products & Chemicals","Materials","HIGH"),
    ("DOW","Dow Inc.","Materials","HIGH"),
    # MATERIALS AVG
    ("AA","Alcoa Corp.","Materials","AVG"),
    ("CLF","Cleveland-Cliffs","Materials","AVG"),
    ("X","U.S. Steel Corp.","Materials","AVG"),
    ("MP","MP Materials","Materials","AVG"),
    # REAL ESTATE HIGH
    ("AMT","American Tower","Real Estate","HIGH"),
    ("PLD","Prologis Inc.","Real Estate","HIGH"),
    ("EQIX","Equinix Inc.","Real Estate","HIGH"),
    ("SPG","Simon Property Group","Real Estate","HIGH"),
    ("CCI","Crown Castle Inc.","Real Estate","HIGH"),
    # REAL ESTATE AVG
    ("Z","Zillow Group","Real Estate","AVG"),
    ("RDFN","Redfin Corp.","Real Estate","AVG"),
    ("CBRE","CBRE Group","Real Estate","AVG"),
    # UTILITIES HIGH
    ("NEE","NextEra Energy","Utilities","HIGH"),
    ("DUK","Duke Energy","Utilities","HIGH"),
    ("SO","Southern Company","Utilities","HIGH"),
    ("D","Dominion Energy","Utilities","HIGH"),
    ("AEP","American Electric Power","Utilities","HIGH"),
    # UTILITIES AVG
    ("RUN","Sunrun Inc.","Utilities","AVG"),
    ("BE","Bloom Energy","Utilities","AVG"),
    ("STEM","Stem Inc.","Utilities","AVG"),
    # CRYPTO
    ("MSTR","MicroStrategy Inc.","Crypto","HIGH"),
    ("MARA","Marathon Digital","Crypto","AVG"),
    ("RIOT","Riot Platforms","Crypto","AVG"),
    ("HUT","Hut 8 Corp.","Crypto","AVG"),
    ("CLSK","CleanSpark Inc.","Crypto","AVG"),
    ("CIFR","Cipher Mining","Crypto","AVG"),
    # ETFs
    ("SPY","SPDR S&P 500 ETF","ETF","HIGH"),
    ("QQQ","Invesco QQQ Trust","ETF","HIGH"),
    ("IWM","iShares Russell 2000","ETF","HIGH"),
    ("DIA","SPDR Dow Jones ETF","ETF","HIGH"),
    ("GLD","SPDR Gold Shares","ETF","HIGH"),
    ("SLV","iShares Silver Trust","ETF","AVG"),
    ("TQQQ","ProShares UltraPro QQQ","ETF","AVG"),
    ("SQQQ","ProShares Short QQQ","ETF","AVG"),
    ("ARKK","ARK Innovation ETF","ETF","AVG"),
    ("XLF","Financial Select SPDR","ETF","AVG"),
    ("XLE","Energy Select SPDR","ETF","AVG"),
    ("XLK","Technology Select SPDR","ETF","AVG"),
]

META_MAP  = {sym:(name,sector,tier) for sym,name,sector,tier in TICKER_META}
ALL_SYMS  = [t[0] for t in TICKER_META]

# ── VWAP ──────────────────────────────────────────────────────
def calc_vwap(df):
    if df.empty or df["Volume"].sum() == 0:
        return 0.0
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    return float((tp * df["Volume"]).sum() / df["Volume"].sum())

# ── fetch one batch ───────────────────────────────────────────
def fetch_batch(symbols):
    out = {}
    try:
        raw = yf.download(
            tickers=" ".join(symbols),
            period="1d",
            interval="5m",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            timeout=REQUEST_TIMEOUT,
        )
    except Exception as e:
        log.warning(f"Batch error: {e}")
        return out

    for sym in symbols:
        try:
            df = raw.copy() if len(symbols) == 1 else raw[sym].copy()
            df.dropna(subset=["Close","Volume"], inplace=True)
            if df.empty:
                continue

            close  = float(df["Close"].iloc[-1])
            volume = int(df["Volume"].sum())
            high   = float(df["High"].max())
            low    = float(df["Low"].min())
            open_  = float(df["Open"].iloc[0])
            vwap   = calc_vwap(df)

            prev_close = close
            try:
                fi = yf.Ticker(sym).fast_info
                if hasattr(fi,"previous_close") and fi.previous_close:
                    prev_close = float(fi.previous_close)
            except Exception:
                pass

            change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0.0
            name, sector, tier = META_MAP.get(sym, (sym,"Unknown","AVG"))

            out[sym] = {
                "symbol":     sym,
                "name":       name,
                "sector":     sector,
                "tier":       tier,
                "price":      round(close, 4),
                "open":       round(open_, 4),
                "high":       round(high, 4),
                "low":        round(low, 4),
                "prev_close": round(prev_close, 4),
                "vwap":       round(vwap, 4),
                "volume":     volume,
                "change_pct": round(change_pct, 4),
                "above_vwap": close > vwap,
                "bars":       len(df),
            }
        except Exception as e:
            log.warning(f"  ✗ {sym}: {e}")
    return out

def fetch_all():
    result = {}
    batches = [ALL_SYMS[i:i+BATCH_SIZE] for i in range(0, len(ALL_SYMS), BATCH_SIZE)]
    log.info(f"Fetching {len(ALL_SYMS)} symbols in {len(batches)} batches …")
    for i, batch in enumerate(batches, 1):
        log.info(f"  Batch {i}/{len(batches)}: {batch}")
        result.update(fetch_batch(batch))
        time.sleep(0.5)
    log.info(f"Done: {len(result)}/{len(ALL_SYMS)} OK")
    return list(result.values())

# ── in-memory cache ───────────────────────────────────────────
cache = {"stocks":[], "last_updated":None, "status":"initializing", "fetch_count":0}
lock  = threading.Lock()

def refresh_loop():
    while True:
        t0 = time.time()
        try:
            data = fetch_all()
            with lock:
                cache["stocks"]       = data
                cache["last_updated"] = datetime.now(timezone.utc).isoformat()
                cache["fetch_count"] += 1
                cache["status"]       = "ok"
            log.info(f"Cache updated — {len(data)} stocks in {time.time()-t0:.1f}s")
        except Exception as e:
            with lock:
                cache["status"] = "error"
            log.error(f"refresh_loop: {e}")
        time.sleep(max(0, REFRESH_INTERVAL - (time.time()-t0)))

# ── Flask ─────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app, origins="*")

# Serve the React frontend
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

# API routes
@app.route("/api/stocks")
def api_stocks():
    with lock:
        return jsonify({
            "stocks":        cache["stocks"],
            "last_updated":  cache["last_updated"],
            "total":         len(cache["stocks"]),
            "fetch_count":   cache["fetch_count"],
            "status":        cache["status"],
            "refresh_every": REFRESH_INTERVAL,
        })

@app.route("/api/stocks/<symbol>")
def api_stock(symbol):
    sym = symbol.upper()
    with lock:
        hit = next((s for s in cache["stocks"] if s["symbol"]==sym), None)
    if not hit:
        return jsonify({"error":f"{sym} not found"}), 404
    return jsonify(hit)

@app.route("/api/sectors")
def api_sectors():
    with lock:
        stocks = cache["stocks"]
    smap = {}
    for s in stocks:
        sec = s["sector"]
        if sec not in smap:
            smap[sec] = {"count":0,"total_change":0.0,"total_volume":0,"above_vwap":0}
        smap[sec]["count"]        += 1
        smap[sec]["total_change"] += s["change_pct"]
        smap[sec]["total_volume"] += s["volume"]
        smap[sec]["above_vwap"]   += 1 if s["above_vwap"] else 0
    result = []
    for sec, d in smap.items():
        n = d["count"] or 1
        result.append({
            "sector":          sec,
            "count":           d["count"],
            "avg_change":      round(d["total_change"]/n, 4),
            "total_vol":       d["total_volume"],
            "above_vwap_pct":  round(d["above_vwap"]/n*100, 1),
        })
    return jsonify(sorted(result, key=lambda x: x["total_vol"], reverse=True))

@app.route("/api/health")
def api_health():
    with lock:
        return jsonify({
            "status":       cache["status"],
            "last_updated": cache["last_updated"],
            "total_stocks": len(cache["stocks"]),
            "fetch_count":  cache["fetch_count"],
        })

# start background thread (works for both `python app.py` and gunicorn)
_thread = threading.Thread(target=refresh_loop, daemon=True)
_thread.start()
log.info("Background refresh thread started.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
