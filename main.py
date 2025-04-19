from dotenv import load_dotenv
load_dotenv()

import json
import paho.mqtt.client as mqtt
import os
import logging
import sys
import requests
from threading import Thread
from time import sleep
import wikiquote
import random

broker = os.environ.get('MQTT_HOST', 'gcmb.io')
client_id = os.environ['MQTT_CLIENT_ID']
username = os.environ['MQTT_USERNAME']
password = os.environ['MQTT_PASSWORD']
awtrix_ip = os.environ['AWTRIX_IP']
port = 8883

STOCK_ICON = 52810
BATTERY_CHARGING_ICON = 1095
BATTERY_DISCHARGING_ICON = 53736
SUN_ICON = 1338
MATH_ICON = 5259
SOLAR_INPUT_ICON = 37515

log_level = os.environ.get('LOG_LEVEL', 'INFO')
print("Using log level", log_level)

logger = logging.getLogger()
logger.setLevel(log_level)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


battery_charging = True


def disable_standard_apps():
    for app in ["Battery", "Temperature"]:
        requests.post(f"http://{awtrix_ip}/api/custom?name={app}", json={})


def connect_mqtt():
    def on_connect(client, userdata, flags, rc, properties):
        if rc == 0:
            logger.info("Connected to MQTT Broker")
            client.subscribe("stefan/house/battery/level")
            client.subscribe("stefan/house/inverters/total_dc_power")
            client.subscribe("finance/stock-exchange/index/GDAXI")
            client.subscribe("stefan/house/kpis/daily_pv_generation")
        else:
            logger.error(f"Failed to connect, return code {rc}")

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        logger.warning(f"Disconnected from MQTT Broker, return code {reason_code}")

    def on_message(client, userdata, msg):

        global battery_charging

        text = msg.payload.decode()
        logger.debug(f"Received '{text}' from '{msg.topic}' topic")
        app_name = None
        icon = None
        if msg.topic == "stefan/house/battery/level":
            app_name = "solarbat"
            icon = BATTERY_CHARGING_ICON if battery_charging else BATTERY_DISCHARGING_ICON
        elif msg.topic == "stefan/house/inverters/total_dc_power":
            app_name = "solarpower"
            power = int(float(text))
            text = str(power)
            icon = SUN_ICON
            battery_charging = power > 0
        elif msg.topic == "finance/stock-exchange/index/GDAXI":
            app_name = "dax"
            icon = STOCK_ICON
        elif msg.topic == "stefan/house/kpis/daily_pv_generation":
            app_name = "dailypvgeneration"
            icon = SOLAR_INPUT_ICON
            text = str(int(float(text)))

        if app_name is not None and icon is not None:
            requests.post(f"http://{awtrix_ip}/api/custom?name={app_name}", json={"text": text, "duration": 5, "icon": icon})
            logger.info(f"Posted message to AWTRIX: {text}")

    mqtt_client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION2, reconnect_on_failure=True)
    mqtt_client.tls_set(ca_certs='/etc/ssl/certs/ca-certificates.crt')
    mqtt_client.username_pw_set(username, password)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message

    # Connection will be made once loop_start() has been called
    mqtt_client.connect_async(broker, port)
    return mqtt_client


def quotes():
    while True:
        # quote = wikiquote.quotes('Hermann Hesse', lang='de')[0]
        quote = wikiquote.quote_of_the_day(lang='de')
        quote_text = f"{quote[0]} - {quote[1]}"
        duration = len(quote) // 5 + 10
        logger.info(f"Quote: {quote_text}")
        requests.post(f"http://{awtrix_ip}/api/custom?name=quote", json={"text": quote_text, "duration": duration})
        # TODO: Do this less often
        sleep(5 * 60)


def math_questions():
    while True:

        # Do this as a side effect
        disable_standard_apps()

        op = random.choice(['+', '-', '*'])

        # For *
        a = random.randint(2, 10)
        b = random.randint(2, 10)

        if op == '+':
            a = random.randint(2, 50)
            b = random.randint(2, 10)

        if op == '-':
            a = random.randint(15, 50)
            b = random.randint(2, 14)

        text = f"{a} {op} {b}"
        logger.info(f"Math question: {text}")
        requests.post(f"http://{awtrix_ip}/api/custom?name=math", json={"text": text, "duration": 5, "icon": MATH_ICON})
        sleep(30)


def english():

    translations = []
    with open("english.txt", "r") as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            if line.startswith("#"):
                continue
            parts = line.split(" = ")
            if len(parts) != 2:
                logger.warning(f"Invalid line in english.txt: {line}")
                continue
            english = parts[0]
            german = parts[1]
            translations.append((english, german))

    while True:
        english, german = random.choice(translations)
        text = f"{english} = {german}"
        body = {
            "text": [
                {"t": english, "c": "#00FF00"},
                {"t": " "},
                {"t": german, "c": "#FF0000"}
            ],
            "duration": 15}
        logger.info(f"English: {text}")
        requests.post(f"http://{awtrix_ip}/api/custom?name=english", json=body)
        sleep(30)


def main():
    mqtt_client = connect_mqtt()

    quotes_thread = Thread(target=quotes, args=())
    quotes_thread.start()

    math_questions_thread = Thread(target=math_questions, args=())
    math_questions_thread.start()

    english_questions_thread = Thread(target=english, args=())
    english_questions_thread.start()

    mqtt_client.loop_forever(retry_first_connection=True)


if __name__ == '__main__':
    main()
