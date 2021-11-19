# Implementing a Reliable "Stop-and-Wait" Protocol Over UDP (and testing it with an automated framework)
## Built for Vanderbilt University CS 5283 Computer Networks - Programming Assignments 2 and 3 - Implementing "TCP" over UDP
### Goal: Implement a reliable protocol over UDP
User Datagram Protocol (UDP) is a minimal protocol running over IP. In this assignment you will implement a reliable message protocol over UDP. The assignment is broken into two milestones, representing programming assignments numbered 2 and 3. You will emulate a subset of TCP protocol. Features to be implemented are:
- Establish a connections
- Ordered data transfer
- Retransmission

### Tools Used
* Apache Spark
* CouchDB
* Docker-Compose, Docker
* Socket Programming

### Usage Without Docker
All of the main components in the architecture (client, server, channel, aggregator) are controlled via the [driver](src/driver.py). The following outlines the usage of the driver.

```
(venv) huntaj-imac:src huntaj$ python driver.py -h
usage: driver for TCP over UDP simulation [-h] [-c] [-upc UDP_PORT_CHANNEL]
                                          -sleepv CHANNEL_SLEEP_V -sleepf
                                          CHANNEL_SLEEP_FACTOR -pds
                                          P_DROP_SERVER -pdc P_DROP_CLIENT
                                          [-cli] [-sip SERVER_UDP_IP]
                                          [-sport SERVER_UDP_PORT]
                                          [-mss MAX_SEGMENT_SIZE]
                                          [-to TIMEOUT] [-f MSG_FILE]
                                          [-m MSG_STRING] [-d DUMP_FOLDER]
                                          [-cdb] [-srv] [-v] [-agg]

optional arguments:
  -h, --help            show this help message and exit
  -c, --channel         create a channel
  -upc UDP_PORT_CHANNEL, --udp_port_channel UDP_PORT_CHANNEL
                        port for binding socket for client <-> channel
                        communication
  -sleepv CHANNEL_SLEEP_V, --channel_sleep_v CHANNEL_SLEEP_V
                        small sleep: to reduce latency (can speed testing),
                        set as small as possible (~0.05); to test higher
                        latency channels, try ~0.25; required for all
                        components for data/stats logging purposes
  -sleepf CHANNEL_SLEEP_FACTOR, --channel_sleep_factor CHANNEL_SLEEP_FACTOR
                        max delay as multiple of sleep_v; do not set too high,
                        otherwise can cause timeouts; if you see client/server
                        timeouts, may need to adjust timeouts in your
                        client/server; recommended client timeout: ~3s with
                        these default parameters; required for all components
                        for data/stats logging purposes
  -pds P_DROP_SERVER, --p_drop_server P_DROP_SERVER
                        probability of channel dropping an ACK from server to
                        client; required for all components for data/stats
                        logging purposes
  -pdc P_DROP_CLIENT, --p_drop_client P_DROP_CLIENT
                        probability of channel dropping a message from client
                        to server; required for all components for data/stats
                        logging purposes
  -cli, --client        create a "TCP" over UDP client
  -sip SERVER_UDP_IP, --server_udp_ip SERVER_UDP_IP
                        IP address of UDP server
  -sport SERVER_UDP_PORT, --server_udp_port SERVER_UDP_PORT
                        UDP Server port
  -mss MAX_SEGMENT_SIZE, --max_segment_size MAX_SEGMENT_SIZE
                        max number of bytes client can receive or send in
                        single segment
  -to TIMEOUT, --timeout TIMEOUT
                        socket timeout
  -f MSG_FILE, --msg_file MSG_FILE
                        optional with -cli; filename to read from to produce
                        message that gets sent to UDP server
  -m MSG_STRING, --msg_string MSG_STRING
                        optional with -cli; message to send "reliably" to UDP
                        server
  -d DUMP_FOLDER, --dump_folder DUMP_FOLDER
                        path to folder in which data (times for messages as
                        they relate to channel properties) should be written
                        by the client
  -cdb, --dump_couchdb  dump time data to couchdb; this depends on COUCHDB_*
                        environment variables COUCHDB_USER, COUCHDB_SERVER,
                        COUCHDB_PASSWORD, COUCHDB_DATABASE; only works with
                        --client
  -srv, --server        create a "TCP" over UDP server
  -v, --verbose         use verbose logging
  -agg, --aggregator    run an aggregator (reads from couchdb database using
                        COUCHDB_* environment variables to calculate average
                        time_to_ack for each combination of channel properties
                        (sleepv, sleepfactor, pdropserver, pdropclient) using
                        MapReduce
```
Execute the following commands from the `src` folder to create the respective components.
#### Client
```
python driver.py --client --channel_sleep_v 0.05 --channel_sleep_factor 4 --p_drop_server 0 --p_drop_client 0 -m "Hello i am trying to send a message" --dump_folder timedata --server_udp_port 5007 --verbose
```

