#!/usr/bin/python
import RPi.GPIO as GPIO
import serial, time
import os
import sys
from xml.dom import minidom
import logging
from datetime import datetime
from datetime import date
import threading
import signal
from multiprocessing import Process, Lock, Manager
from subprocess import Popen, PIPE
import rpyc
import json

# 3rd party modules
import sysv_ipc

BUCATARIE   = 1
LIVING      = 2
SENSOR      = 0
TEMPERATURE = 1
REFERENCE   = 2
ID          = 3
ROOM_ID     = 0


DEFAULT_REFERENCE = 10

BASE_PATH = os.path.dirname(os.path.realpath(__file__))

homeCoordinates = {"Latitude":44.47816,"Longitude":26.034602}

# work location coordinates: 44.413919, 26.1051352

acceptedLatDiff = 0.01
acceptedLongDiff = 0.01

class ShutdownException(Exception):
    def __init__(self, message):
        super(ShutdownException, self).__init__(message)

def signal_handler(signum, stack):
    logging.info("received signal {}".format(signum))
    raise ShutdownException("shutdown")

def serialInit(ser,comPort,baudRate):
    isInitialized = False
    #initialization and open the port
    #possible timeout values:
    #    1. None: wait forever, block call
    #    2. 0: non-blocking mode, return immediately
    #    3. x, x is bigger than 0, float allowed, timeout block call
    ser.port = comPort
    ser.baudrate = baudRate
    ser.bytesize = serial.EIGHTBITS #number of bits per bytes
    ser.parity = serial.PARITY_NONE #set parity check: no parity
    ser.stopbits = serial.STOPBITS_ONE #number of stop bits
    #ser.timeout = None          #block read
    #ser.timeout = 1            #non-block read
    ser.timeout = 2              #timeout block read
    ser.xonxoff = False     #disable software flow control
    ser.rtscts = False     #disable hardware (RTS/CTS) flow control
    ser.dsrdtr = False       #disable hardware (DSR/DTR) flow control
    ser.writeTimeout = 2     #timeout for write
    try:
        ser.open()
    except IOError, e:
        logging.error("error open serial port: {0}".format(str(e)))
    if ser.isOpen():
        #ser.close()
        isInitialized = True
    return isInitialized

def serialCleanup(ser):
    if ser.isOpen():
        ser.close()
        logging.info("closed serial port")

def serialRequest(ser,request,retryMax=5):
    response = None
    #threadLock.acquire()
    try:
        if not ser.isOpen():
            logging.error("serial port not available")
            return None
    #    ser.open()
    except IOError, e:
        logging.debug("error open serial port: {0}".format(str(e)))
        return None
    try:
        ser.flushInput() #flush input buffer, discarding all its contents
        ser.flushOutput()#flush output buffer, aborting current output
                        #and discard all that is in buffer
        #write data
        nrOfRetries = 0
        while nrOfRetries<retryMax:
            ser.write(request)
            logging.debug("Request : {0}".format(request))
            time.sleep(0.2)  #give the serial port sometime to receive the data
            #response = ser.readline()
            response = ser.readline()
            logging.debug("response= {0}".format(response))
            if None == response or "" == response:
                nrOfRetries += 1
                continue
            #print("read data: " + response)
            else:
                break
        #ser.close()
    except IOError, e1:
        logging.error("com error : {0}".format(str(e1)))
    # else:
        # logging.debug("cannot open serial port ")
    # if ser.isOpen():
        # ser.close()
    logging.debug("[serial] {0}".format(response))
    #threadLock.release()
    return response

class Furnace:
    def __init__(self, relay, board):
        self.id = relay
        self.board = board
        self.stop()
    def start(self):
         logging.info("[Furnace] starting")
         self.state = 1
         return self.board.startRelay(self.id)
    def stop(self):
        logging.info("[Furnace] stopping")
        self.state = 0
        return self.board.stopRelay(self.id)

