import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time
import os
from curl_cffi import requests as cffi_requests
warnings.filterwarnings("ignore")

# Impersonate Chrome to bypass SSL cert issues and Yahoo rate limits
SESSION = cffi_requests.Session(impersonate='chrome', verify=False)

# Base directory — works both locally and on GitHub Actions
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Nifty Midcap 150 symbols (Yahoo Finance .NS format) ──────────────────────
SYMBOLS = [
    "ABCAPITAL","ABFRL","AARTIIND","APLAPOLLO","APOLLOHOSP","ASTRAL","AUBANK",
    "BAJAJHLDNG","BALKRISIND","BANDHANBNK","BANKBARODA","BANKINDIA","BEL","BHARATFORG",
    "BHEL","BIOCON","BLUEDART","BOSCHLTD","BRIGADE","CANBK","CANFINHOME","CARBORUNIV",
    "CASTROLIND","CEATLTD","CENTRALBK","CHOLAFIN","CIPLA","COFORGE","COLPAL",
    "CONCOR","CROMPTON","CUMMINSIND","CYIENT","DABUR","DALBHARAT","DATAMATICS",
    "DCMSHRIRAM","DEEPAKNI","DELHIVERY","DELTACORP","DMART","DRREDDY","EDELWEISS",
    "EMAMILTD","ENDURANCE","ENGINERSIN","ESCORTS","EXIDEIND","FEDERALBNK","FINCABLES",
    "FLUOROCHEM","FORTIS","GAIL","GLENMARK","GMRINFRA","GNFC","GODREJAGRO",
    "GODREJCP","GODREJIND","GPIL","GRANULES","GSPL","GUJGASLTD","HBLPOWER",
    "HDFCAMC","HEROMOTOCO","HINDPETRO","HONAUT","HUDCO","IBREALEST","IDBI",
    "IDFCFIRSTB","IEX","IFCI","IGL","INDHOTEL","INDIACEM","INDIAMART","INDUSINDBK",
    "INOXWIND","IOB","IRCTC","IRFC","ISEC","JKCEMENT","JKPAPER","JMFINANCIL",
    "JSL","JUBLFOOD","JUBLINGREA","KAJARIACER","KALPATPOWR","KANSAINER","KARURVYSYA",
    "KPITTECH","KRBL","KSCL","L&TFH","LALPATHLAB","LAURUSLABS","LICHSGFIN",
    "LINDEINDIA","LTTS","LUPIN","M&MFIN","MANAPPURAM","MARICO","MAXHEALTH",
    "MCX","METROPOLIS","MFSL","MIDHANI","MPHASIS","MRF","MUTHOOTFIN","NATCOPHARM",
    "NAUKRI","NBCC","NCC","NESTLEIND","NMDC","NTPC","OBEROIRLTY","OIL",
    "OLECTRA","PAGEIND","PATANJALI","PERSISTENT","PETRONET","PFC","PFIZER",
    "PHOENIXLTD","PIDILITIND","PIIND","POLYCAB","POONAWALLA","POWERGRID","PRESTIGE",
    "PVRINOX","RAJESHEXPO","RALLIS","RAMCOCEM","RECLTD","REDINGTON","RITES",
    "SAIL","SBICARD","SBILIFE","SCHAEFFLER","SCI","SHREECEM","SIEMENS",
    "SKFINDIA","SONACOMS","SRTRANSFIN","STARHEALTH","SUNTV","SUPREMEIND",
    "SUZLON","SYNGENE","TANLA","TATACOMM","TATAELXSI","TATAINVEST","TATAPOWER",
    "TCNSBRANDS","TEAMLEASE","TECHNM","TIINDIA","TIMKEN","TORNTPHARM","TRENT",
    "TRIDENT","TRITURBINE","TVSHLTD","TVSMOTOR","UBL","UNIONBANK","UNITDSPR",
    "VGUARD","VINATIORGA","VOLTAS","VSTIND","WELCORP","WHIRLPOOL","ZEEL","ZOMATO"
]
# Keep only ASCII symbols
SYMBOLS = [s for s in SYMBOLS if all(c.isascii() and (c.isalpha() or c == "&") for c in s)]

