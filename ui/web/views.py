from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import requests

from multiprocessing import Lock

import time
import datetime
import os
import rpyc
import json
import logging
import sys
if "win32" not in sys.platform:
    import sysv_ipc
from deo import deoServer
from collections import OrderedDict
# Create your views here.
TOTAL = 20000


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Room(object):
    def __init__(self):
        id = None
        name = None
        temperature = None
        humidity = None
        reference = None


def index(request):
    service_name = "Deoplace"
    room_list = []

    context = {'service_name': service_name,
               'room_list' : room_list}
    return render(request, 'web/index.html', context)

def status(request):
    return render(request, 'web/status.html')

def access(request):
    service_name = "Deoplace"
    context = {'service_name': service_name}
    return render(request, 'web/access.html', context)


def data(request):
    try:
        mq = sysv_ipc.MessageQueue(42)
    except Exception as e:
        logging.error("cannot acquire message queue: {}".format(e))
        return HttpResponse("cannot acquire message queue")
    data = {"django" : "read request"}
    snd_data = json.dumps(data)
    snd_msg = snd_data.encode()
    mq.send(snd_msg, type=1) # type 1 = data read request

    rcv_msg, _ = mq.receive(type=2)
    rcv_data = rcv_msg.decode()
    try:
        data = json.loads(rcv_data)
    except Exception as msg:
        logging.error("json conversion error %s", msg)

    return JsonResponse(data)

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
    roomIdList = ["1","2","3","6"]
    for roomId in roomIdList:
        temp = deoServer.getPersistantData(roomId,"room","day")
        res = deoServer.setPersistantData(roomId,"room","reference",temp)
    #return HttpResponse("<a href='/web/'>BACK</a>")
    context = {'action' : 'heat set'}
    return render(request, 'web/done.html', context)


def set_reference(request):
    roomIdList = ["1","2","3","6"]
    reference = request.POST.get('new_reference')
    room_id = request.POST.get('room_id')

    res = deoServer.setPersistantData(room_id,"room","reference",reference)
    #return HttpResponse("<a href='/web/'>BACK</a>")
    context = {'action' : 'reference set to {} for room id {}'.format(reference, room_id)}
    return render(request, 'web/done.html', context)

def cold(request):
    roomIdList = ["1","2","3","6"]
    for roomId in roomIdList:
        temp = deoServer.getPersistantData(roomId,"room","night")
        res = deoServer.setPersistantData(roomId,"room","reference",temp)
    #return render(request, 'web/back.html')
    context = {'action' : 'cold set'}
    return render(request, 'web/done.html', context)

def door(request):
    con = rpyc.connect("192.168.0.128", 18812)
    con.root.gate_open()
    con.close()
    context = {'action' : 'opened'}
    return render(request, 'web/done.html', context)

def on(request):

    con = rpyc.connect("192.168.0.128", 18812)
    con.root.water_start()
    con.close()

def off(request):
    con = rpyc.connect("192.168.0.128", 18812)
    con.root.water_stop()
    con.close()
    return render(request)

def inc(request, room):
    con = rpyc.connect("192.168.0.114", 18861)
    con.root.increase(room)
    con.close()
    return render(request, 'web/done.html')

def dec(request, room):
    con = rpyc.connect("192.168.0.114", 18861)
    con.root.decrease(room)
    con.close()
    return render(request, 'web/done.html')

def compute_context():
    donations_file_path = os.path.join(BASE_DIR, "donations.json")
    buy_data_file_path = os.path.join(BASE_DIR, "buylist.json")
    last_update_time_unix = os.stat(donations_file_path).st_mtime
    time_marker = datetime.datetime.fromtimestamp(last_update_time_unix)
    last_update_time = time_marker.strftime("%H:%M:%S - %a, %b %d-%Y")

    with open(donations_file_path) as fd:
        data = json.load(fd)
    with open(buy_data_file_path) as fd:
        buy_data = json.load(fd)

    primit = 0
    for item in data:
        primit += item.get("Suma", 0)

    total_cost = 0
    for item in buy_data:
        total_cost += item.get("pret", 0)

    neplanificat = primit - total_cost if primit > total_cost else 0
    ramas = abs(neplanificat) if neplanificat < 0 else 0

    context = {
        "update_time_stamp" : last_update_time,
        "total" : total_cost,
        "primit" : primit,
        "ramas" : ramas,
        "data" : data,
        "buy_data" : buy_data,
        "total_cost" : total_cost,
        "neplanificat" : neplanificat
    }
    return context

