import socket       #Python socket library
server_address = socket.gethostbyname(socket.gethostname())  #Gets the host name of the current system
server_port = 12000         #Server port
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    #Creates UDP socket
server_socket.bind(("",server_port))        #Binds the socket to the local port number 12000

while True:         #Constantly loops
    message, client_address = server_socket.recvfrom(12000)     #Reads the message from the UDP socket while also getting the client address
    modifiedMessage = message.decode().upper()      #Modifies the recieved message so it's all uppercase
    print("Server Echo: " + modifiedMessage)        #Prints out the modified message
    server_socket.sendto(modifiedMessage.encode(),client_address)   #Sends the modifed message back to the client
    print(client_address)           #Prints the client address