def calculate_rsi(prices, period=14):
    """Wilder's smoothed RSI"""
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def find_pivots(series, window=5):
    """Find pivot highs and lows using a rolling window"""
    pivots_high, pivots_low = [], []
    arr = series.values
    for i in range(window, len(arr) - window):
        if arr[i] == max(arr[i-window:i+window+1]):
            pivots_high.append(i)
        if arr[i] == min(arr[i-window:i+window+1]):
            pivots_low.append(i)
    return pivots_high, pivots_low

def detect_divergence(df, symbol):
    """Detect RSI divergences and apply 5% origin filter"""
    if len(df) < 40:
        return []

    df = df.copy()
    df['RSI'] = calculate_rsi(df['Close'])
    df.dropna(subset=['RSI'], inplace=True)

    if len(df) < 20:
        return []

    prices = df['Close']
    rsi    = df['RSI']
    current_price = float(prices.iloc[-1])
    current_rsi   = float(rsi.iloc[-1])

    ph, pl = find_pivots(prices, window=5)
    n       = len(df)
    RECENCY = 15   # pivot must be within last 15 candles (~2 trading days)
    raw_results = []

    # ── BEARISH: price higher high, RSI lower high ───────────────────────────
    for i in range(1, len(ph)):
        i1, i2 = ph[i-1], ph[i]

        # 1. Recency: second pivot must be recent
        if i2 < n - RECENCY:
            continue

        p1, p2 = float(prices.iloc[i1]), float(prices.iloc[i2])
        r1, r2 = float(rsi.iloc[i1]),   float(rsi.iloc[i2])
        if p2 > p1 and r2 < r1:                          # divergence confirmed
            origin = p2
            # 2. Directional: bearish origin is a HIGH — if price already
            #    fell >3%, divergence resolved; skip
            if current_price < origin * 0.97:
                continue
            dist = abs(current_price - origin) / origin
            if dist <= 0.05:                             # 3. 5% proximity
                raw_results.append({
                    "Symbol":        symbol,
                    "Signal":        "BEARISH",
                    "Origin Price":  round(origin, 2),
                    "Current Price": round(current_price, 2),
                    "Distance %":    round(dist * 100, 2),
                    "RSI @ Origin":  round(r2, 1),
                    "Current RSI":   round(current_rsi, 1),
                    "Pivot Time":    str(df.index[i2]),
                    "_pivot_idx":    i2,
                })

    # ── BULLISH: price lower low, RSI higher low ──────────────────────────────
    for i in range(1, len(pl)):
        i1, i2 = pl[i-1], pl[i]

        # 1. Recency
        if i2 < n - RECENCY:
            continue

        p1, p2 = float(prices.iloc[i1]), float(prices.iloc[i2])
        r1, r2 = float(rsi.iloc[i1]),   float(rsi.iloc[i2])
        if p2 < p1 and r2 > r1:                          # divergence confirmed
            origin = p2
            # 2. Directional: bullish origin is a LOW — if price already
            #    rallied >3%, divergence resolved; skip
            if current_price > origin * 1.03:
                continue
            dist = abs(current_price - origin) / origin
            if dist <= 0.05:                             # 3. 5% proximity
                raw_results.append({
                    "Symbol":        symbol,
                    "Signal":        "BULLISH",
                    "Origin Price":  round(origin, 2),
                    "Current Price": round(current_price, 2),
                    "Distance %":    round(dist * 100, 2),
                    "RSI @ Origin":  round(r2, 1),
                    "Current RSI":   round(current_rsi, 1),
                    "Pivot Time":    str(df.index[i2]),
                    "_pivot_idx":    i2,
                })

    # 4. Deduplicate: per symbol+signal keep only the MOST RECENT pivot
    seen = {}
    for r in raw_results:
        key = (r["Symbol"], r["Signal"])
        if key not in seen or r["_pivot_idx"] > seen[key]["_pivot_idx"]:
            seen[key] = r
    results = list(seen.values())
    for r in results:
        del r["_pivot_idx"]

    return results

