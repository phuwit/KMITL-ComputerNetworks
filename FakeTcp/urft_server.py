'''
Fake TCP Server

filelength: int
filename: str

sequence: int
checksum: bytes
data: bytes
'''

import logging
from sys import argv

from fake_tcp import Server


def main():
    try:
        server_ip = argv[1]
        server_port = int(argv[2])
    except Exception:
        print("2 arguments required: server_ip server_port")
        return

    try:
        server = Server(server_ip=server_ip, server_port=server_port)
        server.recieve()
    except TimeoutError:
        logging.warning('timeout... bailing')
    except ConnectionRefusedError:
        logging.warning('connection closed... bailing')


if __name__ == '__main__':
    main()
