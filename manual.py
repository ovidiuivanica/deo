import logging
from deoServer import RelayBoard
from multiprocessing import Lock

if __name__ == '__main__':
    lck = Lock()
    logging.basicConfig(level=logging.INFO)
    board = RelayBoard(lck)
    # activate raspberry control over main power relays
    board.startRelay(8)

    # enable 3 rooms expcept kitchen
    board.startRelay(1)
    board.startRelay(2)
    board.startRelay(3)

