#!/usr/bin/python
import RPi.GPIO as GPIO
import serial, time
import os
import sys
import logging
import logging.handlers
import threading
import signal
from multiprocessing import Process, Lock, Pipe
from threading import Thread
from subprocess import Popen, PIPE
import rpyc
from rpyc.utils.server import ThreadedServer
import json
from collections import defaultdict
import psutil

# 3rd party modules
import sysv_ipc

BUCATARIE   = 1
LIVING      = 2
SENSOR      = 0
TEMPERATURE = 1
REFERENCE   = 2
ID          = 3
ROOM_ID     = 0

config_file_path = "status.json"

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

def main_signal_handler(signum, stack):
    logging.info("received signal {}".format(signum))
    try:
        parent = psutil.Process(os.getpid())
    except psutil.NoSuchProcess:
        logging.error("main stop signal handler: parent pid error")
    else:
        children = parent.children(recursive=True)
        for process in children:
            process.send_signal(signal.SIGUSR2)

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
    except IOError as msg:
        logging.error("error open serial port: %s", msg)
    if ser.isOpen():

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
    except IOError as msg:
        logging.debug("error open serial port: %s", msg)
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
    except IOError as msg:
        logging.error("com error : %s", msg)
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
        self.active = None
        self.stop()

        # __active = False if GPIO.input(self.board.pinout[self.id]) else True
    def start(self):
        if not self.active:
            self.board.startRelay(self.id)
            logging.info("[Furnace] starting")
            self.active = True

    def stop(self):
        if self.active is True or self.active is None:
            self.board.stopRelay(self.id)
            logging.info("[Furnace] stopping")
            self.active = False


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

    # logging.debug("room: %s", json.dumps(room, indent=4))

    reference = room["control"]["presets"]["day"]

    if (room.get("temperature") + prag) < reference:
        if room.get("heater") is True:
            logging.debug("heater already ON")
        else:
            board.startRelay(room["actuator"]["id"])
            room["heater"] = True
            logging.info("[temperature control] heater ON")
    else:
        if room.get("heater") is False:
            logging.debug("heater already OFF")
        else:
            board.stopRelay(room["actuator"]["id"])
            room["heater"] = False
            logging.info("[temperature control] heater OFF")


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


def temperatureControl(config, board, status, lock):

    logging.info("[temperature control] started")
    loop_status = defaultdict(lambda: defaultdict(lambda: None))
    permissive_init = True

    # switch the legacy manual/automatic mode relay to automatic
    board.startRelay(8)
    sensors = {}

    logging.info("sensors init..")
    for id, data in config.get("sensors").iteritems():
        port = get_usb_from_serial(id)
        try:
            sensors[id] = Sensor('/dev/{}'.format(port),
                                 config["sensor_lib"][data.get("type")]["connection"]["baud"])
            logging.info("[id:%s][port:%s][baud:%d] reader initialized",
                         id,
                         port,
                         config["sensor_lib"][data.get("type")]["connection"]["baud"])
        except Exception as msg:
            logging.warning('[temperature control][%s] sensor init fail: %s', id, msg)
            if permissive_init:
                logging.warning('[temperature control][%s] ignoring', id)
                continue
            else:
                logging.error("[temperature control] sensor init fail, aborting..")
                sys.exit(1)

    # temp sensors init. (a sensor is a resource that could be used by multiple rooms)
    # logging.info("room init..")
    # for name, data in config.get("rooms").iteritems():
    #     # attach sensor reader
    #     data["sensor"]["reader"] = sensors.get(data["sensor"]["id"])
    #     logging.info("[%s] attached sensor: %s", name, data["sensor"]["id"])
    #     # set reference
    #     data["reference"] = data["control"]["presets"]["day"]
    #     logging.info("[%s][reference] set preset day value: %d", name, data["reference"])

    # furnace init
    furnace = Furnace(config['power_supplier']['actuator']['id'],
                      board)

    # main loop
    try:
        logging.info("service started")
        while True:
            heat_request = False
            for name, data in config["rooms"].iteritems():
                logging.debug("\n----------------------------------")
                logging.debug("-- ROOM: %s", name)
                try:
                    sensor_type = data["sensor"]["type"]
                    if sensor_type == "watchport":
                        reader = sensors.get(data["sensor"]["id"])
                        data["temperature"] = reader.getTemperature()
                        data["humidity"] = reader.getHumidity()
                    elif sensor_type == "wifi":
                        sensor = rpyc.connect(host = data["sensor"]["ip"], port = data["sensor"]["port"])
                        reader = sensor.root
                        data["humidity"], data["temperature"] = reader.read()
                        sensor.close()
                    if not reader:
                        # skip room with no reader
                        logging.debug("skipping since no reader attached")
                        continue

                    logging.debug("Temperature =%s", data["temperature"])
                    logging.debug("Humidity =%s", data["humidity"])

                    logging.debug("Heater = %s", data.get("heater"))
                    controllerLogic(data, board)
                    if data.get("heater"):
                        heat_request = True
                        logging.info("[%s] Heat request.. T:%s <> R:%s",
                                     name,
                                     data["temperature"],
                                     data["control"]["presets"]["day"])
                    try:
                        loop_status[name]["temperature"] = round(data["temperature"], 1)
                        loop_status[name]["humidity"] = round(data["humidity"], 1)
                    except Exception as msg:
                        logging.warning("[%s] data storing: %s, using default values", name, msg)
                        loop_status[name]["temperature"] = data["temperature"]
                        loop_status[name]["humidity"] = data["humidity"]

                    loop_status[name]["heater"] = data["heater"]
                    loop_status[name]["reference"] = data["control"]["presets"]["day"]
                except Exception as msg:
                    logging.error("[%s] sensor read failed: %s", name, msg)

            if heat_request:
                furnace.start()
            else:
                furnace.stop()
            loop_status["power_supplier"]["active"] = furnace.active
            if loop_status != status:
                logging.info("[temperature control] updating status..")
            lock.acquire()
            status.update(loop_status)
            lock.release()
            # try:
            #     with open("measurements.json", "w") as fd:
            #         json.dump(status, fd, indent=4)
            # except Exception as msg:
            #     logging.error("failed to write status data")

    except ShutdownException:  # If CTRL+C is pressed, exit cleanly:
        logging.info("[temperature control] preparing to exit")
        GPIO.cleanup()  # cleanup all GPIO

