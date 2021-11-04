from enum import Enum
import random

DEBUG = True

# Extend the possible states based on your implementation
# Refer TCP protocol
class States(Enum):
	CLOSED, LISTEN, SYN_RECEIVED, SYN_SENT, TIME_WAIT = range(1, 6)

class Header:
	def __init__(self, seq_num, ack_num, syn, ack):
		self.seq_num = seq_num
		self.ack_num = ack_num
		self.syn = syn
		self.ack = ack

	def __str__(self): 
		return pretty_bits_print(self.bits().decode())

	def bits(self):
		""" Get the bits representation of the header """
		bits = '{0:032b}'.format(self.seq_num)
		bits += '{0:032b}'.format(self.ack_num)
		bits += '{0:01b}'.format(self.syn)
		bits += '{0:01b}'.format(self.ack)
		bits += '{0:030b}'.format(0)
		if (DEBUG):
			print(pretty_bits_print(bits))
		return bits.encode()

def bits_to_header(bits):
	""" Convert bits to an instance of Header """
	bits = bits.decode()
	seq_num = int(bits[:32], 2)
	ack_num = int(bits[32:64], 2)
	syn = int(bits[64], 2)
	ack = int(bits[65], 2)
	return Header(seq_num, ack_num, syn, ack)

 
def get_body_from_data(data):
	""" 
	Returns the bits beyond the first 12 bytes
	If your header is 12 bytes (96 bits), it returns the body of a message
	"""
	data = data.decode()
	return data[96:]

 
def pretty_bits_print(bits):
	""" Used for debugging; pretty prints header of a message """
	seq_num = bits[:32]
	ack_num = bits[32:64]
	row_3 = bits[64:]
	output = [seq_num+" : seq_num = {0}".format(int(seq_num,2))]
	output.append(ack_num+" : ack_num = {0}".format(int(ack_num,2)))
	output.append(row_3+" : syn = {0}, ack = {1}".format(row_3[0], row_3[1]))
	return '\n'.join(output)

 
def rand_int(power=5):
	""" We rather using small values for number generation
	to make it easier to keep track of for the assignment.
	Random integer between 0 and default of 31, inclusive
	"""
	return random.randint(0, (2 ** power)-1)
