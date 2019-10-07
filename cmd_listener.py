import sqlite3
import rpyc

class CmdListenerService(rpyc.Service):
    def exposed_get_temperature(self, room):
        return
