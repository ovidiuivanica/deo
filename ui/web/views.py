from django.shortcuts import render
from django.http import HttpResponse

import logging
import sysv_ipc
import sys
sys.path.insert(0, "/home/pi/Desktop/deo")
from deoServer import getPersistantData, setPersistantData

# Create your views here.

class Room(object):
    def __init__(self):
        id = None
        name = None
        temperature = None
        humidity = None
        reference = None

def index(request):
    service_name = "Deoplace"
    
    context = {'service_name': service_name}
    return render(request, 'web/index.html', context)

        
def status(request):
    string = "this is my string"
    roomIdList = ["1","2","3","4"]    
    room_list = []
    for roomId in roomIdList:
        room = Room()
        room.id = roomId
        room.temperature = getPersistantData(roomId,"room","temperature")
        room.humidity = getPersistantData(roomId,"room","humidity")
        room.name = getPersistantData(roomId,"room","name")
        room.reference = getPersistantData(roomId,"room","reference")
        room_list.append(room)
    context = {'room_list': room_list}
    return render(request, 'web/status.html', context)

def stop(request):
    try:
        mq = sysv_ipc.MessageQueue(42)
    except Exception,e:
        logging.error("cannot acquire message queue: {}".format(e))
        return HttpResponse("cannot acquire message queue")

    returnString = ""
    s = "closeLight--"
        
    logging.debug("Sending %s" % s)
    s = s.encode()
    mq.send(s)

    s, _ = mq.receive()
    s = s.decode()
    logging.debug("Received %s" % s)
    parts = s.split("--")
    status = parts[0]
    returnString = parts[1]
    if status == "openOK":
        logging.debug("light open success")
        rs = "ok"
    elif s=="openKO":
        logging.debug("light open failed")
        rs = "failed"
    else: 
        logging.debug("broken message")
        rs = "broken message"
    return HttpResponse("Hello, world. You're at the polls index. {}".format(rs))


def start(request):
    try:
        mq = sysv_ipc.MessageQueue(42)
    except Exception,e:
        logging.error("cannot acquire message queue: {}".format(e))
        return HttpResponse("cannot acquire message queue")

    returnString = ""
    s = "openLight--"
        
    logging.debug("Sending %s" % s)
    s = s.encode()
    mq.send(s)

    s, _ = mq.receive()
    s = s.decode()
    logging.debug("Received %s" % s)
    parts = s.split("--")
    status = parts[0]
    returnString = parts[1]
    if status == "openOK":
        logging.debug("light open success")
        rs = "success"
    elif s=="openKO":
        logging.debug("light open failed")
        rs = "open failed"

    else: 
        logging.debug("broken message")
        rs = "broken message"
    return HttpResponse("Hello, world. You're at the polls index. {}".format(rs))
def heat(request):
    roomIdList = ["1","2","3","4"]    
    for roomId in roomIdList:
        temp = getPersistantData(roomId,"room","day")
        res = setPersistantData(roomId,"room","reference",temp)  
    return HttpResponse("<a href='/web/'>BACK</a>")
def cold(request):
    roomIdList = ["1","2","3","4"]    
    for roomId in roomIdList:
        temp = getPersistantData(roomId,"room","night")
        res = setPersistantData(roomId,"room","reference",temp)  
    return render(request, 'web/back.html')
def door(request):
    res = setPersistantData('1000',"door","state","1")  
    return HttpResponse("<a href='/web/'>BACK</a>")
