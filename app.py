import time
import random
import pandas as pd
import streamlit as st
import mysql.connector
import requests
import plotly.express as px
from faker import Faker
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
# SECRETS CONFIG (STREAMLIT)
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

fake = Faker()

DEPARTMENTS = [
    "General Medicine",
    "Orthopedics",
    "Cardiology",
    "Neurology",
    "Pediatrics",
    "Trauma"
]

TRIAGE_WEIGHTS = {
    1: 0.05,
    2: 0.10,
    3: 0.35,
    4: 0.30,
    5: 0.20
}

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
        LIMIT 200
        """,
        conn
    )
    conn.close()
    return df

# ----------------------------
# DATA GENERATOR (SAFE)
# ----------------------------
def generate_patient():
    triage = random.choices(
        list(TRIAGE_WEIGHTS.keys()),
        list(TRIAGE_WEIGHTS.values())
    )[0]

    if triage == 1:
        wait = random.randint(0, 5)
    elif triage == 2:
        wait = random.randint(5, 15)
    elif triage == 3:
        wait = random.randint(15, 40)
    elif triage == 4:
        wait = random.randint(30, 90)
    else:
        wait = random.randint(60, 180)

    return {
        "patient_code": f"ER-{random.randint(100000, 999999)}",
        "patient_name": fake.name(),
        "triage_level": triage,
        "wait_time": wait,
        "department": random.choice(DEPARTMENTS)
    }

def insert_patient(patient):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO er_patients_live
        (patient_code, patient_name, triage_level, wait_time, department)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            patient["patient_code"],
            patient["patient_name"],
            patient["triage_level"],
            patient["wait_time"],
            patient["department"]
        )
    )
    conn.commit()
    cursor.close()
    conn.close()

# ----------------------------
# OPTIONAL GENERATOR CONTROL
# ----------------------------
st.sidebar.header("Simulation Control")

if st.sidebar.button("➕ Insert 1 Fake Patient"):
    insert_patient(generate_patient())
    st.sidebar.success("Patient inserted")

# ----------------------------
# DASHBOARD
# ----------------------------
df = load_data()

if df.empty:
    st.warning("No ER patient data available yet.")
    st.stop()

df["arrival_time"] = pd.to_datetime(df["arrival_time"])

total_patients = len(df)
avg_wait = round(df["wait_time"].mean(), 1)
critical = df[df["triage_level"].isin([1, 2])]

st.markdown("## 🏥 ER Command Center")

c1, c2, c3 = st.columns(3)
c1.metric("Current ER Occupancy", total_patients)
c2.metric("Average Wait Time (min)", avg_wait)
c3.metric("Critical Patients", len(critical))

# ----------------------------
# CHARTS
# ----------------------------
col1, col2 = st.columns(2)

triage_counts = df["triage_level"].value_counts().sort_index().reset_index()
triage_counts.columns = ["Triage", "Patients"]

fig_donut = px.pie(
    triage_counts,
    names="Triage",
    values="Patients",
    hole=0.5,
    title="Triage Severity Distribution",
    template="plotly_dark"
)
col1.plotly_chart(fig_donut, use_container_width=True)

dept_counts = df["department"].value_counts().reset_index()
dept_counts.columns = ["Department", "Patients"]

fig_dept = px.bar(
    dept_counts,
    x="Patients",
    y="Department",
    orientation="h",
    title="Department Load",
    template="plotly_dark"
)
col2.plotly_chart(fig_dept, use_container_width=True)

wait_by_dept = (
    df.groupby("department")["wait_time"]
    .mean()
    .round(1)
    .reset_index()
)

fig_wait = px.bar(
    wait_by_dept,
    x="wait_time",
    y="department",
    orientation="h",
    title="Average Wait Time by Department",
    color="wait_time",
    template="plotly_dark"
)

st.plotly_chart(fig_wait, use_container_width=True)

# ----------------------------
# WEATHER BANNER
# ----------------------------
try:
    weather = requests.get(
        f"https://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={WEATHER_API_KEY}&units=metric"
    ).json()

    condition = weather["weather"][0]["main"]
    temp = weather["main"]["temp"]

    st.info(f"Weather: {condition} | {temp}°C")

    if condition in ["Rain", "Thunderstorm"] or temp > 35:
        st.warning("⚠ Extreme weather detected — monitor ER inflow")

except Exception:
    st.warning("Weather unavailable")

# ----------------------------
# ALERTS & FEED
# ----------------------------
st.subheader("🚨 Critical Triage Alerts")
st.dataframe(critical.head(5), use_container_width=True)

st.subheader("📋 Live Patient Feed")
st.dataframe(df.head(15), use_container_width=True)
