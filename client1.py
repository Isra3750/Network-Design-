import socket       #Python socket library
#server_address = socket.gethostbyname(socket.gethostname())     #Gets the host name of the current system
#server_port = 12000         #Server port
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)    #Creates UDP socket
#client.connect((server_address, server_port))    #Connects to the server
client.connect(('localhost',1002))

file = open('sample.bmp', 'rb')
image_data=file.read(1000000)

while image_data:
    client.send(image_data)
    image_data = file.read(1000000)

file.close()
client.close()
