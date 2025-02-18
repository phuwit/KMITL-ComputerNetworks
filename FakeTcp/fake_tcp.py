from socket import AF_INET, SOCK_STREAM, socket
from typing import List, Tuple


class Constants:
    '''
    FakeTcp Constants
    '''
    HEADER_BYTES: int = 4
    HEADER_BYTEORDER = 'big'
    HEADER_INT_LENGTH = 4

    PAYLOAD_SIZE_BYTES: int = 1024
    LOGGING: bool = True
    LOSS_TIMEOUT_SEC: int = 2
    CONNECTION_END_NULLS_COUNT: int = 10

class Utilities:
    def encode_headers(self, sequence_number: int) -> bytes:
        headers = bytes()
        headers += sequence_number.to_bytes(Constants.HEADER_INT_LENGTH, Constants.HEADER_BYTEORDER)
        return headers

    def decode_headers(self, headers: bytes) -> int:
        sequence_number: int = int.from_bytes(headers[0:Constants.HEADER_INT_LENGTH], Constants.HEADER_BYTEORDER)
        return sequence_number


class Server:
    '''
    Fake TCP Server
    '''
    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket(AF_INET, SOCK_STREAM)
        self.__socket.bind((self.__server_ip, self.__server_port))
        self.__socket.listen(8)
        self.__socket.settimeout(Constants.CONNECTION_END_NULLS_COUNT)

    def recieve(self):
        client_socket, client_address = self.__socket.accept()
        client_socket.settimeout(Constants.CONNECTION_END_NULLS_COUNT)
        nulls: int = 0
        possible_nulls_buffer: List[bytes] = []
        filename = 'file'

        with open(filename, "wb") as file:
            file.write(b'')

        while True:
            data = client_socket.recv(Constants.PAYLOAD_SIZE_BYTES)
            if (data == b''):
                if nulls <= Constants.CONNECTION_END_NULLS_COUNT:
                    nulls += 1
                    possible_nulls_buffer.append(data)
                else:
                    if Constants.LOGGING:
                        print("closing connection after recieving nulls")
                    break
            else:
                with open("file", "ab") as file:
                    if nulls != 0:
                        nulls = 0
                        file.write(possible_nulls_buffer)
                        possible_nulls_buffer = []
                    file.write(data)




class Client:
    '''
    Fake TCP Client
    '''
    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket(AF_INET, SOCK_STREAM)
        self.__socket.connect((self.__server_ip, self.__server_port))

    def send(self, filename: str):
        if Constants.LOGGING:
            payload_no = 1
        with open(filename, "rb") as file:
            while (payload := file.read(Constants.PAYLOAD_SIZE_BYTES)):
                if Constants.LOGGING:
                    payload_no += 1
                    print("Payload count:", payload_no)
                headers = Utilities.encode_headers(1234)
                segment = headers + payload
                self.__socket.send(segment)
            self.__socket.close()
