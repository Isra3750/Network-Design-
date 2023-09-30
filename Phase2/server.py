from socket import *

# Create a UDP socket for server
serverSocket = socket(AF_INET, SOCK_DGRAM)

# Bind the socket to the server address and port num
serverSocket.bind(('127.0.0.1', 12000)) # use 192.168.1.22 (local ipv4) if there's 2 computer

# Open a file for writing the received image data
file = open('output.bmp', 'wb')

print('Checking...')
while True:
    # Receive data from the client, one packet at a time until END message
    data, client_address = serverSocket.recvfrom(1024)
    
    # If done, break out loop
    if data == b'END_OF_FILE':
        break

    # Write to file called output.bmp
    file.write(data)

print("Received from cilent port number " + str(client_address[1])) # Confirm recieved

# Close file and server socket
file.close() 
serverSocket.close()
