import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
import json
import requests
import time
import io
from base64 import b64decode
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
import threading
import asyncio
import websockets

WS_URL = "ws://backend:8765"

def generate_sensor_list(serial, username):
    TsensorS=serial+"T"
    HsensorS=serial+"H"
    MsensorS=serial+"M"
    PHsensorS=serial+"P"

    sensor_list = [{"serialNumber":TsensorS, "measureType":"Temperature", "mqttTopic": f"{username}/{serial}/{TsensorS}"}, 
                   {"serialNumber":HsensorS, "measureType":"Humidity", "mqttTopic": f"{username}/{serial}/{HsensorS}"},
                   {"serialNumber":MsensorS, "measureType":"Moisture", "mqttTopic": f"{username}/{serial}/{MsensorS}"}, 
                   {"serialNumber":PHsensorS, "measureType":"PH", "mqttTopic": f"{username}/{serial}/{PHsensorS}"}]

    return sensor_list

def delete_plant_from_user(self, chat_id, plant_name_to_delete):
    if chat_id in self.logged_users:
        user_data = self.logged_users[chat_id]
        plants = user_data.get("plants", [])
        
        updated_plants = [p for p in plants if p.get("plantName") != plant_name_to_delete]
        user_data["plants"] = updated_plants

class ProjectBot(object):
    def __init__(self, token):
        self.tokenBot = token
        self.bot = telepot.Bot(self.tokenBot)
        self.logged_users = {}
        self.backend_url = "http://backend:8080"

        MessageLoop(self.bot, {"chat": self.on_chat_message, 'callback_query': self.on_callback_query}).run_as_thread()
        self.chat_ID = None
        self.pending_username_change = {}
        self.pending_plant_to_add = False
        self.pending_plant_name = False
        self.selected_plant_type = None
        self.pending_device_serial = False
        self.selected_plant = None
        threading.Thread(target=self._start_ws_listener, daemon=True).start()
        print("🤖 Telegram bot is running...")
        while True:
            time.sleep(10)

    async def _ws_listener(self):
        try:
            async with websockets.connect(WS_URL) as websocket:
                print(f"🔔 Connected to WebSocket at {WS_URL}")
                async for message in websocket:
                    try:
                        alert = json.loads(message)
                        self._handle_alert(alert)
                    except Exception as e:
                        print(f"❌ Error parsing WS message: {e}")
        except Exception as e:
            print(f"❌ WebSocket connection error: {e}")
            await asyncio.sleep(5)
            await self._ws_listener()

    def _start_ws_listener(self):
        asyncio.new_event_loop().run_until_complete(self._ws_listener())

    def _handle_alert(self, alert):
        alert_type = alert.get('type')
        username = alert.get('username') or alert.get('owner')
        plant = alert.get('plant')
        msg_text = None
        if alert_type == 'alert':
            msg_text = f"🚨 Alert for plant {plant}: {alert.get('alert')}"
        elif alert_type == 'irrigation':
            pct = alert.get('percentage')
            msg_text = f"💦 Irrigation event for plant {plant}: {pct}%"
        if msg_text and username:
            for chat_id, data in self.logged_users.items():
                if data.get('username') == username:
                    try:
                        self.bot.sendMessage(chat_id, msg_text)
                    except Exception as e:
                        print(f"❌ Failed sending alert to {chat_id}: {e}")

    def on_chat_message(self, msg):
        content_type, chat_type, chatID = telepot.glance(msg)
        message = msg.get('text', '').strip()
        self.chat_ID = chatID

        if chatID in self.logged_users:
            stored_username = self.logged_users[chatID]["username"]
            try:
                res = requests.get(f"{self.backend_url}/user?username={stored_username}")
                if res.status_code != 200:
                    del self.logged_users[chatID]
                    self.bot.sendMessage(chatID, "⚠️ Your session has expired. Please log in again.")
                    self.initial_menu(chatID)
                    return
            except Exception as e:
                print("❌ Error checking username validity:", e)

        if self.pending_plant_to_add:
            typed=message.strip()
            plant_info = typed.split(":")
            plantName, deviceSerial = plant_info[0], plant_info[1]
            sensorList = generate_sensor_list(deviceSerial, self.logged_users[chatID]["username"]) 
           
            res = requests.post(f"{self.backend_url}/addPlant", json={
                "username":self.logged_users[chatID]["username"],
                "plantName":plantName,
                "plantType":self.selected_plant_type,
                "deviceConnectorSerialNumber":deviceSerial,
                "sensorList":sensorList,
                "waterPumpSerial":deviceSerial+"W",
                "irrigationMode":"only notifications"
            })

            if res.status_code == 200:
                self.bot.sendMessage(chatID, f"✅ Your new plant was added successfully", parse_mode="Markdown")
                self.pending_plant_to_add=False
                res2 =requests.get(f"{self.backend_url}/user?username={self.logged_users[chatID]["username"]}")
                if res2.status_code == 200:
                    data=res2.json()
                    plants = data.get("plants")
                    username = data.get("username")
                    password = data.get("password")
                    self.logged_users[chatID]={
                        "username": username,
                        "password": password,
                        "plants": plants
                    }
                self.send_plants_menu(chatID, self.logged_users[chatID]["plants"])

            else:
                self.bot.sendMessage(chatID, f"an error has occured please try to add your plant again", parse_mode="Markdown")
                self.pending_plant_to_add=False
            return


        if chatID in self.pending_username_change:
            new_username = message.strip()
            current_username = self.pending_username_change[chatID]
            res = requests.put(f"{self.backend_url}/changeUsername", json={
                "currentUsername": current_username,
                "newUsername": new_username
            })

            if res.status_code == 200:
                self.logged_users[chatID]["username"] = new_username
                self.bot.sendMessage(chatID, f"✅ Username changed successfully to `{new_username}`", parse_mode="Markdown")
                self.send_profile_menu(chatID)
            else:
                error = res.json().get("error", "Could not change username")
                self.bot.sendMessage(chatID, f"❌ Failed to change username: {error}")
                self.send_profile_menu(chatID)

            del self.pending_username_change[chatID]
            return

        if chatID not in self.logged_users:
            if message.lower().startswith("register "):
                try:
                    credentials = message[9:].split(":")
                    username, password = credentials[0], credentials[1]

                    res = requests.post(f"{self.backend_url}/register", json={
                        "username": username,
                        "password": password
                    })

                    if res.status_code == 200:
                        self.bot.sendMessage(chatID, "✅ You are registered. Now you can login using: login username:password")
                    else:
                        error = res.json().get("error", "Error while registering")
                        self.bot.sendMessage(chatID, f"❌ Register failed: {error}")
                except:
                    self.bot.sendMessage(chatID, "❌ Incorrect format. Use: register username:password")
                return

            if message.lower().startswith("login "):
                try:
                    credentials = message[6:].split(":")
                    username, password = credentials[0], credentials[1]

                    res = requests.post(f"{self.backend_url}/login", json={
                        "username": username,
                        "password": password
                    })

                    if res.status_code == 200:
                        data = res.json()
                        plants = data.get("plants", [])

                        self.logged_users[chatID] = {
                            "username": username,
                            "password": password,
                            "plants": plants
                        }

                        self.bot.sendMessage(chatID, "✅ Successful login, Welcome!")
                        self.send_main_menu(chatID)
                    else:
                        error = res.json().get("error", "Login failed")
                        self.bot.sendMessage(chatID, f"❌ Login failed: {error}")
                except:
                    self.bot.sendMessage(chatID, "❌ Incorrect login format. Use: login username:password")
                return

            self.initial_menu(chatID)

        else:
            self.bot.sendMessage(chatID, "✅ You are already logged in. Use the menu to continue.")
            self.send_main_menu(chatID)

        
    def initial_menu(self, chat_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Login', callback_data='show_login_info')],
            [InlineKeyboardButton(text='Register', callback_data='show_register_info')]
        ])

        self.bot.sendMessage(chat_id, "🌱 Welcome to SmartPlant! Please login or register to continue:", reply_markup=keyboard)

    def send_main_menu(self, chat_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='My Plants', callback_data='menu_plants')],
            [InlineKeyboardButton(text='My Profile', callback_data='menu_profile')],
            [InlineKeyboardButton(text='Log out', callback_data='log_out_triggered')]
        ])

        self.bot.sendMessage(chat_id, "Welcome, this is you main menu", reply_markup=keyboard)

    def send_plants_menu(self, chat_id, plants):
        if len(plants) == 3:
            plant_names=[]
            for plant in plants:
                plant_names.append(plant["plantName"])
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=plant_names[0], callback_data=f'menu_for_a_plant_{plant_names[0]}')],
                [InlineKeyboardButton(text=plant_names[1], callback_data=f'menu_for_a_plant_{plant_names[1]}')],
                [InlineKeyboardButton(text=plant_names[2], callback_data=f'menu_for_a_plant_{plant_names[2]}')],
                [InlineKeyboardButton(text='Back', callback_data='go_back_from_my_plants')]
            ])

            self.bot.sendMessage(chat_id, "This are all your plants", reply_markup=keyboard)

        elif len(plants) == 2:
            plant_names=[]
            for plant in plants:
                plant_names.append(plant["plantName"])
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=plant_names[0], callback_data=f'menu_for_a_plant_{plant_names[0]}')],
                [InlineKeyboardButton(text=plant_names[1], callback_data=f'menu_for_a_plant_{plant_names[1]}')],
                [InlineKeyboardButton(text='Add plant', callback_data='send_menu_plant_types')],
                [InlineKeyboardButton(text='Back', callback_data='go_back_from_my_plants')]
            ])

            self.bot.sendMessage(chat_id, "This are all your plants", reply_markup=keyboard)

        elif len(plants) == 1:
            plant_names=[]
            for plant in plants:
                plant_names.append(plant["plantName"])
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=plant_names[0], callback_data=f'menu_for_a_plant_{plant_names[0]}')],
                [InlineKeyboardButton(text='Add plant', callback_data='send_menu_plant_types')],
                [InlineKeyboardButton(text='Back', callback_data='go_back_from_my_plants')]
            ])

            self.bot.sendMessage(chat_id, "This are all your plants", reply_markup=keyboard)

        else:
            plant_names=[]
            for plant in plants:
                plant_names.append(plant["plantName"])
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Add plant', callback_data='send_menu_plant_types')],
                [InlineKeyboardButton(text='Back', callback_data='go_back_from_my_plants')]
            ])

            self.bot.sendMessage(chat_id, "No plants, no problem, add one", reply_markup=keyboard)

    def send_profile_menu(self, chat_id):
        res2 =requests.get(f"{self.backend_url}/user?username={self.logged_users[chat_id]["username"]}")
        if res2.status_code == 200:
            data=res2.json()
            plants = data.get("plants")
            username = data.get("username")
            password = data.get("password")
            self.logged_users[chat_id]={
                "username": username,
                "password": password,
                "plants": plants
            }
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='My information', callback_data='send_profile_information')],
            [InlineKeyboardButton(text='Delete account', callback_data='delete_account')],
            [InlineKeyboardButton(text='Back', callback_data='go_back_from_profile_menu')]
        ])

        self.bot.sendMessage(chat_id, "This are your profile options", reply_markup=keyboard)

    def send_a_plant_menu(self, chat_id):
        res2 =requests.get(f"{self.backend_url}/user?username={self.logged_users[chat_id]["username"]}")
        if res2.status_code == 200:
            data=res2.json()
            plants = data.get("plants")
            username = data.get("username")
            password = data.get("password")
            self.logged_users[chat_id]={
                "username": username,
                "password": password,
                "plants": plants
                }
        user=self.logged_users[chat_id]
        plants=user.get("plants")
        for plant in plants:
            if plant["plantName"] == self.selected_plant:
                actual_plant=plant
                break
        irrigation_mode=actual_plant["irrigationMode"]
        if irrigation_mode=="only notifications":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Plant information', callback_data='send_plant_info')],
                [InlineKeyboardButton(text='Graphs', callback_data='menu_graphs')],
                [InlineKeyboardButton(text='Configure irrigation', callback_data='menu_config_irrigation')],
                [InlineKeyboardButton(text='Irrigate', callback_data='irrigation_triggered')],
                [InlineKeyboardButton(text='Delete', callback_data='delete_plant_triggered')],
                [InlineKeyboardButton(text='Back', callback_data='go_back_from_plant_menu')]
            ])

            self.bot.sendMessage(chat_id, "This are your plant options", reply_markup=keyboard)
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Plant information', callback_data='send_plant_info')],
                [InlineKeyboardButton(text='Graphs', callback_data='menu_graphs')],
                [InlineKeyboardButton(text='Configure irrigation', callback_data='menu_config_irrigation')],
                [InlineKeyboardButton(text='Delete', callback_data='delete_plant_triggered')],
                [InlineKeyboardButton(text='Back', callback_data='go_back_from_plant_menu')]
            ])

            self.bot.sendMessage(chat_id, "This are your plant options", reply_markup=keyboard)

    def send_graph_menu(self, chat_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Humidity', callback_data='send_humidity_graph')],
            [InlineKeyboardButton(text='Temperature', callback_data='send_temperature_graph')],
            [InlineKeyboardButton(text='PH', callback_data='send_ph_graph')],
            [InlineKeyboardButton(text='Soil Mosture', callback_data='send_moisture_graph')],
            [InlineKeyboardButton(text='Real time analysis', callback_data='send_realtime_graph')],
            [InlineKeyboardButton(text='Historical analysis', callback_data='send_historical_graph')],
            [InlineKeyboardButton(text='Back', callback_data='go_back_from_graph_menu')]
        ])

        self.bot.sendMessage(chat_id, "Please select the graph you want to see", reply_markup=keyboard)

    def send_configure_irrigation_menu(self, chat_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Automated', callback_data='set_automated_irrigation')],
            [InlineKeyboardButton(text='Scheduled', callback_data='set_scheduled_irrigation')],
            [InlineKeyboardButton(text='Only notifications', callback_data='set_only_notifications_mode')],
            [InlineKeyboardButton(text='Back', callback_data='go_back_from_irrigation_menu')]
        ])

        self.bot.sendMessage(chat_id, "Select the irrigation mode you want to use", reply_markup=keyboard)

    def send_menu_plant_types(self, chat_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Cactus', callback_data='cactus')],
            [InlineKeyboardButton(text='Peace Lily', callback_data='peace lily')],
            [InlineKeyboardButton(text='Spider Plant', callback_data='spider plant')]
        ])

        self.bot.sendMessage(chat_id, "Select the plant type you purchased", reply_markup=keyboard)

    def send_graph(self, chat_id, graph_type):
        user = self.logged_users.get(chat_id)
        if not user or not self.selected_plant:
            return self.bot.sendMessage(chat_id, "⚠️ Please select a plant first.")

        username = user["username"]
        plant_serial = next(
            (p["deviceConnectorSerialNumber"] for p in user.get("plants", [])
            if p["plantName"] == self.selected_plant),
            None
        )
        if not plant_serial:
            return self.bot.sendMessage(chat_id, "❌ Could not find the plant serial.")

        try:
            fig, ax = plt.subplots(figsize=(12, 6))

            if graph_type in ["temperature", "humidity", "moisture", "ph"]:
                res = requests.get(
                    f"{self.backend_url}/get_plot",
                    params={"username": username, "plant": plant_serial, "graph": graph_type},
                    timeout=5
                )
                res.raise_for_status()
                data = res.json()
                ts   = data.get("timestamps", [])
                vals = data.get("values", [])
                if not ts or not vals:
                    return self.bot.sendMessage(chat_id, "⚠️ No data to plot.")
                ax.plot(ts, vals, marker="o", label=graph_type)
                all_times = ts

            elif graph_type == "realtime":
                res = requests.get(
                    f"{self.backend_url}/get_realtime_analysis",
                    params={"username": username, "plant": plant_serial},
                    timeout=5
                )
                res.raise_for_status()
                points = res.json()
                if not points:
                    return self.bot.sendMessage(chat_id, "⚠️ No realtime data to plot.")
                series = {}
                for m in ["temperature","humidity","moisture","ph"]:
                    series[m] = {
                        "timestamps": [p["time"] for p in points if p.get(f"filt_{m}") is not None],
                        "values":     [p[f"filt_{m}"] for p in points if p.get(f"filt_{m}") is not None]
                    }
                    ax.plot(series[m]["timestamps"], series[m]["values"], label=m)
                all_times = sorted({t for s in series.values() for t in s["timestamps"]})

            elif graph_type == "historical":
                res = requests.get(
                    f"{self.backend_url}/get_historical_trends",
                    params={"username": username, "plant": plant_serial},
                    timeout=5
                )
                res.raise_for_status()
                trends = res.json()
                for m, arr in trends.items():
                    times = [pt["time"]       for pt in arr if pt.get("prediction") is not None]
                    preds = [pt["prediction"] for pt in arr if pt.get("prediction") is not None]
                    ax.plot(times, preds, label=m)
                all_times = sorted({pt["time"] for arr in trends.values() for pt in arr})

            else:
                return self.bot.sendMessage(chat_id, f"❌ Unknown graph type: {graph_type}")

            ax.legend()
            ax.set_title(f"{graph_type.capitalize()} for {self.selected_plant}")
            ax.set_xlabel("Time")
            ax.set_ylabel("Value")

            if len(all_times) >= 3:
                ticks = [all_times[0], all_times[len(all_times)//2], all_times[-1]]
            else:
                ticks = all_times
            ax.set_xticks(ticks)
            for label in ax.get_xticklabels():
                label.set_rotation(45)

            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format="png")
            plt.close(fig)
            buf.seek(0)
            self.bot.sendPhoto(chat_id, buf)

        except Exception as e:
            print("❌ Error in send_graph:", e)
            self.bot.sendMessage(chat_id, f"❌ Could not get graph: {e}")
        finally:
            self.send_graph_menu(chat_id)


    def change_irrigation_mode(self, chat_id, mode):
        user = self.logged_users.get(chat_id)
        if not user or not self.selected_plant:
            self.bot.sendMessage(chat_id, "⚠️ Select a plant first.")
            return

        username = user["username"]
        plant_serial = None
        for plant in user["plants"]:
            if plant["plantName"] == self.selected_plant:
                plant_serial = plant["deviceConnectorSerialNumber"]
                break

        if not plant_serial:
            self.bot.sendMessage(chat_id, "❌ Plant serial not found.")
            return

        try:
            res = requests.put(f"{self.backend_url}/changeIrrigationMode", json={
                "username": username,
                "plantSerial": plant_serial,
                "newMode": mode
            })
            if res.status_code == 200:
                self.bot.sendMessage(chat_id, f"✅ Irrigation mode set to '{mode}'")
            else:
                self.bot.sendMessage(chat_id, "❌ Failed to change irrigation mode.")
        except Exception as e:
            print("❌ Error changing irrigation mode:", e)
            self.bot.sendMessage(chat_id, "❌ An error occurred while changing irrigation mode.")


    def on_callback_query(self, msg):
        query_ID, chat_ID, query_data = telepot.glance(msg, flavor='callback_query')

        if chat_ID in self.logged_users:
            stored_username = self.logged_users[chat_ID]["username"]
            try:
                res = requests.get(f"{self.backend_url}/user?username={stored_username}")
                if res.status_code != 200:
                    del self.logged_users[chat_ID]
                    self.bot.sendMessage(chat_ID, "⚠️ Your session has expired. Please log in again.")
                    self.initial_menu(chat_ID)
                    return
            except Exception as e:
                print("❌ Error checking user session in callback:", e)


        if query_data == "show_login_info":
            self.bot.sendMessage(chat_ID, "🔐 For login, Write:\n`login username:password`", parse_mode="Markdown")

        elif query_data == "show_register_info":
            self.bot.sendMessage(chat_ID, "📝 For register, Write:\n`register username:password`", parse_mode="Markdown")

        elif query_data == "menu_plants":
            user = self.logged_users.get(chat_ID, {})
            plants = user.get("plants", [])
            self.send_plants_menu(chat_ID, plants)

        elif query_data == "menu_profile":
            self.send_profile_menu(chat_ID)

        elif query_data == "go_back_from_profile_menu":
            self.send_main_menu(chat_ID)

        elif query_data == "go_back_from_my_plants":
            self.send_main_menu(chat_ID)

        elif query_data == "go_back_from_plant_menu":
            user = self.logged_users.get(chat_ID, {})
            plants = user.get("plants", [])
            self.selected_plant=None
            self.send_plants_menu(chat_ID, plants)

        elif query_data[:16] == "menu_for_a_plant":
            self.selected_plant=query_data[17:]
            print(self.selected_plant)
            self.send_a_plant_menu(chat_ID)

        elif query_data == "menu_graphs":
            self.send_graph_menu(chat_ID)

        elif query_data == "go_back_from_graph_menu":
            self.send_a_plant_menu(chat_ID)

        elif query_data == "menu_config_irrigation":
            self.send_configure_irrigation_menu(chat_ID)

        elif query_data == "go_back_from_irrigation_menu":
            self.send_a_plant_menu(chat_ID)

        elif query_data == "log_out_triggered":
            self.logged_users.pop(chat_ID)
            self.bot.sendMessage(chat_ID, "You Logged out succesfully")
            self.initial_menu(chat_ID)

        elif query_data == "delete_account":
            user=self.logged_users[chat_ID]
            username=user["username"]

            res = requests.delete(f"{self.backend_url}/deleteAccount?username={username}")

            if res.status_code == 200:
                self.logged_users.pop(chat_ID)
                self.bot.sendMessage(chat_ID, "✅ You Logged Out and your account was deleted.")
                self.initial_menu(chat_ID)
            else:
                self.bot.sendMessage(chat_ID, "An error has accurred, your account could not be deleted")
        
        elif query_data == "send_profile_information":
            user=self.logged_users[chat_ID]
            username=user["username"]
            password=user["password"]
            self.bot.sendMessage(chat_ID, f'Your username is: {username}')
            self.bot.sendMessage(chat_ID, f'Your password is: {password}')
            self.send_profile_menu(chat_ID)

        elif query_data == "send_menu_plant_types":
            self.send_menu_plant_types(chat_ID)
        
        elif query_data == "cactus" or query_data=="peace lily" or query_data=="spider plant":
            self.selected_plant_type=query_data
            self.bot.sendMessage(chat_ID, "Please type your plant information as Name:Serial")
            self.bot.sendMessage(chat_ID, "You will find the serial number at the back of the box")
            self.pending_plant_to_add=True
            self.pending_plant_name=True
            
        elif query_data == "delete_plant_triggered":
            user=self.logged_users[chat_ID]
            username=user["username"]
            plantList=user["plants"]
            for plant in plantList:
                if plant["plantName"] == self.selected_plant:
                    plant_to_delete=plant["deviceConnectorSerialNumber"]
                    print(plant_to_delete)
                    break
            res= requests.delete(f"{self.backend_url}/deletePlant?username={username}&plantSerial={plant_to_delete}")

            if res.status_code==200:
                delete_plant_from_user(self, chat_ID, self.selected_plant)
                self.selected_plant=None
                self.bot.sendMessage(chat_ID, "your Plant has been deleted correctly")
                self.send_plants_menu(chat_ID, self.logged_users[chat_ID]["plants"])
            else:
                self.bot.sendMessage(chat_ID, "and error has occured, please try to delete plant again")

        elif query_data.startswith("send_") and query_data.endswith("_graph"):
            graph_type = query_data.replace("send_", "").replace("_graph", "")
            self.send_graph(chat_ID, graph_type)

        elif query_data=='send_plant_info':
            user = self.logged_users[chat_ID]
            plants = user.get('plants', [])
            actual = next((p for p in plants if p['plantName'] == self.selected_plant), None)
            if not actual:
                self.bot.sendMessage(chat_ID, "❌ Plant not found.")
            else:
                name = actual.get('plantName')
                ptype = actual.get('plantType')
                serial = actual.get('deviceConnectorSerialNumber')
                pump = actual.get('waterPump', {}).get('serialNumber')
                tank = actual.get('waterTank', {}).get('serialNumber')
                mode = actual.get('irrigationMode')
                self.bot.sendMessage(chat_ID, f"🌿 Plant Name: {name}")
                self.bot.sendMessage(chat_ID, f"Type: {ptype}")
                self.bot.sendMessage(chat_ID, f"Serial: {serial}")
                for s in actual.get('sensorList', []):
                    m = s.get('measureType')
                    sid = s.get('serialNumber')
                    self.bot.sendMessage(chat_ID, f"{m} Sensor: {sid}")
                self.bot.sendMessage(chat_ID, f"Pump Serial: {pump}")
                self.bot.sendMessage(chat_ID, f"Tank Serial: {tank}")
                self.bot.sendMessage(chat_ID, f"Irrigation Mode: {mode}")
                try:
                    resp = requests.get(
                        f"{self.backend_url}/get_latest_tank_status",
                        params={"username": user['username'], "plant": serial}
                    )
                    if resp.status_code == 200:
                        td = resp.json()
                        val = td.get('value')
                        timestamp = td.get('time')
                        if val is not None:
                            self.bot.sendMessage(chat_ID, f"🚰 Tank Level: {val}% (as of {timestamp})")
                        else:
                            self.bot.sendMessage(chat_ID, "⚠️ No tank data available.")
                    else:
                        self.bot.sendMessage(chat_ID, "❌ Cannot retrieve tank status.")
                except Exception as e:
                    self.bot.sendMessage(chat_ID, f"❌ Error retrieving tank: {e}")
            self.send_a_plant_menu(chat_ID)

        elif query_data == "set_automated_irrigation":
            self.change_irrigation_mode(chat_ID, "automated")
            self.send_configure_irrigation_menu(chat_ID)

        elif query_data == "set_scheduled_irrigation":
            self.change_irrigation_mode(chat_ID, "scheduled")
            self.send_configure_irrigation_menu(chat_ID)

        elif query_data == "set_only_notifications_mode":
            self.change_irrigation_mode(chat_ID, "only notifications")
            self.send_configure_irrigation_menu(chat_ID)

        elif query_data=='irrigation_triggered':
            username = self.logged_users[chat_ID]['username']
            serial = next((p['deviceConnectorSerialNumber'] for p in self.logged_users[chat_ID]['plants'] if p['plantName'] == self.selected_plant), None)
            try:
                res = requests.post(f"{self.backend_url}/irrigate", json={
                    "username": username,
                    "plantSerial": serial
                })
                if res.status_code == 200:
                    self.bot.sendMessage(chat_ID, "✅ Irrigation command sent successfully!")
                else:
                    err = res.json().get('error') or res.json().get('message', 'Failed to send irrigation command.')
                    self.bot.sendMessage(chat_ID, f"❌ {err}")
                self.send_a_plant_menu(chat_ID)
            except Exception as e:
                self.bot.sendMessage(chat_ID, f"❌ Error sending irrigation command: {e}")


        else:
            self.bot.sendMessage(chat_ID, "⚠️ Comando no reconocido. Usa /start para comenzar.")


if __name__ == '__main__':
    TOKEN = '7844271014:AAF5wdJYYBOvrrjGvX-bXByCM1LDP_cgQ40'
    ProjectBot(TOKEN)
    while True:
        pass 