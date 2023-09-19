import socket       #Python socket library
server_address = socket.gethostbyname(socket.gethostname())     #Gets the host name of the current system
server_port = 12000         #Server port
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    #Creates UDP socket
client_socket.connect((server_address, server_port))    #Connects to the server

message = input('Message to be echoed: ')     #The message to be sent to the server
print("Client Message:",message)        #Prints out the message before sending it
client_socket.sendto(message.encode(),(server_address,server_port))     #Sends the message to the server
modifiedMessage,server_address=client_socket.recvfrom(12000)        #Recieves the modified message from the server
print("Server Echo:",modifiedMessage.decode())      #Prints out the message echoed back from the server
print(server_address)           #Prints the server address
