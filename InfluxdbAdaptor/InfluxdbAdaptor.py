import os
import json
import datetime
import requests
import threading
import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient
from urllib.parse import urlparse
import cherrypy

class InfluxDBAdaptor:
    def __init__(self):
        self.backend_url = os.getenv("BACKEND_URL", "http://backend:8080")
        self.catalog_api = f"{self.backend_url.rstrip('/')}/getCatalog"

        print(f"📦 Fetching catalog from {self.catalog_api}...", flush=True)
        self.catalog = self._fetch_catalog()

        broker_cfg = self.catalog.get("broker", {})
        self.mqtt_host = broker_cfg.get("IP", "localhost")
        self.mqtt_port = broker_cfg.get("port", 1883)

        self._init_influx_db()
        self.topic_map = self._build_topic_map()

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message

    def _fetch_catalog(self):
        resp = requests.get(self.catalog_api, timeout=5)
        resp.raise_for_status()
        catalog = resp.json()
        print(f"✅ Catalog loaded: users={len(catalog.get('userList', []))}, broker={catalog.get('broker')}", flush=True)
        return catalog

    def _init_influx_db(self):
        influx_cfg = self.catalog.get("influxdb", {})
        self.db_name = influx_cfg.get("sensorDataBaseName", "plants_measurements")
        url = influx_cfg.get("url", "http://localhost:8086")
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8086
        print(f"📊 Connecting to InfluxDB at {host}:{port}, DB '{self.db_name}'", flush=True)
        client = InfluxDBClient(host=host, port=port)
        if {'name': self.db_name} not in client.get_list_database():
            print(f"⚙️ Creating database: {self.db_name}", flush=True)
            client.create_database(self.db_name)
        self.influx_client = client
        self.influx_client.switch_database(self.db_name)

    def _build_topic_map(self):
        topic_map = {}
        for user in self.catalog.get("userList", []):
            owner = user.get("userName")
            for plant in user.get("plantsList", []):
                pid = plant.get("deviceConnectorSerialNumber")
                for sensor in plant.get("sensorList", []):
                    t = sensor.get("mqttTopic")
                    m = sensor.get("measureType", "").strip().lower()
                    if t and m:
                        topic_map[t] = {"owner": owner, "plant": pid, "measurement": m}
                tank = plant.get("waterTank")
                if tank and tank.get("mqttTopic"):
                    t = tank.get("mqttTopic")
                    topic_map[t] = {"owner": owner, "plant": pid, "measurement": "watertank"}
        print(f"📡 Topics to subscribe: {list(topic_map.keys())}", flush=True)
        return topic_map

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✅ Connected to MQTT broker at {self.mqtt_host}:{self.mqtt_port}", flush=True)
            for t in self.topic_map:
                client.subscribe(t)
                print(f"🔔 Subscribed to: {t}", flush=True)
        else:
            print(f"❌ MQTT connection failed (code {rc})", flush=True)

    def _on_message(self, client, userdata, msg):
        info = self.topic_map.get(msg.topic)
        if not info:
            return
        try:
            payload = json.loads(msg.payload.decode())
            value = float(payload.get("value", 0))
        except Exception as e:
            print(f"⚠️ Invalid payload on {msg.topic}: {e}", flush=True)
            return
        point = {
            "measurement": info['measurement'],
            "tags": {"owner": info['owner'], "plant": info['plant']},
            "time": datetime.datetime.utcnow().isoformat(),
            "fields": {"value": value}
        }
        try:
            self.influx_client.write_points([point])
            print(f"📥 Wrote {info['measurement']}={value} for {info['owner']}/{info['plant']}", flush=True)
        except Exception as e:
            print(f"❌ InfluxDB write error: {e}", flush=True)

    def refresh_subscriptions(self):
        """Fetch the catalog and subscribe to any new topics"""
        new_catalog = self._fetch_catalog()
        new_map = self._build_topic_map_from_catalog(new_catalog)
        added = set(new_map.keys()) - set(self.topic_map.keys())
        for t in added:
            try:
                self.mqtt_client.subscribe(t)
                self.topic_map[t] = new_map[t]
                print(f"🔔 Dynamically subscribed to new topic: {t}", flush=True)
            except Exception as e:
                print(f"❌ Failed to subscribe to {t}: {e}", flush=True)
        return list(added)

    def _build_topic_map_from_catalog(self, catalog):
        topic_map = {}
        for user in catalog.get("userList", []):
            owner = user.get("userName")
            for plant in user.get("plantsList", []):
                pid = plant.get("deviceConnectorSerialNumber")
                for sensor in plant.get("sensorList", []):
                    t = sensor.get("mqttTopic")
                    m = sensor.get("measureType", "").strip().lower()
                    if t and m:
                        topic_map[t] = {"owner": owner, "plant": pid, "measurement": m}
                tank = plant.get("waterTank")
                if tank and tank.get("mqttTopic"):
                    t = tank.get("mqttTopic")
                    topic_map[t] = {"owner": owner, "plant": pid, "measurement": "watertank"}
        return topic_map

class RefreshAPI:
    exposed = True

    @cherrypy.tools.json_out()
    def PUT(self):
        added = adaptor.refresh_subscriptions()
        return {"new_topics": added}

if __name__ == '__main__':
    adaptor = InfluxDBAdaptor()
    threading.Thread(
        target=lambda: (
            adaptor.mqtt_client.connect(adaptor.mqtt_host, adaptor.mqtt_port, keepalive=60),
            adaptor.mqtt_client.loop_forever()
        ), daemon=True
    ).start()
    cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': 8081})
    cherrypy.tree.mount(
        RefreshAPI(), '/refresh',
        {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}}
    )
    print("🚀 Refresh API running on http://0.0.0.0:8081/refresh", flush=True)
    cherrypy.engine.start()
    cherrypy.engine.block()