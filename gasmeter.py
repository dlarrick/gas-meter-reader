#!/usr/bin/env python3
"""Read gas meter and publish as MQTT"""
import sys
import json
from datetime import datetime
from datetime import timedelta
import time
import statistics
import paho.mqtt.client as mqttClient
import cv2
import gas_meter_reader

CONNECTED = False # MQTT connected

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

def get_central_measures(in_vals, measure):
    """Compute median of each column in a 2D array"""
    # Note: independent medians for now
    val_size = len(in_vals[0])
    vals = []
    for column in range(val_size):
        vals.append([])
    for val in in_vals:
        for column in range(val_size):
            vals[column].append(val[column])
    result = []
    for column in vals:
        if measure == 'median':
            result.append(statistics.median(column))
        else if measure == 'mean':
            result.append(statistics.mean(column))
    return result

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
        frames = []
        now = datetime.now()
        next_time = now + timedelta(minutes=5)

        cap = cv2.VideoCapture(0)
        cap.set(3, 1280)
        cap.set(4, 1024)
        for reading in range(10):
            _ = reading
            ret, frame = cap.read()
            if ret:
                frames.append(frame)
        cap.release()
        print("Got %d frames" % len(frames))

        gas_meter_reader.clear_debug()
        if frames:
            circles_list = []
            images_list = []
            sample = 0
            for frame in frames:
                sample += 1
                img, circles = gas_meter_reader.get_circles(frame, sample)
                if circles is None:
                    continue
                sorted_circles = sorted(circles, key=lambda circle: circle[0])
                #print("Circles: %s" % str(sorted_circles))
                if len(sorted_circles) == 4:
                    circles_list.append(sorted_circles)
                    images_list.append(img)
            if not circles_list:
                print("Could not get any circles!")
                continue
            circles = get_central_measures(circles_list, 'median')
            print("Median circles: %s" % str(circles))
            readings = []
            sample = 0
            for image in images_list:
                sample += 1
                reading = gas_meter_reader.process(image, circles, sample)
                if len(reading) == 5:
                    print("Reading: %s" % str(reading))
                    readings.append(reading)
            reading = get_central_measures(readings, 'mean')
            print("Median reading: %s" % str(reading))

            output = 0.0
            power = len(reading) - 2
            for res in reading:
                output += res * 10**power
                power = max(0, power-1)

            message = {"reading": round(float(output), 1),
                       "timestamp": str(now)}
            print("Publish %s" % json.dumps(message))
            client.publish("gasmeter/reading", json.dumps(message))
        else:
            print("Unable to read frames!")

        while datetime.now() < next_time:
            time.sleep(10)

if __name__ == '__main__':
    main(sys.argv[1:])
