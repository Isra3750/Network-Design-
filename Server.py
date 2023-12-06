from RDTclass import *
import time

# Set arguement for RDT2_2 class for server side, from instruction note (Phase 4.pdf):
# 1. Option 1 - No loss/bit-errors
# 2. Option 2 - ACK packet bit-error
# 3. Option 3 - Data packet bit-error
# 4. Option 4 - ACK packet loss
# 5. Option 5 - Data packet loss
server_side = RDTclass("127.0.0.1", 50060, "127.0.0.1", 50040, 10, timeout=0.5, corruption=10, corruption_option=[1], loss=10, loss_option=[3])

print("Server - RDT2-2")

packet_data = None

# keep looping to listen for client send
while True:
    while packet_data is None:
        # Recieve data from client side
        packet_data = server_side.recv()

        # Write to file called "output.bmp" 
        with open("output1.bmp", "wb") as file:
            for packet in packet_data:
                file.write(packet)
    # Reset
    packet_data = None
    print("Completed...")

print("Completed!")