import time
import pandas as pd
import streamlit as st
import mysql.connector
import requests

# ----------------------------
# PAGE CONFIG
# ----------------------------
st.set_page_config(
    page_title="ER Command Center",
    layout="wide"
)

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
# AUTO REFRESH
# ----------------------------
time.sleep(30)
st.rerun()

# ----------------------------
# DATA LOAD
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
# LOAD
# ----------------------------
df = load_data()

total_patients = len(df)
avg_wait = round(df["wait_time"].mean(), 1) if total_patients else 0
critical = df[df["triage_level"].isin([1, 2])]

# ----------------------------
# UI
# ----------------------------
st.markdown("## 🏥 ER Command Center")

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
except:
    st.warning("Weather data unavailable")

# ----------------------------
# ALERTS
# ----------------------------
st.subheader("🚨 Critical Triage Alerts (Level 1 & 2)")
if not critical.empty:
    st.dataframe(critical.head(5), use_container_width=True)
else:
    st.success("No critical patients")

# ----------------------------
# LIVE FEED
# ----------------------------
st.subheader("📋 Live Patient Feed")
st.dataframe(df.head(15), use_container_width=True)
