""" Base Class for the Client, handles handshake, encryption and messages """
import ssl
import time
import socket
import logging

from utils.helpers import run_till_true

socket.setdefaulttimeout(10)


class Client:
    """
    Base Client
    """

    # Header length
    header_length = 8

    # Create socket
    sock = socket.socket()
    ssl_sock: ssl.SSLSocket | None = None
    address: tuple | None = None

    def __init__(self, context: ssl.SSLContext) -> None:
        """ Define a trusted certificate """
        self.context = context

    @run_till_true
    def connect(self, address: tuple, retry_in_seconds: int = 5) -> bool:
        """ Connect to peer """

        self.sock = socket.socket()

        try:
            self.sock.connect(address)
        except ConnectionError:
            # Socket is not open
            return False
        except OSError:
            self.sock.close()
            time.sleep(retry_in_seconds)
            return False

        try:
            self.ssl_sock = self.context.wrap_socket(self.sock, server_hostname=address[0])
        except ssl.SSLError as error:
            logging.error("Error during ssl wrapping: %s", str(error))
            return False

        self.address = address
        return True


    def _read(self, amount: int) -> bytes:
        """ Receive raw data from peer """
        data = b''
        while len(data) < amount:
            buffer = self.ssl_sock.recv(amount)
            if not buffer:
                # Assume connection was closed
                logging.error('Assuming connection was closed: %s', str(self.address))
                raise ConnectionResetError
            data += buffer

        return data

    def read(self) -> bytes:
        """ Read messages from client """
        header = self._read(self.header_length)
        message_length = int.from_bytes(header, 'big')
        return self._read(message_length)

    def write(self, data: bytes) -> None:
        """ Write message data to peer """
        # Create header for data
        header = len(data).to_bytes(self.header_length, byteorder='big')
        message = header + data
        self.ssl_sock.sendall(message)
