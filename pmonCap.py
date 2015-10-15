import argparse, os, socket, struct, sys, textwrap, time
	 
# USAGE: sudo python pmonCap.py [-h] -f FILE -d DESTINATION -t TRAINS -c CARS
#
# Coded using Python 2.7
#
# Author: Wladimir Cabral
# 	  wladimircabral@gmail.com
#
# This software is distributed under the MIT License: http://www.opensource.org/licenses/mit-license.php

# GLOBAL VARIABLES
MAX_HOPS = 30
TIMEOUT = 2
LOCOMOTIVE_SIZE = 1500
GROUP1_CAR_SIZE = 500
GROUP2_CAR_SIZE = 50
CABOOSE_SIZE = 44
ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0
ICMP_PROTOCOL_NUMBER = 1

# Prints to screen and to file
def printer(status, outputFile):
	print status
	outputFile.write(status+"\n")

# Returns the number of hops till destination. It's a variation of traceroute.
def hop_counter(dest_name, outputFile):
	dest_addr = socket.gethostbyname(dest_name) # destination address
	ttl = 1 # ttl initial value
	destinationReached = hopCountExceeded = False
	while not (destinationReached or hopCountExceeded):
		# Create a socket for receiving data
		recv_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, ICMP_PROTOCOL_NUMBER)
		recv_socket.settimeout(TIMEOUT) # set timeout
		# Create a socket for sending data
		send_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, ICMP_PROTOCOL_NUMBER)
		send_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl) # set ttl
		send_icmp_packet(send_socket, dest_name, 0, 'request') # send packet to destination
		curr_addr = None
		try: # Get the address from receiving messages
			_, curr_addr = recv_socket.recvfrom(512)
			curr_addr = curr_addr[0]
		except socket.error:
			pass
		finally: # Close sockets
			send_socket.close()
			recv_socket.close()
		if curr_addr == dest_addr: # check whether the address from current receiving message is actually the destination address
			destinationReached = True # destination reached
		else:
			ttl += 1
			if ttl > MAX_HOPS: # check whether hop count exceeded
				hopCountExceeded = True
	if destinationReached: # destination was successfully reached
		printer(str(ttl)+" hops till "+dest_name,outputFile)
		return ttl
	else: # destination could not be reached
		printer("Hop Count Exceeded!",outputFile)
		return -1

# Returns array of capacity estimates
def capacity_estimation(array1,array2, NUMBER_OF_CARS, output_file):
	cap_array = []
	for i in range (0,len(array1)): # for each pair of rtts
		rtt1 = array1[i] # pick i-th element from group 1 rtt
		rtt2 = array2[i] # pick i-th element from group 2 rtt
		cap = NUMBER_OF_CARS*(GROUP1_CAR_SIZE-GROUP2_CAR_SIZE)*8/(rtt1-rtt2) # calculates capacity
		printer(str(cap)+" bps", output_file)
		cap_array.append(cap)
	return cap_array		
	
# Returns end-link capacity
def capacity_calculator(destination_name, TTL1, TTL2, TTL3, NUMBER_OF_TRAINS, NUMBER_OF_CARS, output_file):
	i = 1 # number of trains initial value
	group1_rtt_array = []
	group2_rtt_array = []
	while i <= NUMBER_OF_TRAINS: # here we will send a packet train for each group to destination
		rtt1 = rtt2 = 0
		while rtt1 <= rtt2 or rtt2 == -1: # rrt1 must be greater than rtt2
			# GROUP 1
			rtt1 = send_packet_train(destination_name, TTL1, TTL2, TTL3, NUMBER_OF_CARS, 1, i, output_file) # sends packet train
			# GROUP 2
			rtt2 = send_packet_train(destination_name, TTL1, TTL2, TTL3, NUMBER_OF_CARS, 2, i, output_file) # sends packet train
		group1_rtt_array.append(rtt1)			
		group2_rtt_array.append(rtt2)
		group1_rtt_array.sort()
		group2_rtt_array.sort()
		printer("Iteration #"+str(i)+" - Capacity estimates:", output_file)
		cap_array = capacity_estimation(group1_rtt_array, group2_rtt_array, NUMBER_OF_CARS, output_file) # calculates capacity for each pair of rtts 
		i += 1
	capacity = cap_array[0] # returns the capacity value associated with the smallest pair of rtt values
	printer("\nEnd-link Capacity: "+str(capacity)+" bps", output_file)
	return capacity

