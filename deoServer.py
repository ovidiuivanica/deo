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
startCodeDict = {1:"a",2:"b",3:"c",4:"d",5:"e",6:"f",7:"g",8:"h"}
stopCodeDict = {1:"i",2:"j",3:"k",4:"l",5:"m",6:"n",7:"o",8:"p"}


DICT_PWD = 0
DICT_ROLE = 1
DICT_BEGIN_DATE = 2
DICT_END_DATE = 3

userDict = {
            #admin section
            "evimic":["","admin"],
            "relu":["","admin"],
            "octavian":["","admin"],
            #thursday evening club section 
            "dani":["","club"],
            "tibi":["","club"],
            "andrei":["","club"],
            #family section 
            "simona":["","family"],
            "stefan":["","family"],
            "vali":["","family"],
            "fibia":["","family"],
            #friend section
            "filip":["","friend",[6,11,2015],[7,11,2015]],
            }

homeCoordinates = {"Latitude":44.47816,"Longitude":26.034602}

homeLat = 44.47816
homeLong = 26.034602

# work location coordinates: 44.413919, 26.1051352

acceptedLatDiff = 0.01
acceptedLongDiff = 0.01

class ShutdownException(Exception):
    def __init__(self, message):
        super(ShutdownException, self).__init__(message)

def signal_handler(signum, stack):
    logging.logINFO("received signal {}".format(signum))
    raise ShutdownException("shutdown") 

   
def getPersistantData(objectId,objectType,parameterName,diskFile=os.path.join(BASE_PATH,"status.xml")):
    # save information on disk 
    returnValue = None
    try:
        inFile = open(diskFile, 'r')
        data = inFile.read()
        inFile.close()
        logging.debug("xml file open OK")
        #print data
    except Exception, e:
        logging.debug("error open/close when reading persisting file: " + str(e))
        return False
    try:
        xmlContent = minidom.parseString(data)
    except Exception, e:
        logging.logERROR("cannot parse xml: " + str(e))
        return returnValue
    house = xmlContent.documentElement
    rooms = house.getElementsByTagName(objectType)
    for room in rooms:
        if str(objectId) == room.getAttribute("id"):
            parameter = room.getElementsByTagName(parameterName) 
            returnValue = parameter[0].childNodes[0].data
            break
    #cleanup
    house.unlink()
    #xmlContent.unlink()
    del(house)
    del(xmlContent) 
            
    logging.debug("returnValue={}".format(returnValue))
    return returnValue   
def getPersistantObjectAttribute(objectType,attributeName,diskFile=os.path.join(BASE_PATH,"status.xml")):
    # save information on disk 
    returnValue = None
    try:
        inFile = open(diskFile, 'r')
        data = inFile.read()
        inFile.close()
        logging.debug("xml file open OK")
        #print data
    except Exception, e:
        logging.error("error open/close when reading persisting file: " + str(e))
        return False
    try:
        xmlContent = minidom.parseString(data)
    except Exception, e:
        logging.error("cannot parse xml: " + str(e))
        return returnValue
    house = xmlContent.documentElement
    returnValue = house.getElementsByTagName(objectType)[0].getAttribute(attributeName) 
    
    #cleanup
    house.unlink()
    #xmlContent.unlink()
    del(house)
    del(xmlContent) 
    
    logging.debug("returnValue={}".format(returnValue))
    return returnValue   
