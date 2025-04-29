import os
import json
import logging
import requests
import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError
import cherrypy
from cherrypy import tools, dispatch, engine, config, tree
from datetime import datetime, timedelta, timezone, date

# Configuración desde entorno
CATALOG_URL       = os.getenv("CATALOG_URL", "http://0.0.0.0:8080/getCatalog").rstrip('/')
IRR_EVAL_INTERVAL = int(os.getenv("IRR_EVAL_INTERVAL_SEC", "60"))
SIM_INTERVAL_SEC  = float(os.getenv("SIM_INTERVAL_SEC", "1"))    # segundos reales por minuto simulado
SCHEDULED_TIMES   = os.getenv("IRR_SCHEDULED_TIMES", "06:00,14:00,18:00").split(',')
BASE_PERCENT      = float(os.getenv("IRR_BASE_PERCENTAGE", "20"))
PUMP_FLOW_LPS     = float(os.getenv("IRR_PUMP_FLOW_LPS", "0.5"))
TANK_CAPACITY_L   = float(os.getenv("IRR_TANK_CAPACITY_L", "10.0"))
DEFICIT_FACTOR    = float(os.getenv("IRR_DEFICIT_FACTOR", "0.5"))

# Rangos óptimos y frecuencias para scheduled
OPTIMAL_RANGES = {
    "cactus":       (10, 30),
    "spider plant": (40, 60),
    "peace lily":   (60, 80)
}
SCHEDULED_FREQUENCIES = {
    "cactus":       1,
    "spider plant": 2,
    "peace lily":   3
}

# Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

