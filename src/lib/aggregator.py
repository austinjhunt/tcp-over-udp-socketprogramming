from .utils import *
import logging
import couchdb
import time
from pyspark.sql import SparkSession, Row


class Aggregator:
    def __init__(self, verbose=False):
        self.setup_logging(verbose=verbose)
        # Use environment for couchdb connection
        self.couchdb_server = os.environ.get('COUCHDB_SERVER', 'localhost:5984')
        self.couchdb_user = os.environ.get('COUCHDB_USER', 'admin')
        self.couchdb_password = os.environ.get('COUCHDB_PASSWORD', '123456')
        self.couchdb_database = os.environ.get('COUCHDB_DATABASE', 'analytics')
        self.debug(
            f"Using DB Info:"
            f"SERVER:{self.couchdb_server}, "
            f"USER: {self.couchdb_user}, "
            f"Password: {self.couchdb_password}, "
            f"DB: {self.couchdb_database}")
        self.connect_couchdb()


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
        self.logger = logging.getLogger('Aggregator')
        formatter = logging.Formatter('%(prefix)s - %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.prefix = {'prefix': 'Aggregator'}
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

    def aggregate(self):
        """ Aggregate/get averages for response times stored in analytics DB by client
        (ack times with varying drop probabilities)"""

        try:
            db = self.couch.create(self.couchdb_database)
            self.debug(
                f"Successfully created new CouchDB database {self.couchdb_database}")
        except:
            db = self.couch[self.couchdb_database]
            self.debug(
                f"Successfully connected to existing CouchDB database {self.couchdb_database}")

        mapped = SparkSession.builder.appName("aggregatedTimeAnalysis")\
                .getOrCreate()\
                .createDataFrame(
                    Row(
                        time_to_ack=db.get(doc_id).get('time_to_ack'),
                        channel_sleep_v=db.get(doc_id).get('channel_sleep_v'),
                        channel_sleep_factor=db.get(doc_id).get('channel_sleep_factor'),
                        channel_p_drop_server=db.get(doc_id).get('channel_p_drop_server'),
                        channel_p_drop_client=db.get(doc_id).get('channel_p_drop_client'),
                    ) for doc_id in db
                )\
                .rdd.map(
                    lambda row: (
                        # Key
                        (
                            row.channel_p_drop_server,
                            row.channel_p_drop_client,
                            row.channel_sleep_v,
                            row.channel_sleep_factor
                        ),
                        # value
                        row.time_to_ack
                    )
                )
        reduced = mapped.aggregateByKey(
        zeroValue=(0, 0),
        # simultaneously calculate the SUM (the numerator for the
        # average that we want to compute), and COUNT (the
        # denominator for the average that we want to compute):
        seqFunc=lambda a, b: (a[0] + b,    a[1] + 1),
        combFunc=lambda a, b: (a[0] + b[0], a[1] + b[1]))\
        .mapValues(lambda v: v[0]/v[1]).collect()  # divide sum by count
        return reduced

    def save_lst_to_db(self, lst, db_name="aggregated_analytics"):
        """ save each record in a list to a database (specified with db name) """
        try:
            db = self.couch.create(db_name)
            self.debug(f"Successfully created new CouchDB database {db_name}")
        except:
            db = self.couch[db_name]
            self.debug(f"Successfully connected to existing CouchDB database {db_name}")
        self.debug(f'Preparing to save {len(lst)} items to database')
        fails = 0
        for msg in lst:
            try:
                jsonified_msg = {
                    'channel_sleep_v': msg[0][2],
                    'channel_sleep_factor': msg[0][3],
                    'channel_p_drop_server': msg[0][0],
                    'channel_p_drop_client': msg[0][1],
                    'avg_time_to_ack': msg[1]
                }
                db.save(jsonified_msg)
            except Exception as e:
                self.error(e)
                fails += 1
        self.debug("Saving completed")
        self.debug(f"Failed to send {fails} items")




    def run(self):
        """ Wait for a trigger ('complete' database creation) before trying to aggregate """
        while 'complete' not in self.couch:
            time.sleep(3)
            self.info(
                f'waiting for "complete" database to be created '
                f'before aggregating data in db {self.couchdb_database}')
        aggregated_results = self.aggregate()
        self.save_lst_to_db(aggregated_results, db_name='aggregated_analytics')