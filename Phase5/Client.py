from RDTclass import *
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

# Create a class for Go back In protocal with address and port number
client_side = RDTclass("127.0.0.1", "127.0.0.1", 12002, 12000)

# Make packet from file named "sample.bmp"
packets = Make_Packet("sample.bmp")

print("Client - Go-back-In")

start_time = time.time() # find start time

# send data(packets) to receiving socket
client_side.send(packets)

stop_time = time.time() # find stop time
elapsed_time = stop_time - start_time

print("\nTime taken: " + str(elapsed_time) + " sec")

print("Completed!")
