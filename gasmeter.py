#!/usr/bin/env python3
"""Read gas meter and publish as MQTT"""
import sys
import json
from datetime import datetime
from datetime import timedelta
import time
import paho.mqtt.client as mqttClient
import cv2
import gas_meter_reader


def on_connect(client, userdata, flags, code):
    """Connect completion for Paho"""
    _ = client
    _ = userdata
    _ = flags
    global CONNECTED
    if code == 0:
        print("Connected to broker")
        CONNECTED = True                #Signal connection
    else:
        print("Connection failed")

CONNECTED = False # MQTT connected

def main(argv):
    """Entry point"""
    _ = argv
    global CONNECTED

    broker_address = "localhost"
    port = 1883

    client = mqttClient.Client("GasMeter")    #create new instance
    client.on_connect = on_connect            #attach function to callback
    client.connect(broker_address, port=port) #connect to broker

    client.loop_start()

    while not CONNECTED:
        time.sleep(0.1)

    while True:
        now = datetime.now()
        next_time = now + timedelta(minutes=5)

        cap = cv2.VideoCapture(0)
        cap.set(3, 1280)
        cap.set(4, 1024)
        ret, frame = cap.read()
        cap.release()

        if ret:
            reading = gas_meter_reader.process(frame)

            message = {"reading": round(float(reading), 2),
                       "timestamp": str(now)}
            print("Publish %s" % json.dumps(message))
            client.publish("gasmeter/reading", json.dumps(message))
        else:
            print("Unable to read frame!")

        while datetime.now() < next_time:
            time.sleep(10)

if __name__ == '__main__':
    main(sys.argv[1:])