def setPersistantData(objectId,objectType,parameter,value="initValue",diskFile=os.path.join(BASE_PATH,"status.xml")):
    # save information on disk 
    
    try:
        inFile = open(diskFile, 'r')
        data = inFile.read()
        inFile.close()
        logging.debug("opened file {0}".format(diskFile))
    except Exception, e:
        logging.debug("error open/close when reading persisting file: " + str(e))
        return False

    logging.debug("setting id{0}: {1}-{2}-{3}".format(objectId,objectType,parameter,value))
    try:
        xmlContent = minidom.parseString(data)
    except Exception, e:
        logging.error("cannot parse xml: " + str(e))
        return False
    house = xmlContent.documentElement
    objects = house.getElementsByTagName(objectType)
    for object in objects:
        if str(objectId) == object.getAttribute("id"):
            item = object.getElementsByTagName(parameter)
            #parameter.getElementsByTagName("value")[0].childNodes[0].data = setValue
            item[0].childNodes[0].data = value
            break
    data = xmlContent.toxml()
    
    #cleanup
    house.unlink()
    #xmlContent.unlink()
    del(house)
    del(xmlContent) 
    
    try:
        outFile = open(diskFile, 'w')
        outFile.write(data)
        outFile.close()
    except Exception, e:
        logging.debug("error open/close when writing to persisting file: " + str(e))
        return False
    return True    
    
def setPersistantData2(objectType,parameter,value,diskFile=os.path.join(BASE_PATH,"status.xml")):
    # save information on disk 
    
    try:
        inFile = open(diskFile, 'r')
        data = inFile.read()
        inFile.close()
        logging.debug("opened file {0}".format(diskFile))
    except Exception, e:
        logging.debug("error open/close when reading persisting file: " + str(e))
        return False

    logging.debug("setting: {0}-{1}-{2}".format(objectType,parameter,value))
    try:
        xmlContent = minidom.parseString(data)
    except Exception, e:
        logging.error("cannot parse xml: " + str(e))
        return False
    house = xmlContent.documentElement
    objects = house.getElementsByTagName(objectType)
    for object in objects:
		item = object.getElementsByTagName(parameter)
		item[0].childNodes[0].data = value
		break
    data = xmlContent.toxml()
    
    #cleanup
    house.unlink()
    #xmlContent.unlink()
    del(house)
    del(xmlContent) 
    
    try:
        outFile = open(diskFile, 'w')
        outFile.write(data)
        outFile.close()
    except Exception, e:
        logging.debug("error open/close when writing to persisting file: " + str(e))
        return False
    return True  

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
        logging.logINFO("closed serial port")

def readFile(filePath):
    line = "notAvailable"
    theFile = open(filePath,"r")
    if not theFile:
        logging.debug("could not open file")
        return line
    else:
        line = theFile.readline()
    theFile.close()
    return line
        
        
def writeFile(filePath,text):
    logging.debug("store: {0}".format(text))
    retCode = 0
    theFile = open(filePath,"w")
    if not file:
        retCode = 0
    else:
        theFile.write(text)
        retCode = 1 
    theFile.close()
    return retCode

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
    def __init__(self,board,rooms):
        self.id = int(getPersistantObjectAttribute("furnace","id"))
        self.board = board
        self.stop()
        self.rooms = rooms
        self.drState = 0
    def readDrState(self):
        raw = getPersistantData(self.id,"furnace","drState")
        if raw:
            try:
                self.drState = int(raw)
            except Exception as e:
                self.drState = 0
        else:
            self.drState = 0
        return self.drState
    def start(self):
         logging.info("starting furnace")
         self.storeFurnace()
         self.state = 1
         return self.board.startRelay(self.id)
    def stop(self):
        logging.info("stopping furnace")
        self.state = 0
        self.storeFurnace()
        return self.board.stopRelay(self.id)
    def storeFurnace(self):
        setPersistantData(self.id,"furnace","state",self.state)
    def refresh(self):
        newState = 0
        for room in self.rooms:
            logging.debug("{}{}".format(room.id,room.heater))
            if room.heater:
                newState = 1
                break        
        
        self.readDrState()
        
        if not newState and self.drState:
            newState = 1
            logging.debug("directRequest")               
        
        if newState != self.state:
            self.state = newState 
            if self.state:
                self.start()
            else:
                self.stop()
                
                
class Yard:
    def __init__(self,board):
        self.light = 0
        self.id = int(getPersistantObjectAttribute("yard","id"))
        self.board = board
    def readLight(self):
        raw = getPersistantData(self.id,"yard","light")
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
        setPersistantData(self.id,"yard","light",self.light)
    def refresh(self):
        newLight = self.readLight()
        if newLight != self.light:
            self.light = newLight 
            if self.light:
                self.start()
            else:
                self.stop()
    
