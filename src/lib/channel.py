
import threading
import random
import socket
import time
import logging
from .utils import *

class Channel:
    def __init__(self,
        verbose=False,
        udp_ip='127.0.0.1',
        udp_port_channel=5007,
        udp_port_server=5008,
        sleep_v=0.05,
        sleep_factor=4,
        p_drop_server=0,
        p_drop_client=0):
        self.udp_ip = udp_ip
        self.udp_port_channel = udp_port_channel
        self.udp_port_server = udp_port_server
        self.sleep_v = sleep_v
        self.sleep_factor = sleep_factor
        self.p_drop_client = p_drop_client
        self.p_drop_server = p_drop_server

        self.setup_logging(verbose=verbose)
        # socket for client <-> channel communication
        self.sock_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
        # self.sock_client.bind((self.udp_ip, self.udp_port_channel))
        self.sock_client.bind(('', self.udp_port_channel ))

        # socket for channel <-> server communication
        self.sock_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP

        # timeouts to prevent socket recvs from potentially hanging
        self.sock_client.settimeout(3.0)
        self.sock_server.settimeout(3.0)

        # used to terminate threads if needed (on ctrl+c, etc.)
        self.event_terminate = threading.Event()
        self.round = 0 # used for some startup synchronization
        self.event_wait_send = threading.Event() # used for some recurring synchronization ordering sends/recvs
        self.teardown_started = False # flag used to not drop messages once teardown has started
        self.round_startup = 2 # number of rounds of communication to wait before dropping messages (so connection is established)
        self.addr_client = [] # client address information, used so channel can send back to client
        self.server_ack_drop_count = 0
        self.client_msg_drop_count = 0

    def setup_logging(self, verbose):
        """ set up self.logger for producer logging """
        self.logger = logging.getLogger('Channel')
        formatter = logging.Formatter('%(prefix)s - %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.prefix = {'prefix': 'Channel'}
        self.logger.addHandler(handler)
        self.logger = logging.LoggerAdapter(self.logger, self.prefix)
        if verbose:
            self.logger.setLevel(logging.DEBUG)
            self.logger.debug('Debug mode enabled', extra=self.prefix)
        else:
            self.logger.setLevel(logging.INFO)

    def debug(self, msg):
        self.logger.debug(msg, extra=self.prefix)

    def info(self, msg):
        self.logger.info(msg, extra=self.prefix)

    def error(self, msg):
        self.logger.error(msg, extra=self.prefix)

    def chan_client(self):
        while True:
            if self.event_terminate.is_set():
                self.info("self.event_terminate is set; break from loop")
                break

            self.info('waiting on client')

            try:
                data_client, self.addr_client = self.sock_client.recvfrom(1024)
            except socket.timeout:
                # this was not needed on python 3.8+
                # on python 3.7.x, this exception is needed to prevent hangs
                # probably a concurrency bug or relationship of timeout values
                # in client/server implementations
                # for this case, the message truly is lost, but
                # if client/server implement reliable transfer
                # (e.g., stop and wait), should be okay (was in our solution
                # at least tested with 50% message/ack loss probability
                # with success)
                # the same exception has been added on the server channel for the
                # same reasoning
                #
                # note: these timeouts can occur if enough msgs/acks are dropped in a row
                # but if client/server resend is working properly, should not matter
                self.error('EXCEPTION: client channel timeout, message lost')
                continue

            header = bits_to_header(data_client)

            channel_wait = random.uniform(self.sleep_v,self.sleep_factor * self.sleep_v)
            time.sleep(channel_wait)
            self.info(f"channel delaying client->server for {channel_wait}s")

            if header.fin == 1:
                self.teardown_started = True

            # drop messages randomly, after connection established
            # avoid dropping connection establishment and teardown messages
            if self.round >= self.round_startup and \
                (header.ack == 0 and header.syn == 0 and header.fin == 0) and \
                random.uniform(0.0,1.0) <= self.p_drop_client and \
                not self.teardown_started:

                self.info("DROPPING MESSAGE FROM CLIENT")
                self.client_msg_drop_count += 1
                continue

            self.info('channel forwarding to server')
            self.sock_server.sendto(data_client, (self.udp_ip, self.udp_port_server))
            time.sleep(self.sleep_v)

            # notify that server has sent without dropping, needed for ordering sends/receives, otherwise can hang
            self.event_wait_send.set()

    # server listener/sender, forwards server messages to client
    def chan_server(self):
        while True:
            if self.event_terminate.is_set():
                break

            self.info('waiting on server response (can hang if server does not resend)')

            # primitive synchronization
            # need to wait until initial client message sent
            # to server, otherwise socket from server
            # is not valid (so sock_server.recvfrom will error)
            self.event_wait_send.wait()

            self.event_wait_send.clear()

            try:
                data_server, addr_server = self.sock_server.recvfrom(1024)
            except socket.timeout:
                self.error('EXCEPTION: server channel timeout, message lost')
                continue

            header = bits_to_header(data_server)

            # drop messages randomly
            # avoids dropping connection establishment and teardown messages
            if self.round >= self.round_startup and \
                (header.ack == 1 and header.syn == 0 and header.fin == 0) and \
                    random.uniform(0.0,1.0) <= self.p_drop_server and \
                        not self.teardown_started:
                self.info("DROPPING ACK FROM SERVER")
                self.server_ack_drop_count += 1
                continue

            self.info(f'channel forwarding to client (addr = {self.addr_client[1]}')

            channel_wait = random.uniform(self.sleep_v, self.sleep_factor * self.sleep_v)
            time.sleep(channel_wait)
            self.info(f"channel delaying server->client for {channel_wait}s")

            self.sock_client.sendto(data_server, (self.addr_client[0], self.addr_client[1]))
            time.sleep(self.sleep_v)
            self.round = self.round + 1

    def run(self):
        t_client = threading.Thread(target=self.chan_client)
        t_server = threading.Thread(target=self.chan_server)
        t_client.start()
        time.sleep(2)
        t_server.start()
        # main loop for keeping client/server threads running and termination handling
        while True:
            try:
                time.sleep(5)
                self.info(f"round: {self.round} ongoing; waiting 5s (threads sampled faster)")
                self.info("") # newline

                if not t_client.is_alive() or not t_server.is_alive():
                    self.info("shutting down channel; client/server threads not running")
                    self.event_terminate.set()
                    break
            except Exception as e:
                self.error(e)
                self.event_terminate.set()
                break