class DispatcherService(rpyc.Service):

    def __init__(self, measurements_table):
        self.measurements_table = measurements_table

    def exposed_read(self):
        try:
            snd_data = json.dumps(self.measurements_table)
        except Exception as msg:
            logging.error("[dispatcher] json conversion error %s", msg)
            snd_data = "{}"
        finally:
            lock.release()


def dispatcher_unfinished(measurements_table, mq, lock):
    # Create the message queue.

    error_counter = 0
    while True:

        try:
            rcv_data = mq.recv()
            logging.debug("read_request:%s", rcv_data)
            if rcv_data == "read":
                lock.acquire()
                try:
                    snd_data = json.dumps(measurements_table)
                except Exception as msg:
                    logging.error("[dispatcher] json conversion error %s", msg)
                    snd_data = "{}"
                finally:
                    lock.release()
                mq.send(snd_data, type=2)
        except (KeyboardInterrupt, SystemExit, ShutdownException):
            break
        except Exception as msg:
            logging.error("[dispatcher] %s", msg)
            error_counter += 1
            if error_counter > 100:
                logging.error("[dispatcher] too many queue reading failures")

                break
        else:
            error_counter = 0

def dispatcher(measurements_table, lock):
    # Create the message queue.
    logging.info("[dispatcher] starting msg dispatcher thread")
    error_counter = 0
    INIT = 0
    OPERATING = 1
    ERROR = 2
    CLOSING = 3
    state = INIT
    create_retry_max = 3
    create_retry = 0
    err_msg = None
    while True:
        if state == INIT:
            logging.info("[dispatcher][INIT] clearing ALL message queues")
            os.system("ipcrm --all=msg")
            try:
                mq = sysv_ipc.MessageQueue(42, sysv_ipc.IPC_CREX, 0777)
            except Exception as e:
                create_retry += 1
                logging.error("[dispatcher][INIT] cannot create message queue: %s", e)
                logging.error("[dispatcher][INIT] measurements will not be available")
                if create_retry > create_retry_max:
                    state = CLOSING
            else:
                logging.info("[dispatcher] successfully created msg queue %s", mq.id)
                create_retry = 0
                state = OPERATING
        elif state == OPERATING:
            try:
                rcv_msg, _ = mq.receive(type=1)
                rcv_data = rcv_msg.decode()
                logging.debug("read_request:%s", rcv_data)
                lock.acquire()
                try:
                    snd_data = json.dumps(measurements_table)
                except Exception as msg:
                    logging.error("[dispatcher] json conversion error %s", msg)
                    snd_data = "{}"
                lock.release()
                snd_msg = snd_data.encode()
                mq.send(snd_msg, type=2)
            except (KeyboardInterrupt, SystemExit, ShutdownException):
                state = CLOSING
            except Exception as msg:
                err_msg = str(msg)
                state = ERROR
            else:
                error_counter = 0
        elif state == ERROR:
            if err_msg and "The queue no longer exists" in err_msg:
                logging.warning("[dispatcher][ERROR] queue failed, recreating queue")
                state = INIT
            else:
                error_counter += 1
                logging.error("[dispatcher][ERROR][%d] %s", error_counter, err_msg)
            if error_counter > 100:
                logging.error("[dispatcher][ERROR] too many queue reading failures")
                state = CLOSING
        elif state == CLOSING:
            logging.info("[dispatcher][CLOSING] exiting, clearing message queue")
            if mq:
                try:
                    mq.remove()
                except:
                    pass
            os.system("ipcrm --all=msg")
            break


