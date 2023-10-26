from RDT2_2 import *

# Sets argument for RDT2_2 class for server side
rdt_server = RDT2_2("127.0.0.1", "127.0.0.1", 45200, 45220, corruption=30, option=[3])

print("Receiver - RDT 2.2")

packet_data = None
while packet_data is None:
    # Receive data from client side
    packet_data = rdt_server.recv()

    # Write to file called "output.bmp"
    with open("output1.bmp", "wb") as file:
       for packet in packet_data:
           file.write(packet)

print("Completed")