class Yard:
    def __init__(self,
                id,
                board,
                lock,
                status_conf):
        self.lock = lock
        self.light = 0
        self.lock.acquire()
        self.id = id
        self.lock.release()
        self.board = board
        self.status_conf = status_conf

    def readLight(self):
        self.lock.acquire()
        raw = self.status_conf["yard"]["light"]
        self.lock.release()
        if raw:
            try:
                light = int(raw)
            except Exception as e:
                light = 0
        else:
            light = 0
        return light
    def start(self):
         logging.info("yard light on")
         return self.board.startRelay(self.id)
    def stop(self):
        logging.info("yard light off")
        return self.board.stopRelay(self.id)
    def storeYard(self):
        self.lock.acquire()
        self.status_conf["yard"]["light"] = self.light
        self.lock.release()
    def refresh(self):
        newLight = self.readLight()
        if newLight != self.light:
            self.light = newLight
            if self.light:
                self.start()
            else:
                self.stop()


def controllerLogic(room, board, prag=0.0):

    #persistantChek(room)

    if (room.get("temperature") + prag) < room.get("reference"):
        if room.get("heater") == True:
            logging.debug("heater already ON")
        else:
            board.startRelay(room["id"])
            board["heater"] = True
    elif (room.get("reference") + prag) <= room.get("temperature"):
        if room.get("heater") == False:
            logging.debug("heater already OFF")
        else:
            board.stopRelay(room["id"])
            board["heater"] = False



def doorControllerLogic(door):
    if door.state == "1":
        print "Open door request"
        door.openDoor()

class Board:
    def __init__(self,com,baud):
        self.port = serial.Serial()
        self.initialized = serialInit(self.port,com,baud)
        #if self.initialized:
        #    self.selfTest()
    def startAll(self):
        for i in range(1,9):
            self.startRelay(i)
    def stopAll(self):
        for i in range(1,9):
            self.stopRelay(i)
    def selfTest(self):
        self.startAll()
        time.sleep(0.5)
        self.stopAll()
    def getStartCode(self,roomId):
        logging.debug("id= {}".format(roomId))
        return startCodeDict[roomId]
    def getStopCode(self,roomId):
        return stopCodeDict[roomId]
    def request(self,request):
        result = serialRequest(self.port,request)
        return result
    def startRelay(self,roomId):
        logging.debug("StartRelay")
        self.request(self.getStartCode(roomId))
        self.request(self.getStartCode(roomId))
        return self.request(self.getStartCode(roomId))
    def stopRelay(self,roomId):
        logging.debug("StopRelay")
        self.request(self.getStopCode(roomId))
        self.request(self.getStopCode(roomId))
        return self.request(self.getStopCode(roomId))

class RelayBoard:
    def __init__(self, lock):
        self.lock = lock
        self.pinout = {1:2,2:3,3:4,4:17,5:27,6:22,7:10,8:9,9:18} # Broadcom
        GPIO.setmode(GPIO.BCM) # Broadcom pin-numbering scheme
        for pin in self.pinout.keys():
            # pin set as output
            GPIO.setup(self.pinout[pin], GPIO.OUT)
            # Initial state for pin:
            GPIO.output(self.pinout[pin], GPIO.HIGH)
        self.selfTest()
        logging.info("board init OK")
        self.initialized = True
    def startAll(self):
        for id in range(8,9):
            self.startRelay(id)
    def stopAll(self):
        for id in range(1,9):
            self.stopRelay(id)
    def selfTest(self):
        self.startAll()
        time.sleep(0.5)
        self.stopAll()
    def startRelay(self,id):
        logging.debug("StartRelay")
        self.lock.acquire()
        GPIO.output(self.pinout[id], GPIO.LOW)
        self.lock.release()
        return True
    def stopRelay(self,id):
        logging.debug("StopRelay")
        self.lock.acquire()
        GPIO.output(self.pinout[id], GPIO.HIGH)
        self.lock.release()
        return True

