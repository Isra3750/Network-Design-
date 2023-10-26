from rdt2_2 import *
import time

# Set arguement for RDT2_2 class for server side
rdtserver = RDTclass("127.0.0.1", "127.0.0.1", 45200, 45220, corruption_rate=20, option=[1])

print("Server - RDT2-2")

packet_data = None
while packet_data is None:
    # Recieve data from client side
    packet_data = rdtserver.recv()

    # Write to file called "output.bmp" 
    with open("output1.bmp", "wb") as file:
        for packet in packet_data:
            file.write(packet)

print("Completed!")
