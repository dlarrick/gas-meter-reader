#!/usr/bin/env python3
"""Read gas meter and publish as MQTT"""
import sys
import os
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

def get_median_circles(in_vals):
    """Compute median of each column of circles in a list
    of columns of circles"""
    val_size = len(in_vals[0])
    columns = []
    for circlelist in range(val_size):
        columns.append([])
    for circlelist in in_vals:
        for column in range(val_size):
            columns[column].append(circlelist[column])
    result = []
    for column in columns:
        x_coords = []
        y_coords = []
        radii = []
        for circle in column:
            x_coords.append(circle[0])
            y_coords.append(circle[1])
            radii.append(circle[2])
        x_median = statistics.median(x_coords)
        y_median = statistics.median(y_coords)
        radius_median = statistics.median(radii)
        result.append([x_median, y_median, radius_median])

    return result

def publish_result(client, reading, last_reading, now):
    """Write result to MQTT or save debug output"""
    if last_reading and abs(last_reading - reading) > last_reading * 0.01:
        bad_reading = str(round(float(reading), 1))
        print("Rejecting bad reading %s" % bad_reading)
        if os.path.isdir('output'):
            os.rename('output', 'output-%s' % bad_reading)
            os.mkdir('output')
        return False
    message = {"reading": round(float(reading), 1),
               "timestamp": str(now)}
    print("Publish %s" % json.dumps(message))
    client.publish("gasmeter/reading", json.dumps(message))
    return True

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

    last_reading = None
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
            circles = get_median_circles(circles_list)
            print("Median circles: %s" % str(circles))
            readings = []
            sample = 0
            for image in images_list:
                sample += 1
                reading = gas_meter_reader.process(image, circles, sample)
                if len(reading) == 5:
                    print("Reading: %s" % str(reading))
                    output = gas_meter_reader.assemble_reading(reading)
                    readings.append(output)
            reading = statistics.mean(readings)
            print("Mean reading: %s" % str(reading))

            if publish_result(client, reading, last_reading, now):
                last_reading = reading
        else:
            print("Unable to read frames!")

        while datetime.now() < next_time:
            time.sleep(10)

if __name__ == '__main__':
    main(sys.argv[1:])
