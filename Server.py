from rdt2_2 import *
from datetime import datetime

# Set arguement for RDT2_2 class for server side
rdtserver = RDTclass("127.0.0.1", "127.0.0.1", 45200, 45220, corruption=40, option=[1])

print("Reciever - RDT2-2")

trails = []
packet_data = None
for i in range(10):
    print("DATA RECEIVING")
    start = datetime.now()
    while packet_data is None:
        # Recieve data from client side
        packet_data = rdtserver.recv()

        # Write to file called "output.bmp" 
        with open("output1.bmp", "wb") as file:
           for packet in packet_data:
               file.write(packet)
    packet_data = None
    end = datetime.now()
    trails.append(end - start)
    print("COMPLETED RECEIVING")

print("\nTrial Times")
for i in range(len(trails)):
    print(f"Trial {i}: {trails[i]}")
print("Completed")
