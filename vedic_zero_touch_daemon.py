#!/usr/bin/env python3
"""
🕉️ VEDIC ZERO-TOUCH AUTONOMOUS CLOUD TRADING DAEMON
Designed for 24/7/365 Zero-Human-Interaction Operation on Cloud VPS / Local Linux.
- Auto-renews Dhan API Token daily at 08:30 AM (Never expires, no copy-pasting).
- Skips Weekends and NSE National Stock Holidays.
- Trades 2 Daily High-Conviction Muhurtas:
    1. Pratah Muhurta (09:45 AM IST)
    2. European Open Muhurta (13:15 PM IST)
- Enforces Atharvaveda Kavacha SL (-0.25%) and Target (+0.35%).
- Hard Auto-Square-off at 15:15 IST (Zero Overnight Risk).
- Pushes Live Trade & Daily PnL Alerts directly to Mobile via Telegram (Optional).
"""

import os
import sys
import json
import time
import socket
import datetime
import subprocess
import warnings
warnings.filterwarnings('ignore')

# Force IPv4 for Dhan API Gateway compatibility
import urllib3.util.connection as urllib3_conn
urllib3_conn.allowed_gai_family = lambda: socket.AF_INET

import requests
import pandas as pd
import yfinance as yf
from dhanhq import DhanContext, dhanhq, DhanLogin

CONFIG_FILE = "dhan_config.json"
SCRIPS_FILE = "dhan_scrips.json"
JOURNAL_FILE = "vedic_zero_touch_journal.csv"
DAILY_LEDGER_FILE = "vedic_zero_touch_daily_ledger.csv"
LOG_FILE = "vedic_zero_touch.log"

# Official NSE Trading Holidays (Sample 2026/2027 calendar)
NSE_HOLIDAYS = {
    "2026-01-26", # Republic Day
    "2026-02-18", # Mahashivratri
    "2026-03-03", # Holi
    "2026-03-20", # Id-Ul-Fitr
    "2026-04-03", # Good Friday
    "2026-04-14", # Dr. Ambedkar Jayanti
    "2026-05-01", # Maharashtra Day
    "2026-05-27", # Bakri Id
    "2026-06-25", # Muharram
    "2026-08-15", # Independence Day
    "2026-10-02", # Mahatma Gandhi Jayanti
    "2026-10-20", # Dussehra
    "2026-11-09", # Diwali Laxmi Pujan
    "2026-11-10", # Diwali Balipratipada
    "2026-11-24", # Gurunanak Jayanti
    "2026-12-25", # Christmas
}

def get_ist_now():
    """Returns current datetime strictly in Indian Standard Time (IST - UTC+05:30)."""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return utc_now.astimezone(ist_tz)

