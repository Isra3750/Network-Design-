from rdt2_2 import *

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
rdtclient = RDT2_2("127.0.0.1", 45220, "127.0.0.1", 45200, 1024, corruption=20)

# Make packet from file named "sample.bmp"
packets = Make_Packet("sample.bmp")

print("Sender - RDT2-2")

# send data(packets) to receiving socket
rdtclient.send(packets)

print("Completed!")