class Sensor:
    def __init__(self,com,baud):
        logging.info('[%s] initializing sensor with baud: %s', com, baud)
        self.port = serial.Serial()
        self.initialized = serialInit(self.port,com,baud)
        logging.info('[%s][%s] init OK', com, baud)
    def sensorResponseParser(self,rawResponse):
        response = ""
        floatResponse = 99.0
        if rawResponse and rawResponse != "":
            #response = rawResponse[:-5]
            response = rawResponse[1:5]
        if response:
            try:
                floatResponse = float(response)
            except Exception, e1:
                print "error parsing sensor string : " + str(e1)
        return floatResponse
    def humidityParse(self,rawResponse):
        intResponse = 0
        response = rawResponse.strip('\r').strip('%').strip('q')
        if response:
            try:
                intResponse = int(response)
            except Exception, e1:
                logging.error("error parsing sensor string : {} rawResponse: {}".format(str(e1),rawResponse))
            if 'q' in rawResponse:
                #the sepecial case of e.g. q528% response format
                intResponse = intResponse / 10
        return intResponse
    def request(self,request):
        requestString = request + '\r'
        return serialRequest(self.port,requestString)
    def getTemperature(self):
        rawResponse = self.request("T")
        return self.sensorResponseParser(rawResponse)
    def getHumidity(self):
        rawResponse = self.request("H")
        return self.humidityParse(rawResponse)
    def setSlewrate(self,value):
        if not value:
            value = "0"
        rawResponse = self.request("L"+str(value))
        return rawResponse
    def cleanup(self):
        serialCleanup(self.port)

class Room:
    def __init__(self,
                    name,
                    roomId,
                    board,
                    sensor,
                    lock,
                    status_table):
        self.lock = lock
        self.status_table = status_table
        self.id = roomId
        self.name = name
        self.readReference()
        self.temperature = 0.0
        self.humidity = 0
        self.heater = 0
        self.resultMessage = "na"
        self.board = board
        self.sensor = sensor
        self.temperature = self.readTemperature()
        if not self.sensor:
            logging.error("sensor init failure")
            sys.exit(1)
        if not self.board:
            logging.error("board init failure")
            sys.exit(1)

    def readReference(self):
        self.lock.acquire()
        rawReference = self.status_table.get(self.name, {}).get("reference")
        self.lock.release()
        self.reference = float(rawReference) if rawReference else float(DEFAULT_REFERENCE)
        return self.reference
    def readTemperature(self):
        return self.sensor.getTemperature()
    def readHumidity(self):
        return self.sensor.getHumidity()
    def getTemperature(self):
        self.lock.acquire()
        data = self.status_table.get(self.name, {}).get("temperature")
        self.lock.release()
        return data
    def getHumidity(self):
        self.lock.acquire()
        data = self.status_table.get(self.name, {}).get("humidity")
        self.lock.release()
        return data
    def getHeater(self):
        self.lock.acquire()
        data = self.status_table.get(self.name, {}).get("heater")
        self.lock.release()
        return data
    def getName(self):
        return self.name
    def storeTemperature(self):
        self.lock.acquire()
        self.status_table[self.name]["temperature"] = self.temperature
        self.lock.release()
    def storeHumidity(self):
        self.lock.acquire()
        self.status_table[self.name]["humidity"] = self.humidity
        self.lock.release()
    def storeHeater(self):
        self.lock.acquire()
        self.status_table[self.name]["heater"] = self.heater
        self.lock.release()
    def readAndStoreTemperature(self):
        noiseMinAmplitude = 0.1
        noiseMaxAmplitude = 10
        temperature = self.readTemperature()
        if (abs(temperature - self.temperature) > noiseMinAmplitude) and \
            (abs(temperature - self.temperature) < noiseMaxAmplitude):
            self.temperature = temperature
            self.storeTemperature()
        return self.temperature
    def readAndStoreHumidity(self):
        noiseAmplitude = 1
        humidity = self.readHumidity()
        if (abs(humidity - self.humidity) > noiseAmplitude):
            self.humidity = humidity
            self.storeHumidity()
        return humidity
    def startHeater(self):
        logging.info("Heater started")
        if self.board.startRelay(self.id):
            self.heater = 1
            self.storeHeater()
    def stopHeater(self):
        logging.info("Heater stopped")
        if self.board.stopRelay(self.id):
            self.heater = 0
            self.storeHeater()
    def cleanup(self):
        self.sensor.cleanup()