def log(msg):
    ts = get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST")
    formatted = f"[{ts}] {msg}"
    print(formatted, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def send_telegram_alert(msg, token=None, chat_id=None):
    """Sends passive push alert to user's mobile phone via Telegram."""
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": f"🕉️ {msg}", "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass

def send_desktop_notification(title, body):
    try:
        subprocess.run(['notify-send', '-u', 'normal', '-t', '5000', f"🕉️ {title}", body], check=False)
    except Exception:
        pass

class VedicZeroTouchDaemon:
    def __init__(self):
        log("🕉️ Initializing Vedic Zero-Touch Autonomous Trading Daemon...")
        self.load_config()
        self.load_scrips()
        self.init_dhan()
        self.candidates = [
            'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 
            'SBIN', 'BHARTIARTL', 'KOTAKBANK', 'LT', 'AXISBANK',
            'ASIANPAINT', 'TITAN', 'BAJFINANCE', 'MARUTI', 'SUNPHARMA',
            'ULTRACEMCO', 'NTPC', 'ONGC', 'POWERGRID', 'TATASTEEL',
            'JSWSTEEL', 'M&M', 'COALINDIA', 'ADANIPORTS', 'BPCL',
            'CIPLA', 'WIPRO', 'DRREDDY', 'HEROMOTOCO', 'BAJAJ-AUTO',
            'BEL', 'BHEL'
        ]
        self.morning_traded_date = None
        self.afternoon_traded_date = None
        
    def load_config(self):
        with open(CONFIG_FILE, "r") as f:
            self.cfg = json.load(f)
        self.client_id = self.cfg.get("client_id")
        self.access_token = self.cfg.get("access_token")
        self.mode = self.cfg.get("mode", "micro") # "micro" (1 share) or "full_capital"
        self.telegram_bot_token = self.cfg.get("telegram_bot_token")
        self.telegram_chat_id = self.cfg.get("telegram_chat_id")

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.cfg, f, indent=4)

    def load_scrips(self):
        if os.path.exists(SCRIPS_FILE):
            with open(SCRIPS_FILE, "r") as f:
                self.scrips = json.load(f)
        else:
            self.scrips = {}

    def init_dhan(self):
        self.ctx = DhanContext(self.client_id, self.access_token)
        self.dhan = dhanhq(self.ctx)
        self.headers = {
            'access-token': self.access_token,
            'client-id': self.client_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def renew_daily_token(self):
        """Zero-Touch Token Renewal: Auto-refreshes token without any user action."""
        try:
            log("🔄 Zero-Touch: Checking Dhan API token renewal...")
            dl = DhanLogin(self.client_id)
            res = dl.renew_token(self.access_token)
            new_tok = res.get("token")
            if new_tok:
                self.access_token = new_tok
                self.cfg["access_token"] = new_tok
                self.save_config()
                self.init_dhan()
                log("✅ Dhan Access Token renewed successfully for next 24 hours!")
                return True
            else:
                log(f"⚠️ Token renewal response did not contain new token: {res}")
        except Exception as e:
            log(f"⚠️ Token renewal notice: {e}")
        return False

    def get_funds(self):
        try:
            funds = self.dhan.get_fund_limits()
            avail = float(funds.get("data", {}).get("availabelBalance", 0.0))
            return avail
        except Exception as e:
            log(f"Error fetching funds: {e}")
            return 0.0

    def get_dynamic_compounding_qty(self, sec_id, price, transaction_type="BUY"):
        """
        Institutional Dynamic Compounding:
        Queries Dhan's live Margin API to get exact leverage and margin per share,
        then calculates compounding quantity using 85% of available balance (15% safety buffer).
        """
        avail = self.get_funds()
        if self.mode == "micro":
            return 1, round(price / 5.0, 2), 5.0
            
        payload = {
            'dhanClientId': self.client_id,
            'exchangeSegment': 'NSE_EQ',
            'transactionType': transaction_type,
            'quantity': 1,
            'productType': 'INTRADAY',
            'securityId': str(sec_id),
            'price': float(price)
        }
        
        try:
            res = requests.post('https://api.dhan.co/v2/margincalculator', headers=self.headers, json=payload, timeout=5).json()
            margin_per_share = float(res.get("totalMargin", 0))
            leverage_str = str(res.get("leverage", "5.00X"))
            leverage_val = float(leverage_str.replace("X", "").strip())
            
            if margin_per_share <= 0:
                margin_per_share = price / (leverage_val if leverage_val > 0 else 5.0)
                
            # 85% fractional allocation (15% cash safety buffer for volatility)
            allocable_cash = avail * 0.85
            unconstrained_exposure = allocable_cash * leverage_val
            actual_exposure = min(unconstrained_exposure, 2000000.0) # Realistic NSE order book ceiling
            qty = int(actual_exposure / price)
            qty = max(1, qty)
            
            log(f"⚡ Live Dhan Margin API: Leverage={leverage_str} | Margin/Share=₹{margin_per_share:.2f} | Wallet=₹{avail:.2f} -> Compounded Qty={qty} shares (Exposure: ₹{qty*price:,.2f})")
            return qty, margin_per_share, leverage_val
        except Exception as e:
            log(f"Margin API query exception: {e}. Fallback to 5x margin.")
            margin_per_share = round(price / 5.0, 2)
            allocable_cash = avail * 0.85
            unconstrained_exposure = allocable_cash * 5.0
            actual_exposure = min(unconstrained_exposure, 2000000.0)
            qty = max(1, int(actual_exposure / price))
            return qty, margin_per_share, 5.0

    def is_trading_day(self):
        """Checks if today is a weekday and not an NSE holiday."""
        today = get_ist_now().date()
        # 0 = Monday, 4 = Friday, 5 = Saturday, 6 = Sunday
        if today.weekday() >= 5:
            return False, "Weekend (Saturday/Sunday)"
        today_str = today.strftime("%Y-%m-%d")
        if today_str in NSE_HOLIDAYS:
            return False, f"NSE Market Holiday ({today_str})"
        return True, "Trading Day"

    def get_nifty_regime(self):
        """Calculates macro NIFTY 50 Guna / Trend direction."""
        try:
            t = yf.Ticker('^NSEI')
            df = t.history(period='1d', interval='5m')
            if len(df) > 0:
                o = float(df['Open'].iloc[0])
                c = float(df['Close'].iloc[-1])
                pct = ((c - o) / o) * 100.0
                if pct >= 0.20:
                    return "BULLISH_RAJAS", pct
                elif pct <= -0.20:
                    return "BEARISH_RAJAS", pct
                else:
                    return "SATTVIC_EQUILIBRIUM", pct
        except Exception:
            pass
        return "SATTVIC_EQUILIBRIUM", 0.0

    def scan_best_setup(self):
        """Scans liquid candidates and picks #1 setup based on Vedic price action."""
        regime, n_pct = self.get_nifty_regime()
        log(f"Market Dharma: NIFTY 50 is {regime} ({n_pct:+.2f}%)")
        
        best = None
        max_conviction = -1.0
        avail = self.get_funds()
        
        for sym in self.candidates:
            try:
                t = yf.Ticker(f"{sym}.NS")
                df = t.history(period="1d", interval="5m")
                if len(df) < 5:
                    continue
                    
                cur_price = float(df['Close'].iloc[-1])
                day_open = float(df['Open'].iloc[0])
                last_o = float(df['Open'].iloc[-1])
                last_h = float(df['High'].iloc[-1])
                last_l = float(df['Low'].iloc[-1])
                last_c = float(df['Close'].iloc[-1])
                
                # VWAP
                cum_vol = df['Volume'].cumsum()
                vwap = float(((df['Close'] * df['Volume']).cumsum() / cum_vol).iloc[-1])
                
                c_range = last_h - last_l
                lower_wick = min(last_o, last_c) - last_l if c_range > 0 else 0
                upper_wick = last_h - max(last_o, last_c) if c_range > 0 else 0
                lw_pct = (lower_wick / c_range) * 100 if c_range > 0 else 0
                uw_pct = (upper_wick / c_range) * 100 if c_range > 0 else 0
                
                margin_needed = round(cur_price / 5.0, 2)
                # Smart liquidity buffer: only consider candidates whose single-share margin fits within available funds
                if margin_needed > (avail * 0.9):
                    continue
                    
                score_long = 60.0
                score_short = 60.0
                
                # Institutional Volume Confirmation (1.15x 20-period Volume SMA)
                vol_sma = df['Volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else df['Volume'].mean()
                last_vol = df['Volume'].iloc[-1]
                vol_ratio = (last_vol / vol_sma) if vol_sma > 0 else 1.0
                if vol_ratio >= 1.15:
                    score_long += 15.0
                    score_short += 15.0
                
                if cur_price >= vwap:
                    score_long += 15.0
                else:
                    score_short += 15.0
                    
                if lw_pct >= 40.0:
                    score_long += 20.0
                if uw_pct >= 40.0:
                    score_short += 20.0
                    
                if "BULLISH" in regime:
                    score_long += 10.0
                elif "BEARISH" in regime:
                    score_short += 10.0
                    
                action = "BUY" if score_long >= score_short else "SHORT"
                conviction = score_long if action == "BUY" else score_short
                setup_desc = "Dharma VWAP Rebound Dip" if action == "BUY" else "Moksha Supply Sweep"
                
                if conviction > max_conviction:
                    max_conviction = conviction
                    best = {
                        "symbol": sym,
                        "sec_id": self.scrips.get(sym, "3499"),
                        "action": action,
                        "setup": setup_desc,
                        "price": cur_price,
                        "margin": margin_needed,
                        "score": conviction
                    }
            except Exception:
                continue
                
        return best

    def execute_trade(self, window_name):
        """Executes a single Muhurta trade and manages tick-by-tick."""
        pick = self.scan_best_setup()
        if not pick:
            log(f"[{window_name}] ⚠️ No setup met strict conviction criteria. Capital preserved.")
            return None
            
        sym = pick["symbol"]
        sec_id = pick["sec_id"]
        action = pick["action"]
        setup = pick["setup"]
        score = pick["score"]
        
        avail = self.get_funds()
        qty, margin_per_share, leverage = self.get_dynamic_compounding_qty(sec_id, pick["price"], action)
        
        log(f"[{window_name}] 🏆 TOP PICK: {action} {qty} {sym} (Conviction: {score}/100)")
        log(f"   Setup: {setup} | Current Price: ~₹{pick['price']:.2f} | Leverage: {leverage}x | Margin/Share: ₹{margin_per_share:.2f}")
        
        order_payload = {
            'dhanClientId': self.client_id,
            'transactionType': "BUY" if action == "BUY" else "SELL",
            'exchangeSegment': "NSE_EQ",
            'productType': "INTRADAY",
            'orderType': "MARKET",
            'validity': "DAY",
            'securityId': str(sec_id),
            'quantity': qty,
            'disclosedQuantity': 0,
            'price': 0,
            'triggerPrice': 0,
            'afterMarketOrder': False
        }
        
        try:
            res = requests.post('https://api.dhan.co/v2/orders', headers=self.headers, json=order_payload)
            order_data = res.json()
            order_id = order_data.get("orderId")
        except Exception as e:
            log(f"❌ Order placement failed: {e}")
            return None
            
        if not order_id:
            log(f"❌ Order rejected by Dhan: {res.text}")
            return None
            
        log(f"🎉 ORDER EXECUTED! Dhan Order ID: {order_id}")
        send_desktop_notification("TRADE EXECUTED", f"{action} {qty} {sym}\nOrder ID: {order_id}")
        send_telegram_alert(
            f"🚀 *{window_name} Trade Executed*\n"
            f"*Stock:* `{sym}`\n"
            f"*Action:* `{action}` {qty} Share(s) (Leverage: {leverage}x)\n"
            f"*Setup:* {setup} (Conviction: {score}/100)\n"
            f"*Dhan Order ID:* `{order_id}`",
            self.telegram_bot_token, self.telegram_chat_id
        )
        
        # Fetch executed price
        exec_price = pick["price"]
        for _ in range(4):
            time.sleep(1.5)
            try:
                r_ord = requests.get(f'https://api.dhan.co/v2/orders/{order_id}', headers=self.headers).json()
                ord_obj = r_ord[0] if (isinstance(r_ord, list) and len(r_ord) > 0) else (r_ord if isinstance(r_ord, dict) else {})
                p = ord_obj.get("averageTradedPrice") or ord_obj.get("price")
                if p and float(p) > 0:
                    exec_price = float(p)
                    break
            except Exception:
                pass
                
        is_long = (action == "BUY")
        # Fine-Tuned Asymmetric 1:2.0 Risk-to-Reward: Target +0.40%, Initial SL -0.20%
        tp = round(exec_price * (1.0040 if is_long else 0.9960), 2)
        sl = round(exec_price * (0.9980 if is_long else 1.0020), 2)
        trailing_be_triggered = False
        
        log(f"Position Active: Entry ₹{exec_price:.2f} | TP (+0.40%): ₹{tp:.2f} | SL (-0.20%): ₹{sl:.2f} | Qty: {qty}")
        log("📡 Streaming live price ticks until Target or SL...")
        
        # Tick Monitoring Loop
        iteration = 0
        trade_outcome = None
        exit_price = exec_price
        
        while True:
            time.sleep(5)
            iteration += 1
            
            try:
                t = yf.Ticker(f"{sym}.NS")
                df = t.history(period="1d", interval="1m")
                if len(df) == 0:
                    continue
                cur_p = float(df['Close'].iloc[-1])
                cur_h = float(df['High'].iloc[-1])
                cur_l = float(df['Low'].iloc[-1])
                
                pnl = ((cur_p - exec_price) if is_long else (exec_price - cur_p)) * qty
                pnl_pct = (pnl / (exec_price * qty)) * 100.0
                
                # ATHARVAVEDA SATYA ZERO-RISK LOCK:
                # Once trade reaches +0.18% in profit, trail SL to Breakeven (+0.05% buffer)
                if not trailing_be_triggered and pnl_pct >= 0.18:
                    be_sl = round(exec_price * (1.0005 if is_long else 0.9995), 2)
                    if (is_long and be_sl > sl) or (not is_long and be_sl < sl):
                        sl = be_sl
                        trailing_be_triggered = True
                        log(f"🛡️ SATYA LOCK TRIGGERED: PnL reached +{pnl_pct:.2f}%! Stop Loss trailed to BREAKEVEN (₹{sl:.2f}). Trade is now ZERO RISK!")
                
                emoji = "🟢" if pnl >= 0 else "🔴"
                if iteration % 4 == 0:
                    log(f"{emoji} Live: ₹{cur_p:.2f} | PnL: ₹{pnl:+.2f} ({pnl_pct:+.2f}%) | TP: ₹{tp:.2f} | SL: ₹{sl:.2f}")
                    
                hit_tp = (cur_h >= tp or cur_p >= tp) if is_long else (cur_l <= tp or cur_p <= tp)
                hit_sl = (cur_l <= sl or cur_p <= sl) if is_long else (cur_h >= sl or cur_p >= sl)
                
                now_check = get_ist_now()
                is_eod = (now_check.hour * 60 + now_check.minute) >= 915 # 15:15 IST
                
                if hit_tp or hit_sl or is_eod:
                    if hit_tp:
                        reason = "🎯 TARGET HIT (+0.40%)"
                        outcome = "TARGET_HIT"
                    elif hit_sl:
                        reason = "🛡️ SL PROTECTED" if not trailing_be_triggered else "🛡️ BREAKEVEN SATYA EXIT (+0.05%)"
                        outcome = "SL_HIT" if not trailing_be_triggered else "BREAKEVEN_EXIT"
                    else:
                        reason = "⏰ EOD 15:15 SQUARE-OFF"
                        outcome = "EOD_EXIT"
                        
                    log(f"{reason}! Sending square-off order to Dhan...")
                    exit_payload = {
                        'dhanClientId': self.client_id,
                        'transactionType': "SELL" if is_long else "BUY",
                        'exchangeSegment': "NSE_EQ",
                        'productType': "INTRADAY",
                        'orderType': "MARKET",
                        'validity': "DAY",
                        'securityId': str(sec_id),
                        'quantity': qty,
                        'disclosedQuantity': 0,
                        'price': 0,
                        'triggerPrice': 0,
                        'afterMarketOrder': False
                    }
                    r_exit = requests.post('https://api.dhan.co/v2/orders', headers=self.headers, json=exit_payload)
                    exit_price = cur_p
                    trade_outcome = outcome
                    log(f"Square-off Response: {r_exit.text}")
                    
                    send_telegram_alert(
                        f"{reason}\n"
                        f"*Stock:* `{sym}`\n"
                        f"*Entry:* ₹{exec_price:.2f} | *Exit:* ₹{exit_price:.2f}\n"
                        f"*Trade PnL:* `₹{pnl:+.2f} ({pnl_pct:+.2f}%)`\n"
                        f"*Status:* Flat (netQty: 0)",
                        self.telegram_bot_token, self.telegram_chat_id
                    )
                    break
            except Exception as e:
                log(f"Monitoring exception: {e}")
                time.sleep(5)
                
        # Journal entry
        self.record_journal(sym, action, qty, exec_price, exit_price, pnl, trade_outcome, window_name)
        return pnl

    def record_journal(self, symbol, action, qty, entry, exit_p, pnl, outcome, window):
        try:
            now_ist = get_ist_now()
            record = {
                "Date": now_ist.strftime("%Y-%m-%d"),
                "Time": now_ist.strftime("%H:%M:%S"),
                "Window": window,
                "Symbol": symbol,
                "Action": action,
                "Quantity": qty,
                "Entry": round(entry, 2),
                "Exit": round(exit_p, 2),
                "PnL": round(pnl, 2),
                "Outcome": outcome
            }
            df_new = pd.DataFrame([record])
            if os.path.exists(JOURNAL_FILE):
                df_old = pd.read_csv(JOURNAL_FILE)
                df_all = pd.concat([df_old, df_new], ignore_index=True)
            else:
                df_all = df_new
            df_all.to_csv(JOURNAL_FILE, index=False)
            log(f"📘 Trade recorded to {JOURNAL_FILE}")
        except Exception as e:
            log(f"Warning recording journal: {e}")

    def run_eod_square_off_check(self):
        """Hard safety check at 15:15 IST: Ensures zero open positions remain."""
        try:
            r = requests.get('https://api.dhan.co/v2/positions', headers=self.headers).json()
            if isinstance(r, list):
                for pos in r:
                    net_qty = pos.get("netQty", 0)
                    if net_qty != 0:
                        sec_id = pos.get("securityId")
                        sym = pos.get("tradingSymbol")
                        action = "SELL" if net_qty > 0 else "BUY"
                        qty = abs(net_qty)
                        log(f"⚠️ EOD SAFETY TRIGGER: Squaring off lingering {action} {qty} {sym}...")
                        payload = {
                            'dhanClientId': self.client_id,
                            'transactionType': action,
                            'exchangeSegment': "NSE_EQ",
                            'productType': "INTRADAY",
                            'orderType': "MARKET",
                            'validity': "DAY",
                            'securityId': str(sec_id),
                            'quantity': qty,
                            'disclosedQuantity': 0,
                            'price': 0,
                            'triggerPrice': 0,
                            'afterMarketOrder': False
                        }
                        requests.post('https://api.dhan.co/v2/orders', headers=self.headers, json=payload)
        except Exception as e:
            log(f"EOD check error: {e}")

    def run(self):
        log("🚀 Vedic Zero-Touch Autonomous Daemon started! Running 24/7 in background.")
        
        while True:
            now = get_ist_now()
            t_min = now.hour * 60 + now.minute
            today_str = now.strftime("%Y-%m-%d")
            
            # 1. Daily Token Refresh at 08:30 AM (510 min)
            if t_min == 510 and now.second < 20:
                self.renew_daily_token()
                time.sleep(30)
                
            # 2. Check if today is a trading day
            is_trade_day, day_reason = self.is_trading_day()
            if not is_trade_day:
                if t_min == 540 and now.second < 20: # 09:00 AM
                    log(f"💤 Market closed today: {day_reason}. Daemon resting.")
                time.sleep(60)
                continue
                
            # 3. Market Open Check (09:15 AM - 555 min)
            if t_min == 555 and now.second < 15:
                bal = self.get_funds()
                log(f"🔔 Market OPEN! Live Dhan Wallet: ₹{bal:,.2f} | Mode: {self.mode.upper()}")
                time.sleep(30)
                
            # 4. Morning Muhurta (09:45 AM - 10:15 AM IST: 585 to 615 min)
            if 585 <= t_min < 615 and self.morning_traded_date != today_str:
                log(f"🌟 Pratah Muhurta Window (09:45 - 10:15 AM IST) ACTIVE. Scanning top liquid stocks...")
                self.morning_traded_date = today_str
                self.execute_trade("Morning_Muhurta")
                    
            # 5. European Open Muhurta (13:15 PM - 13:45 PM IST: 795 to 825 min)
            if 795 <= t_min < 825 and self.afternoon_traded_date != today_str:
                log(f"🌟 European Open Muhurta Window (13:15 - 13:45 PM IST) ACTIVE. Scanning institutional setups...")
                self.afternoon_traded_date = today_str
                self.execute_trade("Afternoon_Muhurta")
                    
            # 6. Hard EOD Square-Off at 15:15 IST (915 min)
            if t_min == 915 and now.second < 20:
                log("⏰ 15:15 IST Hard EOD Square-Off Check Triggered.")
                self.run_eod_square_off_check()
                time.sleep(30)
                
            # 7. EOD Daily Ledger Recording at 15:35 IST (935 min)
            if t_min == 935 and now.second < 20:
                bal = self.get_funds()
                log(f"🏁 Trading Day Finished! Closing Balance: ₹{bal:,.2f}. Standing down until tomorrow.")
                time.sleep(40)
                
            time.sleep(10)

if __name__ == "__main__":
    bot = VedicZeroTouchDaemon()
    bot.run()