class IrrigationController:
    def __init__(self):
        logger.info("🚀 Starting Irrigation Controller...")
        self.plants = {}
        self.mqtt = mqtt.Client(client_id="IrrigationController")
        self.sim_interval = SIM_INTERVAL_SEC
        self.scheduler = None

        self._load_catalog()
        self._setup_influx()
        self._setup_mqtt()
        self._setup_scheduler()

    def _load_catalog(self):
        try:
            response = requests.get(CATALOG_URL, timeout=5)
            response.raise_for_status()
            catalog = response.json()
            broker = catalog.get("broker", {})
            self.broker_ip = broker.get("IP")
            self.broker_port = broker.get("port")
            self.plants.clear()
            for user in catalog.get("userList", []):
                owner = user.get("userName")
                for plant in user.get("plantsList", []):
                    serial = plant.get("deviceConnectorSerialNumber")
                    mode   = plant.get("irrigationMode", "only notifications").lower()
                    topic  = plant.get("waterPump", {}).get("mqttTopic")
                    ptype  = plant.get("plantType", "").lower()
                    if serial and topic:
                        self.plants[serial] = {
                            "owner": owner,
                            "mode": mode,
                            "topic": topic,
                            "type": ptype
                        }
            logger.info(f"✅ Catalog loaded: {len(self.plants)} plants")
        except Exception as e:
            logger.error(f"❌ Failed to load catalog: {e}")

    def _setup_influx(self):
        try:
            influx_cfg = requests.get(CATALOG_URL, timeout=5).json().get("influxdb", {})
            url = influx_cfg.get("url", "http://0.0.0.0:8086")
            sensor_db   = influx_cfg.get("sensorDataBaseName", "plants_measurements")
            analysis_db = influx_cfg.get("microServicesDataBaseName", "analysis_data")
            parsed = requests.utils.urlparse(url)
            host, port = parsed.hostname, parsed.port
            self.sensor_client   = InfluxDBClient(host=host, port=port, database=sensor_db)
            self.analysis_client = InfluxDBClient(host=host, port=port, database=analysis_db)
            logger.info("✅ InfluxDB clients ready")
        except Exception as e:
            logger.error(f"❌ Failed to setup InfluxDB: {e}")

    def _setup_mqtt(self):
        try:
            self.mqtt.connect(self.broker_ip, self.broker_port)
            self.mqtt.loop_start()
            logger.info(f"🔌 MQTT connected to {self.broker_ip}:{self.broker_port}")
        except Exception as e:
            logger.error(f"❌ MQTT connection failed: {e}")

    def _fetch_metrics(self, serial):
        try:
            info = self.plants[serial]
            owner = info['owner']
            query = (
                f"SELECT LAST(\"filt_moisture\") AS m "
                f"FROM realtime_analysis "
                f"WHERE owner='{owner}' AND plant='{serial}'"
            )
            points = list(self.analysis_client.query(query).get_points())
            return points[0]['m'] if points else None
        except Exception as e:
            logger.error(f"❌ _fetch_metrics error for {serial}: {e}")
            return None

    def _automated_cycle(self):
        self._load_catalog()
        for serial, info in self.plants.items():
            if info['mode'] != 'automated':
                continue
            curr = self._fetch_metrics(serial)
            if curr is None:
                continue
            low, _ = OPTIMAL_RANGES.get(info['type'], (0, 100))
            if curr < low:
                deficit = low - curr
                pct = min(deficit * DEFICIT_FACTOR, 100)
                if pct > 0:
                    logger.info(f"🚿 Automated irrigation {serial}: curr={curr:.1f}%, pct={pct:.1f}%")
                    self._trigger_irrigation(serial, pct)

    def _scheduled_cycle(self, event_idx):
        """
        Trigger scheduled irrigation based on event index (order of times in SCHEDULED_TIMES).
        """
        self._load_catalog()
        for serial, info in self.plants.items():
            if info['mode'] != 'scheduled':
                continue
            freq = SCHEDULED_FREQUENCIES.get(info['type'], 1)
            if event_idx < freq:
                pct = BASE_PERCENT
                logger.info(f"⏰ Scheduled irrigation {serial} (event {event_idx+1}/{freq}): pct={pct:.1f}%")
                self._trigger_irrigation(serial, pct)
        # Reschedule this event for next day simulated
        next_run = datetime.now() + timedelta(seconds=1440 * self.sim_interval)
        job_id = f"scheduled_{event_idx}"
        try:
            self.scheduler.reschedule_job(job_id, trigger='date', run_date=next_run)
        except JobLookupError:
            self.scheduler.add_job(self._scheduled_cycle, 'date', run_date=next_run,
                                   args=[event_idx], id=job_id)

    def _setup_scheduler(self):
        self.scheduler = BackgroundScheduler()
        # Automated cycle
        self.scheduler.add_job(self._automated_cycle, 'interval',
                               seconds=IRR_EVAL_INTERVAL, id='automated')
        # Scheduled cycles for each configured time
        now = datetime.now()
        for idx, tm in enumerate(SCHEDULED_TIMES):
            hh, mm = map(int, tm.split(':'))
            # Calculate real run_date for simulated time
            minutes = hh * 60 + mm
            run_date = now + timedelta(seconds=minutes * self.sim_interval)
            job_id = f"scheduled_{idx}"
            self.scheduler.add_job(self._scheduled_cycle, 'date', run_date=run_date,
                                   args=[idx], id=job_id)
        self.scheduler.start()
        logger.info(f"⏰ Scheduler: automated every {IRR_EVAL_INTERVAL}s; scheduled at {SCHEDULED_TIMES} (sim interval {self.sim_interval}s)")

    def _trigger_irrigation(self, serial, percentage):
        try:
            info = self.plants[serial]
            volume = (percentage / 100) * TANK_CAPACITY_L
            duration = volume / PUMP_FLOW_LPS
            payload = json.dumps({
                'trigger': True,
                'duration': round(duration, 2),
                'percentage': round(percentage, 2)
            })
            timestamp = datetime.now(timezone.utc).isoformat()
            self.mqtt.publish(info['topic'], payload)
            logger.info(f"✅ Irrigation command for {serial}: {payload}")
            alert = f"Irrigation for {serial}: {percentage:.1f}%"
            requests.post(
                os.getenv('ALERTS_URL', 'http://0.0.0.0:8080/alerts'),
                json={
                    'alert': alert,
                    'timestamp': timestamp,
                    'username': info['owner'],
                    'plant': serial
                },
                timeout=5
            )
        except Exception as e:
            logger.error(f"❌ _trigger_irrigation error for {serial}: {e}")

    def start(self):
        tree.mount(
            IrrigationREST(self),
            '/',
            {'/': {'request.dispatch': dispatch.MethodDispatcher()}}
        )
        config.update({'server.socket_host': '0.0.0.0',
                       'server.socket_port': int(os.getenv('PORT', '8083'))})
        engine.start()
        engine.block()

class IrrigationREST:
    exposed = True
    def __init__(self, ctrl):
        self.ctrl = ctrl

    @tools.json_in()
    @tools.json_out()
    def PUT(self, *args, **kwargs):
        data = cherrypy.request.json
        serial = data.get('plantSerial')
        new_mode = data.get('newMode')
        if serial in self.ctrl.plants and new_mode:
            self.ctrl.plants[serial]['mode'] = new_mode.lower()
            logger.info(f"🔄 Mode for {serial} set to '{new_mode.lower()}' via REST")
            return {'message': f"Mode updated to {new_mode.lower()}"}
        cherrypy.response.status = 400
        return {'error': 'invalid payload'}

    @tools.json_in()
    @tools.json_out()
    def POST(self, *args, **kwargs):
        data = cherrypy.request.json
        serial = data.get('plantSerial')
        pct = data.get('percentage')
        if serial in self.ctrl.plants and isinstance(pct, (int, float)):
            self.ctrl._trigger_irrigation(serial, pct)
            return {'message': f'Irrigation triggered for {serial}: {pct}%'}
        cherrypy.response.status = 400
        return {'error': 'invalid payload'}

if __name__ == '__main__':
    IrrigationController().start()