# Sends packet train to destination. Returns rtt.
def send_packet_train(destination_name, TTL1, TTL2, TTL3, NUMBER_OF_CARS, GROUP_NUMBER, TRAIN_NUMBER, output_file):
	# Create a socket for receiving data
	recv_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, ICMP_PROTOCOL_NUMBER)
	recv_socket.settimeout(TIMEOUT) # set timeout
	# Create a socket for sending LOCOMOTIVE packet
	send_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, ICMP_PROTOCOL_NUMBER)
	send_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, TTL1) # set ttl
	send_icmp_packet(send_socket, destination_name, LOCOMOTIVE_SIZE, 'reply') # send LOCOMOTIVE packet to destination
	t0 = time.time() # register sending time
	# Set socket for sending CARS packets
	i = 1 # number of cars initial value
	while i <= NUMBER_OF_CARS:
		send_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, TTL2) # set ttl
		CAR_SIZE = GROUP1_CAR_SIZE if GROUP_NUMBER == 1 else GROUP2_CAR_SIZE
		send_icmp_packet(send_socket, destination_name, CAR_SIZE, 'reply') # send CAR packet to destination
		i += 1
	# Set socket for sending CABOOSE packet
	send_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, TTL3) # set ttl
	send_icmp_packet(send_socket, destination_name, CABOOSE_SIZE, 'request') # send CABOOSE packet to destination
	try:
		data = recv_socket.recv(1024) # Receive packet reply
		t1 = time.time() # register receiving time
		rtt = t1 - t0 # calculate rtt
	except:
		print sys.exc_info()[0]
		rtt = -1
		pass
	finally: # close sockets
		send_socket.close()
		recv_socket.close()
	printer("*GROUP #"+str(GROUP_NUMBER)+": Packet Train #"+str(TRAIN_NUMBER)+" --> RTT = "+str(rtt)+"s",output_file)
	return rtt

# Reads rtt from local file. Returns end-link capacity.
def rtt_file_reader(input_file, NUMBER_OF_TRAINS, NUMBER_OF_CARS, output_file):
	in_file = open(input_file) # Open file 
	i = 1 # number of groups initial value
	group1_rtt_array = []
	group2_rtt_array = []
	while i <= 2: # for each group
		printer("\n ========== GROUP #"+str(i)+" - RTTs: ========== \n",output_file)
		j = 1 # number of trains initial value
		while j <= NUMBER_OF_TRAINS: # for each packet train
			rtt = float(in_file.readline()) # read line (rtt) from file
			printer("*Packet Train #"+str(j)+" --> RTT = "+str(rtt)+"s",output_file) 
			if i == 1: # if group 1
				group1_rtt_array.append(rtt)
				group1_rtt_array.sort()
			else: # group 2
				group2_rtt_array.append(rtt)
				group2_rtt_array.sort()
			j += 1
		i += 1
	printer("\nCapacity estimates:", output_file)
	cap_array = capacity_estimation(group1_rtt_array, group2_rtt_array, NUMBER_OF_CARS, output_file) # calculates capacity for each pair of rtts
	capacity = cap_array[0] # returns the capacity value associated with the smallest pair of rtt values
	printer("\nEnd-link Capacity: "+str(capacity)+" bps", output_file)
	return capacity

# Calculates checksum.
def checksum(source_string):
	    sum = 0
	    countTo = (len(source_string)/2)*2
	    count = 0
	    while count<countTo:
		thisVal = ord(source_string[count + 1])*256 + ord(source_string[count])
		sum = sum + thisVal
		sum = sum & 0xffffffff
		count = count + 2

	    if countTo<len(source_string):
		sum = sum + ord(source_string[len(source_string) - 1])
		sum = sum & 0xffffffff

	    sum = (sum >> 16)  +  (sum & 0xffff)
	    sum = sum + (sum >> 16)
	    answer = ~sum
	    answer = answer & 0xffff

	    # Swap bytes
	    answer = answer >> 8 | (answer << 8 & 0xff00)

	    return answer