def persistantChek(room):
    heater = getPersistantData(room.id,"room","heater")
    temperature = getPersistantData(room.id,"room","temperature")
    humidity = getPersistantData(room.id,"room","humidity")
    reference = getPersistantData(room.id,"room","reference")
    
    if (heater != room.heater):
        room.storeHeater()
    if (temperature != room.temperature):
        room.storeTemperature()
    if (humidity != room.humidity):
        room.storeHumidity()
    # this has to go the other way round, since the xml has the input
    if (reference != room.reference):
        room.reference = reference

    
    
def controllerLogic(room,furnace,prag=0.3):
    
    #persistantChek(room)
    
    if (room.temperature + prag) < room.reference:
        if room.heater == 1:
            logging.debug("heater already ON")
        else:
            room.startHeater()
    elif (room.reference + prag) < room.temperature: 
        if room.heater == 0:
            logging.debug("heater already OFF")
        else:
            room.stopHeater()
    furnace.refresh()
    
            
def controllerLogic_basic(room,furnace,prag=0.3):
    if (room.temperature + prag) < room.reference:
        furnace.update(room.id,1)
        if room.heater == 1:
            logging.debug("heater already ON")
        else:
            room.startHeater()
            furnace.refresh()
    elif (room.reference + prag) < room.temperature: 
        furnace.update(room.id,0)
        if room.heater == 0:
            logging.debug("heater already OFF")
        else:
            room.stopHeater()
            furnace.refresh()
    
        
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
        #threadLock.acquire(1)
        result = serialRequest(self.port,request)
        #threadLock.release()
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
    def __init__(self):
        self.pinout = {1:2,2:3,3:4,4:17,5:27,6:22,7:10,8:9} # Broadcom 
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
        GPIO.output(self.pinout[id], GPIO.LOW)
        return True
    def stopRelay(self,id):
        logging.debug("StopRelay")
        GPIO.output(self.pinout[id], GPIO.HIGH)
        return True
        
class DummyBoard:
    def __init__(self):
        pass
    def getStartCode(self,roomId):
        logging.debug("id= {}".format(roomId))
        return startCodeDict[roomId]
    def getStopCode(self,roomId):
        return stopCodeDict[roomId]
    def request(self,request):
        return "OK"
    def startRelay(self,roomId):
        logging.debug("StartRelay")
        return 1
    def stopRelay(self,roomId):
        logging.debug("StopRelay")
        return 1


class Sensor:
    def __init__(self,com,baud):
        self.port = serial.Serial()
        self.initialized = serialInit(self.port,com,baud)
    def sensorResponseParser(self,rawResponse):
        response = ""
        floatResponse = 0.0
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
    def __init__(self,roomId,board,sensor):
        self.id = roomId
        self.name = self.getName()
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
        self.resetRoom()
    def resetRoom(self):
        setPersistantData(self.id,"room","heater",self.heater)
        setPersistantData(self.id,"room","temperature",self.temperature)
        setPersistantData(self.id,"room","humidity",self.humidity)
        self.stopHeater()
    def readReference(self):
        rawReference = getPersistantData(self.id,"room","reference")
        if rawReference:
            self.reference = float(rawReference)
        else:
            self.reference = float(DEFAULT_REFERENCE)
        return self.reference
    def setReference(self,value):
        retCode = 0
        setPersistantData(self.id,"room","reference",value)
        if retCode:
            self.reference = value
            self.resultMessage = "OK"
        else: 
            self.resultMessage = "KO!"
        return retCode
    def readTemperature(self):
        temperature = self.sensor.getTemperature()
        return temperature
    def readHumidity(self):
        humidity = self.sensor.getHumidity()
        return humidity
    def getTemperature(self):
        return getPersistantData(self.id,"room","name")
    def getTemperature(self):
        return getPersistantData(self.id,"room","temperature")
    def getHumidity(self):
        return getPersistantData(self.id,"room","humidity")
    def getHeater(self):
        return getPersistantData(self.id,"room","heater")
    def getName(self):
        return getPersistantData(self.id,"room","name")
    def storeTemperature(self):
        setPersistantData(self.id,"room","temperature",self.temperature)
    def storeHumidity(self):
        setPersistantData(self.id,"room","humidity",self.humidity)
    def storeHeater(self):
        setPersistantData(self.id,"room","heater",self.heater)
    def readAndStoreTemperature(self):
        noiseMinAmplitude = 0.1
        noiseMaxAmplitude = 2
        temperature = self.readTemperature()
        if (abs(temperature - self.temperature) > noiseMinAmplitude) and (abs(temperature - self.temperature) < noiseMaxAmplitude):
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

