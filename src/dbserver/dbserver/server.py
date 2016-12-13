from socket import AF_INET, SOCK_STREAM, socket, SOL_SOCKET, SO_REUSEADDR
from concurrent.futures import ThreadPoolExecutor
import threading
from .tsdb_ops import *
from .tsdb_deserialize import *
from .tsdb_error import *
from .util import genSIM
from timeseries.storagemanager import FileStorageManager
import json
import enum
import socketserver
import pickle

LENGTH_FIELD_LENGTH = 4
DBSERVER_HOME = '/var/dbserver/'
TIMESERIES_DIR = 'tsdata'

class TSDB_Server(socketserver.BaseServer):

    def __init__(self, addr=15001):
        self.addr = addr
        self.deserializer = Deserializer()
        self.sm = FileStorageManager(DBSERVER_HOME+TIMESERIES_DIR)

    def handle_client(sock, client_addr):
        print('Got connection from', client_addr)
        while True:
            msg = sock.recv(65536)
            if not msg:
                break
            json_response = data_received(msg)
            sock.sendall(self.deserializer.serialize(json_response))
        print('Client closed connection')
        sock.close()

    def run(self):
        pool = ThreadPoolExecutor(50)
        sock = socket(AF_INET, SOCK_STREAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.bind(('',self.addr))
        sock.listen(15)

        while True:
            print('connection')
            client_sock, client_addr = sock.accept()
            pool.submit(self.handle_client, client_sock, client_addr)

    def data_received(self, data):
        self.deserializer.append(data)
        if self.deserializer.ready():
            msg = self.deserializer.deserialize()
            status = TSDBStatus.OK  # until proven otherwise.
            response = TSDBOp_Return(status, None)  # until proven otherwise.
            try:
                tsdbop = TSDBOp.from_json(msg)
            except TypeError as e:
                response = TSDBOp_Return(TSDBStatus.INVALID_OPERATION, None)

            if status is TSDBStatus.OK:
                if isinstance(op, TSDBOp_withTS):
                    response = self._with_ts(tsdbop)
                elif isinstance(op, TSDBOp_withID):
                    response = self._with_id(tsdbop)
                else:
                    response = TSDBOp_Return(TSDBStatus.UNKNOWN_ERROR, tsdbop['op'])

            return serialize(response.to_json())

    def _with_ts(self, TSDBOp):
        ids = genSIM(TSDBOp['ts'])
        tslist = [get_file_from_id(idee) for idee in ids]
        tsdump = pickle.dumps(tslist)
        return TSDBOp_Return(TSDBStatus.OK, tsdump)

    def _with_id(self, TSDBOp):
        ids = genSIM(TSDBOp['id'])
        tslist = [get_file_from_id(idee) for idee in ids]
        tsdump = pickle.dumps(tslist)
        return TSDBOp_Return(TSDBStatus.OK, tsdump)

    def get_file_from_id(self, idee):
        ts = SMTimeSeries.from_db(idee, self.sm)
        return ts
