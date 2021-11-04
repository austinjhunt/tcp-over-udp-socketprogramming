# Computer Science 5283 Computer Networks 
## Programming Assignments 2 and 3 - Implementing "TCP" over UDP
### Goal: Implement a reliable protocol over UDP 
User Datagram Protocol (UDP) is a minimal protocol running over IP. In this assignment you will implement a reliable message protocol over UDP. The assignment is broken into two milestones, representing programming assignments numbered 2 and 3. You will emulate a subset of TCP protocol. Features to be implemented are: 
- Establish a connections
- Ordered data transfer
- Retransmission

### Scaffolding
Scaffolding code is provided in [client.py](scaffolding/client.py), [server.py](templates/server.py) and [utils.py](templates/utils.py). 


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
 