class Door:
    def __init__(self,doorId,board):
        self.doorId = doorId
        self.relay = 5
        self.state = 0
        self.resultMessage = "na"
        self.board = board
    def setState(self,value):
        result = setPersistantData(self.doorId,"door","state",value)
        self.state = value
        return result
    def setStateWithValidation(self,value):
        validation = False
        result = setPersistantData(self.doorId,"door","state",value)
        self.state = value
        temp = getPersistantData(self.doorId,"door","state")
        logging.info("written : {}".format(temp))
        if temp == value:
            validation = True
        return validation
    def getState(self):
        self.state = getPersistantData(self.doorId,"door","state")
        logging.debug("door internal state = {}".format(self.state))
        return self.state

    def openDoor(self,sleepTime=1):
        logging.info("Door open request")
        if self.board.startRelay(self.relay):
            logging.info("relay on")
        time.sleep(sleepTime)
        if self.board.stopRelay(self.relay):
            logging.info("relay off")


def serviceMode(board,sensor1,sensor2,sensor3):
    #sensor1 = Sensor("/dev/ttyUSB1",9600)
    #print "Slew rate configuration:"
    #print sensor1.setSlewrate(7)
    #board.startRelay(5)
    #board.stopRelay(2)
    #board.stopRelay(5)
    #board.startRelay(3)
    #time.sleep(2)
    #board.stopRelay(1)
    #time.sleep(2)
    #board.startRelay(1)
    #board.stopRelay(5)
    #print sensor1.getTemperature()
    #print sensor2.getTemperature()
    print sensor3.getTemperature()
        
def temperatureControl(board,sensor1,sensor2,sensor3):

    living = Room(1,"living",board,sensor2)
    dormitor = Room(2,"dormitor",board,sensor1)
    bucatarie = Room(3,"bucatarie",board,sensor3)
    roomList = [living,dormitor,bucatarie]
    furnace = Furnace(board,2)
    currentOpMode = ""


    while True:
        operationMode = getPersistantData(900,"operation","mode")
        if currentOpMode != operationMode:
            currentOpMode = operationMode
            if operationMode == "manual":
                logging.debug("switching to maual..")
                board.stopRelay(5)
            else:
                logging.debug("switching to auto..")
                board.startRelay(5)
                
        if currentOpMode == "manual":
            time.sleep(1)
            logging.debug("manual operation ...");
            continue

        for room in roomList:
            logging.info("\n----------------------------------")
            logging.info("-- ROOM: {}".format(room.name))
            logging.info("Reference= {0}".format(room.readReference()))
            logging.info("Temperature = {0}".format(room.readAndStoreTemperature()))
            logging.info("Heater = {0}".format(room.heater))
            #logging.info("Humidity = {0}".format(room.readAndStoreHumidity()))
            controllerLogic(room,furnace) 
        time.sleep(1)
        
