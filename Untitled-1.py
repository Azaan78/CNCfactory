"""This file is the simulator engine for CNC machine factories dealing with the factories machines, sensors and KG's"""
#Imports
import random
import time
import json
import os
import csv   # ADDED

# -------- KG CSV Loader (NEW) --------
# ADDED: Function to load a KG CSV into a dictionary mapping
def load_kg_csv(file_path):
    mapping = {}
    try:
        with open(file_path, mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            for row in reader:
                source = row["Source entity"].strip()
                mapping[source] = {
                    "relationship": row["relationship"].strip(),
                    "target_entity": row["target entity"].strip()
                }
    except FileNotFoundError:
        print(f"[WARNING] KG file not found: {file_path}")
    return mapping

# ADDED: Load all KG mappings
maintenance_map = load_kg_csv("maintenance-kg.csv")
normal_map = load_kg_csv("normal-kg.csv")
cyberattack_map = load_kg_csv("cyberattack-kg.csv")

# -------- Components and sensor classes --------
# (No changes here)
class Sensor:
    def __init__(self, name:str):
        self.name = name

    def read(self):
        raise NotImplementedError

class SpindleTempSensor(Sensor):
    def read(self):
        return round(random.uniform(45, 100), 2)

class VibrationSensor(Sensor):
    def read(self):
        return round(random.uniform(0.2, 4.0), 2)

class PowerDrawSensor(Sensor):
    def read(self):
        return round(random.uniform(200, 450), 1)

class PositionEncoder(Sensor):
    def read(self):
        return {
            "X": round(random.uniform(0, 100), 1),
            "Y": round(random.uniform(0, 100), 1),
            "Z": round(random.uniform(0, 50), 1),
        }

class VisionQCSensor(Sensor):
    def read(self):
        return random.choice(["PASS", "FAIL"])

class AutomaticToolChanger:
    def __init__(self, tools: list[int]):
        self.tools = tools
        self.current_tool = tools[0]

    def check_and_change_tool(self, cycle_id: int):
        if cycle_id % 10 == 0:
            self.current_tool = random.choice(self.tools)
        return self.current_tool

# -------- Machine classes --------
class Machine:
    def __init__(self, name: str):
        self.name = name

    def perform_operation(self, cycle_id: int):
        raise NotImplementedError

class CNCMill(Machine):
    def __init__(self, name: str, atc: AutomaticToolChanger):
        super().__init__(name)
        self.atc = atc

    def perform_operation(self, cycle_id: int):
        op = random.choice(["cutting", "drilling", "idle"])
        tool = self.atc.check_and_change_tool(cycle_id)
        return {
            "operation": op,
            "tool_id": tool
        }

class RoboticArm(Machine):
    def perform_operation(self, cycle_id: int):
        task = random.choice(["load_material", "unload_part", "assemble_component", "idle"])
        return {
            "robotic_arm_task": task
        }

class ConveyorBelt(Machine):
    def perform_operation(self, cycle_id: int):
        position = random.choice(["Station A", "Station B", "Inspection", "Exit"])
        part_id = f"PART-{1000 + cycle_id}"
        return {
            "conveyor_position": position,
            "part_id": part_id
        }

class InspectionSystem(Machine):
    def perform_operation(self, cycle_id: int):
        decision = random.choice(["PASS", "FAIL"])
        confidence = round(random.uniform(0.7, 1.0), 2)
        return {
            "inspection_result": decision,
            "inspection_confidence": confidence
        }

# -------- Message class --------
class SimulationMessage:
    def __init__(self, cycle_id: int, machine_data: dict, sensor_readings: dict):
        self.cycle_id = cycle_id
        self.timestamp = time.time()
        self.machine = machine_data
        self.sensors = sensor_readings

    def to_json(self):
        payload = {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            **self.machine,
            **self.sensors
        }
        return json.dumps(payload)

# -------- Engine --------
class CNCFactory:
    def __init__(self, machines:list[Machine], sensors:list[Sensor]):
        self.machines = machines
        self.sensors = sensors

    def get_data_source(self):
        mode = os.getenv("MODE", "SIM")
        if mode == "REAL":
            return self.read_real_data()
        else:
            return None

    def read_real_data(self):
        return {
            "operation": "cutting",
            "tool_id": 2,
            "spindle_temp": 82.5,
            "vibration": 1.1,
            "power_draw": 310.2,
            "position": {"X": 50.0, "Y": 30.0, "Z": 10.0},
            "inspection": "PASS",
        }

    def run_cycle(self, cycle_id: int):
        machine_data = {}
        for m in self.machines:
            machine_data.update(m.perform_operation(cycle_id))

        sensor_readings = {}
        real = self.get_data_source()
        if real:
            sensor_readings = {
                "spindle_temp": real["spindle_temp"],
                "vibration": real["vibration"],
                "power_draw": real["power_draw"],
                "position": real["position"],
                "inspection": real["inspection"],
            }
        else:
            for s in self.sensors:
                sensor_readings[s.name] = s.read()

        msg = SimulationMessage(cycle_id, machine_data, sensor_readings)
        classification = classify_state(sensor_readings, machine_data)
        send_to_KG(msg.to_json(), classification)

# ---- KG Mapping & Output ----
def classify_state(sensors: dict, machine: dict):
    if sensors["spindle_temp"] >75 and sensors["spindle_temp"] <= 90:
        return "Maintenance_KG:Possible_Overheating"
    if sensors["spindle_temp"] > 90:
        if sensors["power_draw"] > 350 and sensors["power_draw"] < 400:
            return "Cyberattack_KG:Possible_Glitch/Firmware"
        elif sensors["power_draw"] >= 400:
            return "Cyberattack_KG:Likely_Glitch/Firmware"
        else:
            return "Maintenance_KG:Spindle_Overheat"

    if sensors["vibration"] > 1.5 and sensors["vibration"] <= 3.5:
        return "Cyberattack_KG:Possible_Vibration_Sabotage"
    if sensors["vibration"] > 3.5:
        return "Cyberattack_KG:Likely_Vibration_Sabotage"

    if sensors["power_draw"] >= 350 and sensors["power_draw"] < 400:
        return "PowerDraw_KG:Possible_Elevated_Load"
    if sensors["power_draw"] >= 400:
        return "PowerDraw_KG:High_Power_Consumption"

    EXPECTED_POSITION = {"X": 50.0, "Y": 30.0, "Z": 10.0}
    TOLERANCE_WARNING = 5.0
    TOLERANCE_CRITICAL = 10.0
    pos = sensors["position"]
    max_dev = max(abs(pos[axis] - EXPECTED_POSITION[axis]) for axis in ["X", "Y", "Z"])    
    if max_dev > TOLERANCE_WARNING and max_dev <= TOLERANCE_CRITICAL:
        return "Maintenance_KG:Minor_Position_Drift"
    if max_dev > TOLERANCE_CRITICAL:
        return "Cyberattack_KG:Major_Position_Change"

    if machine.get("tool_id") and machine["tool_id"] not in [1, 2, 3]:
        return "Maintenance_KG:Tool_Change"

    if sensors["inspection"] == "FAIL":
        return "Normal_KG:Inspection_Fail"
    return "Normal_KG:Operation_Normal"

def send_to_KG(payload_json: str, classification: str):
    record = json.loads(payload_json)
    record["kg_node"] = classification

    # ADDED: Find KG triple from CSV
    triple = None
    if "Maintenance_KG" in classification:
        triple = maintenance_map.get(classification)
    elif "Normal_KG" in classification:
        triple = normal_map.get(classification)
    elif "Cyberattack_KG" in classification:
        triple = cyberattack_map.get(classification)

    record["kg_triple"] = triple  # ADDED
    print(json.dumps(record))

# ---- Main Execution ----
if __name__ == "__main__":
    NUM_CYCLES  = 5
    CYCLE_DELAY = 1  

    sensors = [
        SpindleTempSensor("spindle_temp"),
        VibrationSensor("vibration"),
        PowerDrawSensor("power_draw"),
        PositionEncoder("position"),
        VisionQCSensor("inspection"),
    ]

    atc = AutomaticToolChanger([1, 2, 3, 4, 5])

    machines = [
        CNCMill("CNC_Mill_1", atc),
        RoboticArm("Robotic_Arm_1"),
        ConveyorBelt("Conveyor_1"),
        InspectionSystem("Inspection_Station")
    ]

    factory = CNCFactory(machines, sensors)

    for cycle in range(1, NUM_CYCLES + 1):
        factory.run_cycle(cycle)
        time.sleep(CYCLE_DELAY)
