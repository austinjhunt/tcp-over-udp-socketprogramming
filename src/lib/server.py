import socket
from .utils import *
import time
import logging

class Server:
    def __init__(self, time_wait_on_terminate=30, verbose=False):
        self.setup_logging(verbose=verbose)
        self.server_state = States.CLOSED
        self.sock = None
        self.time_wait_on_terminate = time_wait_on_terminate
        self.last_received_seq_num = None
        self.message_buffer = []

    def setup_logging(self, verbose):
        """ set up self.logger for producer logging """
        self.logger = logging.getLogger('Server')
        formatter = logging.Formatter('%(prefix)s - %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.prefix = {'prefix': 'Server'}
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

    def start(self, udp_ip, udp_port):
        self.debug(f'Starting server on {udp_ip}:{udp_port}')
        self.sock = socket.socket(socket.AF_INET,    # Internet
                                  socket.SOCK_DGRAM)  # UDP
        self.debug(f'Binding to ({udp_ip}, {udp_port})')
        # self.sock.bind((udp_ip, udp_port))
        self.sock.bind(('', udp_port))
        # the server runs in an infinite loop and takes
        # action based on current state and updates its state
        # accordingly
        # You will need to add more states, please update the possible
        # states in py file
        self.debug("Beginning infinite loop to listen for client connections")
        while True:
            if self.server_state == States.CLOSED:
                # we already started listening, just update the state
                self.update_server_state(States.LISTEN)
            elif self.server_state == States.LISTEN:
                # we are waiting for a message
                self.debug("Waiting for message...")
                header, body, addr = self.recv_msg()
                self.debug("\nRECEIVED")
                self.debug(f'{header} {body} {addr}')
                if header.syn == 1:
                    self.debug('SYN received, new handshake started by client')
                    self.update_server_state(States.SYN_RECEIVED)
                    self.seq_num = rand_int()
                    self.ack_num = header.seq_num + 1
                    # Update max segment size to reflect client value
                    self.max_segment_size = header.mss
                    syn_ack_header = Header(
                        seq_num=self.seq_num,
                        ack_num=self.ack_num,
                        syn=1,
                        ack=1
                    )
                    self.debug("\nSENDING")
                    self.debug(syn_ack_header)
                    self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                    self.sock.sendto(syn_ack_header.bits(), addr)
                    self.update_server_state(States.SYNACK_SENT)
                    self.last_received_seq_num = header.seq_num

            elif self.server_state == States.SYNACK_SENT:
                header, body, addr = self.recv_msg()
                self.debug("\nRECEIVED ")
                self.debug(f'{header} {body} {addr}')
                self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                if header.ack == 1:
                    self.update_server_state(States.ACK_RECEIVED)
                    self.update_server_state(States.ESTABLISHED)

            elif self.server_state == States.ESTABLISHED:
                # Listen for normal messages AND for FIN messages
                header, body, addr = self.recv_msg()
                self.debug("\nRECEIVED")
                self.debug(f'{header} {body} {addr}')
                self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                if header.fin == 1:
                    self.update_server_state(States.FIN_RECEIVED)
                    self.seq_num = header.ack_num
                    self.ack_num = header.seq_num + 1
                    fin_ack_header = Header(
                        seq_num=self.seq_num,
                        ack_num=self.ack_num,
                        ack=1,
                        fin=1
                    )
                    self.debug("\nSENDING")
                    self.debug(fin_ack_header)
                    self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                    self.sock.sendto(fin_ack_header.bits(), addr)
                    self.update_server_state(States.FINACK_SENT)

                elif header.psh == 1:
                    self.debug(f'Payload Length: {len(str.encode(body))}')
                    if header.seq_num == self.last_received_seq_num:
                        self.debug(f'Duplicate! seq_num {header.seq_num} matches previous seq num')
                    else:
                        self.message_buffer.append(body)
                        self.debug(f'Received message buffer: {self.message_buffer}')
                        with open('./server/received-full-msg.txt','w') as f:
                            f.writelines(self.message_buffer)
                    self.seq_num = header.ack_num
                    self.ack_num += len(str.encode(body))
                    with open(f'./server/received-seqnum-{header.seq_num}.txt','w') as f:
                        f.write(body)
                    # Keep sequence number at current value
                    # respond with ACK
                    ack_header = Header(
                        seq_num=self.seq_num,
                        ack_num=self.ack_num,
                        ack=1
                    )
                    self.debug("\nSENDING")
                    self.debug(ack_header)
                    self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                    self.sock.sendto(ack_header.bits(), addr)
                self.last_received_seq_num = header.seq_num

            elif self.server_state == States.FINACK_SENT:
                header, body, addr = self.recv_msg()
                self.seq_num = header.ack_num
                self.ack_num = header.seq_num + 1
                self.debug("\nRECEIVED")
                self.debug(f'{header} {body} {addr}')
                self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                if header.ack == 1:
                    self.update_server_state(States.ACK_RECEIVED)
                    self.debug('Completed 3-way termination')
                    self.update_server_state(States.TIME_WAIT)
                    self.time_wait()
                self.last_received_seq_num = header.seq_num

    def time_wait(self):
        """ Currently in TIME WAIT state ; wait 2 * Max Segment Lifetime then close socket,
        Assume Max Segment Lifetime is 5 seconds """
        max_segment_lifetime = 5
        wait_time = 2 * max_segment_lifetime
        while wait_time > 0 :
            self.debug(f'TIME_WAIT(remaining={wait_time}s)')
            time.sleep(1)
            wait_time -= 1
        self.debug('TIME WAIT over, can listen again')
        self.update_server_state(States.LISTEN)

    def update_server_state(self, new_state):
        """ Update the self.server_state attribute with new state"""
        self.debug(f'{self.server_state} -> {new_state}')
        self.server_state = new_state

    def recv_msg(self):
        """ Receive a message and return header, body and addr; addr
        is used to reply to the client; this call is blocking """
        data, addr = self.sock.recvfrom(1024)
        header = bits_to_header(data)
        body = get_body_from_data(data)
        return (header, body, addr)


if __name__ == "__main__":
    server = Server()
    UDP_PORT_SERVER = 5008
    server.start(udp_ip='127.0.0.1', udp_port=UDP_PORT_SERVER)