#!/usr/bin/env python3
"""
🕉️ VEDIC BOT CLOUD DASHBOARD & RUNNER (RENDER.COM)
Runs the 24/7 background trading daemon and serves a live mobile web dashboard.
"""

import os
import json
import socket
import datetime
import threading
import warnings
warnings.filterwarnings('ignore')

# Force IPv4
import urllib3.util.connection as urllib3_conn
urllib3_conn.allowed_gai_family = lambda: socket.AF_INET

from flask import Flask, render_template_string, jsonify
import requests
import pandas as pd
from vedic_zero_touch_daemon import VedicZeroTouchDaemon

app = Flask(__name__)
bot_engine = None

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vedic Bot Cloud Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f172a;
            --card-bg: #1e293b;
            --border: #334155;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
            --primary: #38bdf8;
            --success: #34d399;
            --danger: #f87171;
            --accent: #fbbf24;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            padding: 16px;
            max-width: 650px;
            margin: 0 auto;
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 20px;
        }
        .header-title { font-size: 20px; font-weight: 700; color: var(--primary); }
        .pulse-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(52, 211, 153, 0.15);
            color: var(--success);
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
        }
        .pulse-dot {
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse { 0% { opacity: 0.4; } 50% { opacity: 1; } 100% { opacity: 0.4; } }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .card-header { font-size: 13px; font-weight: 600; text-transform: uppercase; color: var(--text-sub); margin-bottom: 12px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .stat-val { font-size: 24px; font-weight: 700; margin-top: 4px; }
        .stat-sub { font-size: 12px; color: var(--text-sub); }
        .table-wrap { overflow-x: auto; margin-top: 8px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); }
        th { color: var(--text-sub); font-weight: 600; }
        .pnl-green { color: var(--success); font-weight: 600; }
        .pnl-red { color: var(--danger); font-weight: 600; }
        .footer { text-align: center; font-size: 12px; color: var(--text-sub); margin-top: 24px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-title">🕉️ Vedic Cloud Bot</div>
        <div class="pulse-badge">
            <div class="pulse-dot"></div> ACTIVE 24/7
        </div>
    </div>

    <!-- Account & Wallet Card -->
    <div class="card">
        <div class="card-header">Dhan Live Account</div>
        <div class="grid-2">
            <div>
                <div class="stat-sub">Available Balance</div>
                <div class="stat-val" style="color: var(--primary);">₹{{ funds }}</div>
            </div>
            <div>
                <div class="stat-sub">Trading Mode</div>
                <div class="stat-val" style="color: var(--accent); font-size: 18px;">{{ mode.upper() }}</div>
                <div class="stat-sub">Client: {{ client_id }}</div>
            </div>
        </div>
    </div>

    <!-- Live Position Status -->
    <div class="card">
        <div class="card-header">Current Market Position</div>
        <div style="font-size: 15px; font-weight: 600;">
            {% if pos_count == 0 %}
                🛡️ FLAT (Zero Open Risk)
            {% else %}
                🟢 OPEN: {{ open_pos_str }}
            {% endif %}
        </div>
        <div class="stat-sub" style="margin-top: 6px;">Next Window: 09:45 AM (Pratah) & 13:15 PM (London Open)</div>
    </div>

    <!-- Recent Trades Table -->
    <div class="card">
        <div class="card-header">Today's Executed Trades</div>
        <div class="table-wrap">
            {% if trades|length > 0 %}
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Symbol</th>
                        <th>Type</th>
                        <th>Entry</th>
                        <th>Exit</th>
                        <th>PnL</th>
                    </tr>
                </thead>
                <tbody>
                    {% for t in trades %}
                    <tr>
                        <td>{{ t['Time'] }}</td>
                        <td><strong>{{ t['Symbol'] }}</strong></td>
                        <td>{{ t['Action'] }}</td>
                        <td>₹{{ t['Entry'] }}</td>
                        <td>₹{{ t['Exit'] }}</td>
                        <td class="{{ 'pnl-green' if t['PnL'] >= 0 else 'pnl-red' }}">
                            {{ "+" if t['PnL'] >= 0 else "" }}₹{{ t['PnL'] }}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div style="font-size: 13px; color: var(--text-sub); text-align: center; padding: 12px;">
                No trades taken yet today. Standing by for next Muhurta.
            </div>
            {% endif %}
        </div>
    </div>

    <div class="footer">
        Zero-Touch Cloud Daemon • Render Free Tier • Auto Token Renewal Active
    </div>
</body>
</html>
"""

def start_bot_thread():
    global bot_engine
    try:
        bot_engine = VedicZeroTouchDaemon()
        t = threading.Thread(target=bot_engine.run, daemon=True)
        t.start()
        print("✅ Background trading thread launched successfully!", flush=True)
    except Exception as e:
        print(f"❌ Error launching bot thread: {e}", flush=True)

# Start background thread automatically
start_bot_thread()

def get_ist_now():
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return utc_now.astimezone(ist_tz)

@app.route('/')
def dashboard():
    global bot_engine
    funds = "0.00"
    mode = "compounding"
    client_id = "1000544603"
    pos_count = 0
    open_pos_str = "None"
    trades = []
    
    if bot_engine:
        try:
            funds = f"{bot_engine.get_funds():,.2f}"
            mode = bot_engine.mode
            client_id = bot_engine.client_id
        except Exception:
            pass
            
        try:
            # Check positions
            r = requests.get('https://api.dhan.co/v2/positions', headers=bot_engine.headers, timeout=5).json()
            if isinstance(r, list):
                for p in r:
                    if p.get("netQty", 0) != 0:
                        pos_count += 1
                        open_pos_str = f"{p.get('tradingSymbol')} (Qty: {p.get('netQty')}) | Buy Avg: ₹{p.get('buyAvg')}"
        except Exception:
            pass

    # Read trades from journal
    j_file = "vedic_zero_touch_journal.csv"
    if os.path.exists(j_file):
        try:
            df = pd.read_csv(j_file)
            today = get_ist_now().strftime("%Y-%m-%d")
            df_today = df[df['Date'] == today]
            trades = df_today.to_dict('records')
        except Exception:
            pass
            
    return render_template_string(
        HTML_DASHBOARD,
        funds=funds,
        mode=mode,
        client_id=client_id,
        pos_count=pos_count,
        open_pos_str=open_pos_str,
        trades=trades
    )

@app.route('/health')
def health():
    """Endpoint for cron-job.org / UptimeRobot to keep Render container awake."""
    return jsonify({
        "status": "healthy",
        "timestamp": get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "daemon": "running"
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
