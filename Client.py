from rdt2_2 import *
import time

def Make_Packet(input_file):
        packets = [] # List to be returned
        packet_size = 1024 # 1024 byte chunk size

        # open a file, read one by one and appent to list
        with open(input_file, "rb") as file:
            while True: 
                packet = file.read(packet_size) # Read a chunk of data (1024 bytes) from the file
                if not packet: # If there is no more data to read, exit the loop
                    break
                packets.append(packet)  # Append the data as a packet (1024b) into packets list

        # return from function list with image chunks
        return packets

# Set arguement for RDT2_2 class for server side
rdtclient = RDTclass("127.0.0.1", "127.0.0.1", 45220, 45200, corruption_rate=20, option=[1])

# Make packet from file named "sample.bmp"
packets = Make_Packet("sample.bmp")

print("Client - RDT2-2")

start_time = time.time() # find start time

# send data(packets) to receiving socket
rdtclient.send(packets)

stop_time = time.time() # find stop time
elapsed_time = stop_time - start_time

print("\nTime taken: " + str(elapsed_time))

print("Completed!")
