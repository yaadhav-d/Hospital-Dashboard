import pandas as pd
import streamlit as st
import mysql.connector
import requests
from streamlit.runtime.scriptrunner import add_script_run_ctx
from streamlit_autorefresh import st_autorefresh

# ----------------------------
# PAGE CONFIG
# ----------------------------
st.set_page_config(
    page_title="ER Command Center",
    layout="wide"
)

# ----------------------------
# AUTO REFRESH (EVERY 30s)
# ----------------------------
st_autorefresh(interval=30 * 1000, key="er_refresh")

# ----------------------------
# DATABASE CONFIG
# ----------------------------
DB_CONFIG = {
    "host": "hopper.proxy.rlwy.net",
    "user": "root",
    "password": "FvyCUTYQxcYEiJOnmqmanwRoWnlVzzVV",
    "database": "railway",
    "port": 20747
}

# ----------------------------
# WEATHER CONFIG
# ----------------------------
WEATHER_API_KEY = "efd6b4dcc0f1b762d34a167b399098a5"
CITY = "Chennai"

# ----------------------------
# LOAD DATA
# ----------------------------
def load_data():
    conn = mysql.connector.connect(**DB_CONFIG)
    query = """
        SELECT patient_code, patient_name, triage_level,
               wait_time, department, arrival_time
        FROM er_patients_live
        ORDER BY arrival_time DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def get_weather():
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={CITY}&appid={WEATHER_API_KEY}&units=metric"
    )
    data = requests.get(url).json()
    return data["weather"][0]["main"], data["main"]["temp"]

# ----------------------------
# MAIN DATA
# ----------------------------
df = load_data()

if df.empty:
    st.warning("No ER patient data available yet.")
    st.stop()

total_patients = len(df)
avg_wait = round(df["wait_time"].mean(), 1)
critical = df[df["triage_level"].isin([1, 2])]

# ----------------------------
# HEADER
# ----------------------------
st.markdown("## 🏥 ER Command Center")

# ----------------------------
# KPI ROW
# ----------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Current ER Occupancy", total_patients)
c2.metric("Average Wait Time (min)", avg_wait)
c3.metric("Critical Patients", len(critical))

# ----------------------------
# WEATHER
# ----------------------------
try:
    condition, temp = get_weather()
    st.info(f"Weather: {condition} | {temp}°C")

    if condition in ["Rain", "Thunderstorm"] or temp > 35:
        st.warning("⚠ Extreme weather detected — possible ER inflow spike")
except Exception:
    st.warning("Weather data unavailable")

# ----------------------------
# CRITICAL ALERTS
# ----------------------------
st.subheader("🚨 Critical Triage Alerts (Level 1 & 2)")
if not critical.empty:
    st.dataframe(critical.head(5), use_container_width=True)
else:
    st.success("No critical patients currently")

# ----------------------------
# LIVE FEED
# ----------------------------
st.subheader("📋 Live Patient Feed")
st.dataframe(df.head(15), use_container_width=True)
