import socket       #Python socket library

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)    #Creates UDP socket


#server_address = socket.gethostbyname(socket.gethostname())  #Gets the host name of the current system
#server_port = 12000         #Server port

#server.bind(("",server_port))        #Binds the socket to the local port number 12000
server.bind(('localhost',1002))
server.listen()

client_socket, client_address = server.accept()

file = open('GODplzwork.bmp', "wb")
image_chunk = client_socket.recv(1000000)

while image_chunk:
    file.write(image_chunk)
    image_chunk = client_socket.recv(1000000)

    file.close()
    client_socket.close()

