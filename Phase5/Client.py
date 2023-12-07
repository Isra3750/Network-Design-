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

# Set arguement for RDT2_2 class for server side, from instruction note (Phase 5.pdf):
# 1. Option 1 - No loss/bit-errors
# 2. Option 2 - ACK packet bit-error
# 3. Option 3 - Data packet bit-error
# 4. Option 4 - ACK packet loss
# 5. Option 5 - Data packet loss
client_side = RDTclass("127.0.0.1", 12002, "127.0.0.1", 12000, window_size=20, timeout=0.5, corruption_rate=5, loss_rate = 5, option=[3])

# Make packet from file named "sample.bmp"
packets = Make_Packet("sample.bmp")

print("Client - RDT2-2")

start_time = time.time() # find start time

# send data(packets) to receiving socket
client_side.send(packets)

stop_time = time.time() # find stop time
elapsed_time = stop_time - start_time

print("\nTime taken: " + str(elapsed_time) + " sec")

print("Completed!")
