'''
Packet types
INIT
1 byte: type
8 byte: size
others: name

DATA
1 byte: type
8 byte: sequence
8 byte: checksum
others: data

ACK
1 byte: type
8 byte: sequence
'''

from collections import OrderedDict
from enum import Enum
from os import path, unlink
import select
from time import time
from zlib import crc32
import socket
from typing import List, Tuple, Union
import logging

logging.basicConfig(
    level=logging.DEBUG, format="[%(asctime)s] %(levelname)s: %(message)s"
)


class Constants:
    """
    FakeTcp Constants
    """

    class SEGMENT_TYPE(Enum):
        INIT = 1
        DATA = 2
        ACK = 3

    HEADER_BYTEORDER = "big"
    HEADER_TYPE_LENGTH = 1
    HEADER_SEQUENCE_LENGTH = 4
    HEADER_CHECKSUM_LENGTH = 4
    HEADER_FILESIZE_LENGTH = 4

    MAX_SEGMENT_SIZE: int = 1024
    HEADER_SIZE: int = (
        HEADER_TYPE_LENGTH + HEADER_SEQUENCE_LENGTH + HEADER_CHECKSUM_LENGTH
    )
    MAX_PAYLOAD_SIZE: int = MAX_SEGMENT_SIZE - HEADER_SIZE
    ACK_SEGMENT_SIZE = HEADER_TYPE_LENGTH + HEADER_SEQUENCE_LENGTH

    LOGGING: bool = True
    LOSS_TIMEOUT: float = 5
    CONSECUTIVE_PACKETS_TIMEOUT: float = 2
    CONNECTION_END_NULLS_COUNT: int = 10

    INIT_SEQUENCE_NUMBER = int.from_bytes(b'ffff', HEADER_BYTEORDER) -1


class Utilities:
    @staticmethod
    def encode_init(filesize: int, filename: str) -> bytes:
        segment = bytes()
        segment += Constants.SEGMENT_TYPE.INIT.value.to_bytes(
            Constants.HEADER_TYPE_LENGTH, Constants.HEADER_BYTEORDER
        )
        segment += filesize.to_bytes(
            Constants.HEADER_SEQUENCE_LENGTH, Constants.HEADER_BYTEORDER
        )
        segment += filename.encode()
        return segment

    @staticmethod
    def encode_data_headers(
        sequence_number: int, crc32sum: int
    ) -> bytes:
        headers = bytes()
        headers += Constants.SEGMENT_TYPE.DATA.value.to_bytes(
            Constants.HEADER_TYPE_LENGTH, Constants.HEADER_BYTEORDER
        )
        headers += sequence_number.to_bytes(
            Constants.HEADER_SEQUENCE_LENGTH, Constants.HEADER_BYTEORDER
        )
        headers += crc32sum.to_bytes(
            Constants.HEADER_CHECKSUM_LENGTH, Constants.HEADER_BYTEORDER
        )
        return headers

    @staticmethod
    def encode_ack(sequence_number: int) -> bytes:
        segment = bytes()
        segment += Constants.SEGMENT_TYPE.ACK.value.to_bytes(
            Constants.HEADER_TYPE_LENGTH, Constants.HEADER_BYTEORDER
        )
        segment += sequence_number.to_bytes(
            Constants.HEADER_SEQUENCE_LENGTH, Constants.HEADER_BYTEORDER
        )
        return segment

    @staticmethod
    def decode_init(segment: bytes) -> Union[Tuple[int, str], None]:
        segment_type = Constants.SEGMENT_TYPE(int.from_bytes(
            segment[0 : Constants.HEADER_TYPE_LENGTH], Constants.HEADER_BYTEORDER
        ))
        if segment_type != Constants.SEGMENT_TYPE.INIT:
            return None

        filesize = int.from_bytes(
            segment[
                Constants.HEADER_TYPE_LENGTH : Constants.HEADER_TYPE_LENGTH
                + Constants.HEADER_FILESIZE_LENGTH :
            ],
            Constants.HEADER_BYTEORDER,
        )
        filename = path.basename(segment[Constants.HEADER_TYPE_LENGTH + Constants.HEADER_FILESIZE_LENGTH::].decode())
        return (filesize, filename)

    @staticmethod
    def decode_data_headers(headers: bytes) -> Tuple[Constants.SEGMENT_TYPE, int, int]:
        segment_type = Constants.SEGMENT_TYPE(int.from_bytes(
            headers[0 : Constants.HEADER_TYPE_LENGTH], Constants.HEADER_BYTEORDER
        ))
        sequence_number = int.from_bytes(
            headers[
                Constants.HEADER_TYPE_LENGTH : Constants.HEADER_TYPE_LENGTH
                + Constants.HEADER_SEQUENCE_LENGTH :
            ],
            Constants.HEADER_BYTEORDER,
        )
        crc32sum = int.from_bytes(
            headers[
                Constants.HEADER_TYPE_LENGTH
                + Constants.HEADER_SEQUENCE_LENGTH : Constants.HEADER_TYPE_LENGTH
                + Constants.HEADER_SEQUENCE_LENGTH
                + Constants.HEADER_CHECKSUM_LENGTH :
            ],
            Constants.HEADER_BYTEORDER,
        )
        return (segment_type, sequence_number, crc32sum)

    @staticmethod
    def decode_ack(segment: bytes) -> Union[int, None]:
        segment_type = Constants.SEGMENT_TYPE(int.from_bytes(
            segment[0 : Constants.HEADER_TYPE_LENGTH], Constants.HEADER_BYTEORDER
        ))
        if segment_type != Constants.SEGMENT_TYPE.ACK:
            return None

        sequence_number = int.from_bytes(
            segment[
                Constants.HEADER_TYPE_LENGTH : Constants.HEADER_TYPE_LENGTH
                + Constants.HEADER_SEQUENCE_LENGTH :
            ],
            Constants.HEADER_BYTEORDER,
        )
        return sequence_number


