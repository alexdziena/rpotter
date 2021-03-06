#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
  _\
  \
O O-O
 O O
  O
  
Raspberry Potter
Ollivander - Version 0.2 

Use your own wand or your interactive Harry Potter wands to control the IoT.  


Copyright (c) 2016 Sean O'Brien.  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''
import io
import numpy as np
import argparse
import cv2
from cv2 import *
import threading
import sys
import math
import time

import warnings
import tplink
is_py2 = sys.version[0] == '2'
if is_py2: import Queue as queue
else: import queue as queue
from device import DeviceFactory, Bulb
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
warnings.filterwarnings("ignore", category=np.VisibleDeprecationWarning)

_SUPPORTS_PI_LIBS = False

try:
    import pigpio
    import picamera
    _SUPPORTS_PI_LIBS = True
except:
    print "Can not import Raspberry Pi Libraries"
if _SUPPORTS_PI_LIBS:
    GPIOS=32
    MODES=["INPUT", "OUTPUT", "ALT5", "ALT4", "ALT0", "ALT1", "ALT2", "ALT3"]

    pi = pigpio.pi()

    #NOTE pins use BCM numbering in code.  I reference BOARD numbers in my articles - sorry for the confusion!

    #pin for Powerswitch (Lumos,Nox)
    switch_pin = 23
    pi.set_mode(switch_pin,pigpio.OUTPUT)

    #pin for Particle (Nox)
    nox_pin = 24
    pi.set_mode(nox_pin,pigpio.OUTPUT)

    #pin for Particle (Incendio)
    incendio_pin = 22
    pi.set_mode(incendio_pin,pigpio.OUTPUT)

    #pin for Trinket (Colovario)
    trinket_pin = 12
    pi.set_mode(trinket_pin,pigpio.OUTPUT)

logging.info("Initializing point tracking")

# Parameters
lk_params = dict( winSize  = (15,15),
                  maxLevel = 2,
                  criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
blur_params = (4,4)
dilation_params = (5, 5)
movment_threshold = 80

logging.info("START switch_pin ON for pre-video test")
if _SUPPORTS_PI_LIBS:
    pi.write(nox_pin,0)
    pi.write(incendio_pin,0)
    pi.write(switch_pin,1)

# start capturing
cv2.namedWindow("Raspberry Potter")
if _SUPPORTS_PI_LIBS:
    CAM_NUMBER = -1
else:
    CAM_NUMBER = 0
cam = cv2.VideoCapture(CAM_NUMBER)
if _SUPPORTS_PI_LIBS:
    cam.set(3, 640)
    cam.set(4, 480)
else:
    cam.set(3, 1024)
    cam.set(4, 768)


class TPLinkWorker(threading.Thread):
    # Based on https://eli.thegreenplace.net/2011/12/27/python-threads-communication-and-stopping
    """ A worker thread that takes directory names from a queue, finds all
        files in them recursively and reports the result.

        Input is done by placing directory names (as strings) into the
        Queue passed in dir_q.

        Output is done by placing tuples into the Queue passed in result_q.
        Each tuple is (thread name, dirname, [list of files]).

        Ask the thread to stop by calling its join() method.
    """

    def __init__(self, tasks_queue, result_queue):
        super(TPLinkWorker, self).__init__()
        self.tasks_queue = tasks_queue
        self.result_queue = result_queue
        self.stoprequest = threading.Event()
        self.stopcolovaria = threading.Event()

    def run(self):
        # As long as we weren't asked to stop, try to take new tasks from the
        # queue. The tasks are taken with a blocking 'get', so no CPU
        # cycles are wasted while waiting.
        # Also, 'get' is given a timeout, so stoprequest is always checked,
        # even if there's nothing in the queue.
        logging.info("Starting Worker")
        while not self.stoprequest.isSet():
            try:
                spell = self.tasks_queue.get(True, 3)
                self.result_queue.put(spell())
                self.tasks_queue.task_done()
                logging.info(self.result_queue.get(True,3))
            except queue.Empty:
                continue

    def join(self, timeout=None):
        self.stoprequest.set()
        super(TPLinkWorker, self).join(timeout)

    def _lumos(self):
        logging.info("Lumos called")
        tplink.allOn()

    def _nox(self):
        logging.info("Nox called")
        tplink.allOff()

    def _colovaria(self):
        logging.info("Colovaria called")
        self.stopcolovaria.clear()
        l = tplink.TPLink()
        logging.info(l.login())
        factory = DeviceFactory(l.endpoint)
        devices = defaultdict(list)
        for device in l.getDeviceList()['result']['deviceList']:
            logging.info('{}: {}'.format(device['alias'], device['deviceId']))
            device = factory.buildDevice(device)
            devices[device.__class__].append(device)
            device.token = l.token
            # logging.info(device.on())
            # time.sleep(.5)
            # logging.info(device.off())
        for bulb in devices[Bulb]:
            logging.info(bulb.on())
            logging.info(bulb.color())
            logging.info(bulb.saturation(100))
            for hue in range(361):
                if self.stopcolovaria.isSet():
                    break
                logging.info(bulb.hue(hue))
                time.sleep(20 / 1000.0)
            logging.info(bulb.white())
            if self.stopcolovaria.isSet():
                break
        self.stopcolovaria.clear()


TASKS = queue.Queue(maxsize=10)
RESULTS = queue.Queue(maxsize=20)
WORKER = None


def startWorker():
    global WORKER
    WORKER = TPLinkWorker(TASKS,RESULTS)
    WORKER.start()


def Spell(spell):
    # clear all checks
    ig = [[0] for x in range(15)]
    # Invoke IoT (or any other) actions here
    cv2.putText(mask, spell, (5, 25), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0))
    if not WORKER or not WORKER.isAlive():
        startWorker()
    if (spell == "Colovaria"):
        TASKS.put(WORKER._colovaria, True, 1)
    elif (spell == "Lumos"):
        WORKER.stopcolovaria.set()
        TASKS.put(WORKER._lumos, True, 1)
    elif (spell == "Nox"):
        WORKER.stopcolovaria.set()
        TASKS.put(WORKER._nox, True, 1)
    else:
        logging.error("Spell not found: {}".format(spell))
        return False
    logging.info("CAST: {}".format(spell))
    return True


