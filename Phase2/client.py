from socket import *

# Function to create packets from the image file
def Make_Packet(file):
    packet_size = 1024 # 1024 byte chunks
    packets = []
    while True:
        data = file.read(packet_size) # Seperate file into chunks base on packet size
        if not data:
            break
        packets.append(data)  # Append the data as a packet (1024b) into packets list
    return packets

# Create a UDP socket for client
clientSocket = socket(AF_INET, SOCK_DGRAM)
clientSocket.bind(('127.0.0.1', 12002))  # Bind the client socket to the client local address

# Server address and port
server_address = ('127.0.0.1', 12000)

# Open a file for reading the image data
file = open('sample.bmp', 'rb')

# Send packets to the server, for each packet in list, send one by one
print('Sending...')
for packet in Make_Packet(file):
    # Send data to the server
    clientSocket.sendto(packet, server_address)


# Send an end-of-transmission flag in byte
clientSocket.sendto(b'END_OF_FILE', server_address)
print('Done!')

# Close file and client socket
file.close()
clientSocket.close()
