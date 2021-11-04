from multiprocessing import Value
from threading import Timer
from utils import States
import multiprocessing
import random
import socket
import time
import utils
import sys
from time import sleep

UDP_IP = "127.0.0.1"
UDP_PORT = 5005
MSS = 12 # maximum segment size

def send_udp(message):
  sock.sendto(message, (UDP_IP, UDP_PORT))

class Client:
  def __init__(self):
    self.client_state = States.CLOSED
    self.handshake()

  def handshake(self):
    if self.client_state == States.CLOSED:
      seq_num = utils.rand_int()
      syn_header = utils.Header(seq_num, 0, syn = 1, ack = 0)
      # for this case we send only header;
      # if you need to send data you will need to append it
      
      print('send handshake')
      
      send_udp(syn_header.bits())
      self.update_state(States.SYN_SENT)
      
#      sleep(1) # wait for startup of main thread
      self.last_received_ack = -1 # initialize last received ack
      self.receive_acks()

    else:
      pass

  def terminate(self):
    pass

  def update_state(self, new_state):
    if utils.DEBUG:
      print(self.client_state, '->', new_state)
    self.client_state = new_state

  def send_reliable_message(self, message):
    # send messages
    # we loop/wait until we receive all ack.
    pass

  # these two methods/function can be used receive messages from
  # server. the reason we need such mechanism is `recv` blocking
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
  def receive_acks_sub_process(self, s, lst_rec_ack_shared):
    if utils.DEBUG:
      print('subproc start in function')
    while True:
      recv_data, addr = s.recvfrom(1024)
      header = utils.bits_to_header(recv_data)
      if utils.DEBUG:
        print('received subproc header: ')
        print(header)
      if header.ack_num > lst_rec_ack_shared.value:
        lst_rec_ack_shared.value = header.ack_num
        if utils.DEBUG:
          print('subproc updated ack: ', lst_rec_ack_shared.value)

  def receive_acks(self):
    # Start receive_acks_sub_process as a process
    lst_rec_ack_shared = Value('i', self.last_received_ack)
    p = multiprocessing.Process(target=self.receive_acks_sub_process, args=(sock, lst_rec_ack_shared))
    p.start()
    # Wait for 1 seconds or until process finishes
    p.join(1)
    # If process is still active, we kill it
    if p.is_alive():
      p.terminate()
      p.join()
    # here you can update your client's instance variables.
    self.last_received_ack = lst_rec_ack_shared.value
    if utils.DEBUG:
      print('received: ', self.last_received_ack)
      print('shared variable: ', lst_rec_ack_shared)

# windows requires using this main check when working with the subprocess, otherwise Client object will 
# get recreated when using subprocess (causing potential issues with socket as well as received values), 
# should have worked on other (*nix) platforms though
if __name__ == "__main__":
  sock = socket.socket(socket.AF_INET,    # Internet
                     socket.SOCK_DGRAM) # UDP

  # we create a client, which establishes a connection
  client = Client()
  # we send a message
  client.send_reliable_message("This message is to be received in pieces")
  # we terminate the connection
  client.terminate()
