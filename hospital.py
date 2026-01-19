import time
import random
import logging
from faker import Faker
import mysql.connector
from mysql.connector import Error

# ----------------------------
# CONFIGURATION
# ----------------------------
DB_CONFIG = {
    "host": "hopper.proxy.rlwy.net",
    "user": "root",
    "password": "FvyCUTYQxcYEiJOnmqmanwRoWnlVzzVV",
    "database": "railway",
    "port": 20747
}

INTERVAL_SECONDS = 60  # 1 minute

# ----------------------------
# SETUP
# ----------------------------
fake = Faker()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

DEPARTMENTS = [
    "General Medicine",
    "Orthopedics",
    "Cardiology",
    "Neurology",
    "Pediatrics",
    "Trauma"
]

TRIAGE_WEIGHTS = {
    1: 0.05,  # Critical
    2: 0.10,
    3: 0.35,
    4: 0.30,
    5: 0.20
}

# ----------------------------
# DATABASE CONNECTION
# ----------------------------
def get_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        logging.error(f"DB connection failed: {e}")
        return None

# ----------------------------
# PATIENT GENERATION
# ----------------------------
def generate_patient():
    triage = random.choices(
        population=list(TRIAGE_WEIGHTS.keys()),
        weights=list(TRIAGE_WEIGHTS.values())
    )[0]

    if triage == 1:
        wait_time = random.randint(0, 5)
    elif triage == 2:
        wait_time = random.randint(5, 15)
    elif triage == 3:
        wait_time = random.randint(15, 40)
    elif triage == 4:
        wait_time = random.randint(30, 90)
    else:
        wait_time = random.randint(60, 180)

    return {
        "patient_code": f"ER-{random.randint(100000, 999999)}",
        "patient_name": fake.name(),
        "triage_level": triage,
        "wait_time": wait_time,
        "department": random.choice(DEPARTMENTS)
    }

# ----------------------------
# INSERT LOGIC
# ----------------------------
def insert_patient(conn, patient):
    query = """
        INSERT INTO er_patients_live
        (patient_code, patient_name, triage_level, wait_time, department)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor = conn.cursor()
    cursor.execute(query, (
        patient["patient_code"],
        patient["patient_name"],
        patient["triage_level"],
        patient["wait_time"],
        patient["department"]
    ))
    conn.commit()
    cursor.close()

# ----------------------------
# MAIN LOOP
# ----------------------------
def run():
    logging.info("Hospital ER Live Feed started")

    while True:
        conn = get_connection()
        if conn:
            try:
                patient = generate_patient()
                insert_patient(conn, patient)

                logging.info(
                    f"New Patient | {patient['patient_name']} | "
                    f"Triage {patient['triage_level']} | "
                    f"{patient['department']} | "
                    f"Wait {patient['wait_time']} min"
                )

            except Exception as e:
                logging.error(f"Insertion error: {e}")

            finally:
                conn.close()

        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    run()