def temperatureAndGateControl(board,roomList):
    furnace = Furnace(board,roomList)
    yard = Yard(board)
    currentOpMode = ""
    door1 = Door(1000,board)
    outTemp = 0.0
    newOutTemp = 0.0
    prevTime = 0.0
    prevDateTime = 0.0
    
    try:
        logging.info("service started")
        while True:
            door1.getState()
            logging.debug("Gate = {0}".format(door1.state))
            if door1.state == "1":
                door1.openDoor()
                door1.setStateWithValidation("0")
            # limit outisde temp request to one per hour minutes
            
            timeNow = time.time()
            
            # loop refresh time
            if timeNow - prevDateTime > 60.0:
                prevDateTime = timeNow
                dateNow = datetime.now()
                setPersistantData(20,"refresh","time",int(prevDateTime))

            #yard light
            yard.refresh()
            
            operationMode = getPersistantData(900,"operation","mode")
#            if currentOpMode != operationMode:
#                currentOpMode = operationMode
            if operationMode == "manual":
                logging.debug("switching to maual..")
                board.stopRelay(8)
            elif operationMode == "automat":
                logging.debug("switching to auto..")
                board.startRelay(8)
            else:
                logging.error("unknown operation mode, choosing auto")
                board.startRelay(8)
                    
            if currentOpMode == "manual":
                time.sleep(1)
                logging.debug("manual operation ...");
                continue

            for room in roomList:
                logging.debug("\n----------------------------------")
                logging.debug("-- ROOM: {}".format(room.name))
                logging.debug("Reference= {0}".format(room.readReference()))
                logging.debug("Temperature = {0}".format(room.readAndStoreTemperature()))
                logging.debug("Heater = {0}".format(room.heater))
                logging.debug("Humidity = {0}".format(room.readAndStoreHumidity()))
                controllerLogic(room,furnace) 
            
            #time.sleep(1)
    except ShutdownException: # If CTRL+C is pressed, exit cleanly:
        logging.info("preparing to exit")
        GPIO.cleanup() # cleanup all GPIO
        for room in roomList:
            room.cleanup()
def validateUserLocation(userLat,userLong):
    validate = False
    latDiff = abs(userLat - homeLat)
    longDiff = abs(userLong - homeLong)
    #print "latDiff  ={} <br />".format(latDiff)
    #print "longDiff ={} <br />".format(longDiff)
    if  latDiff < acceptedLatDiff and  longDiff < acceptedLongDiff:
        validate = True
    return validate

def validateUserTime(userOkDay,userOkHour):
    validate = False
    now = datetime.now()
    if now.weekday() == userOkDay and now.hour >= userOkHour:
        validate = True
    return validate

def validateUserDate(start,stop):
    validate = False
    today = date.today()
    if today.year >= start[2] and today.year <= stop[2]: 
        if today.month >= start[1] and today.month <= stop[1]:
            if today.day >= start[0] and today.day <=stop[0]:
                validate = True
    
    return validate


def gateControl(board):
    door1 = Door(4,board)
    doorList = [door1]
    openDoorFlag = False
    
    # Create the message queue.
    try:
        mq = sysv_ipc.MessageQueue(42, sysv_ipc.IPC_CREX, 0777)
    except Exception, e:
        logging.error("cannot create message queue: " + str(e))
        return

    whatISent = ""
    while True:
        logging.debug("waiting to receive..")
        s, _ = mq.receive()
        s = s.decode()
        parts = s.split("--")
        logging.debug("received: {}".format(s))
        if s == whatISent:
            s = s.encode()
            logging.debug("message not consumed by client, sending back %s" % s)
            mq.send(s)
        elif parts[0] == "openGate":
            logging.debug("opening gate")
            returnString = ""
            # ----------------------
            user = parts[1]
            latitude = float(parts[2])
            longitude = float(parts[3])
            if user in userDict.keys():
                keyValue = userDict[user]
                if keyValue[DICT_ROLE] == "admin":
                    openDoorFlag = True
                if keyValue[DICT_ROLE] == "family":
                    if validateUserLocation(latitude,longitude):
                        openDoorFlag = True
                    else:
                        returnString = "<h1>action restricted from this location</h1>"
                if keyValue[DICT_ROLE] == "club":
                    if validateUserTime(userOkDay=3,userOkHour=20):
                        if validateUserLocation(latitude,longitude):
                            openDoorFlag = True
                        else:
                            returnString = "<h1>action restricted from this location</h1>"
                    else: 
                        returnString = "<h1>action restricted at this time</h1>"
                if keyValue[DICT_ROLE] == "friend":
                    if validateUserDate(start=keyValue[DICT_BEGIN_DATE],stop=keyValue[DICT_END_DATE]):
                        openDoorFlag = True
                    else: 
                        returnString = "<h1>action restricted at this time</h1>"
            else:
                returnString = "<h1>access restricted</h1>"
            # ----------------------
            if openDoorFlag == True:
                door1.openDoor()
                status = "openOK"
                openDoorFlag = False
            else:
                status = "openKO"
            s = "{}--{}".format(status,returnString)
            whatISent = s
            s = s.encode()
            logging.debug("Sending %s" % s)
            mq.send(s)
        else:
            logging.error("unrecognized message")

    logging.debug("Destroying the message queue.")
    mq.remove()
    
    
