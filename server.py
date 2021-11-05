import socket
import utils
from utils import States
import time
import os

class Server:
    def __init__(self, time_wait_on_terminate=30):
        self.server_state = States.CLOSED
        self.sock = None
        self.time_wait_on_terminate = time_wait_on_terminate
        os.mkdir(f'server-received-msgs/{id(self)}')

    def start(self, udp_ip, udp_port):
        if utils.DEBUG:
            print(f'Starting server on {udp_ip}:{udp_port}')
        self.sock = socket.socket(socket.AF_INET,    # Internet
                                  socket.SOCK_DGRAM)  # UDP
        self.sock.bind((udp_ip, udp_port))
        # the server runs in an infinite loop and takes
        # action based on current state and updates its state
        # accordingly
        # You will need to add more states, please update the possible
        # states in utils.py file
        if utils.DEBUG:
            print("Beginning infinite loop to listen for client connections")
        while True:
            if self.server_state == States.CLOSED:
                # we already started listening, just update the state
                self.update_server_state(States.LISTEN)
            elif self.server_state == States.LISTEN:
                # we are waiting for a message
                if utils.DEBUG:
                    print("Waiting for message...")
                header, body, addr = self.recv_msg()
                if utils.DEBUG:
                    print("\nRECEIVED")
                    print(header, body, addr)
                if header.syn == 1:
                    if utils.DEBUG:
                        print('SYN received, new handshake started by client')
                    self.update_server_state(States.SYN_RECEIVED)
                    self.seq_num = utils.rand_int()
                    self.ack_num = header.seq_num + 1
                    # Update max segment size to reflect client value
                    self.max_segment_size = header.mss
                    syn_ack_header = utils.Header(
                        seq_num=self.seq_num,
                        ack_num=self.ack_num,
                        syn=1,
                        ack=1
                    )
                    if utils.DEBUG:
                        print("\nSENDING")
                        print(syn_ack_header)
                        print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                    self.sock.sendto(syn_ack_header.bits(), addr)
                    self.update_server_state(States.SYNACK_SENT)

            elif self.server_state == States.SYNACK_SENT:
                header, body, addr = self.recv_msg()
                if utils.DEBUG:
                    print("\nRECEIVED ")
                    print(header, body, addr)
                    print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                if header.ack == 1 and header.syn == 0:
                    self.update_server_state(States.ACK_RECEIVED)
                    self.update_server_state(States.ESTABLISHED)

            elif self.server_state == States.ESTABLISHED:
                # Listen for normal messages AND for FIN messages
                header, body, addr = self.recv_msg()
                if utils.DEBUG:
                    print("\nRECEIVED")
                    print(header, body, addr)
                    print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                if header.fin == 1:
                    self.update_server_state(States.FIN_RECEIVED)
                    self.seq_num = header.ack_num
                    self.ack_num = header.seq_num + 1
                    fin_ack_header = utils.Header(
                        seq_num=self.seq_num,
                        ack_num=self.ack_num,
                        ack=1,
                        fin=1
                    )
                    if utils.DEBUG:
                        print("\nSENDING")
                        print(fin_ack_header)
                        print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                    self.sock.sendto(fin_ack_header.bits(), addr)
                    self.update_server_state(States.FINACK_SENT)

                elif header.psh == 1:
                    # increment acknowledgement number by length of payload
                    if utils.DEBUG:
                        print(f'Payload Length: {len(str.encode(body))}')
                    self.seq_num = header.ack_num
                    self.ack_num += len(str.encode(body))
                    with open(f'server-received-msgs/{id(self)}/seqnum-{self.seq_num}.txt','w') as f:
                        f.write(body)
                    # Keep sequence number at current value
                    # respond with ACK
                    ack_header = utils.Header(
                        seq_num=self.seq_num,
                        ack_num=self.ack_num,
                        ack=1
                    )
                    if utils.DEBUG:
                        print("\nSENDING")
                        print(ack_header)
                        print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                    self.sock.sendto(ack_header.bits(), addr)

            elif self.server_state == States.FINACK_SENT:
                header, body, addr = self.recv_msg()
                self.seq_num = header.ack_num
                self.ack_num = header.seq_num + 1
                if utils.DEBUG:
                    print("\nRECEIVED")
                    print(header, body, addr)
                    print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                if header.ack == 1:
                    self.update_server_state(States.ACK_RECEIVED)
                    if utils.DEBUG:
                        print('Completed 3-way termination')
                    self.update_server_state(States.TIME_WAIT)
                    self.time_wait()

    def time_wait(self):
        """ Currently in TIME WAIT state ; wait 2 * Max Segment Lifetime then close socket,
        Assume Max Segment Lifetime is 5 seconds """
        max_segment_lifetime = 5
        wait_time = 2 * max_segment_lifetime
        while wait_time > 0 :
            if utils.DEBUG:
                print(f'TIME_WAIT(remaining={wait_time}s)')
            time.sleep(1)
            wait_time -= 1
        if utils.DEBUG:
            print('TIME WAIT over, can listen again')
        self.update_server_state(States.LISTEN)

    def update_server_state(self, new_state):
        """ Update the self.server_state attribute with new state"""
        if utils.DEBUG:
            print(self.server_state, '->', new_state)
        self.server_state = new_state

    def recv_msg(self):
        """ Receive a message and return header, body and addr; addr
        is used to reply to the client; this call is blocking """
        data, addr = self.sock.recvfrom(1024)
        header = utils.bits_to_header(data)
        body = utils.get_body_from_data(data)
        return (header, body, addr)


if __name__ == "__main__":
    server = Server()
    server.start(udp_ip='127.0.0.1', udp_port=5005)