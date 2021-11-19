""" Driver for 'TCP' over UDP assignment; use driver to create either a server, a client or a channel """
import argparse
import logging
from pathlib import Path
import sys
from urllib import parse
from lib.channel import Channel
from lib.server import Server
from lib.client import Client
from lib.aggregator import Aggregator


class Driver:
    def __init__(self, verbose=False):
        self.setup_logging(verbose=verbose)

    def setup_logging(self, verbose):
        """ set up self.logger for producer logging """
        self.logger = logging.getLogger('Driver')
        formatter = logging.Formatter('%(prefix)s - %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.prefix = {'prefix': 'Driver'}
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser('driver for TCP over UDP simulation')
    ### CHANNEL OPTS ###
    parser.add_argument('-c', '--channel', action='store_true', help=(
        'create a channel'
    ))
    parser.add_argument('-upc','--udp_port_channel', type=int, default=5007,
        help='port for binding socket for client <-> channel communication')

    ### END CHANNEL OPTS ####

    ### REQUIRED FOR ALL (CHANNEL, SERVER, CLIENT) FOR LOGGING ###
    ### Want client/server to know properties about the channel so they can
    ### write CSV data that includes those properties; i.e. what does
    ### ACK response time look like when P_DROP_CLIENT = X? Can't know unless
    ### I, the client, know that probability.

    parser.add_argument('-sleepv', '--channel_sleep_v', type=float, default=0.05, required=True,
        help=(
            'small sleep: to reduce latency (can speed testing), '
            'set as small as possible (~0.05); to test higher latency channels, try ~0.25; '
            'required for all components for data/stats logging purposes'
            ))
    parser.add_argument('-sleepf', '--channel_sleep_factor', type=float, default=4, required=True,
        help=(
            'max delay as multiple of sleep_v; do not set too high, '
            'otherwise can cause timeouts; if you see client/server timeouts, '
            'may need to adjust timeouts in your client/server; recommended '
            'client timeout: ~3s with these default parameters; '
            'required for all components for data/stats logging purposes'
            ))
    parser.add_argument('-pds','--p_drop_server', type=float, default=0.0,required=True,
        help=(
            'probability of channel dropping an ACK from server to client; '
            'required for all components for data/stats logging purposes')
        )
    parser.add_argument('-pdc','--p_drop_client', type=float, default=0.0,required=True,
        help=(
            'probability of channel dropping a message from client to server; '
            'required for all components for data/stats logging purposes')
    )
    ### END REQUIRED FOR ALL ####

    ### CLIENT OPTS ####
    parser.add_argument('-cli', '--client', action='store_true', help=(
        'create a "TCP" over UDP client'
    ))
    parser.add_argument('-sip', '--server_udp_ip', default='127.0.0.1', type=str, help=(
        'IP address of UDP server'
    ))
    parser.add_argument('-sport', '--server_udp_port', default=5008, type=int, help=(
        'UDP Server port'
    ))
    parser.add_argument('-mss', '--max_segment_size', default=12, type=int, help=(
        'max number of bytes client can receive or send in single segment'
    ))
    parser.add_argument('-to', '--timeout', default=1, type=int, help=(
        'socket timeout'
    ))
    ### ONE OF THESE TWO REQUIRED FOR -cli ####
    parser.add_argument('-f', '--msg_file', type=str, help=(
        'optional with -cli; filename to read from to produce message that gets sent to UDP server'
    ))
    parser.add_argument('-m', '--msg_string', type=str, help=(
        'optional with -cli; message to send "reliably" to UDP server'
    ))
    parser.add_argument('-d', '--dump_folder', type=str, help=(
        'path to folder in which data (times for messages as they relate to channel properties) '
        'should be written by the client'
    ))

    parser.add_argument('-cdb', '--dump_couchdb', action='store_true', help=(
        'dump time data to couchdb; this depends on COUCHDB_* environment variables '
        'COUCHDB_USER, COUCHDB_SERVER, COUCHDB_PASSWORD, COUCHDB_DATABASE; only works with --client'
    ))
    ### END CLIENT OPTS ###

    ### SERVER OPTS ###
    parser.add_argument('-srv', '--server', action='store_true', help=(
        'create a "TCP" over UDP server'
    ))
    ### END SERVER OPTS ###
    parser.add_argument('-v', '--verbose', action='store_true', help=(
        'use verbose logging'
    ))


    ### Aggregator opts ####
    parser.add_argument('-agg', '--aggregator', action='store_true', help=(
        'run an aggregator (reads from couchdb database using COUCHDB_* environment variables '
        'to calculate average time_to_ack for each combination of channel properties '
        '(sleepv, sleepfactor, pdropserver, pdropclient) using MapReduce'
    ))
    ### End Aggregator opts ####


    args = parser.parse_args()


    driver = Driver(verbose=args.verbose)
    if args.aggregator:
        aggregator = Aggregator(verbose=args.verbose)
        # You need to manually create a database called "complete" in your
        # couchbase server in order to trigger the aggregator
        aggregator.run()

    elif args.channel:
        channel = Channel(
            verbose=args.verbose,
            udp_ip=args.server_udp_ip,
            udp_port_channel=args.udp_port_channel,
            udp_port_server=args.server_udp_port,
            sleep_v=args.channel_sleep_v,
            sleep_factor=args.channel_sleep_factor,
            p_drop_server=args.p_drop_server,
            p_drop_client=args.p_drop_client
            )
        channel.run()

    elif args.server:
        server = Server(verbose=args.verbose)
        server.start(
            udp_ip=args.server_udp_ip,
            udp_port=args.server_udp_port,
        )

    elif args.client:
        if not args.msg_string and not args.msg_file:
            raise argparse.ArgumentError(
                'You need to provide either a -f MSG_FILE or -m "MSG STRING" argument '
                'with -cli so that the client has a message to send'
            )
        elif args.msg_string:
            msg = args.msg_string
        elif args.msg_file:
            try:
                f = open(args.msg_file, 'r')
                msg = f.read()
                f.close()
            except Exception as e:
                driver.error(e)
                sys.exit(1)
        client = Client(
            channel_sleep_v=args.channel_sleep_v,
            channel_sleep_factor=args.channel_sleep_factor,
            channel_p_drop_server=args.p_drop_server,
            channel_p_drop_client=args.p_drop_client,
            server_udp_ip=args.server_udp_ip,
            server_udp_port=args.server_udp_port,
            max_segment_size=args.max_segment_size,
            timeout=args.timeout,
            verbose=args.verbose
        )
        client.start()
        data = client.send_reliable_message(msg)
        client.terminate()
        if args.dump_folder:
            Path(args.dump_folder).mkdir(parents=True, exist_ok=True)
            client.dump_data_to_folder(args.dump_folder, data)
        if args.dump_couchdb:
            client.dump_data_to_couchdb(data)


