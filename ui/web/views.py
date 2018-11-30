from django.shortcuts import render
from django.http import HttpResponse, JsonResponse

from multiprocessing import Lock

import logging
import sysv_ipc
import sys
from deo import deoServer

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
    roomIdList = ["1","2","3","4"]
    room_list = []
    for roomId in roomIdList:
        room = Room()
        room.id = roomId
        room.temperature = deoServer.getPersistantData(roomId,"room","temperature")
        room.humidity = deoServer.getPersistantData(roomId,"room","humidity")
        room.name = deoServer.getPersistantData(roomId,"room","name")
        room.reference = deoServer.getPersistantData(roomId,"room","reference")
        room.ref_temp_list = ["10", "12", "13", "14", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25"]
        room_list.append(room)


    context = {'service_name': service_name,
               'room_list' : room_list}
    return render(request, 'web/index.html', context)


def status(request):
    string = "this is my string"
    roomIdList = ["1","2","3","4"]
    room_list = []
    for roomId in roomIdList:
        room = Room()
        room.id = roomId
        room.temperature = deoServer.getPersistantData(roomId,"room","temperature")
        room.humidity = deoServer.getPersistantData(roomId,"room","humidity")
        room.name = deoServer.getPersistantData(roomId,"room","name")
        room.reference = deoServer.getPersistantData(roomId,"room","reference")
        room_list.append(room)
    context = {'room_list': room_list}
    return render(request, 'web/status.html', context)

def data(request):
    string = "this is my string"
    roomIdList = ["1","2","3","4"]
    house_data = {}
    for roomId in roomIdList:
        room = {}
        room['id'] = roomId
        room['temperature'] = deoServer.getPersistantData(roomId,"room","temperature")
        room['humidity'] = deoServer.getPersistantData(roomId,"room","humidity")
        room['name'] = deoServer.getPersistantData(roomId,"room","name")
        room['reference'] = deoServer.getPersistantData(roomId,"room","reference")
        house_data[room.get('name')] = room
    return JsonResponse(house_data)


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
        temp = deoServer.getPersistantData(roomId,"room","day")
        res = deoServer.setPersistantData(roomId,"room","reference",temp)
    #return HttpResponse("<a href='/web/'>BACK</a>")
    context = {'action' : 'heat set'}
    return render(request, 'web/done.html', context)


def set_reference(request):
    roomIdList = ["1","2","3","4"]
    reference = request.POST.get('new_reference')
    room_id = request.POST.get('room_id')

    res = deoServer.setPersistantData(room_id,"room","reference",reference)
    #return HttpResponse("<a href='/web/'>BACK</a>")
    context = {'action' : 'reference set to {} for room id {}'.format(reference, room_id)}
    return render(request, 'web/done.html', context)

def cold(request):
    roomIdList = ["1","2","3","4"]
    for roomId in roomIdList:
        temp = deoServer.getPersistantData(roomId,"room","night")
        res = deoServer.setPersistantData(roomId,"room","reference",temp)
    #return render(request, 'web/back.html')
    context = {'action' : 'cold set'}
    return render(request, 'web/done.html', context)
def door(request):
    res = deoServer.setPersistantData('1000',"door","state","1")
    context = {'action' : 'door_opened'}
    return render(request, 'web/done.html', context)

def light_start(request):
    res = deoServer.setPersistantData('6',"yard","light","1")
    context = {'action' : 'light_on'}
    return render(request, 'web/done.html', context)
def light_stop(request):
    res = deoServer.setPersistantData('6',"yard","light","0")
    context = {'action' : 'light_stopped'}
    return render(request, 'web/done.html', context)

def on(request):

    lck = Lock()
    board = deoServer.RelayBoard(lck)
    # activate raspberry control over main power relays
    board.startRelay(8)

    # enable 3 rooms expcept kitchen
    board.startRelay(1)
    board.startRelay(2)
    board.startRelay(3)

def off(request):

    lck = Lock()
    board = RelayBoard(lck)
    # activate raspberry control over main power relays
    board.stopRelay(8)

    # enable 3 rooms expcept kitchen
    board.stopRelay(1)
    board.stopRelay(2)
    board.stopRelay(3)