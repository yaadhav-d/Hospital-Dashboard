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
IST = pytz.timezone("Asia/Kolkata")

DEPARTMENTS = [
    "General Medicine",
    "Orthopedics",
    "Cardiology",
    "Neurology",
    "Pediatrics",
    "Trauma"
]

# -------------------------------------------------
# CONFIGURABLE ER RULES
# -------------------------------------------------
MAX_ER_HOURS = 6          # discharge patients older than this
AUTO_INSERT_INTERVAL = 60  # seconds

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

def format_wait_time(minutes):
    minutes = int(minutes)
    if minutes < 60:
        return f"{minutes} min"
    hrs = minutes // 60
    mins = minutes % 60
    return f"{hrs} hr {mins} min"

# -------------------------------------------------
# 🧹 AUTO DISCHARGE FUNCTION
# -------------------------------------------------
def cleanup_discharged_patients():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""
        DELETE FROM er_patients_live
        WHERE arrival_time < NOW() - INTERVAL {MAX_ER_HOURS} HOUR
        """
    )
    conn.commit()
    cursor.close()
    conn.close()

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
            random.randint(5, 140),
            random.choice(DEPARTMENTS),
            round(temperature + random.uniform(-1.5, 1.5), 1)
        )
    )
    conn.commit()
    cursor.close()
    conn.close()

# -------------------------------------------------
# APP WAKE LOGIC (ORDER MATTERS)
# -------------------------------------------------
# 1️⃣ Cleanup old patients
cleanup_discharged_patients()

# 2️⃣ Insert new patient (once per minute)
if "last_insert_ts" not in st.session_state:
    st.session_state["last_insert_ts"] = 0

if time.time() - st.session_state["last_insert_ts"] >= AUTO_INSERT_INTERVAL:
    insert_fake_patient()
    st.session_state["last_insert_ts"] = time.time()

# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------
df = load_data()

if df.empty:
    st.warning("No ER patient data available yet.")
    st.stop()

df["arrival_time"] = pd.to_datetime(df["arrival_time"], utc=True).dt.tz_convert(IST)
df["Arrival Time (IST)"] = df["arrival_time"].dt.strftime("%I:%M %p")
df["Temperature Band"] = df["temperature_at_arrival"].apply(temperature_band)
df["Wait Duration"] = df["wait_time"].apply(format_wait_time)

df_display = df.rename(columns={
    "patient_code": "Patient Code",
    "patient_name": "Patient Name",
    "triage_level": "Triage Level",
    "department": "Department",
    "temperature_at_arrival": "Temp at Arrival (°C)"
})

total_patients = len(df)
avg_wait = round(df["wait_time"].mean(), 1)
critical_df = df_display[df_display["Triage Level"].isin([1, 2])]

latest_patient = df_display.iloc[0]
latest_time = df.iloc[0]["Arrival Time (IST)"]

# -------------------------------------------------
# HEADER
# -------------------------------------------------
st.markdown(
    """
    <div style="padding:16px;border-radius:14px;
                background:linear-gradient(90deg,#1f2937,#111827);
                color:white;">
        <h1 style="margin-bottom:4px;">🏥 ER Command Center</h1>
        <p style="margin:0;color:#d1d5db;">
            Live Emergency Operations & Patient Flow Monitoring
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------
# KPI ROW
# -------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Current ER Occupancy", total_patients)
k2.metric("Avg Wait Time (min)", avg_wait)
k3.metric("Critical Patients", len(critical_df))
k4.metric(
    "Latest Entry",
    latest_patient["Patient Name"],
    f"{latest_patient['Department']} • {latest_time}"
)

# -------------------------------------------------
# CHARTS
# -------------------------------------------------
col1, col2 = st.columns(2)

triage_counts = df["triage_level"].value_counts().sort_index().reset_index()
triage_counts.columns = ["Triage Level", "Patients"]
col1.plotly_chart(
    px.pie(triage_counts, names="Triage Level", values="Patients",
           hole=0.55, title="Triage Severity Distribution",
           template="plotly_dark"),
    use_container_width=True
)

dept_counts = df["department"].value_counts().reset_index()
dept_counts.columns = ["Department", "Patients"]
col2.plotly_chart(
    px.bar(dept_counts, x="Patients", y="Department",
           orientation="h", title="Department Load",
           template="plotly_dark"),
    use_container_width=True
)

temp_counts = df["Temperature Band"].value_counts().reset_index()
temp_counts.columns = ["Temperature Band", "Patients"]
st.plotly_chart(
    px.pie(temp_counts, names="Temperature Band", values="Patients",
           hole=0.55, title="Patient Distribution by Temperature Range",
           template="plotly_dark"),
    use_container_width=True
)

# -------------------------------------------------
# TABLES
# -------------------------------------------------
st.subheader("🚨 Critical Triage Alerts")
st.dataframe(
    critical_df[[
        "Patient Code", "Patient Name", "Triage Level",
        "Wait Duration", "Department",
        "Arrival Time (IST)", "Temp at Arrival (°C)"
    ]].head(10),
    use_container_width=True
)

st.subheader("📋 Live Patient Feed")
st.dataframe(
    df_display[[
        "Patient Code", "Patient Name", "Triage Level",
        "Wait Duration", "Department",
        "Arrival Time (IST)", "Temp at Arrival (°C)",
        "Temperature Band"
    ]].head(15),
    use_container_width=True
)
