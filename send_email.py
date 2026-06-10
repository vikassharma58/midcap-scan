"""
send_email.py — Sends daily divergence scan summary via Resend API.
Called by GitHub Actions after scan.py completes.

Requires env vars:
  RESEND_API_KEY — API key from resend.com (free tier)
  RECIPIENT      — destination address (default: vikassharma58@gmail.com)
"""

import os
import csv
import requests
from datetime import datetime

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
CSV_PATH       = os.path.join(BASE_DIR, "divergence_results.csv")
PAGES_URL      = "https://vikassharma58.github.io/midcap-scan/"

RESEND_API_KEY = os.environ["RESEND_API_KEY"].strip()
RECIPIENT      = os.environ.get("RECIPIENT", "vikassharma58@gmail.com").strip()


def load_results():
    bullish, bearish = [], []
    if not os.path.exists(CSV_PATH):
        return bullish, bearish
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if "BULLISH" in row.get("Signal", "").upper():
                bullish.append(row)
            elif "BEARISH" in row.get("Signal", "").upper():
                bearish.append(row)
    return bullish, bearish


def make_table_rows(rows, signal_type):
    if not rows:
        return f'<tr><td colspan="6" style="text-align:center;color:#888;padding:16px;">No {signal_type} divergences today.</td></tr>'
    out = ""
    for r in rows:
        dist = float(r.get("Distance %", 0))
        if signal_type == "BULLISH":
            color = "#16a34a"
            bg    = f"rgba(34,197,94,{max(0.06, 0.25 - dist * 0.04):.2f})"
        else:
            color = "#dc2626"
            bg    = f"rgba(239,68,68,{max(0.06, 0.25 - dist * 0.04):.2f})"
        badge = (
            f'<span style="background:{color};color:#fff;padding:2px 8px;'
            f'border-radius:10px;font-size:11px;font-weight:700;">{signal_type}</span>'
        )
        pivot_time = str(r.get("Pivot Time", ""))[:16]
        out += f"""
        <tr style="background:{bg};">
          <td style="font-weight:700;font-size:13px;padding:8px 12px;">{r['Symbol']}</td>
          <td style="padding:8px 12px;">{badge}</td>
          <td style="padding:8px 12px;">&#8377;{float(r['Origin Price']):,.2f}</td>
          <td style="padding:8px 12px;">&#8377;{float(r['Current Price']):,.2f}</td>
          <td style="padding:8px 12px;font-weight:700;">{dist:.2f}%</td>
          <td style="padding:8px 12px;color:#888;font-size:11px;">{pivot_time}</td>
        </tr>"""
    return out


def build_html(bullish, bearish):
    now       = datetime.now().strftime("%d %b %Y")
    total     = len(bullish) + len(bearish)
    b_rows    = make_table_rows(bullish, "BULLISH")
    bear_rows = make_table_rows(bearish, "BEARISH")

    th = ('style="padding:8px 12px;text-align:left;font-size:11px;'
          'text-transform:uppercase;letter-spacing:0.5px;color:#64748b;'
          'background:#0f172a;border-bottom:1px solid #334155;"')
    thead = f"<tr><th {th}>Symbol</th><th {th}>Signal</th><th {th}>Origin</th><th {th}>Current</th><th {th}>Dist%</th><th {th}>Pivot Time</th></tr>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#0f172a;color:#e2e8f0;margin:0;padding:24px;">

  <div style="max-width:720px;margin:0 auto;">

    <!-- Header -->
    <div style="text-align:center;margin-bottom:28px;">
      <h1 style="font-size:22px;font-weight:800;color:#f8fafc;margin:0;">
        Nifty Midcap 150 &mdash; RSI Divergence Scan
      </h1>
      <p style="color:#94a3b8;margin:6px 0 0;font-size:13px;">{now}</p>
    </div>

    <!-- Stats -->
    <div style="display:flex;gap:14px;justify-content:center;margin-bottom:28px;">
      <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px 24px;text-align:center;">
        <div style="font-size:26px;font-weight:800;color:#4ade80;">{len(bullish)}</div>
        <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Bullish</div>
      </div>
      <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px 24px;text-align:center;">
        <div style="font-size:26px;font-weight:800;color:#f87171;">{len(bearish)}</div>
        <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Bearish</div>
      </div>
      <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px 24px;text-align:center;">
        <div style="font-size:26px;font-weight:800;color:#60a5fa;">{total}</div>
        <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Total</div>
      </div>
    </div>

    <!-- Bullish table -->
    <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;
                margin-bottom:20px;overflow:hidden;">
      <div style="background:rgba(34,197,94,0.1);padding:12px 16px;
                  border-bottom:1px solid #334155;">
        <h2 style="margin:0;font-size:15px;color:#4ade80;">
          &#9650; Bullish Divergences ({len(bullish)})
        </h2>
        <p style="margin:4px 0 0;font-size:11px;color:#4ade80;opacity:0.7;">
          Price lower low &amp; RSI higher low &rarr; potential reversal up
        </p>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <thead>{thead}</thead>
        <tbody>{b_rows}</tbody>
      </table>
    </div>

    <!-- Bearish table -->
    <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;
                margin-bottom:20px;overflow:hidden;">
      <div style="background:rgba(239,68,68,0.1);padding:12px 16px;
                  border-bottom:1px solid #334155;">
        <h2 style="margin:0;font-size:15px;color:#f87171;">
          &#9660; Bearish Divergences ({len(bearish)})
        </h2>
        <p style="margin:4px 0 0;font-size:11px;color:#f87171;opacity:0.7;">
          Price higher high &amp; RSI lower high &rarr; potential reversal down
        </p>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <thead>{thead}</thead>
        <tbody>{bear_rows}</tbody>
      </table>
    </div>

    <!-- CTA -->
    <div style="text-align:center;margin:28px 0 20px;">
      <a href="{PAGES_URL}"
         style="background:#3b82f6;color:#fff;padding:12px 28px;border-radius:8px;
                text-decoration:none;font-weight:700;font-size:14px;">
        View Full Report &rarr;
      </a>
    </div>

    <!-- Footer -->
    <p style="text-align:center;color:#475569;font-size:11px;margin-top:16px;">
      RSI(14) hourly divergence &bull; Current price within 5% of divergence origin &bull;
      Data via Yahoo Finance &bull; Not investment advice.
    </p>

  </div>
</body>
</html>"""


def send():
    bullish, bearish = load_results()
    now     = datetime.now().strftime("%d %b %Y")
    subject = f"Midcap RSI Scan — {now} | {len(bullish)} Bullish  {len(bearish)} Bearish"

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from":    "Midcap Scan <onboarding@resend.dev>",
            "to":      [RECIPIENT],
            "subject": subject,
            "html":    build_html(bullish, bearish),
            "text":    f"Midcap RSI Scan — {now}\n\nBullish: {len(bullish)}  Bearish: {len(bearish)}\n\nFull report: {PAGES_URL}",
        },
    )
    response.raise_for_status()
    print(f"Email sent to {RECIPIENT} — {len(bullish)} bullish, {len(bearish)} bearish signals")


if __name__ == "__main__":
    send()