or, if you'd rather use file contents for a message instead of a string:

```
python driver.py --client --channel_sleep_v 0.05 --channel_sleep_factor 4 --p_drop_server 0 --p_drop_client 0 -f path/to/file/with/message --dump_folder timedata --server_udp_port 5007 --verbose
```
#### Server
```
python driver.py --server --server_udp_ip 127.0.0.1 --server_udp_port 5008 --verbose --channel_sleep_v 0.05 --channel_sleep_factor 4 --p_drop_server 0 --p_drop_client 0
```
#### Channel
```
python driver.py --channel --channel_sleep_v 0.05 --channel_sleep_factor 4 --p_drop_server 0 --p_drop_client 0 --udp_port_channel 5007 --verbose
```


### Usage with Docker (Recommended, Includes Analytics)
I've created a Docker image using [this Dockerfile](Dockerfile) that can be used to run a client, a server, a channel, or an aggregator. The [docker-compose.yml](docker-compose.yml) file defines a set of services (containers) that use that Docker image to run some performance tests.
#### How is it organized?
The docker compose file is ultimately split into 4 categories of services:
1. `no-drop-*` - this category contains a server, a client, and a channel that does not drop any messages
2. `quarter-drop-*` - this category contains a server and a client, and a channel configured with a 25% probability of dropping both client messages and server ACKs
3. `half-drop-*` - this category contains a server and a client, and a channel configured with a 50% probability of dropping both client messages and server ACKs
4. `threequarters-drop-*` - this category contains a server and a client, and a channel configured with a 75% probability of dropping both client messages and server ACKs

Each of those categories run simultaneously, where each category is a set of services whose intercommunication looks like: `client<->channel<->server`

Now, the client in each of those categories keeps a record of the channel properties (sleep_v, sleep_factor, p_drop_client, p_drop_server) and also keeps track of the time it takes to successfully send and receive acknowledgment of each message chunk (where max segment size is 12 bytes).

Then, once the full message has been "reliably" sent to the server through the lossy (or non-lossy) channel, the client saves all of those individual times to a CouchDB database (running as a single `couchdb` service/container).

Obviously, the client in the most lossy category (`threequarters-drop-*`) will take the longest amount of time to finish saving the data.

Once that happens, it is up to you to log into your CouchDB server's web GUI ([http://localhost:5984](http://localhost:5984)) using the credentials you can find in the [docker-compose file](docker-compose.yml), and simply **create a database called 'complete'**.

The existence of this new `complete` database on the CouchDB server will **trigger** the `aggregator` service to aggregate the data collected by all of the clients using Map Reduce via Apache Spark.

In short, for each unique tuple of channel properties `(sleep_v, sleep_factor, p_drop_client, p_drop_server)`, the aggregator writes the average time to acknowledgement to a new database called `aggregated_analytics`.

#### Steps to Execute
1. `docker-compose up -d` from project root
2. Wait for a little while, monitor container logs with:
   1. `docker logs no-drop-client`
   2. `docker logs quarter-drop-client`
   3. `docker logs half-drop-client`
   4. `docker logs threequarters-drop-client`
3. When you see output that looks like:
```
Client - Using DB Info:SERVER:couchdb:5984, USER: admin, Password: 987456321, DB: analytics
Client - Connecting to CouchDB server at: http://admin:987456321@couchdb:5984/"
Client - Successfully connected to existing CouchDB database analytics
Client - Successfully connected to existing CouchDB database analytics
Client - Preparing to save 138 items to database
Client - Saving completed
Client - Failed to save 0 items
```
for the `threequarters-drop-client` service (the client using the most lossy channel), then you can log into the CouchDB web GUI and create the `completed` database to trigger the aggregation.
4. Then, you can look at the aggregator logs to verify that it is running: `docker logs aggregator`
   1. You will notice that the logs contain a lot of these lines while the aggregator waits on the creation of the 'complete' database in CouchDB:
```
Aggregator - waiting for "complete" database to be created before aggregating data in db analytics
Aggregator - waiting for "complete" database to be created before aggregating data in db analytics
Aggregator - waiting for "complete" database to be created before aggregating data in db analytics
Aggregator - waiting for "complete" database to be created before aggregating data in db analytics
Aggregator - waiting for "complete" database to be created before aggregating data in db analytics
Aggregator - waiting for "complete" database to be created before aggregating data in db analytics
Aggregator - waiting for "complete" database to be created before aggregating data in db analytics
```
5. Once you trigger the aggregator, give it a few moments and then go back to the CouchDB web GUI to see the contents of the new `aggregated_analytics` database, a product of Map Reduce and Apache Spark.