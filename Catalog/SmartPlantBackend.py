import cherrypy
from datetime import datetime
import json
import os
from influxdb import InfluxDBClient
import requests
import threading
import asyncio
import websockets

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "catalog.json")

alert_queue = asyncio.Queue()
active_websockets = set()


def load_catalog():
    if not os.path.exists(CATALOG_PATH):
        return {"userList": []}
    with open(CATALOG_PATH, 'r') as f:
        return json.load(f)

def save_catalog(data):
    with open(CATALOG_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def find_user(username):
    catalog = load_catalog()
    return next((user for user in catalog.get("userList", []) if user.get("userName") == username), None)

def add_plant(new_plant, username):
    catalog = load_catalog()
    for user in catalog["userList"]:
        if user["userName"] == username:
            if len(user["plantsList"]) < 3:
                user["plantsList"].append(new_plant)
            break
    save_catalog(catalog)

def remove_plant(plantserial, username):
    catalog = load_catalog()
    for user in catalog["userList"]:
        if user["userName"] == username:
            user["plantsList"] = [p for p in user["plantsList"] if p["deviceConnectorSerialNumber"] != plantserial]
            save_catalog(catalog)
            return {"message": "Plant removed successfully"}
    return {"error": "User not found"}

def CORS():
    cherrypy.response.headers["Access-Control-Allow-Origin"] = "*"
    cherrypy.response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    cherrypy.response.headers["Access-Control-Allow-Headers"] = "Content-Type"

cherrypy.tools.cors = cherrypy.Tool('before_handler', CORS)

async def broadcast_alert_loop():
    global alert_queue
    while True:
        alert_message = await alert_queue.get()
        if active_websockets:
            await asyncio.gather(*(ws.send(alert_message) for ws in active_websockets))

async def websocket_handler(websocket):
    active_websockets.add(websocket)
    try:
        async for _ in websocket:
            pass
    finally:
        active_websockets.remove(websocket)

async def websocket_main():
    global alert_queue
    alert_queue = asyncio.Queue()

    async with websockets.serve(websocket_handler, "0.0.0.0", 8765):
        print("✅ WebSocket server running at ws://0.0.0.0:8765")
        await broadcast_alert_loop() 

global websocket_loop
websocket_loop = None

async def start_websocket_server():
    global websocket_loop
    websocket_loop = asyncio.get_event_loop()

    server = await websockets.serve(websocket_handler, "0.0.0.0", 8765)
    websocket_loop.create_task(broadcast_alert_loop())
    print("✅ WebSocket server running at ws://0.0.0.0:8765")
    await server.wait_closed()

def websocket_thread_runner():
    asyncio.run(start_websocket_server())

class SmartPlantBackend(object):
    exposed = True

    def __init__(self):
        catalog = load_catalog()
        influx_info = catalog.get("influxdb", {})
        self.client = InfluxDBClient(
            host=influx_info.get("url", "http://influxdb:8086").replace("http://", "").split(":")[0],
            port=int(influx_info.get("url", "http://influxdb:8086").split(":")[-1])
        )
        self.sensor_db = influx_info.get("sensorDataBaseName", "plants_measurements")
        self.notifications_db = influx_info.get("notificationsDataBase", "user_notifications")
        self.analysis_db = influx_info.get("microServicesDataBaseName", "analysis_data")


    def OPTIONS(self, *args, **kwargs):
        cherrypy.response.status = 200
        return ""

    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def GET(self, *args, **kwargs):
        if args and args[0] == "user":
            username = cherrypy.request.params.get("username")
            if not username:
                cherrypy.response.status = 400
                return {"error": "Username required"}
            user = find_user(username)
            if not user:
                cherrypy.response.status = 404
                return {"error": "User not found"}
            return {
                "username": user["userName"],
                "password": user["password"],
                "plants": user.get("plantsList", [])
            }

        if args and args[0] == "get_sensor_data":
            username = kwargs.get("username")
            plant = kwargs.get("plant")
            measure = kwargs.get("measure")
            if not all([username, plant, measure]):
                cherrypy.response.status = 400
                return {"error": "Missing parameters"}

            self.client.switch_database(self.sensor_db)

            query = f"""
            SELECT value FROM {measure} 
            WHERE time > now() - 10m 
            AND "owner" = '{username}' 
            AND "plant" = '{plant}'
            """
            result = self.client.query(query)
            return list(result.get_points())

        if args and args[0] == "get_plot":
            username = kwargs.get("username")
            plant = kwargs.get("plant")
            graph = kwargs.get("graph")
            if not all([username, plant, graph]):
                cherrypy.response.status = 400
                return {"error": "Missing parameters"}

            self.client.switch_database(self.sensor_db)

            query = f"""
            SELECT value, time FROM {graph} 
            WHERE time > now() - 1h 
            AND "owner" = '{username}' 
            AND "plant" = '{plant}'
            """
            result = self.client.query(query)
            points = list(result.get_points())

            if not points:
                cherrypy.response.status = 404
                return {"error": "No data available"}

            return {
                "timestamps": [p["time"] for p in points],
                "values": [p["value"] for p in points]
            }


        if args and args[0] == "getCatalog":
            return load_catalog()

        if args and args[0] == "get_latest_tank_status":
            username = kwargs.get("username")
            plant    = kwargs.get("plant")
            if not username or not plant:
                cherrypy.response.status = 400
                return {"error": "Missing parameters"}
            try:
                self.client.switch_database(self.sensor_db)

                query = (
                    f'SELECT LAST("value") '
                    f'FROM "watertank" '
                    f"WHERE \"owner\" = '{username}' AND \"plant\" = '{plant}'"
                )
                result = self.client.query(query)

                points = list(result.get_points())
                if points:
                    return {
                        "value": round(points[0].get("last", 0), 2),
                        "time":  points[0].get("time")
                    }
                return {"value": None, "time": None}
            except Exception as e:
                cherrypy.response.status = 500
                return {"error": str(e)}


    
        if args and args[0] == "get_historical_trends":
            username = kwargs.get("username")
            plant    = kwargs.get("plant")
            if not username or not plant:
                cherrypy.response.status = 400
                return {"error": "Missing parameters"}

            try:
                self.client.switch_database(self.analysis_db)
                query = f"""
                SELECT * FROM historical_analysis
                WHERE "owner" = '{username}' AND "plant" = '{plant}'
                AND time > now() - 1d
                """
                result     = self.client.query(query)
                raw_points = list(result.get_points())

                trends = { m: [] for m in ["temperature","humidity","moisture","ph"] }

                for p in raw_points:
                    metric = p.get("metric")
                    if metric in trends:
                        trends[metric].append({
                            "time":               p.get("time"),
                            "prediction":         p.get("prediction"),
                            "slope":              p.get("slope"),
                            "residual_std":       p.get("residual_std"),
                            "cluster_dominance":  p.get("cluster_dominance")
                        })

                return trends

            except Exception as e:
                cherrypy.response.status = 500
                return {"error": f"Failed to fetch trends: {e}"}


        if args and args[0] == "get_historical_alerts":
            username = kwargs.get("username")
            plant = kwargs.get("plant")
            if not username or not plant:
                cherrypy.response.status = 400
                return {"error": "Missing parameters"}

            try:
                self.client.switch_database(self.notifications_db)
                query = f"""
                SELECT * FROM user_alerts
                WHERE "owner" = '{username}' AND "plant" = '{plant}'
                AND time > now() - 2d
                """
                result = self.client.query(query)
                points = list(result.get_points())
                return points
            except Exception as e:
                cherrypy.response.status = 500
                return {"error": f"Failed to fetch alerts: {str(e)}"}

        if args and args[0] == "get_realtime_analysis":
            username = kwargs.get("username")
            plant = kwargs.get("plant")
            if not username or not plant:
                cherrypy.response.status = 400
                return {"error": "Missing parameters"}

            try:
                self.client.switch_database(self.analysis_db)
                query = f"""
                SELECT * FROM realtime_analysis
                WHERE "owner" = '{username}' AND "plant" = '{plant}'
                ORDER BY time ASC
                LIMIT 1000
                """
                result = self.client.query(query)
                points = list(result.get_points())
                if not points:
                    return []
                return points
            except Exception as e:
                cherrypy.response.status = 500
                return {"error": f"Failed to fetch realtime analysis: {str(e)}"}


            
        
        cherrypy.response.status = 404
        return {"error": "Not found"}


    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, *args, **kwargs):
        data = cherrypy.request.json

        if not args:
            cherrypy.response.status = 400
            return {"error": "Missing endpoint."}

        action = args[0]

        if action == "login":
            username = data.get("username")
            password = data.get("password")
            user = find_user(username)
            if user and user.get("password") == password:
                return {
                    "message": "Successful login",
                    "username": username,
                    "password": password,
                    "plants": user.get("plantsList", [])
                }
            cherrypy.response.status = 401
            return {"error": "Invalid credentials"}

        if action == "register":
            from datetime import datetime
            username = data.get("username")
            password = data.get("password")

            if not username or not password:
                cherrypy.response.status = 400
                return {"error": "Username and password required"}

            catalog = load_catalog()
            for user in catalog.get("userList", []):
                if user.get("userName") == username:
                    cherrypy.response.status = 409
                    return {"error": "Username already exists"}

            new_user = {
                "userName": username,
                "password": password,
                "plantsList": []
            }
            catalog["userList"].append(new_user)
            catalog["lastUpdate"] = datetime.utcnow().strftime("%Y-%m-%d")
            save_catalog(catalog)

            return {"message": "User registered successfully"}

        if action == "addPlant":
            username = data.get("username")
            plantName = data.get("plantName")
            plantType = data.get("plantType")
            deviceConnectorSerialNumber = data.get("deviceConnectorSerialNumber")
            sensorList = data.get("sensorList")
            waterPumpSerial = data.get("waterPumpSerial")
            irrigationMode = data.get("irrigationMode")
            url = f"http://{deviceConnectorSerialNumber}.local:9090"

            user = find_user(username)
            if not user:
                cherrypy.response.status = 404
                return {"error": "User not found"}

            pump_data = {
                "serialNumber": f"{deviceConnectorSerialNumber}w",
                "mqttTopic": f"{username}/{deviceConnectorSerialNumber}/{deviceConnectorSerialNumber}W"
            }
            tank_data = {
                "serialNumber": f"{deviceConnectorSerialNumber}R",
                "mqttTopic": f"{username}/{deviceConnectorSerialNumber}/{deviceConnectorSerialNumber}R"
            }

            new_plant = {
                "plantName": plantName,
                "plantType": plantType,
                "deviceConnectorSerialNumber": deviceConnectorSerialNumber,
                "url": url,
                "sensorList": sensorList,
                "waterPump": pump_data,
                "waterTank": tank_data,
                "availableServices": ["MQTT", "REST"],
                "irrigationMode": irrigationMode
            }

            add_plant(new_plant, username)

            try:
                catalog = load_catalog()
                broker = catalog.get("broker", {})
                raspberry_url = f"{url}/startSimulation_{deviceConnectorSerialNumber}"
                payload = {
                    "owner": username,
                    "sensorList": sensorList,
                    "plantType": plantType,
                    "pumpSerial": waterPumpSerial,
                    "tankData": tank_data,
                    "broker": broker
                }
                response = requests.post(raspberry_url, json=payload, timeout=5)
                print(f"[BACKEND] Sent simulation request to {raspberry_url} → Status: {response.status_code}")
                adaptor_data=catalog["influxdbAdaptor"]
                print(adaptor_data, flush=1)
                adaptor_url=adaptor_data["url"]
                print(adaptor_url)
                adaptor_endpoint=adaptor_data["updateEndpoint"]
                print(adaptor_endpoint)
                request_url=adaptor_url+adaptor_endpoint
                print(request_url, flush=1)
                requests.put(f"{request_url}")
            except Exception as e:
                print(f"[BACKEND] Failed to contact RaspberryPi at {url}: {e}")

            return {"message": "Plant added and simulation started (if reachable)."}

        if action == "irrigate":
            import paho.mqtt.publish as publish
            import datetime
            import asyncio
            import json

            username     = data.get("username")
            plant_serial = data.get("plantSerial")
            pct          = data.get("percentage", None)

            if not username or not plant_serial:
                cherrypy.response.status = 400
                return {"error": "username and plantSerial required"}

            if pct is None:
                catalog    = load_catalog()
                plant_type = None
                for u in catalog.get("userList", []):
                    if u["userName"] == username:
                        for p in u.get("plantsList", []):
                            if p["deviceConnectorSerialNumber"] == plant_serial:
                                plant_type = p["plantType"].lower()
                                break

                DEFAULT_MANUAL = {
                    "cactus":      15,
                    "peace lily":  30,
                    "spider plant":20
                }
                pct = DEFAULT_MANUAL.get(plant_type, 20)

            topic   = f"{username}/{plant_serial}/{plant_serial}W"
            payload = json.dumps({
                "trigger":    True,
                "percentage": pct
            })

            try:
                broker = load_catalog().get("broker", {})
                publish.single(
                    topic,
                    payload,
                    hostname=broker.get("IP", "localhost"),
                    port=broker.get("port", 1883)
                )

                if websocket_loop:
                    asyncio.run_coroutine_threadsafe(
                        alert_queue.put(json.dumps({
                            "type":       "irrigation",
                            "username":   username,
                            "plant":      plant_serial,
                            "percentage": pct,
                            "timestamp":  datetime.datetime.utcnow().isoformat()
                        })),
                        websocket_loop
                    )

                cherrypy.response.status = 200
                return {"status": "ok", "percentage_used": pct}

            except Exception as e:
                cherrypy.log.error(f"Irrigate handler error: {e}", traceback=True)
                cherrypy.response.status = 500
                return {"error": str(e)}
            
        if action == "alerts":
            from datetime import datetime 

            alert_text = data.get("alert")
            timestamp = data.get("timestamp", datetime.utcnow().isoformat())
            username = data.get("username")
            plant = data.get("plant")

            if not alert_text or not username or not plant:
                cherrypy.response.status = 400
                return {"error": "Missing fields"}

            self.client.switch_database(self.notifications_db)
            point = {
                "measurement": "user_alerts",
                "tags": {
                    "owner": username,
                    "plant": plant
                },
                "fields": {
                    "alert_text": alert_text
                },
                "time": timestamp
            }
            self.client.write_points([point])

            if websocket_loop:
                import asyncio, json
                asyncio.run_coroutine_threadsafe(
                    alert_queue.put(
                        json.dumps({
                            "type": "alert",
                            "alert": alert_text,
                            "timestamp": timestamp,
                            "owner": username,
                            "plant": plant
                        })
                    ),
                    websocket_loop
                )

            return {"status": "Alert received"}




        cherrypy.response.status = 404
        return {"error": "Unknown POST action"}
    


    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def PUT(self, *args, **kwargs):
        data = cherrypy.request.json

        if args[0] == "changeIrrigationMode":
            username = data.get("username")
            serialNumber = data.get("plantSerial")
            newMode = data.get("newMode")
            catalog = load_catalog()
            for user in catalog.get("userList", []):
                if user["userName"] == username:
                    for plant in user["plantsList"]:
                        if plant["deviceConnectorSerialNumber"] == serialNumber:
                            plant["irrigationMode"] = newMode
                            user["lastUpdate"] = datetime.utcnow().strftime("%Y-%m-%d")
                            catalog["lastUpdate"] = user["lastUpdate"]
                            save_catalog(catalog)

                            try:
                                irrigation_control_url = "http://irrigation_control:8083/change_irrigation_mode"
                                payload = {
                                    "plantSerial": serialNumber,
                                    "newMode": newMode
                                }
                                headers = {'Content-Type': 'application/json'}
                                response = requests.put(irrigation_control_url, json=payload, headers=headers, timeout=3)
                                if response.status_code == 200:
                                    print(f"✅ Irrigation Control updated for {serialNumber}: {newMode}")
                                else:
                                    print(f"⚠️ Failed to update Irrigation Control, status {response.status_code}")
                            except Exception as e:
                                print(f"❌ Error contacting Irrigation Control: {e}")

                            return {"message": "Mode updated"}
            cherrypy.response.status = 404
            return {"error": "Plant or user not found"}



    @cherrypy.tools.json_out()
    def DELETE(self, *args, **kwargs):
        catalog = load_catalog()
        influx_info = catalog.get("influxdb", {})
        sensor_db       = influx_info.get("sensorDataBaseName",       "plants_measurements")
        analysis_db     = influx_info.get("microServicesDataBaseName","analysis_data")
        notifications_db= influx_info.get("notificationsDataBase",    "user_notifications")

        if args and args[0] == "deleteAccount":
            username = kwargs.get("username")
            if not username:
                cherrypy.response.status = 400
                return {"error": "Username required"}
            user = find_user(username)
            if not user:
                cherrypy.response.status = 404
                return {"error": "User not found"}

            for plant in user.get("plantsList", []):
                serial = plant["deviceConnectorSerialNumber"]
                try:
                    requests.delete(f"http://{serial}.local:9090/stopSimulation_{serial}", timeout=5)
                except:
                    pass

            try:
                self.client.switch_database(sensor_db)
                for m in ["temperature", "humidity", "moisture", "ph"]:
                    self.client.query(f"DELETE FROM {m} WHERE owner='{username}'")

                self.client.switch_database(analysis_db)
                self.client.query(f"DELETE FROM realtime_analysis WHERE owner='{username}'")
                self.client.query(f"DELETE FROM historical_analysis WHERE owner='{username}'")

                self.client.switch_database(notifications_db)
                self.client.query(f"DELETE FROM user_alerts WHERE owner='{username}'")

            except Exception as e:
                print(f"Error while deleting user data: {e}")

            catalog["userList"] = [u for u in catalog["userList"] if u["userName"] != username]
            catalog["lastUpdate"] = datetime.utcnow().strftime("%Y-%m-%d")
            save_catalog(catalog)
            return {"message": "User deleted successfully"}
        
        if args and args[0] == "deletePlant":
            username    = kwargs.get("username")
            plantSerial = kwargs.get("plantSerial")
            if not username or not plantSerial:
                cherrypy.response.status = 400
                return {"error": "Missing parameters"}
            user = find_user(username)
            if not user:
                cherrypy.response.status = 404
                return {"error": "User not found"}

            try:
                requests.delete(f"http://{plantSerial}.local:9090/stopSimulation_{plantSerial}", timeout=5)
            except:
                pass

            try:
                self.client.switch_database(sensor_db)
                for m in ["temperature", "humidity", "moisture", "ph"]:
                    self.client.query(
                        f"DELETE FROM {m} WHERE owner='{username}' AND plant='{plantSerial}'"
                    )

                self.client.switch_database(analysis_db)
                self.client.query(
                    f"DELETE FROM realtime_analysis WHERE owner='{username}' AND plant='{plantSerial}'"
                )
                self.client.query(
                    f"DELETE FROM historical_analysis WHERE owner='{username}' AND plant='{plantSerial}'"
                )

                self.client.switch_database(notifications_db)
                self.client.query(
                    f"DELETE FROM user_alerts WHERE owner='{username}' AND plant='{plantSerial}'"
                )

            except Exception as e:
                print(f"Error while deleting plant data: {e}")

            remove_plant(plantSerial, username)
            return {"message": "Plant removed successfully"}

        cherrypy.response.status = 404
        return {"error": "Not found"}



        

if __name__ == "__main__":
    websocket_thread = threading.Thread(target=websocket_thread_runner, daemon=True)
    websocket_thread.start()

    config = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.cors.on': True
        }
    }

    cherrypy.tree.mount(SmartPlantBackend(), '/', config)
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8080
    })
    print("🌿 SmartPlantBackend running on http://0.0.0.0:8080")
    cherrypy.engine.start()
    cherrypy.engine.block()

