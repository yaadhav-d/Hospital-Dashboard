import pandas as pd
import streamlit as st
import mysql.connector
import requests
import plotly.express as px
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# ----------------------------
# PAGE CONFIG
# ----------------------------
st.set_page_config(
    page_title="ER Command Center",
    layout="wide"
)

# ----------------------------
# AUTO REFRESH (EVERY 1 MIN)
# ----------------------------
st_autorefresh(interval=60 * 1000, key="er_refresh")

# ----------------------------
# SECRETS (STREAMLIT CLOUD)
# ----------------------------
DB_CONFIG = {
    "host": st.secrets["DB_HOST"],
    "user": st.secrets["DB_USER"],
    "password": st.secrets["DB_PASSWORD"],
    "database": st.secrets["DB_NAME"],
    "port": int(st.secrets["DB_PORT"])
}

WEATHER_API_KEY = st.secrets["WEATHER_API_KEY"]
CITY = "Chennai"

# ----------------------------
# DB HELPERS
# ----------------------------
def get_conn():
    return mysql.connector.connect(**DB_CONFIG)

def load_data():
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT patient_code, patient_name, triage_level,
               wait_time, department, arrival_time
        FROM er_patients_live
        ORDER BY arrival_time DESC
        LIMIT 500
        """,
        conn
    )
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
# LOAD DATA
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
# KPIs
# ----------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Current ER Occupancy", total_patients)
c2.metric("Average Wait Time (min)", avg_wait)
c3.metric("Critical Patients", len(critical))

# ============================
# 📊 CORE OPERATIONAL CHARTS
# ============================

col1, col2 = st.columns(2)

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
    title="Triage Severity Distribution",
    template="plotly_dark"
)

col1.plotly_chart(fig_donut, use_container_width=True)

# ----------------------------
# BAR — DEPARTMENT LOAD
# ----------------------------
dept_counts = df["department"].value_counts().reset_index()
dept_counts.columns = ["Department", "Patients"]

fig_dept = px.bar(
    dept_counts,
    x="Patients",
    y="Department",
    orientation="h",
    title="Department Load",
    text="Patients",
    template="plotly_dark"
)

col2.plotly_chart(fig_dept, use_container_width=True)

# ============================
# 🌦 WEATHER IMPACT ON PATIENT FLOW
# ============================

condition, temperature = get_weather()

# Patient inflow per 10 minutes
flow = (
    df
    .set_index("arrival_time")
    .resample("10T")
    .size()
    .reset_index(name="Patients")
)

# Weather line (constant temp over time window)
flow["Temperature"] = temperature

fig_weather = go.Figure()

fig_weather.add_trace(
    go.Bar(
        x=flow["arrival_time"],
        y=flow["Patients"],
        name="Patient Inflow",
        yaxis="y1"
    )
)

fig_weather.add_trace(
    go.Scatter(
        x=flow["arrival_time"],
        y=flow["Temperature"],
        name="Temperature (°C)",
        yaxis="y2",
        mode="lines+markers"
    )
)

fig_weather.update_layout(
    title="Weather Impact on ER Patient Flow",
    template="plotly_dark",
    height=420,
    xaxis_title="Time",
    yaxis=dict(title="Patients"),
    yaxis2=dict(
        title="Temperature (°C)",
        overlaying="y",
        side="right"
    )
)

st.plotly_chart(fig_weather, use_container_width=True)

# ----------------------------
# WEATHER INFO
# ----------------------------
st.info(f"Current Weather: {condition} | {temperature}°C")

if condition in ["Rain", "Thunderstorm"] or temperature > 35:
    st.warning("⚠ Extreme weather detected — ER inflow trend should be monitored")

# ============================
# ALERTS & LIVE FEED
# ============================

st.subheader("🚨 Critical Triage Alerts (Level 1 & 2)")
st.dataframe(critical.head(5), use_container_width=True)

st.subheader("📋 Live Patient Feed")
st.dataframe(df.head(15), use_container_width=True)
