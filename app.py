import time
import random
import pandas as pd
import streamlit as st
import mysql.connector
import requests
import plotly.express as px
from faker import Faker
from streamlit_autorefresh import st_autorefresh
import pytz

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
# STREAMLIT SECRETS
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

fake = Faker()

DEPARTMENTS = [
    "General Medicine",
    "Orthopedics",
    "Cardiology",
    "Neurology",
    "Pediatrics",
    "Trauma"
]

IST = pytz.timezone("Asia/Kolkata")

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
# SAFE AUTO INSERT (ON APP WAKE)
# -------------------------------------------------
def insert_fake_patient():
    _, temperature = get_weather()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO er_patients_live
        (
            patient_code,
            patient_name,
            triage_level,
            wait_time,
            department,
            temperature_at_arrival
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            f"ER-{random.randint(100000, 999999)}",
            fake.name(),
            random.choices([1, 2, 3, 4, 5], weights=[5, 10, 35, 30, 20])[0],
            random.randint(5, 120),
            random.choice(DEPARTMENTS),
            round(temperature + random.uniform(-1.5, 1.5), 1)
        )
    )

    conn.commit()
    cursor.close()
    conn.close()

if "last_insert_ts" not in st.session_state:
    st.session_state["last_insert_ts"] = 0

if time.time() - st.session_state["last_insert_ts"] >= 60:
    insert_fake_patient()
    st.session_state["last_insert_ts"] = time.time()

# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------
df = load_data()

if df.empty:
    st.warning("No ER patient data available yet.")
    st.stop()

# Convert arrival_time to IST (timezone-safe)
df["arrival_time"] = pd.to_datetime(df["arrival_time"], utc=True).dt.tz_convert(IST)

# 🔑 DISPLAY-ONLY TIME COLUMN (12-hour format)
df["Arrival Time (IST)"] = df["arrival_time"].dt.strftime("%I:%M %p")

total_patients = len(df)
avg_wait = round(df["wait_time"].mean(), 1)
critical_df = df[df["triage_level"].isin([1, 2])]

latest_patient = df.iloc[0]
latest_time_ist = latest_patient["Arrival Time (IST)"]

# -------------------------------------------------
# HEADER (ENHANCED)
# -------------------------------------------------
st.markdown(
    """
    <div style="padding:15px;border-radius:12px;
                background:linear-gradient(90deg,#1f2937,#111827);
                color:white;">
        <h1 style="margin-bottom:0;">🏥 ER Command Center</h1>
        <p style="margin-top:5px;color:#d1d5db;">
            Real-time Emergency Room Operations & Patient Flow Monitoring
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("")

# -------------------------------------------------
# KPI ROW + LATEST ENTRY
# -------------------------------------------------
k1, k2, k3, k4 = st.columns(4)

k1.metric("Current ER Occupancy", total_patients)
k2.metric("Average Wait Time (min)", avg_wait)
k3.metric("Critical Patients", len(critical_df))
k4.metric(
    "Latest Entry",
    latest_patient["patient_name"],
    f"{latest_patient['department']} • {latest_time_ist}"
)

# =================================================
# 📊 CHARTS
# =================================================
col1, col2 = st.columns(2)

# TRIAGE DONUT
triage_counts = df["triage_level"].value_counts().sort_index().reset_index()
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

# DEPARTMENT LOAD
dept_counts = df["department"].value_counts().reset_index()
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
# 🌡 TEMPERATURE DONUT
# =================================================
df["Temperature Band"] = df["temperature_at_arrival"].apply(temperature_band)

temp_counts = df["Temperature Band"].value_counts().reset_index()
temp_counts.columns = ["Temperature Band", "Patients"]

fig_temp = px.pie(
    temp_counts,
    names="Temperature Band",
    values="Patients",
    hole=0.55,
    title="Patient Distribution by Temperature Range",
    template="plotly_dark"
)
st.plotly_chart(fig_temp, use_container_width=True)

# -------------------------------------------------
# ALERTS & LIVE FEED
# -------------------------------------------------
st.subheader("🚨 Critical Triage Alerts")
st.dataframe(critical_df.head(5), use_container_width=True)

st.subheader("📋 Live Patient Feed")

display_cols = [
    "patient_code",
    "patient_name",
    "triage_level",
    "wait_time",
    "department",
    "Arrival Time (IST)",
    "temperature_at_arrival",
    "Temperature Band"
]

st.dataframe(df[display_cols].head(15), use_container_width=True)
