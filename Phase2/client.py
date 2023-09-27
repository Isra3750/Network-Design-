import socket

# Function to create packets from the image file
def Make_Packet(file):
    packet_size = 1024
    packets = []
    while True:
        data = file.read(packet_size)
        if not data:
            break
        packets.append(data)  # Append the data as a packet (1024b) into packets list
    return packets

# Create a UDP socket for client
clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
clientSocket.bind(('127.0.0.1', 12002))  # Bind the client socket to the client local address

# Server address and port
server_address = ('127.0.0.1', 12000)

# Open a file for reading the image data
file = open('sample.bmp', 'rb')

# Send packets to the server, for each packet in list, send one by one
i = 0
print('Sending...')
for packet in Make_Packet(file):
    # Send data to the server
    clientSocket.sendto(packet, server_address)

    #print out current progress / byte
    print(str(i * 1024) + ' bytes')
    i = i + 1

# Send an end-of-transmission flag
clientSocket.sendto(b'END_OF_TRANSMISSION', server_address)
print('Done!')

# Close file and client socket
file.close()
clientSocket.close()