def IsGesture(a, b, c, d, i):
    logging.debug("point: {}".format(i))
    # look for basic movements - TODO: trained gestures
    if ((a < (c - 5)) & (abs(b - d) < 2)):
        ig[i].append("left")
    elif ((c < (a - 5)) & (abs(b - d) < 2)):
        ig[i].append("right")
    elif ((b < (d - 5)) & (abs(a - c) < 5)):
        ig[i].append("up")
    elif ((d < (b - 5)) & (abs(a - c) < 5)):
        ig[i].append("down")
    # check for gesture patterns in array
    astr = ''.join(map(str, ig[i]))
    logging.debug(astr)
    if "rightup" in astr:
        return Spell("Lumos")
    elif "rightdown" in astr:
        return Spell("Nox")
    elif "leftdown" in astr:
        return Spell("Colovaria")
    # elif "leftup" in astr:
    #     return Spell("Incendio")
    return False


def FindWand():
    global rval, old_frame, old_gray, p0, mask, color, ig, img, frame
    try:
        rval, old_frame = cam.read()
        cv2.flip(old_frame, 1, old_frame)
        old_gray = cv2.cvtColor(old_frame, cv2.COLOR_BGR2GRAY)
        equalizeHist(old_gray)
        old_gray = GaussianBlur(old_gray, (9, 9), 1.5)
        dilate_kernel = np.ones(dilation_params, np.uint8)
        old_gray = cv2.dilate(old_gray, dilate_kernel, iterations=1)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        old_gray = clahe.apply(old_gray)
        # TODO: trained image recognition
        p0 = cv2.HoughCircles(old_gray, cv2.HOUGH_GRADIENT, 3, 50, param1=240, param2=8, minRadius=4, maxRadius=15)
        if p0 is not None:
            p0.shape = (p0.shape[1], 1, p0.shape[2])
            p0 = p0[:, :, 0:2]
            mask = np.zeros_like(old_frame)
            ig = [[0] for x in range(20)]
        logging.info("finding...")
        threading.Timer(3, FindWand).start()
    except:
        e = sys.exc_info()[1]
        logging.error("Error: {}".format(e))
        if WORKER.isAlive():
            WORKER.stoprequest.set()
            WORKER.join()
        exit()


