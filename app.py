import pandas as pd
import streamlit as st
import mysql.connector
import requests
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(
    page_title="ER Command Center",
    layout="wide"
)

# -------------------------------------------------
# AUTO REFRESH (EVERY 1 MINUTE)
# -------------------------------------------------
st_autorefresh(interval=60 * 1000, key="er_refresh")

# -------------------------------------------------
# STREAMLIT SECRETS (FOR DEPLOYMENT)
# -------------------------------------------------
DB_CONFIG = {
    "host": st.secrets["DB_HOST"],
    "user": st.secrets["DB_USER"],
    "password": st.secrets["DB_PASSWORD"],
    "database": st.secrets["DB_NAME"],
    "port": int(st.secrets["DB_PORT"])
}

WEATHER_API_KEY = st.secrets["WEATHER_API_KEY"]
CITY = "Chennai"

# -------------------------------------------------
# DB FUNCTIONS
# -------------------------------------------------
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def load_data():
    conn = get_connection()
    query = """
        SELECT patient_code,
               patient_name,
               triage_level,
               wait_time,
               department,
               arrival_time,
               temperature_at_arrival
        FROM er_patients_live
        ORDER BY arrival_time DESC
        LIMIT 500
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# -------------------------------------------------
# WEATHER FUNCTIONS
# -------------------------------------------------
def get_weather():
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={CITY}&appid={WEATHER_API_KEY}&units=metric"
    )
    data = requests.get(url).json()
    return data["weather"][0]["main"], data["main"]["temp"]

def temperature_band(temp):
    if pd.isna(temp):
        return "Unknown"
    elif temp >= 38:
        return "Extreme Heat"
    elif temp >= 32:
        return "Hot"
    elif temp >= 25:
        return "Normal"
    else:
        return "Cool"

# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------
df = load_data()

if df.empty:
    st.warning("No ER patient data available yet.")
    st.stop()

df["arrival_time"] = pd.to_datetime(df["arrival_time"])

total_patients = len(df)
avg_wait = round(df["wait_time"].mean(), 1)
critical_df = df[df["triage_level"].isin([1, 2])]

# -------------------------------------------------
# WEATHER DATA
# -------------------------------------------------
condition, temperature = get_weather()
current_temp_category = temperature_band(temperature)

# -------------------------------------------------
# HEADER
# -------------------------------------------------
st.markdown("## 🏥 ER Command Center")

# -------------------------------------------------
# KPI ROW
# -------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Current ER Occupancy", total_patients)
c2.metric("Average Wait Time (min)", avg_wait)
c3.metric("Critical Patients", len(critical_df))

# =================================================
# 📊 CHARTS SECTION
# =================================================
col1, col2 = st.columns(2)

# ----------------------------
# TRIAGE DISTRIBUTION (DONUT)
# ----------------------------
triage_counts = (
    df["triage_level"]
    .value_counts()
    .sort_index()
    .reset_index()
)
triage_counts.columns = ["Triage Level", "Patients"]

fig_triage = px.pie(
    triage_counts,
    names="Triage Level",
    values="Patients",
    hole=0.55,
    title="Triage Severity Distribution",
    template="plotly_dark"
)

col1.plotly_chart(fig_triage, use_container_width=True)

# ----------------------------
# DEPARTMENT LOAD (BAR)
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
    text="Patients",
    title="Department Load",
    template="plotly_dark"
)

col2.plotly_chart(fig_dept, use_container_width=True)

# =================================================
# 🌡 TEMPERATURE BASED PATIENT FLOW (DONUT)
# =================================================
df_temp = df.copy()
df_temp["Temperature Band"] = df_temp["temperature_at_arrival"].apply(temperature_band)

temp_counts = (
    df_temp["Temperature Band"]
    .value_counts()
    .reset_index()
)
temp_counts.columns = ["Temperature Band", "Patients"]

fig_temp = px.pie(
    temp_counts,
    names="Temperature Band",
    values="Patients",
    hole=0.55,
    title="Patient Distribution by Temperature Range",
    color="Temperature Band",
    color_discrete_map={
        "Extreme Heat": "#D0021B",
        "Hot": "#F5A623",
        "Normal": "#7ED321",
        "Cool": "#4A90E2",
        "Unknown": "#9B9B9B"
    },
    template="plotly_dark"
)

st.plotly_chart(fig_temp, use_container_width=True)

st.info(f"Current Temperature: **{temperature}°C** → **{current_temp_category}** conditions")

# -------------------------------------------------
# WEATHER ALERT
# -------------------------------------------------
if condition in ["Rain", "Thunderstorm"] or temperature > 35:
    st.warning("⚠ Extreme weather detected — ER inflow may increase")

# =================================================
# 🚨 CRITICAL ALERTS
# =================================================
st.subheader("🚨 Critical Triage Alerts (Level 1 & 2)")
if not critical_df.empty:
    st.dataframe(critical_df.head(5), use_container_width=True)
else:
    st.success("No critical patients currently")

# =================================================
# 📋 LIVE FEED
# =================================================
st.subheader("📋 Live Patient Feed")
st.dataframe(df.head(15), use_container_width=True)
