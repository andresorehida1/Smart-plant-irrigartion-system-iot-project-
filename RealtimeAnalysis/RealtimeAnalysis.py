import os
import time
import logging
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone

import numpy as np
from influxdb import InfluxDBClient
from sklearn.linear_model import LinearRegression

BACKEND_URL      = os.getenv("BACKEND_URL", "http://127.0.0.1:8080").rstrip('/')
CATALOG_ENDPOINT = f"{BACKEND_URL}/getCatalog"
RT_INTERVAL_SEC  = int(os.getenv("RT_INTERVAL_SEC", "5")) 
KALMAN_PVAR      = float(os.getenv("KALMAN_PROCESS_VAR", "1e-5"))
KALMAN_MVAR      = float(os.getenv("KALMAN_MEASURE_VAR", "0.1"))
KALMAN_ERR       = float(os.getenv("KALMAN_INIT_ERROR",  "1.0"))

OPTIMAL_RANGES = {
    "cactus":       {"moisture": (10, 30), "temperature": (25, 35), "humidity": (30, 50), "ph": (6.5, 7.5)},
    "spider plant": {"moisture": (40, 60), "temperature": (18, 28), "humidity": (40, 70), "ph": (6.0, 7.0)},
    "peace lily":   {"moisture": (60, 80), "temperature": (18, 25), "humidity": (60, 80), "ph": (5.5, 6.5)}
}


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def load_catalog():
    """Fetch the latest catalog, retrying until successful."""
    while True:
        try:
            resp = requests.get(CATALOG_ENDPOINT, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.warning(f"Waiting for catalog: {e}")
            time.sleep(2)

def send_alert(owner: str, plant: str, message: str):
    """Post an alert to the backend."""
    payload = {
        "alert":     message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "username":  owner,
        "plant":     plant
    }
    try:
        requests.post(f"{BACKEND_URL}/alerts", json=payload, timeout=5)
        logging.warning(f"RT alert sent: {message}")
    except Exception as e:
        logging.error(f"Failed sending RT alert: {e}")

catalog     = load_catalog()
influx_cfg  = catalog.get("influxdb", {})
DB_SENSOR   = influx_cfg.get("sensorDataBaseName",    "plants_measurements")
DB_ANALYSIS = influx_cfg.get("microServicesDataBaseName","analysis_data")
parsed      = urlparse(influx_cfg.get("url", "http://localhost:8086"))
INFLUX_HOST = parsed.hostname or "localhost"
INFLUX_PORT = parsed.port     or 8086

influx = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT)
influx.switch_database(DB_SENSOR)

class KalmanFilter:
    """Simple 1D Kalman filter for smoothing."""
    def __init__(self, q=KALMAN_PVAR, r=KALMAN_MVAR, p=KALMAN_ERR, x0=0.0):
        self.q = q
        self.r = r
        self.p = p
        self.x = x0

    def update(self, z):
        self.p += self.q
        k = self.p / (self.p + self.r)
        self.x += k * (z - self.x)
        self.p *= (1 - k)
        return self.x

class RealTimeAnalyzer:
    def __init__(self):
        self.kalman = {}  
        self.plants = []
        self.alert_counters = {} 

    def refresh_plants(self):
        """Reload plant list from catalog and manage Kalman filters and counters."""
        cat = load_catalog()
        new_plants = []
        for u in cat.get("userList", []):
            owner = u["userName"]
            for p in u.get("plantsList", []):
                serial     = p["deviceConnectorSerialNumber"]
                ptype      = p.get("plantType", "").lower()
                plant_name = p.get("plantName", serial)
                new_plants.append({
                    "owner": owner,
                    "serial": serial,
                    "type": ptype,
                    "name": plant_name
                })

        new_serials = {p["serial"] for p in new_plants}
        old_serials = set(self.kalman.keys())
        for s in new_serials - old_serials:
            self.kalman[s] = {m: KalmanFilter() for m in ["temperature","humidity","moisture","ph"]}

        for s in old_serials - new_serials:
            self.kalman.pop(s, None)

        for p in new_plants:
            if p["serial"] not in self.alert_counters:
                self.alert_counters[p["serial"]] = 0

        for s in set(self.alert_counters) - new_serials:
            self.alert_counters.pop(s, None)

        self.plants = new_plants

    def run_cycle(self):
        now = datetime.now(timezone.utc).isoformat()

        for p in self.plants:
            owner, serial, ptype, plant_name = p["owner"], p["serial"], p["type"], p["name"]

            influx.switch_database(DB_SENSOR)

            raw_vals = {}
            for m in ["temperature","humidity","moisture","ph"]:
                q = (
                    f'SELECT LAST("value") AS v '
                    f'FROM "{m}" '
                    f'WHERE "owner"=\'{owner}\' AND "plant"=\'{serial}\''
                )
                pts = list(influx.query(q).get_points())
                if pts and pts[0].get("v") is not None:
                    raw_vals[m] = float(pts[0]["v"])
            if len(raw_vals) < 4:
                continue

            filt = {m: self.kalman[serial][m].update(raw_vals[m])
                    for m in raw_vals}

            influx.switch_database(DB_ANALYSIS)

            point = {
                "measurement": "realtime_analysis",
                "tags":       {"owner": owner, "plant": serial},
                "time":        now,
                "fields":      {f"raw_{m}": raw_vals[m] for m in raw_vals}
                            | {f"filt_{m}": filt[m] for m in filt}
            }
            influx.write_points([point])
            logging.info(f"RT written for {serial}")


    def start(self):
        """Main loop: refresh plants and perform analysis cycles."""
        logging.info("Starting Real-Time Analysis (dynamic)...")
        while True:
            self.refresh_plants()
            self.run_cycle()
            time.sleep(RT_INTERVAL_SEC)

if __name__ == "__main__":
    RealTimeAnalyzer().start()
