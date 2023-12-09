from RDTclass import *
import time

# Create a class for Go back In protocal with address and port number
server_side = RDTclass("127.0.0.1", "127.0.0.1", 12000, 12002)

# Print ready status
print("Server - Go-back-In")
print("Server ready...")

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

print("End of File")
