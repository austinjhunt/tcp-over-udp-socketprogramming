# Computer Science 5283 Computer Networks
## Programming Assignments 2 and 3 - Implementing "TCP" over UDP
### Goal: Implement a reliable protocol over UDP
User Datagram Protocol (UDP) is a minimal protocol running over IP. In this assignment you will implement a reliable message protocol over UDP. The assignment is broken into two milestones, representing programming assignments numbered 2 and 3. You will emulate a subset of TCP protocol. Features to be implemented are:
- Establish a connections
- Ordered data transfer
- Retransmission

### Milestone 1 (due 11/4/2021) - Programming Assignment 2
#### Requirements
##### Establish a Connection
Implement the TCP 3-way Handshake Protocol. Please refer to Connection establishment section as discussed in class, or e.g. here: [https://en.wikipedia.org/wiki/Transmission_Control_Protocol#Connection_establishment](https://en.wikipedia.org/wiki/Transmission_Control_Protocol#Connection_establishment)
- Server is waiting for a connection
- Client sends a SYN
- Server replies with SYN-ACK
- Client replies with ACK

##### Tear Down a Connection
Bonus: TIME_WAIT state implementation is bonus points. You won't lose points if you don't implement TIME_WAIT.


### Usage Without Docker
Execute the following commands from the `src` folder to create the respective components.
#### Client
`python driver.py --client --channel_sleep_v 0.05 --channel_sleep_factor 4 --p_drop_server 0 --p_drop_client 0 -m "Hello i am trying to send a message" --dump_folder timedata --server_udp_port 5007 --verbose`
or, if you'd rather use file contents for a message instead of a string:
`python driver.py --client --channel_sleep_v 0.05 --channel_sleep_factor 4 --p_drop_server 0 --p_drop_client 0 -f path/to/file/with/message --dump_folder timedata --server_udp_port 5007 --verbose`
#### Server
`python driver.py --server --server_udp_ip 127.0.0.1 --server_udp_port 5008 --verbose --channel_sleep_v 0.05 --channel_sleep_factor 4 --p_drop_server 0 --p_drop_client 0`
#### Channel
`python driver.py --channel --channel_sleep_v 0.05 --channel_sleep_factor 4 --p_drop_server 0 --p_drop_client 0 --udp_port_channel 5007 --verbose`


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