def alexandria(request):
    context = compute_context()
    return render(request, "web/alexandria.html", context)

def test(request):
    return render(request, "web/test.html")

def tranzactii(request):
    context = compute_context()
    return render(request, "web/tranzactii.html", context)

def achizitii(request):
    return render(request, "web/achizitii.html")

def link(request):
    return render(request, "web/LINK.html")

def comanda(request, furnizor):
    context = {"furnizor" : furnizor}
    return render(request, "web/comanda.html", context)

def copii(request):
    return render(request, "web/copii.html")

def advent(request):
    file_path = os.path.join(BASE_DIR, "advent.json")
    with open(file_path) as fd:
        data = json.load(fd)
    id = datetime.datetime.now().day
    pasaj_reference = data.get(str(id), {}).get("pasaj")
    pasaj_text = "."
    try:
        request_url = "https://bible-api.com/{}?translation=rccv".format(pasaj_reference)
        r = requests.get(request_url)
        pasaj_text = json.loads(r.text).get("text", "-")
    except Exception as _:
        logging.error("failed to get passage")
        pasaj_text = "..."

    context = {
        "id" : str(id),
        "data" : data.get(str(id), {}),
        "pasaj" : pasaj_text
    }
    return render(request, "web/advent.html", context)

def lucrari(request):
    lucrari_path = os.path.join(BASE_DIR, "static", "web", "lucrari")
    pictures = os.listdir(lucrari_path)

    context = {
        "folder" : "lucrari",
        "pictures" : pictures
    }
    return render(request, "web/lucrari.html", context)

def cadouri(request):
    files_path = os.path.join(BASE_DIR, "static", "web", "cadouri")
    pictures = os.listdir(files_path)[:]

    context = {
        "folder" : "cadouri",
        "pictures" : pictures
    }
    return render(request, "web/lucrari.html", context)

def familie(request):
    file_path = os.path.join(BASE_DIR, "familie.json")
    with open(file_path) as fd:
        data = json.load(fd)
    zi = datetime.datetime.today().strftime("%A")

    context = {
        "data" : data.get(zi, {})
    }
    return render(request, "web/familie.html", context)

def munte(request):
    file_path = os.path.join(BASE_DIR, "munte.json")
    with open(file_path) as fd:
        data = json.load(fd)
    zi = datetime.datetime.today().strftime("%A")

    context = {
        "data" : data
    }
    return render(request, "web/munte.html", context)

def studiu(request):
    file_path = os.path.join(BASE_DIR, "studiu.json")
    with open(file_path) as fd:
        data = json.load(fd)
    # zi = datetime.datetime.today().strftime("%A")
    zi = "14_februarie"
    # pasaj_reference = data.get(zi, {}).get("reference")
    # try:
    #     request_url = "https://bible-api.com/{}?translation=rccv".format(pasaj_reference)
    #     r = requests.get(request_url)
    #     pasaj_text = json.loads(r.text).get("text", "-")
    # except Exception as _:
    #     logging.error("failed to get passage")
    #     pasaj_text = "..."

    context = {
        "data": data.get(zi, {})
        # "pasaj_text": pasaj_text
    }
    return render(request, "web/studiu.html", context)

def aproape(request, familie):
    file_path = os.path.join(BASE_DIR, "rugaciune.json")
    with open(file_path) as fd:
        data = json.load(fd, object_pairs_hook=OrderedDict)
    zi = datetime.datetime.today().strftime("%A")

    familie = familie if familie in ["rice", "radoi", "popescu", "bechenea", "iancu", "mavrodin", "cazacu", "bledea"] else ""
    context = {
        "data" : data.get(familie, {}),
        "familie" : familie
    }
    return render(request, "web/rugaciune.html", context)
