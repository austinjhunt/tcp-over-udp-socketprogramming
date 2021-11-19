from .utils import *
import socket
import time
import csv
import logging
import couchdb
from datetime import datetime

class Client:
    def __init__(self,
        channel_sleep_v=0.05,
        channel_sleep_factor=4,
        channel_p_drop_server=0,
        channel_p_drop_client=0,
        server_udp_ip='127.0.0.1', server_udp_port=5005,
        max_segment_size=12, timeout=1, verbose=False):

        self.setup_logging(verbose=verbose)
        # Save channel properties to include in data dump process
        self.channel_sleep_v = channel_sleep_v
        self.channel_sleep_factor = channel_sleep_factor
        self.channel_p_drop_client = channel_p_drop_client
        self.channel_p_drop_server = channel_p_drop_server

        self.client_state = States.CLOSED
        self.server_addr = (server_udp_ip, server_udp_port)
        self.max_segment_size = max_segment_size # max num bytes client can receive or send in single segment
        self.timeout = timeout

    def connect_couchdb(self):
        # couchdb connection
        self.debug(
            f'Connecting to CouchDB server at: http://{self.couchdb_user}:{self.couchdb_password}@{self.couchdb_server}/"')
        self.couch = couchdb.Server(
            f"http://{self.couchdb_user}:{self.couchdb_password}@{self.couchdb_server}/")
        # create the database if not existing, get the database if already existing
        try:
            self.db = self.couch.create(self.couchdb_database)
            self.debug(
                f"Successfully created new CouchDB database {self.couchdb_database}")
        except:
            self.db = self.couch[self.couchdb_database]
            self.debug(
                f"Successfully connected to existing CouchDB database {self.couchdb_database}")

    def database_exists(self, database):
        return database in self.couch

    def setup_logging(self, verbose):
        """ set up self.logger for producer logging """
        self.logger = logging.getLogger('Client')
        formatter = logging.Formatter('%(prefix)s - %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.prefix = {'prefix': 'Client'}
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

    def start(self):
        """ Start client by creating UDP socket and handshaking with server """
        self.debug(f'Starting client, connecting to server: {self.server_addr}')
        self.sock = socket.socket(socket.AF_INET,    # Internet
                            socket.SOCK_DGRAM)  # UDP
        self.sock.settimeout(self.timeout)
        self.handshake()

    def send_udp(self, message):
        """ Send a message over UDP """
        self.debug(f'Sending message over UDP: {message}')
        self.sock.sendto(message, self.server_addr)

    def handshake(self):
        if self.client_state == States.CLOSED:
            self.seq_num = rand_int()
            syn_header = Header(
                seq_num=self.seq_num,
                syn=1,
                mss=12
                )
            # for this case we send only header;
            # if you need to send data you will need to append it
            # Step 1, init handshake
            self.info("\nSENDING HANDSHAKE")
            self.debug(syn_header)
            self.send_udp(syn_header.bits())
            self.update_state(States.SYN_SENT)

            # wait for SYN-ACK from server (step 2)
            header, body, addr = self.recv_msg()
            self.debug("\nRECEIVED")
            self.debug(f'{header} {body} {addr}')
            if header.syn and header.ack: ## SYN-ACK
                self.update_state(States.SYNACK_RECEIVED)
                # Respond with ACK (step 3)
                self.seq_num = header.ack_num
                self.ack_num = header.seq_num + 1
                ack_header = Header(
                    ack=1,
                    seq_num=self.seq_num,
                    ack_num=self.ack_num
                    )
                self.debug("\nSENDING")
                self.debug(ack_header)
                self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
                self.sock.sendto(ack_header.bits(), self.server_addr)
                self.update_state(States.ACK_SENT)
                self.update_state(States.ESTABLISHED)
            else:
                self.debug('Not SYNACK')
        else:
            self.debug('Client state is not CLOSED; handshake already started or complete')

    def recv_msg(self):
        """ Receive a message and return header, body and addr; addr
        is used to reply to the client; this call is blocking """
        data, addr = self.sock.recvfrom(1024)
        header = bits_to_header(data)
        body = get_body_from_data(data)
        return (header, body, addr)

    def terminate(self):
        """ Terminate "TCP" connection using a 3 way handshake
        (client)FIN->(server)FINACK->(client)ACK """
        if self.client_state == States.ESTABLISHED:
            fin_header = Header(
                seq_num=self.seq_num,
                ack_num=self.ack_num,
                fin=1
            )
            self.debug("\nSENDING")
            self.debug(fin_header)
            self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
            self.send_udp(fin_header.bits())
            self.update_state(States.FIN_SENT)
            self.debug('Waiting for FINACK from server')
            header, body, addr = self.recv_msg()
            self.debug("\nRECEIVED")
            self.debug(f'{header} {body} {addr}')
            self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
            if header.ack == 1 and header.fin == 1:
                self.update_state(States.FINACK_RECEIVED)
                self.debug("Acknowledging FINACK (step 4)")
                self.seq_num = header.ack_num
                self.ack_num = header.seq_num + 1
                ack_header = Header(
                    seq_num=self.seq_num,
                    ack_num=self.ack_num,
                    ack=1,
                )
                self.debug("\nSENDING")
                self.debug(ack_header)
                self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
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
            self.debug(f'TIME_WAIT(remaining={wait_time}s)')
            time.sleep(1)
            wait_time -= 1
        self.debug('Closing socket')
        self.sock.close()

    def update_state(self, new_state):
        self.debug(f'{self.client_state} -> {new_state}')
        self.client_state = new_state

    def send_reliable_message(self, message):
        # For each chunk, save the time it takes to send and then receive acknowledgement
        chunk_acknowledgement_times = []
        # send messages
        # we loop/wait until we receive all ack.
        message_bytestring = str.encode(message)
        # split message into chunks of self.max_segment_size bytes
        chunks = [message_bytestring[i: i + self.max_segment_size] \
                    for i in range(0, len(message_bytestring), self.max_segment_size)]
        self.debug(f'Message "{message}" split into {len(chunks)} chunks')
        for chunk in chunks:
            header = Header(
                seq_num=self.seq_num,
                ack_num=self.ack_num,
                psh=1
            )
            full_message = header.bits() + chunk
            self.debug("\nSENDING (header and payload chunk)")
            self.debug(header)
            self.debug(chunk)
            self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
            successfully_sent_and_acknowledged = False
            attempts = 0
            start_time = time.time()
            while not successfully_sent_and_acknowledged:
                successfully_sent = False
                while not successfully_sent:
                    try:
                        self.send_udp(full_message)
                        successfully_sent = True
                    except socket.timeout as e:
                        # message drop
                        self.info('timeout while sending message, resending segment')

                try:
                    header, body, addr = self.recv_msg()
                    if header.ack:
                        # Only at this point has the message been
                        # successfully sent AND acknowledged
                        successfully_sent_and_acknowledged = True # exit outer while
                        end_time = time.time()
                        time_to_acknowledgement = end_time - start_time
                        chunk_acknowledgement_times.append(
                            {
                                'chunk': chunk.decode(),
                                'time_to_ack': time_to_acknowledgement,
                                'channel_sleep_v': self.channel_sleep_v,
                                'channel_sleep_factor': self.channel_sleep_factor,
                                'channel_p_drop_server': self.channel_p_drop_server,
                                'channel_p_drop_client': self.channel_p_drop_client,
                            }
                        )

                except socket.timeout as e:
                    self.info('timeout waiting for ACK, assume undelivered; restarting delivery for this chunk')
                    attempts += 1
                    if attempts >= 30: # 30 drops in a row very unlikely; server likely down
                        self.debug('Server no longer responding, closing connection')
                        self.sock.close()
                        self.server_alive = False
                        return

            self.debug("\nRECEIVED")
            self.debug(f'{header} {body} {addr}')
            self.debug(f'Current seq_num={self.seq_num}, ack_num={self.ack_num}')
            if header.ack:
                self.debug('PSH has been acknowledged')
                self.seq_num = header.ack_num
                self.ack_num = header.seq_num + 1

        return chunk_acknowledgement_times

    def dump_data_to_folder(self, folder_path, data):
        fname = f"{folder_path}/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        self.info(f"Dumping data to {fname}.csv")
        with open(f'{fname}','w') as f:
            writer = csv.DictWriter(f, fieldnames=['time_to_ack', 'chunk', 'channel_sleep_v', 'channel_sleep_factor', 'channel_p_drop_server', 'channel_p_drop_client'])
            writer.writeheader()
            writer.writerows(data)

    def dump_data_to_couchdb(self, data_lst):
        """ Dump a provided list of data to couchdb database using environment variables"""

        # Use environment for couchdb connection
        self.couchdb_server = os.environ.get('COUCHDB_SERVER', 'localhost:5984')
        self.couchdb_user = os.environ.get('COUCHDB_USER', 'admin')
        self.couchdb_password = os.environ.get('COUCHDB_PASSWORD', '123456')
        self.couchdb_database = os.environ.get('COUCHDB_DATABASE', 'database')
        self.debug(
            f"Using DB Info:"
            f"SERVER:{self.couchdb_server}, "
            f"USER: {self.couchdb_user}, "
            f"Password: {self.couchdb_password}, "
            f"DB: {self.couchdb_database}")
        self.connect_couchdb()

        try:
            db = self.couch.create(self.couchdb_database)
            self.debug(
                f"Successfully created new CouchDB database {self.couchdb_database}")
        except:
            db = self.couch[self.couchdb_database]
            self.debug(
                f"Successfully connected to existing CouchDB database {self.couchdb_database}")
        self.debug(f'Preparing to save {len(data_lst)} items to database')
        fails = 0
        for item in data_lst:
            try:
                db.save(item)
            except Exception as e:
                self.error(e)
                fails += 1
        self.debug("Saving completed")
        self.debug(f"Failed to save {fails} items")

if __name__ == "__main__":

        UDP_IP='127.0.0.1'
        UDP_PORT_CHANNEL=5007
        CLIENT_TIMEOUT = 3
        client = Client(
            server_udp_ip=UDP_IP,
            server_udp_port=UDP_PORT_CHANNEL,
            timeout=CLIENT_TIMEOUT
            )
        client.start()
        # we send a message
        # with open('client-send-cheeseipsum.txt','r') as f:
        #     content = f.read()
        #     chunk_acknowledgement_times = client.send_reliable_message(content)

        chunk_acknowledgement_times = client.send_reliable_message(
            "I have been trying to reach you about your car's extended warranty")
        with open('chunk-stats.csv','w') as f:
            writer = csv.DictWriter(f, fieldnames=['time_to_ack', 'chunk'])
            writer.writeheader()
            writer.writerows(chunk_acknowledgement_times)
        with open('client-stats.csv','w') as f:
            writer = csv.DictWriter(f, fieldnames=['channel_sleep_v', 'channel_sleep_factor', 'channel_p_drop_server', 'channel_p_drop_client'])
            writer.writeheader()
            writer.writerows(chunk_acknowledgement_times)
        avg_acknowledgment_time = sum([c['time_to_ack'] for c in chunk_acknowledgement_times]) / len(chunk_acknowledgement_times)
        client.info(f'Average acknowledgement time: {avg_acknowledgment_time}s')
        # we terminate the connection
        try:
            client.terminate()
        except OSError as e:
            client.error(e)

