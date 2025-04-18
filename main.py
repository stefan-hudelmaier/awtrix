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

log_level = os.environ.get('LOG_LEVEL', 'INFO')
print("Using log level", log_level)

logger = logging.getLogger()
logger.setLevel(log_level)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

last_successful_message = None


def connect_mqtt():
    def on_connect(client, userdata, flags, rc, properties):
        if rc == 0:
            logger.info("Connected to MQTT Broker")
            client.subscribe("stefan/house/battery/level")
            client.subscribe("stefan/house/inverters/total_dc_power")
        else:
            logger.error(f"Failed to connect, return code {rc}")

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        logger.warning(f"Disconnected from MQTT Broker, return code {reason_code}")

    def on_message(client, userdata, msg):
        print(f"Received '{msg.payload.decode()}' from '{msg.topic}' topic")
        app_name = None
        icon = None
        if msg.topic == "stefan/house/battery/level":
            app_name = "solarbat"
            icon = 12124
        elif msg.topic == "stefan/house/inverters/total_dc_power":
            app_name = "solarpower"
            icon = 1338

        if app_name is not None and icon is not None:
            requests.post(f"http://{awtrix_ip}/api/custom?name={app_name}", json={"text": msg.payload.decode(), "duration": 5, "icon": icon})

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
        a = random.randint(1, 10)
        b = random.randint(1, 10)
        op = random.choice(['+', '-', '*'])
        text = f"{a} {op} {b}"
        requests.post(f"http://{awtrix_ip}/api/custom?name=math", json={"text": text, "duration": 5, "icon": 5259})
        sleep(30)

def main():
    mqtt_client = connect_mqtt()

    quotes_thread = Thread(target=quotes, args=())
    quotes_thread.start()

    math_questions_thread = Thread(target=math_questions, args=())
    math_questions_thread.start()

    mqtt_client.loop_forever(retry_first_connection=True)


if __name__ == '__main__':
    main()
