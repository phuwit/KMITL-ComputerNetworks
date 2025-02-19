'''
Fake TCP Server

filelength: int
filename: str

sequence: int
checksum: bytes
data: bytes
'''

from sys import argv

from fake_tcp import Server


def main():
    try:
        server_ip = argv[1]
        server_port = int(argv[2])
    except Exception:
        print("2 arguments required: server_ip server_port")
        return

    server = Server(server_ip=server_ip, server_port=server_port)
    server.recieve()


if __name__ == '__main__':
    main()