class InflightSegment:
    def __init__(self, segment_number: int, resend_epoch: float) -> None:
        self.segment_number = segment_number
        self.resend_epoch = resend_epoch


class Server:
    """
    Fake TCP Server
    """

    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__send_ack_at: float = -1
        self.__recieving: bool = True
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.bind((self.__server_ip, self.__server_port))
        self.__socket.settimeout(Constants.CONNECTION_END_NULLS_COUNT)

        self.__segments: OrderedDict[int, bytes] = OrderedDict()
        self.__pending_ack: List[int] = []
        self.__acked: List[int] = []

    def send_acks(self, address: Tuple[str, int]):
        logging.info(f"sending acks for {self.__pending_ack}")
        self.__recieving = False
        try:
            for sequence_number in self.__pending_ack:
                segment = Utilities.encode_ack(sequence_number=sequence_number)
                logging.info(f"sending ack for {sequence_number}")
                self.__socket.sendto(segment, address)
                self.__acked.append(sequence_number)
            self.__pending_ack.clear()
        except Exception as exc:
            logging.error(exc)
        self.__recieving = True

    def process_segment(self, segment: bytes) -> bool:
        type, sequence_number, claimed_crc32sum = Utilities.decode_data_headers(segment)
        payload = segment[Constants.HEADER_SIZE : :]
        # logging.info(f"payload {payload}")
        if type == Constants.SEGMENT_TYPE.ACK:
            sequence_number = Utilities.decode_ack(segment)
            if sequence_number in self.__acked:
                index = self.__acked.index(sequence_number)
                self.__acked.pop(index)
                self.__pending_ack.append(index)
            return True
        if crc32(payload) != claimed_crc32sum:
            logging.warning(f"crc mismatch {claimed_crc32sum} {crc32(payload)}")
            return False
        # logging.debug(f"segment #{sequence_number} {payload}")

        self.__segments[sequence_number] = payload
        self.__pending_ack.append(sequence_number)
        return True

    # def process_segments(self, segments: List[bytes]) -> None:
    #     for segment in segments:
    #         result = self.process_segment(segment)
    #         if result is None:
    #             continue
    #         sequence_number, payload = result
    #         segments[sequence_number] = payload

    def recieve(self):
        nulls: int = 0
        possible_nulls: List[bytes] = []
        return_address = None
        next_segment: int = 0


        filename: Union[str, None] = None
        filesize: Union[int, None] = None

        while filename is None or filesize is None:
            ready = select.select([self.__socket], [], [], Constants.CONSECUTIVE_PACKETS_TIMEOUT)
            if ready[0] and self.__recieving:
                segment, return_address = self.__socket.recvfrom(Constants.MAX_SEGMENT_SIZE)
                # logging.info(f"data {segment}")
                # logging.info(f"nulls {nulls}")

                if segment == b"":
                    continue
                else:
                    logging.debug(f'init segment {segment}')
                    result = Utilities.decode_init(segment)
                    if result is None:
                        continue
                    filesize, filename = result
                    self.__pending_ack.append(Constants.INIT_SEQUENCE_NUMBER)
                    self.send_acks(return_address)

        if path.exists(filename):
            unlink(filename)

        with open(filename, "ab") as file:
            while True:
                ready = select.select([self.__socket], [], [], Constants.CONSECUTIVE_PACKETS_TIMEOUT)
                if ready[0] and self.__recieving:
                    segment, return_address = self.__socket.recvfrom(Constants.MAX_SEGMENT_SIZE)
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
                        self.__send_ack_at = time() + Constants.CONSECUTIVE_PACKETS_TIMEOUT
                        if not self.process_segment(segment):
                            continue
                        # logging.debug(f"all segments {self.__segments.keys()}")
                        logging.debug(f"expecting {next_segment}")
                        # logging.debug(f"nulls {nulls}")
                        # logging.debug(f"{next_segment in self.__segments.keys()}")
                        # logging.info(f"segment {segment}")
                        if nulls != 0:
                            nulls = 0
                            for segment in possible_nulls:
                                self.process_segment(segment)
                            possible_nulls = []
                        while next_segment in self.__segments.keys():
                            logging.debug(f"got {next_segment}")
                            segment = self.__segments.pop(next_segment)
                            # logging.debug(f"writing {next_segment} {segment}")
                            next_segment += len(segment)
                            logging.debug(f"next should be {next_segment}")
                            file.write(segment)
                if self.__send_ack_at != -1 and time() >= self.__send_ack_at and return_address is not None:
                    logging.info("sending backlogged ack")
                    self.send_acks(return_address)


