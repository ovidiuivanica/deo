import logging
from deoServer import RelayBoard
from multiprocessing import Lock

if __name__ == '__main__':
    lck = Lock()
    logging.basicConfig(level=logging.INFO)
    board = RelayBoard(lck)
    board.startRelay(1)
    board.startRelay(2)
    board.startRelay(3)

