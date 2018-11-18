import logging
from deoServer import RelayBoard
from multiprocessing import Lock

if __name__ == '__main__':
    lck = Lock()
    logging.basicConfig(level=logging.INFO)
    board = RelayBoard(lck)
    # activate raspberry control over main power relays
    board.startRelay(9)



