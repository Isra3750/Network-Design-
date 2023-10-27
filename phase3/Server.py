from RDTclass import *
import time

# Set arguement for RDT2_2 class for server side
rdtserver = RDTclass("127.0.0.1", "127.0.0.1", 45200, 45220, corruption_rate=15, option=[1])

print("Server - RDT2-2")

packet_data = None

# keep looping to listen for client send
while True:
    while packet_data is None:
        # Recieve data from client side
        packet_data = rdtserver.recv()

        # Write to file called "output.bmp" 
        with open("output1.bmp", "wb") as file:
            for packet in packet_data:
                file.write(packet)
    # Reset
    packet_data = None
    print("Completed...")

print("Completed!")
