import os
import time
import logging
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse

import numpy as np
from influxdb import InfluxDBClient
from sklearn.linear_model import LinearRegression
from sklearn.cluster import KMeans

BACKEND_URL      = os.getenv("BACKEND_URL",      "http://0.0.0.0:8080").rstrip('/')
CATALOG_ENDPOINT = f"{BACKEND_URL}/getCatalog"
HIST_WINDOW      = os.getenv("HIST_WINDOW",      "1h")        # time window, e.g. '1h'
HIST_INTERVAL    = int(os.getenv("HIST_INTERVAL_SEC", "60"))  # seconds between analysis
MIN_POINTS       = int(os.getenv("HIST_MIN_POINTS", "5"))      # minimum data points per metric
CLUSTERS         = int(os.getenv("HIST_NUM_CLUSTERS", "3"))    # KMeans clusters
BUFFER_FACTOR    = float(os.getenv("HIST_BUFFER_FACTOR", "0.2")) # buffer ratio
METRICS          = ["temperature", "humidity", "moisture", "ph"]

OPTIMAL_RANGES = {
    "cactus":       {"moisture": (10, 30), "temperature": (25, 35), "humidity": (30, 50), "ph": (6.5, 7.5)},
    "spider plant": {"moisture": (40, 60), "temperature": (18, 28), "humidity": (40, 70), "ph": (6.0, 7.0)},
    "peace lily":   {"moisture": (60, 80), "temperature": (18, 25), "humidity": (60, 80), "ph": (5.5, 6.5)}
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

def load_catalog():
    while True:
        try:
            resp = requests.get(CATALOG_ENDPOINT, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.warning(f"Waiting for catalog: {e}")
            time.sleep(2)

def send_alert(owner: str, plant: str, plant_name: str, message: str):
    payload = {
        "alert":     message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "username":  owner,
        "plant":     plant,
        "plantName": plant_name
    }
    try:
        requests.post(f"{BACKEND_URL}/alerts", json=payload, timeout=5)
        logging.warning(f"Alert sent: {message}")
    except Exception as e:
        logging.error(f"Failed sending alert: {e}")

catalog      = load_catalog()
influx_cfg   = catalog.get("influxdb", {})
DB_SENSOR    = influx_cfg.get("sensorDataBaseName", "plants_measurements")
DB_ANALYSIS  = influx_cfg.get("microServicesDataBaseName", "analysis_data")
parsed       = urlparse(influx_cfg.get("url", "http://0.0.0.0:8086"))
INFLUX_HOST  = parsed.hostname or "0.0.0.0"
INFLUX_PORT  = parsed.port     or 8086

influx = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT)

if {'name': DB_ANALYSIS} not in influx.get_list_database():
    influx.create_database(DB_ANALYSIS)

def analyze_plant(owner: str, plant: str, plant_type: str, plant_name: str):
    influx.switch_database(DB_SENSOR)
    series = {}
    for meas in METRICS:
        q = (
            f'SELECT value FROM "{meas}" '
            f"WHERE \"owner\"='{owner}' AND \"plant\"='{plant}' "
            f"AND time > now() - {HIST_WINDOW}"
        )
        pts = list(influx.query(q).get_points())
        if len(pts) >= MIN_POINTS:
            series[meas] = [
                (datetime.fromisoformat(p['time']).timestamp(), p['value'])
                for p in pts
            ]
    if not series:
        logging.info(f"Skipping {owner}/{plant}: no metric has >= {MIN_POINTS} points")
        return

    influx.switch_database(DB_ANALYSIS)
    now = datetime.now(timezone.utc).isoformat()
    alerts = []

    for meas, data in series.items():
        times = np.array([t for t,_ in data]).reshape(-1,1)
        vals  = np.array([v for _,v in data], dtype=float)

        model = LinearRegression().fit(times, vals)
        pred   = float(model.predict([[datetime.now(timezone.utc).timestamp()]])[0])
        slope  = float(model.coef_[0])
        resid  = vals - model.predict(times)
        stddev = float(np.std(resid, ddof=1)) if len(resid)>1 else 0.0

        kmeans   = KMeans(n_clusters=CLUSTERS, random_state=0).fit(vals.reshape(-1,1))
        dom_frac = np.bincount(kmeans.labels_).max() / len(vals)

        point = {
            'measurement': 'historical_analysis',
            'tags': {
                'owner': owner,
                'plant': plant,
                'metric': meas
            },
            'time': now,
            'fields': {
                'prediction': pred,
                'slope': slope,
                'residual_std': stddev,
                'cluster_dominance': dom_frac
            }
        }
        influx.write_points([point])
        logging.info(f"Historical analysis saved: {plant}/{meas}")

        rng = OPTIMAL_RANGES.get(plant_type, {}).get(meas)
        if rng:
            lo, hi = rng
            buf = (hi - lo) * BUFFER_FACTOR
            if pred < lo - buf:
                alerts.append(
                    f"[{meas}] predicted too LOW ({pred:.2f}), optimal [{lo},{hi}] (plant: {plant_name})"
                )
            elif pred > hi + buf:
                alerts.append(
                    f"[{meas}] predicted too HIGH ({pred:.2f}), optimal [{lo},{hi}] (plant: {plant_name})"
                )
        if dom_frac < 0.5:
            alerts.append(
                f"[{meas}] unstable clusters (dominance {dom_frac:.2%}) (plant: {plant_name})"
            )

    for msg in alerts:
        send_alert(owner, plant, plant_name, msg)
        
def main():
    logging.info("🚀 Starting Unified Historical Analysis...")
    while True:
        catalog = load_catalog()
        for user in catalog.get('userList', []):
            owner = user['userName']
            for pl in user.get('plantsList', []):
                analyze_plant(
                    owner,
                    pl['deviceConnectorSerialNumber'],
                    pl.get('plantType','').lower(),
                    pl.get('plantName', pl['deviceConnectorSerialNumber'])
                )
        time.sleep(HIST_INTERVAL)

if __name__ == '__main__':
    main()
