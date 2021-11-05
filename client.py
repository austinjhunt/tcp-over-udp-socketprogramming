from multiprocessing import Value
from utils import States
import multiprocessing
import socket
import time
import utils

class Client:
    def __init__(self, server_udp_ip='127.0.0.1', server_udp_port=5005, max_segment_size=12):
        self.client_state = States.CLOSED
        self.server_addr = (server_udp_ip, server_udp_port)
        self.max_segment_size = max_segment_size # max num bytes client can receive or send in single segment

    def start(self):
        """ Start client by creating UDP socket and handshaking with server """
        if utils.DEBUG:
            print(f'Starting client, connecting to server: {self.server_addr}')
        self.sock = socket.socket(socket.AF_INET,    # Internet
                            socket.SOCK_DGRAM)  # UDP
        self.sock.settimeout(1)
        self.handshake()

    def send_udp(self, message):
        """ Send a message over UDP """
        if utils.DEBUG:
            print(f'Sending message over UDP: {message}')
        self.sock.sendto(message, self.server_addr)

    def handshake(self):
        if self.client_state == States.CLOSED:
            self.seq_num = utils.rand_int()
            syn_header = utils.Header(
                seq_num=self.seq_num,
                syn=1,
                mss=12
                )
            # for this case we send only header;
            # if you need to send data you will need to append it
            # Step 1, init handshake
            print("\nSENDING HANDSHAKE")
            if utils.DEBUG:
                print(syn_header)
            self.send_udp(syn_header.bits())
            self.update_state(States.SYN_SENT)

            # wait for SYN-ACK from server (step 2)
            header, body, addr = self.recv_msg()
            if utils.DEBUG:
                print("\nRECEIVED")
                print(header, body, addr)
            if header.syn and header.ack: ## SYN-ACK
                self.update_state(States.SYNACK_RECEIVED)
                # Respond with ACK (step 3)
                self.seq_num = header.ack_num
                self.ack_num = header.seq_num + 1
                ack_header = utils.Header(
                    ack=1,
                    seq_num=self.seq_num,
                    ack_num=self.ack_num
                    )
                if utils.DEBUG:
                    print("\nSENDING")
                    print(ack_header)
                    print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                self.sock.sendto(ack_header.bits(), self.server_addr)
                self.update_state(States.ACK_SENT)
                self.update_state(States.ESTABLISHED)
            else:
                if utils.DEBUG:
                    print('Not SYNACK')
        else:
            if utils.DEBUG:
                print('Client state is not CLOSED; handshake already started or complete')

    def recv_msg(self):
        """ Receive a message and return header, body and addr; addr
        is used to reply to the client; this call is blocking """
        data, addr = self.sock.recvfrom(1024)
        header = utils.bits_to_header(data)
        body = utils.get_body_from_data(data)
        return (header, body, addr)

    def terminate(self):
        """ Terminate "TCP" connection using a 3 way handshake
        (client)FIN->(server)FINACK->(client)ACK """
        if self.client_state == States.ESTABLISHED:
            fin_header = utils.Header(
                seq_num=self.seq_num,
                ack_num=self.ack_num,
                fin=1
            )
            if utils.DEBUG:
                print("\nSENDING")
                print(fin_header)
                print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
            self.send_udp(fin_header.bits())
            self.update_state(States.FIN_SENT)
            if utils.DEBUG:
                print('Waiting for FINACK from server')
            header, body, addr = self.recv_msg()
            if utils.DEBUG:
                print("\nRECEIVED")
                print(header,body,addr)
                print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
            if header.ack == 1 and header.fin == 1:
                self.update_state(States.FINACK_RECEIVED)
                if utils.DEBUG:
                    print("Acknowledging FINACK (step 4)")
                self.seq_num = header.ack_num
                self.ack_num = header.seq_num + 1
                ack_header = utils.Header(
                    seq_num=self.seq_num,
                    ack_num=self.ack_num,
                    ack=1,
                )
                if utils.DEBUG:
                    print("\nSENDING")
                    print(ack_header)
                    print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                self.send_udp(ack_header.bits())
                self.update_state(States.ACK_SENT)
                self.update_state(States.TIME_WAIT)
                self.time_wait()

    def time_wait(self):
        """ Currently in TIME WAIT state ; wait 2 * Max Segment Lifetime then close,
        Assume Max Segment Lifetime is 5 seconds """
        max_segment_lifetime = 5
        wait_time = 2 * max_segment_lifetime
        while wait_time > 0 :
            if utils.DEBUG:
                print(f'TIME_WAIT(remaining={wait_time}s)')
            time.sleep(1)
            wait_time -= 1
        if utils.DEBUG:
            print('Closing socket')
        self.sock.close()

    def update_state(self, new_state):
        if utils.DEBUG:
            print(self.client_state, '->', new_state)
        self.client_state = new_state

    def send_reliable_message(self, message):
        # send messages
        # we loop/wait until we receive all ack.
        message_bytestring = str.encode(message)
        # split message into chunks of self.max_segment_size bytes
        chunks = [message_bytestring[i: i + self.max_segment_size] \
                    for i in range(0, len(message_bytestring), self.max_segment_size)]
        if utils.DEBUG:
            print(f'Message "{message}" split into {len(chunks)} chunks')
        for chunk in chunks:
            header = utils.Header(
                seq_num=self.seq_num,
                ack_num=self.ack_num,
                psh=1
            )
            full_message = header.bits() + chunk
            if utils.DEBUG:
                print("\nSENDING (header and payload chunk)")
                print(header)
                print(chunk)
                print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
            successfully_sent_and_acknowledged = False
            attempts = 0
            while not successfully_sent_and_acknowledged:
                successfully_sent = False
                while not successfully_sent:
                    try:
                        self.send_udp(full_message)
                        successfully_sent = True
                    except socket.timeout as e:
                        # message drop
                        print('timeout while sending message, resending segment')
                        self.send_udp(full_message)

                try:
                    header, body, addr = self.recv_msg()
                    if header.ack:
                        # Only at this point has the message been
                        # successfully sent AND acknowledged
                        successfully_sent_and_acknowledged = True # exit outer while
                except socket.timeout as e:
                    print('timeout waiting for ACK, assume undelivered; restarting delivery for this chunk')
                    attempts += 1
                    if attempts >= 10:
                        if utils.DEBUG:
                            print('Server no longer responding, closing connection')
                        self.sock.close()
                        self.server_alive = False
                        return

            if utils.DEBUG:
                print("\nRECEIVED")
                print(header,body,addr)
                print(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
            if header.ack:
                if utils.DEBUG:
                    print('PSH has been acknowledged')
                self.seq_num = header.ack_num
                self.ack_num = header.seq_num + 1



    # these two methods/function can be used to receive messages from
    # server. the reason we need such mechanism is `recv` is blocking
    # and we may never recieve a package from a server for multiple
    # reasons.
    # 1. our message is not delivered so server cannot send an ack.
    # 2. server responded with ack but it's not delivered due to
    # a network failure.
    # these functions provide a mechanism to receive messages for
    # 1 second, then the client can decide what to do, like retransmit
    # if not all packets are acked.
    # you are free to implement any mechanism you feel comfortable
    # especially, if you have a better idea ;)
    def receive_acks_sub_process(self, last_rec_ack_shared):
        while True:
            recv_data, addr = self.sock.recvfrom(1024)
            header = utils.bits_to_header(recv_data)
            if header.ack_num > last_rec_ack_shared.value:
                last_rec_ack_shared.value = header.ack_num

    def receive_acks(self):
        # Start receive_acks_sub_process as a process
        lst_rec_ack_shared = Value('i', self.last_received_ack)
        p = multiprocessing.Process(
            target=self.receive_acks_sub_process, args=(lst_rec_ack_shared,))
        p.start()
        # Wait for 1 seconds or until process finishes
        p.join(timeout=1)
        # If process is still active, we kill it
        if p.is_alive():
            p.terminate()
            p.join()
        # here you can update your client's instance variables.
        self.last_received_ack = lst_rec_ack_shared.value


# we create a client, which establishes a connection
client = Client()
client.start()
# we send a message
with open('client-send-cheeseipsum.txt','r') as f:
    content = f.read()
    client.send_reliable_message(content)

client.send_reliable_message("I have been trying to reach you about your car's extended warranty")
# we terminate the connection
client.terminate()