def update_config(config_file_path, config):
    with open(config_file_path) as conf_handler:
        config.update(json.load(conf_handler))


def config_monitor(conf_lock, config_file_path, config, refresh_interval=5):
    last_mtime = 0
    last_check_time = time.time()
    logging.info("[conf monitor] started")
    while True:
        try:
            if time.time() - last_check_time > refresh_interval:
                current_mtime = os.path.getmtime(config_file_path)
                if os.path.getmtime(config_file_path) != last_mtime:
                    logging.info("[conf monitor] update detected, time to reload")
                    last_mtime = current_mtime
                    with conf_lock:
                        update_config(config_file_path, config)
                        logging.info("[conf monitor] reloaded")

            time.sleep(1)
        except (KeyboardInterrupt, SystemExit, ShutdownException) as msg:
            logging.info("[conf monitor] shutting down %s", msg)
            break
        except Exception as msg:
            logging.error("[conf monitor] %s", msg)


def heat_solution(config_file_path, board, lock):

    signal.signal(signal.SIGUSR2, signal_handler)
    logging.getLogger().setLevel(logging.INFO)
    logging.info("starting heating solution process")

    config_lock = threading.Lock()
    config = {}
    logging.info("[heat_solution] initial config loading..")
    update_config(config_file_path, config)
    logging.info("[heat_solution] loaded")

    measurements_table = defaultdict(lambda: defaultdict(lambda: None))

    monitoring = Thread(target=config_monitor, args=(config_lock, config_file_path, config))
    heating = Thread(target=temperatureControl, args=(config, board, measurements_table, lock,))
    cmd_listener = Thread(target=dispatcher, args=(measurements_table, lock,))

    heating.start()
    cmd_listener.start()
    monitoring.start()

    heating.join()
    cmd_listener.join()
    monitoring.join()


class ConfiguratorService(rpyc.Service):

    @staticmethod
    def add(a, b):
        return a + b

    @staticmethod
    def substract(a, b):
        return a - b

    @staticmethod
    def alter(room, operation):
        with open(config_file_path) as fd:
            data = json.load(fd)
            value = data["rooms"][room]["control"]["presets"]["day"]
            data["rooms"][room]["control"]["presets"]["day"] = operation(value, 0.5)
        try:
            with open(config_file_path, "w") as fd:
                json.dump(data, fd, indent=4)
        except Exception as msg:
            with open("config_bkp.json", "w") as fd:
                json.dump(data, fd)
                logging.error("failed to save json data, creating bkp: config_bkp.json", msg)
        else:
            logging.info("[%s] new val set %s ", data["rooms"][room]["control"]["presets"]["day"])

    def exposed_increase(self, room):
        self.alter(room, self.add)

    def exposed_decrease(self, room):
        self.alter(room, self.substract)


def configurator():
    logging.basicConfig(level=logging.INFO)
    server = ThreadedServer(ConfiguratorService, hostname="0.0.0.0", port=18861)
    logging.info("configurator service starting")
    server.start()

if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO, format='%(relativeCreated)6d %(threadName)s %(message)s')
    # manager = Manager()
    # create file handler which logs even debug messages
    fh = logging.handlers.RotatingFileHandler("deo.log", maxBytes=1048576)
    fh.setLevel(logging.INFO)
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

    # status_table = manager.dict()
    status_lock = Lock()
    gpio_lock = Lock()
    roomList = []
    roomDict = {}
    pid = os.getpid()
    logging.info("starting service on pid{}".format(pid))

    board = RelayBoard(gpio_lock)
    if not board.initialized:
        logging.error("board init fail")
        sys.exit(1)

    signal.signal(signal.SIGUSR1, main_signal_handler)


    logging.info("starting workers")
    measurements = Process(target=heat_solution, args=(config_file_path, board, status_lock))
    # appliances = Process(target=YardGateControl, args=(config, board, status_lock))
    configuration = Process(target=configurator)

    # appliances.start()
    measurements.start()
    configuration.start()
    logging.info("all services started")

    # appliances.join()
    measurements.join()
    configuration.join()

    exit(0)

# -----------------------------------------------------------
# -----------------------------------------------------------
# -----------------------------------------------------------
