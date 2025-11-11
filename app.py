import streamlit as st
import threading
import time
import re
import os
import sqlite3
import socket
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from dateutil import tz
from collections import deque, Counter
from streamlit_autorefresh import st_autorefresh
from functools import lru_cache

# =====================================================
# CONFIGURAÇÕES INICIAIS
# =====================================================
LOG_PATH = "/var/log/squid/access.log"
DB_PATH = "squid_monitor.db"

# Buffer global thread-safe
BUFFER = deque(maxlen=10000)

# =====================================================
# BANCO DE DADOS
# =====================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Tabela de cache DNS
    c.execute("""
        CREATE TABLE IF NOT EXISTS dns_cache (
            ip TEXT PRIMARY KEY,
            hostname TEXT,
            updated TIMESTAMP
        )
    """)

    # Tabela de logs de acesso
    c.execute("""
        CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TIMESTAMP,
            client_ip TEXT,
            client_host TEXT,
            method TEXT,
            url TEXT,
            result TEXT,
            size INTEGER
        )
    """)

    conn.commit()
    conn.close()

init_db()

# =====================================================
# CACHE DNS PERSISTENTE
# =====================================================
def get_cached_hostname(ip):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT hostname, updated FROM dns_cache WHERE ip = ?", (ip,))
    row = c.fetchone()
    conn.close()
    if row:
        hostname, updated = row
        if datetime.now() - datetime.fromisoformat(updated) < timedelta(days=7):
            return hostname
    return None

def set_cached_hostname(ip, hostname):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO dns_cache (ip, hostname, updated)
        VALUES (?, ?, ?)
    """, (ip, hostname, datetime.now().isoformat()))
    conn.commit()
    conn.close()

@lru_cache(maxsize=2048)
def resolve_dns(ip):
    cached = get_cached_hostname(ip)
    if cached:
        return cached
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except Exception:
        hostname = ip
    set_cached_hostname(ip, hostname)
    return hostname

# =====================================================
# PARSE DO LOG
# =====================================================
LINE_RE = re.compile(
    r'^(?P<ts>\d+\.\d+)\s+(?P<elapsed>\S+)\s+(?P<client>\S+)\s+(?P<result>\S+)\s+'
    r'(?P<size>\S+)\s+(?P<method>\S+)\s+(?P<url>\S+)'
)
IP_RE = re.compile(r'(\d{1,3}(?:\.\d{1,3}){3})')

def parse_line(line):
    m = LINE_RE.match(line.strip())
    if not m:
        return None
    ts = float(m.group("ts"))
    client_field = m.group("client")
    ip_search = IP_RE.search(client_field)
    ip = ip_search.group(1) if ip_search else client_field
    host = resolve_dns(ip)
    try:
        size = int(m.group("size")) if m.group("size").isdigit() else 0
    except:
        size = 0
    return {
        "time": datetime.fromtimestamp(int(ts), tz=tz.tzlocal()),
        "client_ip": ip,
        "client_host": host,
        "method": m.group("method"),
        "url": m.group("url"),
        "result": m.group("result"),
        "size": size
    }

# =====================================================
# SALVAR ACESSOS NO BANCO
# =====================================================
def save_access_to_db(entry):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO access_log (time, client_ip, client_host, method, url, result, size)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        entry["time"].isoformat(),
        entry["client_ip"],
        entry["client_host"],
        entry["method"],
        entry["url"],
        entry["result"],
        entry["size"]
    ))
    conn.commit()
    conn.close()

# =====================================================
# MONITORAMENTO DO LOG
# =====================================================
def tail_file(path, stop_event):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, 2)
            while not stop_event.is_set():
                line = f.readline()
                if not line:
                    time.sleep(0.3)
                    continue
                parsed = parse_line(line)
                if parsed:
                    save_access_to_db(parsed)
                    BUFFER.appendleft(parsed)
    except Exception as e:
        BUFFER.appendleft({"error": str(e)})

# =====================================================
# INTERFACE STREAMLIT
# =====================================================
st.set_page_config(page_title="Squid Proxy Monitor", layout="wide")
st.title("🦑 Squid Proxy Monitor (com SQLite e DNS Cache)")

st.sidebar.header("Configurações")
log_path = st.sidebar.text_input("Caminho do access.log", LOG_PATH)
refresh_rate = st.sidebar.slider("Atualização (s)", 1, 10, 3)
max_lines = st.sidebar.slider("Linhas exibidas", 100, 5000, 1000, 100)

# Inicializa thread do monitor
if "stop_event" not in st.session_state:
    st.session_state.stop_event = threading.Event()

if "thread" not in st.session_state or not st.session_state.thread.is_alive():
    st.session_state.stop_event.clear()
    t = threading.Thread(target=tail_file, args=(log_path, st.session_state.stop_event), daemon=True)
    st.session_state.thread = t
    t.start()

# Atualização automática
st_autorefresh(interval=refresh_rate * 1000, key="refresh")

# Consulta dados do banco
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("SELECT * FROM access_log ORDER BY time DESC LIMIT ?", conn, params=(max_lines,))
conn.close()

if not df.empty:
    st.subheader("📋 Últimos acessos")
    st.dataframe(df, width="stretch")

    # =====================================================
    # TOP 50 SITES MAIS ACESSADOS (GRÁFICO DE PIZZA)
    # =====================================================
    st.subheader("🍕 Top 50 Sites mais acessados")
    df["dominio"] = df["url"].apply(lambda x: re.sub(r"^https?://(www\.)?", "", x).split("/")[0])
    top_sites = Counter(df["dominio"]).most_common(50)
    top_df = pd.DataFrame(top_sites, columns=["Domínio", "Acessos"])
    fig = px.pie(top_df, names="Domínio", values="Acessos", title="Top 50 Domínios", hole=0.3)
    st.plotly_chart(fig, use_container_width=True)

    # =====================================================
    # TRÁFEGO POR CLIENTE (GRÁFICO DE BARRAS)
    # =====================================================
    st.subheader("📈 Tráfego total por cliente")
    df_group = df.groupby("client_host")["size"].sum().reset_index()
    fig2 = px.bar(df_group, x="client_host", y="size", title="Tráfego total (bytes) por cliente")
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Aguardando dados do log do Squid...")

# Botão parar
if st.button("🛑 Parar monitor"):
    st.session_state.stop_event.set()
    if st.session_state.thread.is_alive():
        st.session_state.thread.join(timeout=1)
    st.success("Monitor parado.")