def TrackWand():
    global rval, old_frame, old_gray, p0, mask, color, ig, img, frame
    try:
        color = (0, 0, 255)
        rval, old_frame = cam.read()
        cv2.flip(old_frame, 1, old_frame)
        old_gray = cv2.cvtColor(old_frame, cv2.COLOR_BGR2GRAY)
        equalizeHist(old_gray)
        old_gray = GaussianBlur(old_gray, (9, 9), 1.5)
        dilate_kernel = np.ones(dilation_params, np.uint8)
        old_gray = cv2.dilate(old_gray, dilate_kernel, iterations=1)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        old_gray = clahe.apply(old_gray)

        # Take first frame and find circles in it
        p0 = cv2.HoughCircles(old_gray, cv2.HOUGH_GRADIENT, 3, 50, param1=240, param2=8, minRadius=4, maxRadius=15)
        if p0 is not None:
            p0.shape = (p0.shape[1], 1, p0.shape[2])
            p0 = p0[:, :, 0:2]
            mask = np.zeros_like(old_frame)
    except:
        logging.warning("No points found")
    # Create a mask image for drawing purposes

    while True:
        try:
            rval, frame = cam.read()
            cv2.flip(frame, 1, frame)
            if p0 is not None:
                frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                equalizeHist(frame_gray)
                frame_gray = GaussianBlur(frame_gray, (9, 9), 1.5)
                dilate_kernel = np.ones(dilation_params, np.uint8)
                frame_gray = cv2.dilate(frame_gray, dilate_kernel, iterations=1)
                frame_clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                frame_gray = frame_clahe.apply(frame_gray)

                # calculate optical flow
                p1, st, err = cv2.calcOpticalFlowPyrLK(old_gray, frame_gray, p0, None, **lk_params)

                # Select good points
                good_new = p1[st == 1]
                good_old = p0[st == 1]

                # draw the tracks
                for i, (new, old) in enumerate(zip(good_new, good_old)):
                    a, b = new.ravel()
                    c, d = old.ravel()
                    # only try to detect gesture on highly-rated points (below 10)
                    if (i < 10):
                        if IsGesture(a, b, c, d, i): time.sleep(3.1)
                    dist = math.hypot(a - c, b - d)
                    if (dist < movment_threshold):
                        cv2.line(mask, (a, b), (c, d), (0, 255, 0), 2)
                    cv2.circle(frame, (a, b), 5, color, -1)
                    cv2.putText(frame, str(i), (a, b), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255))
                img = cv2.add(frame, mask)

                cv2.putText(img, "Press ESC to close.", (5, 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255))
            cv2.imshow("Raspberry Potter", frame)

            # get next frame
            rval, frame = cam.read()

            # Now update the previous frame and previous points
            old_gray = frame_gray.copy()
            p0 = good_new.reshape(-1, 1, 2)
        except IndexError:
            logging.warning("Index error - Tracking")
        except KeyboardInterrupt:
            cleanupAll()
            exit(0)
        except:
            e = sys.exc_info()[0]
            logging.error("Tracking Error: {}".format(e))
        key = cv2.waitKey(20)
        if key in [27, ord('Q'), ord('q')]:  # exit on ESC
            cleanupAll()
            exit(0)
            break

def cleanupAll():
    if WORKER.isAlive():
        WORKER.stoprequest.set()
        WORKER.join()
    cv2.destroyAllWindows()
    cam.release()


try:
    startWorker()
    FindWand()
    logging.info("START incendio_pin ON and set switch off if video is running")
    if _SUPPORTS_PI_LIBS:
        pi.write(incendio_pin,1)
        pi.write(switch_pin,0)
    TrackWand()

finally:
    cleanupAll();
