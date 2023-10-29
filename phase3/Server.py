from RDTclass import *
import time

# Set arguement for RDT2_2 class for server side, from instruction note (Phase 3.pdf):
# 1. Option 1 - No loss/bit-errors
# 2. Option 2 - ACK packet bit-error
# 3. Option 3 - Data packet bit-error
rdtserver = RDTclass("127.0.0.1", "127.0.0.1", 12000, 12002, corruption_rate = 15, option = [1])

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
