import socket

# Create a UDP socket
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind the socket to the server address and port
serverSocket.bind(('127.0.0.1', 12000)) # use 192.168.1.22 (local ipv4) if there's 2 computer

# Open a file for writing the received image data
file = open('output.bmp', 'wb')

print('Checking...')
while True:
    # Receive data from the client, one packet at a time until END message
    image_chunk, client_address = serverSocket.recvfrom(1024)
    
    # When done, break out loop
    if image_chunk == b'END_OF_TRANSMISSION':
        break

    #Write to file
    file.write(image_chunk)

print("Received from cilent port number " + str(client_address[1])) #confirm recieve

# Close file and server socket
file.close() 
serverSocket.close()
