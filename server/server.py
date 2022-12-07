import os
import socket
import platform
import logging

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import padding, serialization

from modules.clients import Client
from modules.baseserver import BaseServer
from utils.prompts import increase_timeout_prompt

logging.basicConfig(level=logging.DEBUG)
socket.setdefaulttimeout(10)

# Padding for AES
pad = padding.PKCS7(256)
header_length = 8

menu_help = """
Commands:

list
open (ID)
shutdown
help
"""

interact_help = """
Available commands:

shell
python
exit/back
"""


class ServerCLI(BaseServer):
    """ CLI for BaseServer """

    def __init__(self, certificate: x509.Certificate, private_key: ec.EllipticCurvePrivateKey):
        super().__init__(certificate, private_key)

    def cli(self) -> None:
        """ Start CLI """
        while True:
            try:
                self.menu()
            except KeyboardInterrupt:
                print('Ctrl-C detected: Shutting down server')
                self.shutdown()
                break
            except Exception as error:
                logging.critical('Critical errors occurred: %s' % str(error))

    def menu(self) -> None:
        """ Menu for interacting with clients """
        while True:
            command, *args = input('> ').split()

            match command:
                case 'help':
                    print(menu_help)
                case 'open':
                    try:
                        self.select(args)
                    except KeyboardInterrupt:
                        # Quit selector when ctrl-c is detected
                        print()
                        continue
                    except Exception as error:
                        logging.error('Client experiened an error: %s' % str(error))
                        continue
                case 'list':
                    self.list_cli()
                case 'shutdown':
                    raise KeyboardInterrupt
                case _:
                    print('Command was not recognized, type "help" for help.')

    def select(self, *args) -> None:
        """ Interact with a client """
        selected_client = None
        argument = args[0]

        if not argument:
            print('No client ID was given')
            return

        # Create a copy of the clients list
        # This ensures the list is looped through entirely
        # as some items may be otherwise removed mid loop
        clients = self.clients.copy()

        # Check if the given id matches a client.id
        for client in clients:
            if client.id == argument[0]:
                selected_client = client

        if selected_client is None:
            print('Invalid client ID')
            return

        while True:
            try:
                if self.interact(client):
                    break
            except KeyboardInterrupt:
                print('Ctrl-C detected: Returning to menu')
                break

    def interact(self, client: Client) -> None:
        """ Interact with a client """
        command, *args = input(f'{client.address[0]}> ').split()
        match command:
            case 'help':
                print(interact_help)
            case 'exit' | 'back':
                return True
            case 'shell':
                self.shell_cli(client)
            case 'python':
                self.python_cli(client)
            case _:
                print('Command was not recognized, type "help" for help.')

    def list_cli(self):
        """ CLI for list """
        clients = self.list()
        for client in clients:
            print(f'ID: {client.id} / Address: {client.address}')

    def shell_cli(self, client: Client) -> None:
        """ Open a shell to client """
        logging.debug('Launched shell')
        while True:
            command = input('shell> ')

            # Check for cases where command only affects output visually
            match command.strip():
                case 'exit':
                    break
                case 'clear' | 'cls':
                    if platform.system() == 'Windows':
                        os.system('cls')
                    else:
                        os.system('clear')
                    continue

            # Check if the directory is changed, in which case it should be remembered
            comm, *_ = command.split()
            if comm.lower() in ['cd', 'chdir']:

                print(client.shell(command).decode(), end='')
                # TODO: update cwd accordingly

            # Increase timeout to 60 seconds for shell
            client.conn.settimeout(60)
            try:
                print(client.shell(command).decode(), end='')
            except TimeoutError:
                logging.info('Shell command timed out: %s' % client.id)
                # Prompt user if they want to increase the timeout limit
                if increase_timeout_prompt():
                    # Indefinitely block for output
                    client.conn.settimeout(None)
                    print(client.read().decode(), end='')
            finally:
                # Set timeout back to default
                client.conn.settimeout(socket.getdefaulttimeout())

    def python_cli(self, client: Client) -> None:
        """ Open a python interpreter to client """
        logging.debug('Launched python interpreter')
        while True:
            command = input('>>> ')

            if command.strip().lower() in ['exit', 'exit()']:
                break

            # Increase timeout to 60 seconds for python interpreter
            client.conn.settimeout(60)
            try:
                print(client.python(command).decode(), end='')
            except TimeoutError:
                logging.info('Python command timed out: %s' % client.id)
                # Prompt user if they want to increase the timeout limit
                if increase_timeout_prompt():
                    # Indefinitely block for output
                    client.conn.settimeout(None)
                    print(client.read().decode(), end='')
            finally:
                client.conn.settimeout(socket.getdefaulttimeout())


if __name__ == '__main__':

    # Read certficate from file
    with open('cert.pem', 'rb') as file:
        cert = x509.load_pem_x509_certificate(file.read())

    # Read private key from file
    with open('key.pem', 'rb') as file:
        private_key = serialization.load_pem_private_key(file.read(), None)

    # Start server
    server = ServerCLI(cert, private_key)
    server.start(('localhost', 6969))

    # Get a client that connected
    client = server.connections_queue.get()
    print(client.id.encode())

    # Begin server CLI
    server.cli()
