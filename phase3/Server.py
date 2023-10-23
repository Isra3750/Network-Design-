from rdt2_2 import *

# Set arguement for RDT2_2 class for server side
rdtserver = RDT2_2("127.0.0.1", 45200, "127.0.0.1", 45220, corruption=30, option=[3])

print("Reciever - RDT2-2")

packet_data = None
while packet_data is None:
    # Recieve data from client side
    packet_data = rdtserver.recv()

    # Write to file called "output.bmp" 
    with open("output1.bmp", "wb") as file:
       for packet in packet_data:
           file.write(packet)

print("Completed")
