import time
import json
import threading
import cherrypy
import paho.mqtt.client as mqtt

from simulators.HumiditySensorSimulator import HumiditySensorSimulator
from simulators.TemperatureSensorSimulator import TemperatureSensorSimulator
from simulators.PHSensorSimulator import PHSensorSimulator
from simulators.SoilMoistureSensorSimulator import SoilMoistureSensorSimulator
from simulators.WaterPumpSimulator import WaterPumpSimulator
from simulators.WaterTankSimulator import WaterTankSimulator
import os

class DeviceConnectorSimulator:
    """
    Servicio CherryPy que arranca/detiene la simulación MQTT
    de sensores y tanque para un único serial de planta.
    """
    exposed = True

    def __init__(self, plant_serial: str, interval: float = 1.0):
        self.plant_serial = plant_serial
        self.interval = interval
        self._active = False
        self._thread = None
        self.client = mqtt.Client()
        self.topics = {}
        self.temp_sensor = None
        self.humidity_sensor = None
        self.soil_sensor = None
        self.ph_sensor = None
        self.tank = None
        self.pump = None

    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, *args, **kwargs):
        if not args or args[0] != f"startSimulation_{self.plant_serial}":
            cherrypy.response.status = 404
            return {"error": "Unknown POST action"}
        if self._active:
            return {"status": "Simulation already running"}

        data = cherrypy.request.json
        owner       = data.get("owner")
        sensor_list = data.get("sensorList", [])
        plant_type  = data.get("plantType")
        pump_serial = data.get("pumpSerial")
        tank_data   = data.get("tankData", {})
        broker_cfg  = data.get("broker", {})
        if not all([owner, sensor_list, plant_type, pump_serial, tank_data, broker_cfg]):
            cherrypy.response.status = 400
            return {"error": "Missing simulation parameters"}

        self.topics = {
            "temperature":      sensor_list[0]["mqttTopic"],
            "humidity":         sensor_list[1]["mqttTopic"],
            "soil_moisture":    sensor_list[2]["mqttTopic"],
            "ph":               sensor_list[3]["mqttTopic"],
            "tank_status":      tank_data["mqttTopic"],
            "command_irrigate": f"{owner}/{self.plant_serial}/{self.plant_serial}W"
        }

        self.temp_sensor     = TemperatureSensorSimulator()
        self.humidity_sensor = HumiditySensorSimulator()
        self.soil_sensor     = SoilMoistureSensorSimulator(plant_type=plant_type)
        self.ph_sensor       = PHSensorSimulator(plant_type=plant_type)
        self.tank            = WaterTankSimulator()
        self.pump            = WaterPumpSimulator()
        self.pump.link_soil_sensor(self.soil_sensor)
        self.pump.link_water_tank(self.tank)

        self.tank.set_publish_callback(lambda pct:
            self.client.publish(self.topics["tank_status"], json.dumps({"value": pct}))
        )
        self.tank._publish_percentage()

        def on_message(client, userdata, msg):
            try:
                pl = json.loads(msg.payload.decode())
                if msg.topic == self.topics["command_irrigate"] and pl.get("trigger"):
                    duration   = pl.get("duration", 5)
                    percentage = pl.get("percentage", 20)
                    if self.pump.turn_on(duration):
                        liters = (percentage/100) * self.tank.capacity
                        self.tank.consume_liters(liters)
            except Exception as e:
                print(f"[ERROR] on_message: {e}")

        def run_loop():
            self.client.on_message = on_message
            self.client.connect(
                broker_cfg.get("IP", "localhost"),
                broker_cfg.get("port", 1883),
                keepalive=60
            )
            self.client.subscribe(self.topics["command_irrigate"])
            self.client.loop_start()

            self._active = True
            try:
                while self._active:
                    readings = {
                        self.topics["temperature"]:   self.temp_sensor.simulate(),
                        self.topics["humidity"]:      self.humidity_sensor.simulate(),
                        self.topics["soil_moisture"]: self.soil_sensor.simulate(),
                        self.topics["ph"]:            self.ph_sensor.simulate()
                    }
                    for topic, val in readings.items():
                        self.client.publish(topic, json.dumps({"value": val}))
                    self.pump.tick()
                    time.sleep(self.interval)
            finally:
                self.client.loop_stop()

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()
        return {"status": "Simulation started"}

    @cherrypy.tools.json_out()
    def DELETE(self, *args, **kwargs):
        if not args or args[0] != f"stopSimulation_{self.plant_serial}":
            cherrypy.response.status = 404
            return {"error": "Unknown DELETE action"}
        self._active = False
        if self._thread:
            self._thread.join(timeout=2)
        return {"status": "Simulation stopped"}

if __name__ == "__main__":
    SERIAL   = os.getenv('PLANT_SERIAL', '000000')
    INTERVAL = float(os.getenv('INTERVAL', '1'))
    cherrypy.config.update({
        "server.socket_host": "0.0.0.0",
        "server.socket_port": int(os.getenv('PORT', '9090'))
    })
    simulator = DeviceConnectorSimulator(plant_serial=SERIAL, interval=INTERVAL)
    cherrypy.tree.mount(
        simulator, '/',
        {'/': {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}}
    )
    cherrypy.engine.start()
    cherrypy.engine.block()