class Client:
    """
    Fake TCP Client
    """

    def __init__(self, server_ip: str, server_port: int):
        self.__server_ip = server_ip
        self.__server_port = server_port
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.connect((self.__server_ip, self.__server_port))
        self.__socket.settimeout(Constants.LOSS_TIMEOUT)
        self.__recieve_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.__segment_inflight: List[InflightSegment] = []

    def send_segment(self, segment_number: int, payload: bytes):
        checksum = crc32(payload)
        headers = Utilities.encode_data_headers(segment_number, checksum)
        segment = headers + payload

        resend_epoch = time() + Constants.LOSS_TIMEOUT
        self.__segment_inflight.append(InflightSegment(segment_number, resend_epoch))

        logging.debug(f"sending #{segment_number}({checksum})")
        # logging.debug(f"sending #{segment_number}({checksum}) {payload}")
        self.__socket.send(segment)

    def send_file(self, filepath: str):
        segment_number = 0
        filesize = path.getsize(filepath)
        filename = path.basename(filepath)
        logging.debug(f'filesize {filesize}')
        with open(filepath, "rb") as file:
            # init
            payload = Utilities.encode_init(filesize, filename)
            logging.debug(f'init payload {payload}')
            self.__socket.send(payload)
            self.__segment_inflight.append((Constants.INIT_SEQUENCE_NUMBER))

            # first pass of data
            while payload := file.read(Constants.MAX_PAYLOAD_SIZE):
                payload_length = len(payload)
                self.send_segment(segment_number=segment_number, payload=payload)
                segment_number += payload_length

            self.__segment_inflight = sorted(self.__segment_inflight, key=lambda x: x.resend_epoch)

            # recieve ack and resend if necessary
            while self.__segment_inflight:
                resend_segment = self.__segment_inflight[0]
                if time() > resend_segment.resend_epoch:
                    segment = self.__segment_inflight.pop(0)
                    logging.info(f'now is {time()}')
                    logging.info(f'resending {segment.segment_number}')
                    logging.info(f'expired at {segment.resend_epoch}')
                    if segment.segment_number >= filesize:
                        logging.error(f'aborting resend: out of scope {segment.segment_number}')
                        continue
                    file.seek(segment.segment_number)
                    payload = file.read(Constants.MAX_PAYLOAD_SIZE)
                    payload_length = len(payload)
                    segment_number += payload_length

                    self.send_segment(segment_number=segment_number, payload=payload)

                segment, _ = self.__socket.recvfrom(Constants.MAX_SEGMENT_SIZE)
                if segment == b'':
                    continue
                sequence_number = Utilities.decode_ack(segment)
                if sequence_number is None:
                    continue
                try:
                    logging.info(f'recieved ack for {sequence_number}')
                    # logging.info(f'inflights {list(map(lambda x: x.segment_number, self.__segment_inflight))}')
                    self.__segment_inflight = [seg for seg in self.__segment_inflight if seg.segment_number != sequence_number]

                except:
                    logging.exception(f"cant pop {sequence_number} from inflight segment")

            logging.info('job done')

            self.__socket.close()
