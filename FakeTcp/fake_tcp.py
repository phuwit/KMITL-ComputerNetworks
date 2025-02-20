from os import path, unlink
from zlib import crc32
from socket import AF_INET, SOCK_DGRAM, socket
from typing import Dict, List, Tuple
import logging

logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(levelname)s: %(message)s')

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
        self.__socket = socket(AF_INET, SOCK_DGRAM)
        self.__socket.bind((self.__server_ip, self.__server_port))
        self.__socket.settimeout(Constants.CONNECTION_END_NULLS_COUNT)

        self.__segments: Dict[int, bytes] = {}

    def process_segment(self, segment: bytes) -> None:
        sequence_number, claimed_crc32sum = Utilities.decode_headers(segment)
        payload = segment[Constants.HEADER_SIZE::]
        # logging.info(f"payload {payload}")
        if crc32(payload) != claimed_crc32sum:
            logging.warning(f"crc mismatch {claimed_crc32sum} {crc32(payload)}")
            return None
        # logging.debug(f"segment #{sequence_number} {payload}")

        self.__segments[sequence_number] = payload
        logging.debug(f"all segments {self.__segments.keys()}")

    # def process_segments(self, segments: List[bytes]) -> None:
    #     for segment in segments:
    #         result = self.process_segment(segment)
    #         if result is None:
    #             continue
    #         sequence_number, payload = result
    #         segments[sequence_number] = payload

    def recieve(self):
        # self.__socket.bind(("127.0.0.1", 5001))
        self.__socket.settimeout(Constants.CONNECTION_END_NULLS_COUNT)

        nulls: int = 0
        possible_nulls: List[bytes] = []
        filename: str = "file"
        next_segment: int = 0

        if path.exists(filename):
            unlink(filename)

        while True:
            segment, _ = self.__socket.recvfrom(Constants.SEGMENT_SIZE)
            # logging.info(f"data {segment}")
            # logging.info(f"nulls {nulls}")
            if segment == b"":
                if nulls <= Constants.CONNECTION_END_NULLS_COUNT:
                    nulls += 1
                    possible_nulls.append(segment)
                else:
                    logging.warning("closing connection after recieving nulls")
                    break
            else:
                self.process_segment(segment)
                # logging.info(f"segment {segment}")

                if nulls != 0:
                    nulls = 0
                    for segment in possible_nulls:
                        self.process_segment(segment)
                    possible_nulls = []
                with open("file", "ab") as file:
                    while next_segment in self.__segments:
                        segment = self.__segments.pop(next_segment)
                        logging.debug(f"writing {next_segment} {segment}")
                        next_segment += Constants.PAYLOAD_SIZE
                        file.write(segment)



class Client:
    """
    Fake TCP Client
    """

    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket(AF_INET, SOCK_DGRAM)
        self.__socket.connect((self.__server_ip, self.__server_port))

    def send(self, filename: str):
        segment_number = 0
        with open(filename, "rb") as file:
            while payload := file.read(Constants.PAYLOAD_SIZE):
                logging.debug(f"segment number {segment_number}")

                checksum = crc32(payload)
                headers = Utilities.encode_headers(segment_number, checksum)
                segment = headers + payload
                logging.debug(f"payload {payload}")
                logging.debug(f"crc32sum {checksum}")
                segment_number += Constants.PAYLOAD_SIZE
                self.__socket.send(segment)
            self.__socket.close()