def get_usb_from_serial(serial):
    result = None
    for usb in os.listdir('/sys/bus/usb-serial/devices'):
        cmd = 'udevadm info -a -p /sys/bus/usb-serial/devices/{usb} | grep ATTRS{{serial}}'.format(usb=usb)
        proc = Popen(cmd,
                     stdout=PIPE,
                     stderr=PIPE,
                     shell=True)
        out, err = proc.communicate()
        if out:
            data = out.splitlines()
            if len(data) >=1:
                device_serial = data[0].split('==')[1].strip('"')
                if serial == device_serial:
                    result = usb
                    break
    return result


def temperatureControl(config, board, lock):

    logging.getLogger().setLevel(logging.DEBUG)
    permissive_init = True

    # switch the legacy manual/automatic mode relay to automatic
    board.startRelay(8)

    # temp sensors init. (a sensor is a resource that could be used by multiple rooms)
    for name, data in config.get("rooms").iteritems():
        sensor_data = data.get('sensor')
        if sensor_data:
            # sensor init
            try:

                sensor_data["port"] = get_usb_from_serial(sensor_data.get("id"))
                sensor_data["reader"] = Sensor('/dev/{}'.format(sensor_data["port"]),
                                                config["sensors"][sensor_data.get("type")]["connection"]["baud"])
                logging.debug("[name:%s][id:%s][port:%s][baud:%d] added reader",
                                name,
                                sensor_data.get("id"),
                                sensor_data["port"],
                                config["sensors"][sensor_data.get("type")]["connection"]["baud"])
            except Exception as msg:
                logging.warning('[%s] sensor: %s init fail: %s', name, sensor_data.get("id"), msg)
                if permissive_init:
                    logging.warning('ignoring')
                    continue
                else:
                    break

    # furnace init
    furnace = Furnace(config['power_supplier']['actuator']['id'],
                     board)
    logging.info("%s : %s init ok", name, data.get('type'))

    outTemp = 0.0
    newOutTemp = 0.0
    prevTime = 0.0
    prevDateTime = 0.0

    # main loop
    try:
        logging.info("service started")
        while True:

            heat_request = False
            for name, data in config["rooms"].iteritems():
                logging.debug("\n----------------------------------")
                logging.debug("-- ROOM: %s", name)
                reader = data["sensor"]["reader"]
                logging.debug("Reference=%s", data.get("reference"))
                data["temperature"] = reader.getTemperature()
                data["humidity"] = reader.getHumidity()
                logging.debug("Temperature =%s", data["temperature"])
                logging.debug("Humidity =%s", data["humidity"])
                logging.debug("Heater = %s", data.get("heater"))
                controllerLogic(data, board)
                if data.get("heater"):
                    heat_request = True
            if heat_request:
                furnace.start()
            else:
                furnace.stop()

    except ShutdownException: # If CTRL+C is pressed, exit cleanly:
        logging.info("preparing to exit")
        GPIO.cleanup() # cleanup all GPIO

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(relativeCreated)6d %(threadName)s %(message)s')
    manager = Manager()
    # create file handler which logs even debug messages
    fh = logging.FileHandler('deo.log')
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logging.getLogger().addHandler(fh)
    logging.getLogger().addHandler(ch)

    status_table = manager.dict()
    status_lock = Lock()
    gpio_lock = Lock()
    roomList = []
    roomDict = {}
    pid = os.getpid()
    logging.info("starting service on pid{}".format(pid))

    config_file_path = "status.json"

    try:
        with open(config_file_path) as conf_handler:
            config = json.load(conf_handler)
    except Exception as msg:
        logging.error('config load error: %s', msg)
        sys.exit(1)

    board = RelayBoard(gpio_lock)
    if not board.initialized:
        logging.error("board init fail")
        sys.exit(1)

    signal.signal(signal.SIGUSR1, signal_handler)


    logging.info("starting workers")
    measurements = Process(target=temperatureControl, args=(config, board, status_lock))
    # appliances = Process(target=YardGateControl, args=(config, board, status_lock))

    # appliances.start()
    measurements.start()

    # appliances.join()
    measurements.join()

    exit(0)

# -----------------------------------------------------------
# -----------------------------------------------------------
# -----------------------------------------------------------

