import pandas as pd
import streamlit as st
import mysql.connector
import requests
import plotly.express as px
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
# WEATHER CONFIG (BANNER ONLY)
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
        LIMIT 200
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

df["arrival_time"] = pd.to_datetime(df["arrival_time"])

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

# ============================
# 📊 ATTRACTIVE CHARTS
# ============================

col_left, col_right = st.columns(2)

# ----------------------------
# DONUT — TRIAGE DISTRIBUTION
# ----------------------------
triage_counts = (
    df["triage_level"]
    .value_counts()
    .sort_index()
    .reset_index()
)
triage_counts.columns = ["Triage Level", "Patients"]

fig_donut = px.pie(
    triage_counts,
    names="Triage Level",
    values="Patients",
    hole=0.5,
    title="Triage Severity Distribution"
)

fig_donut.update_layout(
    template="plotly_dark",
    height=380
)

col_left.plotly_chart(fig_donut, use_container_width=True)

# ----------------------------
# BAR — DEPARTMENT LOAD
# ----------------------------
dept_counts = (
    df["department"]
    .value_counts()
    .reset_index()
)
dept_counts.columns = ["Department", "Patients"]

fig_dept = px.bar(
    dept_counts,
    x="Patients",
    y="Department",
    orientation="h",
    title="Department Load",
    text="Patients"
)

fig_dept.update_layout(
    template="plotly_dark",
    height=380
)

col_right.plotly_chart(fig_dept, use_container_width=True)

# ============================
# ⏱ AVERAGE WAIT TIME BY DEPARTMENT (REPLACEMENT CHART)
# ============================
wait_by_dept = (
    df.groupby("department")["wait_time"]
    .mean()
    .round(1)
    .reset_index()
    .sort_values("wait_time", ascending=True)
)

fig_wait = px.bar(
    wait_by_dept,
    x="wait_time",
    y="department",
    orientation="h",
    title="Average Wait Time by Department (minutes)",
    text="wait_time",
    color="wait_time",
    color_continuous_scale="Oranges"
)

fig_wait.update_layout(
    template="plotly_dark",
    height=350
)

st.plotly_chart(fig_wait, use_container_width=True)

# ----------------------------
# WEATHER BANNER (INFO ONLY)
# ----------------------------
try:
    condition, temp = get_weather()
    st.info(f"Weather: {condition} | {temp}°C")

    if condition in ["Rain", "Thunderstorm"] or temp > 35:
        st.warning("⚠ Extreme weather detected — monitor ER inflow closely")
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