# Creates and sends icmp packet to destination.
def send_icmp_packet(my_socket, dest_name, packet_size, MESSAGE_TYPE):

	    # Check whether it's a Echo or Echo Reply Message
	    if MESSAGE_TYPE=='reply':
		icmp_echo_message = ICMP_ECHO_REPLY
	    else:
		icmp_echo_message = ICMP_ECHO_REQUEST

	    dest_addr  =  socket.gethostbyname(dest_name) # destination address

	    ID = os.getpid() & 0xFFFF

	    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
	    my_checksum = 0

	    # Make a dummy header with a 0 checksum.
    	    header = struct.pack("bbHHh", icmp_echo_message, 0, my_checksum, ID, 1)
	    headerSize = sys.getsizeof(header) - 1 # 44 bytes
	    if int(packet_size) >= headerSize: # Here we make sure packet_size = headerSize + data
	    	data = (packet_size - headerSize) * "Q"
	    else:
		data = ""

	    # Calculate the checksum on the data and the dummy header.
	    my_checksum = checksum(header + data)

	    # Now that we have the right checksum, we put that in. It's just easier
	    # to make up a new header than to stuff it into the dummy.
	    header = struct.pack(
		"bbHHh", icmp_echo_message, 0, socket.htons(my_checksum), ID, 1
	    )
	    packet = header + data
	    my_socket.sendto(packet, (dest_addr, 1)) # Port number is irrelevant for ICMP		

def main():

	# Creates a log dir if needed
	if not os.path.exists("./logs/"):
		os.makedirs("./logs/")

	# Gets current time
	localtime   = time.localtime()
	timeString  = time.strftime("%Y%m%d%H%M%S", localtime)

	# Creates a log file
	output = open("./logs/"+timeString+".out","w")

	# Writes time to log file
	timeString = time.strftime("%Y-%m-%d %H:%M:%S", localtime)
	printer("Started at "+timeString,output)

	# Parses the arguments
	parser = argparse.ArgumentParser(prog='sudo python main.py',
	formatter_class=argparse.RawDescriptionHelpFormatter, 
	description=textwrap.dedent(''' 
	===================== END-LINK CAPACITY CALCULATOR =====================

	Author: Wladimir Cabral
		wladimircabral@gmail.com

	*   This software is distributed under the MIT License: http://www.opensource.org/licenses/mit-license.php

	**  Coded using Python 2.7

	*** WARNING: You must have root permissions as this script uses ICMP packets.
	'''))
	parser.add_argument('-d','--destination', help='Destination IP address')
	parser.add_argument('-t','--trains',help='Number of packet trains (Default: 100)', default=100, type=int)
	parser.add_argument('-c','--cars',help='Number of car packets per train (Default: 100)', default=100, type=int)
	parser.add_argument('-f','--file',help='Input file', type=argparse.FileType('r'))
	args = parser.parse_args()

	DESTINATION_NAME = args.destination
	NUMBER_OF_TRAINS = args.trains
	NUMBER_OF_CARS = args.cars
	INPUT_FILE = args.file

	if INPUT_FILE: # check if input file is given
			# If so, no need to send probes as we read rtt values from it
			printer("\nI) Reading RTT values from file...\n", output)
			rtt_file_reader(INPUT_FILE.name, NUMBER_OF_TRAINS, NUMBER_OF_CARS, output)
	elif not DESTINATION_NAME: # otherwise, check if destination is given
		parser.error("No destination or input file. Please add either --destination or --file")
	else: # if destination is passed instead of input file then
		# I) Calculates number of hops till destination
		printer("\nI) Running traceroute...\n",output)
		K = hop_counter(DESTINATION_NAME, output)
		printer("\nDone!",output) 

		# II) Sends probes to destination
		printer("\nII) Sending groups of packet trains...\n",output)

		printer("TRAIN = LOCOMOTIVE + CARS + CABOOSE\n",output)
	
		printer("LOCOMOTIVE --> Length = 1500B | TTL = "+str(K-1)+" hops", output)
		printer("GROUP1 CAR --> Length = 500B  | TTL = "+str(K)+" hops", output)
		printer("GROUP2 CAR --> Length = 50B   | TTL = "+str(K)+" hops", output)
		printer("CABOOSE    --> Length = 44B   | TTL = "+str(K)+" hops", output)

		printer("\n# of TRAINS: "+str(NUMBER_OF_TRAINS),output)
		printer("# of CARS (PER TRAIN): "+str(NUMBER_OF_CARS)+"\n",output)

		capacity_calculator(DESTINATION_NAME, K-1, K, K, NUMBER_OF_TRAINS, NUMBER_OF_CARS, output)

	printer("\nDone!",output)
	output.close()

if __name__ == '__main__':
	main()