from os import unlink
from zlib import crc32
from socket import AF_INET, SOCK_STREAM, socket
from typing import Dict, List, Tuple


class Constants:
    """
    FakeTcp Constants
    """

    SEGMENT_SIZE: int = 1024
    HEADER_SIZE: int = 8
    PAYLOAD_SIZE: int = SEGMENT_SIZE - HEADER_SIZE

    HEADER_BYTEORDER = "big"
    HEADER_INT_LENGTH = 4
    HEADER_CHECKSUM_LENGTH = 4

    LOGGING: bool = True
    LOSS_TIMEOUT_SEC: int = 2
    CONNECTION_END_NULLS_COUNT: int = 10


class Utilities:
    @staticmethod
    def encode_headers(sequence_number: int, crc32sum: int) -> bytes:
        headers = bytes()
        headers += sequence_number.to_bytes(
            Constants.HEADER_INT_LENGTH, Constants.HEADER_BYTEORDER
        )
        headers += crc32sum.to_bytes(
            Constants.HEADER_INT_LENGTH, Constants.HEADER_BYTEORDER
        )
        return headers

    @staticmethod
    def decode_headers(headers: bytes) -> Tuple[int, int]:
        sequence_number = int.from_bytes(
            headers[0 : Constants.HEADER_INT_LENGTH], Constants.HEADER_BYTEORDER
        )
        crc32sum = int.from_bytes(
            headers[
                Constants.HEADER_INT_LENGTH : Constants.HEADER_INT_LENGTH
                + Constants.HEADER_CHECKSUM_LENGTH
            ],
            Constants.HEADER_BYTEORDER,
        )
        return (sequence_number, crc32sum)


class Server:
    """
    Fake TCP Server
    """

    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket(AF_INET, SOCK_STREAM)
        self.__socket.bind((self.__server_ip, self.__server_port))
        self.__socket.settimeout(Constants.CONNECTION_END_NULLS_COUNT)

        self.__segments: Dict[int, bytes] = {}

    def process_segment(self, segment: bytes) -> None:
        sequence_number, claimed_crc32sum = Utilities.decode_headers(segment)
        payload = segment[Constants.HEADER_SIZE::]
        if crc32(payload) != claimed_crc32sum:
            return None
        self.__segments[sequence_number] = payload

    # def process_segments(self, segments: List[bytes]) -> None:
    #     for segment in segments:
    #         result = self.process_segment(segment)
    #         if result is None:
    #             continue
    #         sequence_number, payload = result
    #         segments[sequence_number] = payload

    def recieve(self):
        client_socket, client_address = self.__socket.accept()
        client_socket.settimeout(Constants.CONNECTION_END_NULLS_COUNT)

        nulls: int = 0
        possible_nulls: List[bytes] = []
        filename: str = "file"
        next_segment: int = 0

        unlink(filename)

        while True:
            data = client_socket.recv(Constants.PAYLOAD_SIZE)
            if data == b"":
                if nulls <= Constants.CONNECTION_END_NULLS_COUNT:
                    nulls += 1
                    possible_nulls.append(data)
                else:
                    if Constants.LOGGING:
                        print("closing connection after recieving nulls")
                    break
            else:
                if nulls != 0:
                    nulls = 0
                    for segment in possible_nulls:
                        self.process_segment(segment)
                    possible_nulls = []
                with open("file", "ab") as file:
                    while next_segment in self.__segments:
                        segment = self.__segments.pop(next_segment)
                        next_segment += Constants.PAYLOAD_SIZE
                        file.write(segment)



class Client:
    """
    Fake TCP Client
    """

    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket(AF_INET, SOCK_STREAM)
        self.__socket.connect((self.__server_ip, self.__server_port))

    def send(self, filename: str):
        if Constants.LOGGING:
            payload_no = 1
        with open(filename, "rb") as file:
            while payload := file.read(Constants.PAYLOAD_SIZE):
                if Constants.LOGGING:
                    payload_no += 1
                    print("Payload count:", payload_no)
                checksum = crc32(payload)
                headers = Utilities.encode_headers(1234, checksum)
                segment = headers + payload
                self.__socket.send(segment)
            self.__socket.close()