def run_scan():
    print(f"\n{'='*65}")
    print(f"  NIFTY MIDCAP 150 — RSI(14) HOURLY DIVERGENCE SCANNER")
    print(f"  Run time : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Filter   : Current price within 5% of divergence origin")
    print(f"{'='*65}\n")

    tickers = [s + ".NS" for s in SYMBOLS]
    all_results = []
    failed = []

    print(f"Fetching hourly data for {len(tickers)} stocks...\n")

    for symbol, ticker in zip(SYMBOLS, tickers):
        try:
            t = yf.Ticker(ticker, session=SESSION)
            df = t.history(period="10d", interval="1h", auto_adjust=True)

            if df is None or len(df) < 20:
                failed.append(symbol)
                continue

            df = df[["Open","High","Low","Close","Volume"]].copy()
            df.dropna(subset=["Close"], inplace=True)

            if len(df) < 20:
                failed.append(symbol)
                continue

            hits = detect_divergence(df, symbol)
            all_results.extend(hits)
            print(f"  OK {symbol:<15} {len(df)} candles  ({len(all_results)} hits so far)", end="\r")
            time.sleep(0.3)  # gentle rate limiting

        except Exception as e:
            failed.append(symbol)
            continue

    fetched = len(tickers) - len(failed)
    print(f"\nFetched data for {fetched}/{len(tickers)} stocks. Skipped: {len(failed)}")

    # ── Print results ─────────────────────────────────────────────────────────
    if all_results:
        result_df = pd.DataFrame(all_results)
        result_df['_sort'] = result_df['Signal'].apply(lambda x: 0 if 'BULLISH' in x else 1)
        result_df.sort_values(['_sort','Distance %'], inplace=True)
        result_df.drop('_sort', axis=1, inplace=True)
        result_df.reset_index(drop=True, inplace=True)

        bullish = result_df[result_df['Signal'].str.contains('BULLISH')].copy()
        bearish = result_df[result_df['Signal'].str.contains('BEARISH')].copy()

        # Use ASCII signal names for Windows terminal
        bullish['Signal'] = 'BULLISH'
        bearish['Signal'] = 'BEARISH'

        print(f"\n[BULLISH DIVERGENCES] ({len(bullish)} found)")
        print("-" * 65)
        if len(bullish):
            print(bullish.to_string(index=False))
        else:
            print("  None found.")

        print(f"\n[BEARISH DIVERGENCES] ({len(bearish)} found)")
        print("-" * 65)
        if len(bearish):
            print(bearish.to_string(index=False))
        else:
            print("  None found.")

        result_df.to_csv(os.path.join(BASE_DIR, "divergence_results.csv"), index=False)
        generate_html(result_df, fetched, len(tickers), datetime.now())
        print(f"\nResults saved to divergence_results.csv and index.html")
    else:
        generate_html(pd.DataFrame(), fetched, len(tickers), datetime.now())
        print("No divergences found. index.html updated.")

    if failed:
        print(f"Skipped symbols: {', '.join(failed[:15])}{'...' if len(failed)>15 else ''}")

    print(f"\n{'='*65}\n")
    return all_results

