from RDT2_2 import *

def Make_Packet(input_file):
        packets = []  # Creates packet array
        packet_size = 1024  # 1024 byte chunk size

        # Opens file, then reads one by one and appends it to packets array
        with open(input_file, "rb") as file:
            while True:
                packet = file.read(packet_size)  # Read a chunk of data (1024 bytes) from the file
                if not packet:  # If there is no more data to read, exit the loop
                    break
                packets.append(packet)  # Append the data as a packet (1024b) into packets array

        # Return from function packets array with image chunks
        return packets

# Sets argument for RDT2_2 class for the server side
rdt_client = RDT2_2("127.0.0.1", "127.0.0.1", 45220, 45200, corruption=30, option=[3])

# Makes packet from file named "sample.bmp"
packets = Make_Packet("sample.bmp")

print("Sender - RDT 2.2")

# Sends data(packets) to receiver
rdt_client.send(packets)

print("Completed!")