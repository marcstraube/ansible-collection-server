#!/usr/bin/env python3
"""memcached in front of the local one, for the restore tests (stdlib only).

    molecule-memcached-proxy <address> <port> <mode>

Listens on <address>:<port> and forwards every connection to
127.0.0.1:11211, so SOGo sees a memcached on another host. 'flush_all'
lines are handled by <mode>:
  forward  passed on (memcached answers OK)
  error    answered with SERVER_ERROR, not passed on
  hang     never answered (a firewall dropping the packets)
  close    connection closed without an answer
"""

import socket
import sys
import threading
import time

UPSTREAM = ('127.0.0.1', 11211)


def pump(source, target, client, mode):
    try:
        while True:
            data = source.recv(65536)
            if not data:
                break
            if client and data.lstrip().startswith(b'flush_all'):
                if mode == 'error':
                    source.sendall(b'SERVER_ERROR molecule\r\n')
                    continue
                if mode == 'close':
                    break
                if mode == 'hang':
                    time.sleep(3600)
                    break
            target.sendall(data)
    except OSError:
        pass
    finally:
        for sock in (source, target):
            try:
                sock.close()
            except OSError:
                pass


def main():
    address, port, mode = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((address, port))
    server.listen(64)
    while True:
        client, _ = server.accept()
        upstream = socket.create_connection(UPSTREAM)
        threading.Thread(target=pump, args=(client, upstream, True, mode), daemon=True).start()
        threading.Thread(target=pump, args=(upstream, client, False, mode), daemon=True).start()


if __name__ == '__main__':
    main()
