#!/usr/bin/env python3
"""Read gas meter using machine vision"""
import sys
import glob
import os
import os.path
import math
import numpy as np
import cv2

DIALS = [
    #offset, clockwise, factor
    [0, False, 1],
    [0, True, 1],
    [0, False, 1],
    [0, True, 1],
    [0, False, 0],
    [0, False, 0],
    [0, False, 0],
    [0, False, 0],
    [0, False, 0],
    [0, False, 0],
    [0, False, 0],
    [0, False, 0],
    [0, False, 0],
    [0, False, 0],
    [0, False, 0]
]

def clear_debug():
    """Clear debug directory"""
    filelist = glob.glob("output/*.jpg")
    for file in filelist:
        os.remove(file)

def write_debug(img, name):
    """Write image to debug directory"""
    cv2.imwrite(f"output/{name}.jpg", img)

def find_least_covered_angle(edges, idx):
    """Find angle with the fewest pixels covered from center"""
    height, width = edges.shape[:2]

    center = [width / 2, height / 2]
    radius = int(width / 2)

    least_count = height * width
    least_angle = None
    streak = 0
    step = 1
    deb = -1

    # Remove the border, often noisy
    mask = np.zeros((height, width, 1), np.uint8)
    cv2.circle(mask, (int(center[0]), int(center[1])), radius,
               (255, 255, 255), 20)
    mask = cv2.bitwise_not(mask)
    trimmed = cv2.bitwise_and(edges, edges, mask=mask)
    write_debug(trimmed, f"trimmed-{idx}")
    for angle in range(0, 360, step):
        angle_r = angle * (np.pi / 180)

        origin_point = [center[0], 0]
        angle_point = [
            math.cos(angle_r) * (origin_point[0] - center[0]) - \
            math.sin(angle_r) * (origin_point[1] - center[1]) + center[0],
            math.sin(angle_r) * (origin_point[0] - center[0]) + \
            math.cos(angle_r) * (origin_point[1] - center[1]) + center[1]
        ]

        mask = np.zeros((height, width, 1), np.uint8)
        cv2.line(mask, (int(center[0]), int(center[1])),
                 (int(angle_point[0]), int(angle_point[1])),
                 (255, 255, 255), 2)
        masked = cv2.bitwise_and(trimmed, trimmed, mask=mask)
        count = cv2.countNonZero(masked)
        if deb == idx:
            write_debug(masked, f"masked-{idx}-{angle}-{count}")
        if count < least_count:
            least_count = count
            least_angle = angle
        elif count == least_count:
            streak = streak + 1
            least_angle = int((2 * angle - (streak * step)) / 2)
        else:
            streak = 1

    return least_angle

def black_white_points(in_img):
    """Normalize & crush image to darkest/lightest pixels"""
    crush = 15
    blackest = 255
    whitest = 0
    rows, cols = in_img.shape
    for x_coord in range(cols):
        for y_coord in range(rows):
            black = in_img[y_coord, x_coord]
            if black < blackest:
                blackest = black
            white = in_img[y_coord, x_coord]
            if white > whitest:
                whitest = white
    out_img = in_img.copy()
    blackest += crush
    whitest -= crush
    offset = blackest
    scale = 250.0 / (whitest-blackest)
    #print("Blackest: %d, whitest: %d, scale %f" % (blackest, whitest, scale))
    for x_coord in range(cols):
        for y_coord in range(rows):
            newval = min(255,
                         max(0, (in_img[y_coord, x_coord] - offset) * scale))
            out_img[y_coord, x_coord] = newval
    return out_img

def read_dial(config, idx, img):
    """Read one dial"""
    offset, clockwise, factor = config
    offset_r = offset * (np.pi / 180)

    height, width = img.shape[:2]
    center = [width / 2, height / 2]

    offset_img = img.copy()
    origin_point = [center[0], 0]
    offset_point = [
        math.cos(offset_r) * (origin_point[0] - center[0]) -
        math.sin(offset_r) * (origin_point[1] - center[1]) + center[0],
        math.sin(offset_r) * (origin_point[0] - center[0]) +
        math.cos(offset_r) * (origin_point[1] - center[1]) + center[1]
    ]
    cv2.line(offset_img, (int(center[0]), int(center[1])),
             (int(offset_point[0]), int(offset_point[1])), (0, 255, 0), 2)
    #write_debug(offset_img, f"dial-{idx}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Instead of norm, it might be better to crush blacks somewhat
    #norm = cv2.equalizeHist(gray)
    #write_debug(norm, f"norm-{idx}")
    norm = gray.copy()
    blurred = cv2.GaussianBlur(norm, (5, 5), 0)
    #write_debug(blurred, f"blurred-{idx}")

    edges = cv2.Canny(blurred, 50, 200)
    write_debug(edges, f"edges-{idx}")

    angle = find_least_covered_angle(edges, idx)
    angle_r = angle * (np.pi / 180)
    angle_point = [
        math.cos(angle_r) * (origin_point[0] - center[0]) - \
        math.sin(angle_r) * (origin_point[1] - center[1]) + center[0],
        math.sin(angle_r) * (origin_point[0] - center[0]) + \
        math.cos(angle_r) * (origin_point[1] - center[1]) + center[1]]
    cv2.line(img, (int(center[0]), int(center[1])),
             (int(angle_point[0]), int(angle_point[1])), (0, 0, 255), 2)
    write_debug(img, f"angle-{idx}")

    if angle < 0:
        angle = 360 + angle
    angle_p = angle/360
    if not clockwise:
        angle_p = 1 - angle_p

    return (angle, int(10*angle_p*factor))

def process(original):
    """Process a captured image"""
    clear_debug()

    area = [218, 20, 218+1018, 20+391] # x1, y1, x2, y2

    crop = original[area[1]:area[3], area[0]:area[2]].copy()
    #crop = original.copy()

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    write_debug(gray, "gray")

    #norm = cv2.equalizeHist(gray)
    norm = black_white_points(gray)
    write_debug(norm, "norm")
    #norm = gray.copy()

    blurred = cv2.GaussianBlur(norm, (5, 5), 0)
    write_debug(blurred, "blurred")

    circles = cv2.HoughCircles(blurred, cv2.HOUGH_GRADIENT, 1, 40,
                               np.array([]), 100, 100, 20, 300)

    dials = np.uint16(np.around(circles))[0, :]

    sorted_dials = sorted(dials, key=lambda dial: dial[0])
    result = ""
    lastangle = 0

    for idx, dial in enumerate(sorted_dials):
        x_pos, y_pos, radius = dial
        radius = radius + 5
        dial_img = crop[y_pos-radius:y_pos+radius,
                        x_pos-radius:x_pos+radius].copy()
        angle, value = read_dial(DIALS[idx], idx, dial_img)
        if DIALS[idx][2]:
            result += str(value)
            lastangle = angle
        # draw the outer circle
        cv2.circle(crop, (x_pos, y_pos), radius, (0, 255, 0), 2)
        # draw the center of the circle
        cv2.circle(crop, (x_pos, y_pos), 2, (0, 0, 255), 3)

    write_debug(crop, "circles")

    remainder = (lastangle/360.0)*10 - value
    result += str(remainder)[1:]
    return result

def main(argv):
    """Command line entry point"""
    clear_debug()

    filename = argv[0] if len(sys.argv) > 0 else ""

    if not os.path.exists(filename):
        print("Usage: python3 power-meter-reader.py <image>")
        sys.exit(1)

    original = cv2.imread(filename)

    result = process(original)

    print("%s" % result)

if __name__ == '__main__':
    main(sys.argv[1:])
