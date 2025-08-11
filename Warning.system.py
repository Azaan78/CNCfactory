import sys
import json
import time
import logging
from collections import deque
import statistics

# --- Configuration ---
WINDOW_SIZE = 10
TEMP_THRESHOLD = 75  # °C threshold for immediate alert
Z_SCORE_LIMIT = 2.5  # Z-score threshold for anomaly

# Setup logging
logging.basicConfig(filename='temperature_alerts.log', level=logging.INFO, format='%(asctime)s %(message)s')

# Temperature history buffer per machine
machine_temp_data = {}


# --- Core Function: Detect Anomalies ---
def detect_anomaly(machine_id, temp):
    if machine_id not in machine_temp_data:
        machine_temp_data[machine_id] = deque(maxlen=WINDOW_SIZE)

    readings = machine_temp_data[machine_id]
    readings.append(temp)

    if len(readings) < 5:
        return False, None  # Not enough data yet

    mean = statistics.mean(readings)
    stdev = statistics.stdev(readings)

    if stdev == 0:
        return False, None

    z_score = (temp - mean) / stdev

    if temp > TEMP_THRESHOLD or z_score > Z_SCORE_LIMIT:
        reason = "HIGH_TEMP" if temp > TEMP_THRESHOLD else "Z_SCORE_SPIKE"
        return True, {
            "machine_id": machine_id,
            "temperature": temp,
            "z_score": round(z_score, 2),
            "mean_temp": round(mean, 2),
            "anomaly_reason": reason,
            "timestamp": time.time()
        }

    return False, None


# --- Alert Formatter ---
def generate_alert(anomaly_data):
    alert = {
        "type": "TEMP_ANOMALY",
        "machine": anomaly_data["machine_id"],
        "temperature": anomaly_data["temperature"],
        "z_score": anomaly_data["z_score"],
        "reason": anomaly_data["anomaly_reason"],
        "timestamp": anomaly_data["timestamp"]
    }

    alert_json = json.dumps(alert)
    logging.info(f"ALERT: {alert_json}")
    print(alert_json)


# --- Main Processor: Handle One Simulation Output Line ---
def process_simulation_output(sim_json: str):
    try:
        data = json.loads(sim_json)
        temp = data.get("spindle_temp")

        if temp is None:
            return  # Ignore if spindle_temp missing

        # Identify machine_id from known keys in Azaan's JSON output
        if "tool_id" in data:
            machine_id = f"CNCMill_Tool{data['tool_id']}"
        elif "robotic_arm_task" in data:
            machine_id = "Robotic_Arm"
        elif "conveyor_position" in data:
            machine_id = "Conveyor_Belt"
        elif "inspection_result" in data:
            machine_id = "Inspection_System"
        else:
            machine_id = "Unknown_Machine"

        is_anomaly, anomaly_data = detect_anomaly(machine_id, temp)
        if is_anomaly:
            generate_alert({**anomaly_data, "cycle_id": data.get("cycle_id")})

    except json.JSONDecodeError:
        print("⚠️ Skipped: Received malformed or non-JSON line.")


# --- Main Listener: Read Azaan's Output via Pipe ---
def main():
    print("🔍 Real-time analytics running. Waiting for simulation data...\n")
    for line in sys.stdin:
        process_simulation_output(line.strip())


if __name__ == "__main__":
    main()