def generate_html(result_df, fetched, total, run_time):
    """Generate a clean, shareable HTML report."""

    def make_rows(df, signal_type):
        if df.empty:
            return f'<tr><td colspan="7" style="text-align:center;color:#888;padding:20px;">No {signal_type} divergences found today.</td></tr>'
        rows = ""
        for _, r in df.iterrows():
            dist = float(r["Distance %"])
            # Color intensity based on distance — closer = brighter
            if signal_type == "BULLISH":
                bg = f"rgba(34,197,94,{max(0.08, 0.35 - dist*0.05):.2f})"
                badge = '<span style="background:#16a34a;color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700;">BULLISH</span>'
            else:
                bg = f"rgba(239,68,68,{max(0.08, 0.35 - dist*0.05):.2f})"
                badge = '<span style="background:#dc2626;color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700;">BEARISH</span>'
            rows += f"""
            <tr style="background:{bg};">
              <td style="font-weight:700;font-size:14px;">{r['Symbol']}</td>
              <td>{badge}</td>
              <td>&#8377;{r['Origin Price']:,.2f}</td>
              <td>&#8377;{r['Current Price']:,.2f}</td>
              <td><b>{dist:.2f}%</b></td>
              <td>{r['RSI @ Origin']}</td>
              <td>{r['Current RSI']}</td>
              <td style="font-size:11px;color:#666;">{str(r['Pivot Time'])[:16]}</td>
            </tr>"""
        return rows

    bullish_df = result_df[result_df['Signal'].str.contains('BULLISH')] if not result_df.empty else pd.DataFrame()
    bearish_df = result_df[result_df['Signal'].str.contains('BEARISH')] if not result_df.empty else pd.DataFrame()

    bullish_rows = make_rows(bullish_df, "BULLISH")
    bearish_rows = make_rows(bearish_df, "BEARISH")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nifty Midcap 150 - RSI Divergence Scanner</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px; }}
  .header {{ text-align: center; margin-bottom: 32px; }}
  .header h1 {{ font-size: 24px; font-weight: 800; color: #f8fafc; letter-spacing: -0.5px; }}
  .header p {{ color: #94a3b8; margin-top: 6px; font-size: 13px; }}
  .stats {{ display: flex; gap: 16px; justify-content: center; margin-bottom: 32px; flex-wrap: wrap; }}
  .stat {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 16px 28px; text-align: center; }}
  .stat .num {{ font-size: 28px; font-weight: 800; }}
  .stat .lbl {{ font-size: 12px; color: #94a3b8; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .bullish .num {{ color: #4ade80; }}
  .bearish .num {{ color: #f87171; }}
  .neutral .num {{ color: #60a5fa; }}
  .section {{ background: #1e293b; border: 1px solid #334155; border-radius: 16px; margin-bottom: 28px; overflow: hidden; }}
  .section-header {{ padding: 16px 20px; border-bottom: 1px solid #334155; display: flex; align-items: center; gap: 10px; }}
  .section-header h2 {{ font-size: 16px; font-weight: 700; }}
  .bullish-header {{ background: rgba(34,197,94,0.1); }}
  .bullish-header h2 {{ color: #4ade80; }}
  .bearish-header {{ background: rgba(239,68,68,0.1); }}
  .bearish-header h2 {{ color: #f87171; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ padding: 10px 14px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; background: #0f172a; border-bottom: 1px solid #334155; }}
  td {{ padding: 10px 14px; font-size: 13px; border-bottom: 1px solid rgba(255,255,255,0.04); }}
  tr:last-child td {{ border-bottom: none; }}
  .footer {{ text-align: center; color: #475569; font-size: 12px; margin-top: 24px; }}
  .dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
  .dot-green {{ background: #4ade80; }}
  .dot-red {{ background: #f87171; }}
</style>
</head>
<body>
<div class="header">
  <h1>Nifty Midcap 150 &mdash; RSI(14) Hourly Divergence Scanner</h1>
  <p>Run: {run_time.strftime('%d %b %Y, %I:%M %p IST')} &nbsp;|&nbsp; Stocks scanned: {fetched}/{total} &nbsp;|&nbsp; Filter: current price within 5% of divergence origin</p>
</div>

<div class="stats">
  <div class="stat bullish"><div class="num">{len(bullish_df)}</div><div class="lbl">Bullish Signals</div></div>
  <div class="stat bearish"><div class="num">{len(bearish_df)}</div><div class="lbl">Bearish Signals</div></div>
  <div class="stat neutral"><div class="num">{fetched}</div><div class="lbl">Stocks Scanned</div></div>
</div>

<div class="section">
  <div class="section-header bullish-header">
    <span class="dot dot-green"></span>
    <h2>Bullish Divergences ({len(bullish_df)})</h2>
    <span style="margin-left:auto;font-size:12px;color:#4ade80;">Price lower low &amp; RSI higher low &rarr; potential reversal up</span>
  </div>
  <table>
    <thead><tr><th>Symbol</th><th>Signal</th><th>Origin Price</th><th>Current Price</th><th>Distance</th><th>RSI @ Origin</th><th>Current RSI</th><th>Pivot Time</th></tr></thead>
    <tbody>{bullish_rows}</tbody>
  </table>
</div>

<div class="section">
  <div class="section-header bearish-header">
    <span class="dot dot-red"></span>
    <h2>Bearish Divergences ({len(bearish_df)})</h2>
    <span style="margin-left:auto;font-size:12px;color:#f87171;">Price higher high &amp; RSI lower high &rarr; potential reversal down</span>
  </div>
  <table>
    <thead><tr><th>Symbol</th><th>Signal</th><th>Origin Price</th><th>Current Price</th><th>Distance</th><th>RSI @ Origin</th><th>Current RSI</th><th>Pivot Time</th></tr></thead>
    <tbody>{bearish_rows}</tbody>
  </table>
</div>

<div class="footer">
  Generated by Nifty Midcap RSI Divergence Scanner &nbsp;&bull;&nbsp; Data via Yahoo Finance &nbsp;&bull;&nbsp; For informational purposes only, not investment advice.
</div>
</body>
</html>"""

    path = os.path.join(BASE_DIR, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML report saved to {path}")

if __name__ == "__main__":
    run_scan()
