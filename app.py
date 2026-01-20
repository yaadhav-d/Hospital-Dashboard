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
# WAIT TIME FORMATTER
# -------------------------------------------------
def format_wait_time(minutes):
    minutes = int(minutes)
    if minutes < 60:
        return f"{minutes} min"
    else:
        hrs = minutes // 60
        mins = minutes % 60
        return f"{hrs} hr {mins} min"

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

# Timezone conversion
df["arrival_time"] = pd.to_datetime(df["arrival_time"], utc=True).dt.tz_convert(IST)

# Display-friendly columns
df["Arrival Time (IST)"] = df["arrival_time"].dt.strftime("%I:%M %p")
df["Temperature Band"] = df["temperature_at_arrival"].apply(temperature_band)
df["Wait Duration"] = df["wait_time"].apply(format_wait_time)

# Presentation layer (human-friendly)
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

st.markdown("")

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

fig_triage = px.pie(
    triage_counts,
    names="Triage Level",
    values="Patients",
    hole=0.55,
    title="Triage Severity Distribution",
    template="plotly_dark"
)
col1.plotly_chart(fig_triage, use_container_width=True)

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
# CRITICAL TRIAGE ALERTS
# -------------------------------------------------
st.subheader("🚨 Critical Triage Alerts")

critical_cols = [
    "Patient Code",
    "Patient Name",
    "Triage Level",
    "Wait Duration",
    "Department",
    "Arrival Time (IST)",
    "Temp at Arrival (°C)"
]

st.dataframe(
    critical_df[critical_cols].head(10),
    use_container_width=True
)

# -------------------------------------------------
# LIVE PATIENT FEED
# -------------------------------------------------
st.subheader("📋 Live Patient Feed")

live_cols = [
    "Patient Code",
    "Patient Name",
    "Triage Level",
    "Wait Duration",
    "Department",
    "Arrival Time (IST)",
    "Temp at Arrival (°C)",
    "Temperature Band"
]

st.dataframe(
    df_display[live_cols].head(15),
    use_container_width=True
)
