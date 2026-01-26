import streamlit as st
import pandas as pd
import json
import os
import time
import altair as alt
from datetime import datetime, timedelta

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Sentient Trader | Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded" 
)

# --- CONSTANTS ---
REFRESH_RATE_SEC = 2
SYSTEM_STATE_FILE = "system_state.json"
TRADE_LOG_FILE = "trade_log.csv"

# --- FINTECH PRO CSS ---
st.markdown("""
    <style>
    /* Clean Reset */
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;700&family=Inter:wght@400;600;800&display=swap');
    
    .stApp {
        background-color: #050505;
        color: #e0e0e0;
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0a0a0a;
        border-right: 1px solid #222;
    }
    
    /* Headers */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        letter-spacing: -1px;
        color: #fff;
    }
    
    /* Metrics */
    .big-metric {
        font-family: 'Roboto Mono', monospace;
        font-size: 2.2rem;
        font-weight: 700;
        color: #fff;
    }
    
    .metric-label {
        color: #666;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.2rem;
    }
    
    /* Cards */
    .fin-card {
        background: #111;
        border: 1px solid #222;
        border-radius: 6px;
        padding: 1.5rem;
        transition: border 0.3s;
    }
    .fin-card:hover {
        border-color: #444;
    }
    
    /* Tables */
    [data-testid="stTable"] {
        font-family: 'Roboto Mono', monospace;
        font-size: 0.9rem;
    }
    
    /* Colors */
    .green { color: #00ff9d; }
    .red { color: #ff3b3b; }
    .blue { color: #29b6f6; }
    
    /* Cortex Feed */
    .cortex-item {
        border-left: 2px solid #333;
        padding-left: 1rem;
        margin-bottom: 1.5rem;
        font-family: 'Roboto Mono', monospace;
    }
    .cortex-meta {
        font-size: 0.75rem;
        color: #555;
        margin-bottom: 0.5rem;
    }
    .cortex-body {
        font-size: 0.95rem;
        line-height: 1.5;
        color: #ccc;
    }
    
    </style>
""", unsafe_allow_html=True)

# --- DATA LOADER ---
def load_data():
    state = {}
    df = pd.DataFrame()
    
    if os.path.exists(SYSTEM_STATE_FILE):
        try:
            with open(SYSTEM_STATE_FILE, 'r') as f: state = json.load(f)
        except: pass
        
    if os.path.exists(TRADE_LOG_FILE):
        try: # Handle malformed CSVs robustly
            df = pd.read_csv(TRADE_LOG_FILE, on_bad_lines='skip') 
            if "PnL" not in df.columns: df["PnL"] = 0.0
        except: pass
    
    return state, df

state, df_log = load_data()

# --- SIDEBAR NAVIGATION ---
st.sidebar.markdown("## ⚡ SENTIENT")
page = st.sidebar.radio("Navigation", ["1. COCKPIT", "2. CORTEX", "3. DEEP MARKET", "4. LEDGER"])

st.sidebar.markdown("---")
# Connection Status
if state:
    last_beat = datetime.fromisoformat(state.get("last_heartbeat", "2000-01-01"))
    if (datetime.now() - last_beat) < timedelta(minutes=2):
        st.sidebar.success(f"ONLINE {last_beat.strftime('%H:%M:%S')}")
    else:
        st.sidebar.error("OFFLINE")
    
    st.sidebar.markdown(f"**Symbol**: `{state.get('symbol')}`")
    st.sidebar.caption(f"Broker: {state.get('name')}")

else:
    st.sidebar.warning("Initializing...")