class Gate(threading.Thread):
    def __init__(self, threadID, board):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.board = board
    def run(self):
        print "Starting {}".format(self.threadID)
        # Get lock to synchronize threads
        gateControl(self.board)
        
        
class Heating(threading.Thread):
    def __init__(self, threadID, board8, sensor1,sensor2,sensor3):
        threading.Thread.__init__(self)
        self.threadID = threadID
    def run(self):
        print "Starting {}".format(self.threadID)
        # Get lock to synchronize threads
        temperatureControl(board8,sensor1,sensor2,sensor3)

def parseConfig(roomDict,diskFile=os.path.join(BASE_PATH,"status.xml")):
    # save information on disk 
    returnValue = None
    try:
        inFile = open(diskFile, 'r')
        data = inFile.read()
        inFile.close()
        logging.debug("xml file open OK")
        #print data
    except Exception, e:
        logging.debug("error open/close when reading persisting file: " + str(e))
        return False
    try:
        xmlContent = minidom.parseString(data)
    except Exception, e:
        logging.error("cannot parse xml: " + str(e))
        return returnValue
    house = xmlContent.documentElement
    rooms = house.getElementsByTagName("room")
    for room in rooms:
        parameter = room.getElementsByTagName("name") 
        name = parameter[0].childNodes[0].data
        parameter = room.getElementsByTagName("sensor") 
        sensor = parameter[0].childNodes[0].data
        id = room.getAttribute("id")
        roomDict[name] = {'id':id,'sensor':sensor}
        
    #cleanup
    house.unlink()
    #xmlContent.unlink()
    del(house)
    del(xmlContent) 
            
    logging.debug("returnValue={}".format(returnValue))
    return returnValue           
        

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(relativeCreated)6d %(threadName)s %(message)s')
    
    
    #threadLock = threading.Lock()
    roomList = []
    roomDict = {}
    pid = os.getpid()
    logging.info("starting service on pid{}".format(pid))
    result = setPersistantData("1100","pid","value",pid)
    board = RelayBoard()
    if not board.initialized:
        logging.error("board init fail")
        sys.exit(2)
    parseConfig(roomDict)
    
    logging.info("Board init stus:{}".format(board.initialized))
    for roomName in roomDict.keys():
        
        id = int(roomDict[roomName]['id'])
        serialAddr = roomDict[roomName]['sensor']
        logging.info("preparing room:{} id:{} serialAddress:{}".format(roomName,id,serialAddr))
        sensor = Sensor(serialAddr,9600)
        if not sensor.initialized:
            logging.error("sensor: {} init failed".format( xcsc))
            sys.exit(2)
        room = Room(id,board,sensor)
        logging.info("Sensor: {} init stus:{}".format(id,sensor.initialized))
        roomList.append(room)
        logging.info("Room: {} added".format(roomName))

    signal.signal(signal.SIGUSR1, signal_handler)

    temperatureAndGateControl(board,roomList)

    exit(0)

# -----------------------------------------------------------
# -----------------------------------------------------------
# -----------------------------------------------------------