# --- 1. COCKPIT (Overview) ---
if page == "1. COCKPIT":
    st.title("COMMAND COCKPIT")
    
    if state:
        # Top Row: KPIs
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            st.markdown('<div class="metric-label">TOTAL EQUITY</div>', unsafe_allow_html=True)
            profit = state.get("profit", 0.0)
            col_class = "green" if profit >= 0 else "red"
            st.markdown(f'<div class="big-metric {col_class}">${state.get("equity", 0):,.2f}</div>', unsafe_allow_html=True)
        
        with c2:
            st.markdown('<div class="metric-label">BALANCE</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="big-metric">${state.get("balance", 0):,.2f}</div>', unsafe_allow_html=True)

        with c3:
            st.markdown('<div class="metric-label">REALIZED PNL (ALL)</div>', unsafe_allow_html=True)
            pnl = df_log["PnL"].sum() if not df_log.empty else 0.0
            col_class = "green" if pnl >= 0 else "red"
            st.markdown(f'<div class="big-metric {col_class}">${pnl:,.2f}</div>', unsafe_allow_html=True)
            
        with c4:
            st.markdown('<div class="metric-label">ACTIVE TRADES</div>', unsafe_allow_html=True)
            active_count = len(state.get("active_trades", []))
            st.markdown(f'<div class="big-metric blue">{active_count}</div>', unsafe_allow_html=True)

        st.markdown("---")
        
        # Main Layout: 2/3 Charts, 1/3 Active Positions
        m1, m2 = st.columns([2, 1])
        
        with m1:
            st.markdown("### 📈 Performance Curve")
            if not df_log.empty and "PnL" in df_log.columns:
                 df_realized = df_log[df_log["PnL"] != 0].copy()
                 if not df_realized.empty:
                    df_realized["Timestamp"] = pd.to_datetime(df_realized["Timestamp"])
                    df_realized["Cumulative PnL"] = df_realized["PnL"].cumsum()
                    
                    chart = alt.Chart(df_realized).mark_area(
                        line={'color':'#00ff9d'},
                        color=alt.Gradient(
                            gradient='linear',
                            stops=[alt.GradientStop(color='#00ff9d', offset=0),
                                   alt.GradientStop(color='rgba(0, 255, 157, 0)', offset=1)],
                            x1=1, x2=1, y1=1, y2=0
                        )
                    ).encode(
                        x='Timestamp:T',
                        y='Cumulative PnL:Q'
                    ).properties(height=350).configure_axis(
                        gridColor='#222', domainColor='#333'
                    ).configure_view(strokeWidth=0)
                    st.altair_chart(chart, use_container_width=True)
                 else:
                     st.info("No closed trades to display.")
            else:
                 st.info("Waiting for history...")

        with m2:
            st.markdown("### ✋ Open Positions")
            trades = state.get("active_trades", [])
            for t in trades:
                st.markdown(f"""
                <div class="fin-card">
                    <div style="font-weight:bold; font-size:1.2rem;">{t.get('symbol')}</div>
                    <div style="color:#aaa;">{t.get('action')} | {t.get('volume')} Lots</div>
                    <div style="margin-top:0.5rem; font-family:monospace;">
                        Entry: {t.get('open_price')}<br>
                        SL: {t.get('sl')}<br>
                        TP: {t.get('tp')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            if not trades:
                st.caption("No active exposure.")

# --- 2. CORTEX (Neural Feed) ---
elif page == "2. CORTEX":
    st.title("NEURAL CORTEX")
    
    col_l, col_r = st.columns([1, 2])
    
    with col_l:
        st.markdown("### 🧠 AI Analytics")
        if not df_log.empty:
            df_closed = df_log[df_log["PnL"]!=0]
            total = len(df_closed)
            wins = len(df_closed[df_closed["PnL"]>0])
            wr = (wins/total*100) if total > 0 else 0
            
            st.metric("Win Rate (Reflective Memory)", f"{wr:.1f}%")
            st.metric("Total Decisions Logged", len(df_log))
            
            st.markdown("#### Latest Intent")
            latest = df_log.iloc[-1] if not df_log.empty else {}
            act = latest.get("Action", "N/A")
            conf = latest.get("Confidence", 0)
            
            c = "blue"
            if act == "BUY": c = "green"
            elif act == "SELL": c = "red"
            
            st.markdown(f"<h1 class='{c}'>{act}</h1>", unsafe_allow_html=True)
            st.progress(float(conf))
            st.caption(f"Confidence: {float(conf)*100:.0f}%")
            
    with col_r:
        st.markdown("### 📡 Thought Stream")
        if not df_log.empty:
            # Reverse order for latest first
            for idx, row in df_log.iloc[::-1].iterrows():
                act = row['Action']
                color = "#333"
                if act == "BUY": color = "#00ff9d"
                elif act == "SELL": color = "#ff3b3b"
                
                st.markdown(f"""
                <div class="cortex-item" style="border-color: {color}">
                    <div class="cortex-meta">
                        <span style="color:{color}; font-weight:bold;">{act}</span> 
                        • {row['Timestamp']} • Confidence: {row['Confidence']}
                    </div>
                    <div class="cortex-body">
                        {row['Reasoning']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

# --- 3. DEEP MARKET (Indicators) ---
elif page == "3. DEEP MARKET":
    st.title("MARKET INTELLIGENCE")
    
    if state and "market_data" in state:
        md = state["market_data"]
        
        # Indicator Grid
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Current Price", f"{md.get('close', 0):.4f}")
        d2.metric("RSI (14)", f"{md.get('rsi', 0):.2f}")
        d3.metric("ATR (Vol)", f"{md.get('atr', 0):.4f}")
        d4.metric("Trend", md.get("trend", "N/A"))
        
        st.markdown("---")
        
        # MACD Section
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### MACD Momentum")
            macd = md.get('macd', 0)
            sig = md.get('macd_signal', 0)
            hist = macd - sig
            
            st.metric("MACD", f"{macd:.5f}", delta=f"{hist:.5f} (Hist)")
            st.metric("Signal Line", f"{sig:.5f}")
            
            # Simple Bar Representation
            val = hist * 1000 # Scale for vis
            color = "green" if hist > 0 else "red"
            st.markdown(f"**Histogram Intent**: :{color}[{'|' * int(abs(val))}]")

        with c2:
            st.markdown("### Bollinger Volatility")
            upper = md.get('bb_upper', 0)
            lower = md.get('bb_lower', 0)
            close = md.get('close', 0)
            
            st.metric("Upper Band", f"{upper:.4f}")
            st.metric("Lower Band", f"{lower:.4f}")
            
            # Position in Band
            width = upper - lower
            if width > 0:
                pos = (close - lower) / width
                st.progress(min(max(pos, 0.0), 1.0))
                st.caption(f"Price Position: {pos*100:.1f}% of Range")
            
        st.markdown("### 🧬 Moving Averages")
        e1, e2 = st.columns(2)
        e1.metric("EMA 50 (Fast)", f"{md.get('ema_50', 0):.4f}")
        e2.metric("EMA 200 (Slow)", f"{md.get('ema_200', 0):.4f}")

    else:
        st.info("Waiting for market snapshot... (Next tick)")

# --- 4. LEDGER (Risk & Account) ---
elif page == "4. LEDGER":
    st.title("RISK & ACCOUNT LEDGER")
    
    if state:
        r1, r2 = st.columns(2)
        
        with r1:
            st.markdown("### 🛡️ Risk Management")
            st.json({
                "Risk Per Trade": f"{state.get('risk_per_trade', 0.01)*100}%",
                "Max Leverage": f"1:{state.get('leverage')}",
                "Margin Level": f"{(state.get('equity',1) / state.get('margin',1) * 100):.2f}%" if state.get('margin',0) > 0 else "∞"
            })
            
        with r2:
            st.markdown("### 🏦 Broker Info")
            st.markdown(f"**Name**: {state.get('name')}")
            st.markdown(f"**Server**: {state.get('server')}")
            st.markdown(f"**Base Currency**: {state.get('currency')}")

        st.markdown("### 📝 Detailed Trade Log")
        if not df_log.empty:
            st.dataframe(df_log.sort_values("Timestamp", ascending=False), height=400, use_container_width=True)
            
            if st.button("Download CSV"):
                df_log.to_csv("export_log.csv")
                st.success("Saved to export_log.csv")

# Auto Refresh
time.sleep(REFRESH_RATE_SEC)
st.rerun()
