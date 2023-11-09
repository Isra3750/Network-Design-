# RDTclass - phase 4 - network 4830, phase 4 change client (send and recv_ACK) side only

from socket import * # socket libary for server and client binding
from random import * # import randrange for corruption methods
from time import *

# On / Off print statement, save time if off (#1)
debug = True
def debug_print(message):
    if debug:
        print(message)

class RDTclass:
    def __init__(self, send_address, recv_address, send_port, recv_port, corruption_rate, option=[1, 2, 3, 4, 5]):
        self.ACK = 0x00 # 8-bit ACK value, hexadecimal
        self.packet_size = 1024 # packet size of 1024 byte as default

        # Initialize the connection and set parameters
        self.send_address, self.recv_address = send_address, recv_address
        self.send_port, self.recv_port = send_port, recv_port
        self.corruption_rate, self.option = corruption_rate, option

        # timer function
        self.start_time = 0
        self.end_time = 0

        # Initialize FSM state
        self.Cur_state, self.Prev_state = 0, 1

        # Create sender and receiver sockets
        self.send_sock = socket(AF_INET, SOCK_DGRAM)
        self.recv_sock = socket(AF_INET, SOCK_DGRAM)
        self.recv_sock.bind((self.recv_address, self.recv_port))

    def send(self, packets):
        # Print total amount of packet
        debug_print("RDT-class sender MSG: Amount of packet to be sent = " + str(len(packets)) + " packets")

        # Create a header with the number of packets to be sent
        packet_count = len(packets).to_bytes(1024, 'big')
        self.send_sock.sendto(self.create_header(packet_count, self.Cur_state), (self.send_address, self.send_port))

        # Handshake, for the packet len
        while True:
            # Wait for ACK and its associated state
            ack, state = self.ACK_recv()
            if ack and state == self.Cur_state:
                debug_print("RDT-class sender counting MSG: Starting loop")
                self.state_change()
                break
            debug_print("RDT-class sender handshake MSG: Handshake Resending...")

        packet_number = 0
        flag = True # Packet loss indication, True = No packet loss currently, False = Packet loss process
        while packet_number < len(packets):
            # Print total recieved packet amount, noted that packet number is plus one to simplify output log, although actual packet num has no plus one
            if flag:
                debug_print(f"RDT-class sender counting MSG: Sending packet number = " + str(packet_number + 1) + " / " + str(len(packets)))

            # Send the packet
            if flag == True:
                if ((self.is_packet_loss()) and (5 in self.option)): # databit packet loss
                    debug_print("RDT-class sender counting MSG: Data Packet loss!")
                    self.start_time = time() # start timer
                    flag = False # set to False to indicate packet loss
                elif ((self.is_packet_loss()) and (4 in self.option)): # ACK packet loss
                    debug_print("RDT-class sender counting MSG: ACK Packet loss!")
                    self.start_time = time() # start timer
                    flag = False # set to False to indicate packet loss
                else:
                    self.send_sock.sendto(self.create_header(packets[packet_number], self.Cur_state), (self.send_address, self.send_port))
                    self.start_time = time() # start timer

            # Stop timer
            self.end_time = time()
            if flag == False:
                debug_print("RDT-class sender counting MSG: Elasped Time - " + (str((self.end_time - self.start_time) * 1000)) + " ms")

            # resend packet if above 5 ms
            if (((self.end_time - self.start_time) * 1000) > 5):
                debug_print("RDT-class sender counting MSG: Timeout - resending current packet\n")
                self.send_sock.sendto(self.create_header(packets[packet_number], self.Cur_state), (self.send_address, self.send_port)) # Resend current packet
                flag = True
            
            if flag:
                ack, state = self.ACK_recv()

            if ack and state == self.Cur_state: # change current state if ACK is correct
                self.state_change()
                packet_number += 1
            else: # else loop
                if flag:
                    debug_print("RDT-class sender counting MSG: Resending...")

        # Reset state after all packet has been sent for next trail
        debug_print("RDT class MSG: Resetting state, ready to restart!")
        self.state_reset()

    def recv(self):
        packet_data= [] # data out

        # Loop until handshake is made
        while True:
            debug_print("RDT-class recv handhshake MSG: Receiving packet length...")

            # Unpack first packet
            packet, address = self.recv_sock.recvfrom(self.packet_size + 3) # 3 extra bytes for the header
            SeqNum, data, checksum = self.split_packet(packet)
            data, checksum = int.from_bytes(data, 'big'), int.from_bytes(checksum, 'big') # Get int from bytes
            

            # Validate the packet and perform else if based on options (#2)
            if not (self.is_Corrupted(packet)):
                # If packet is corrupted, resend ACK with different state
                debug_print("RDT-class recv counting MSG: Received corrupted data packet")
                self.ACK_send(self.Prev_state)
            else:
                # If packet is not corrupted, check state
                if (SeqNum == self.Cur_state):
                    # Get packet amount
                    packet_count = data
                    debug_print("RDT-class recv counting MSG: Received packet amount is " + str(packet_count) + " packets")

                    # Send ACK with current state before switching state
                    self.ACK_send(self.Cur_state)
                    self.state_change()

                    # Once validation is completed, break out of loop
                    break

                elif (SeqNum != self.Cur_state):
                    # If state is wrong, resend ACK with different state
                    debug_print("RDT-class recv counting MSG: Received packet with wrong state")
                    self.ACK_send(self.Prev_state)
        
        packet_number = 0
        while packet_number < packet_count:
            debug_print("RDT-class recv counting MSG: Receiving packet number - " + str(packet_number + 1) + " of " + str(packet_count))

            # Unpack all packets -> SeqNum, data, cs
            packet, address = self.recv_sock.recvfrom(self.packet_size + 3) # 3 extra bytes for the header
            SeqNum, data, checksum = self.split_packet(packet)
            checksum = int.from_bytes(checksum, 'big') # unpack checksum to int, no need for data since data is appended to packet_data

            # Validate the packet and perform else if based on options (#3)
            if not (self.is_Corrupted(packet)):
                # If packet is corrupted, resend ACK with different state
                debug_print("RDT-class recv counting MSG: Received corrupted data packet")
                self.ACK_send(self.Prev_state)
            else:
                if (SeqNum == self.Cur_state):
                    # If there's no problem with packet, print current num, append, and shift to next packet
                    debug_print("RDT-class recv counting MSG: Received packet number - " + str(packet_number + 1))
                    packet_data.append(data) 
                    packet_number += 1

                    # Send ACK with current state before switching state
                    self.ACK_send(self.Cur_state)
                    self.state_change()

                elif (SeqNum != self.Cur_state):
                    # If state is wrong, resend ACK with different state
                    debug_print("RDT-class recv counting MSG: Received packet with wrong state")
                    self.ACK_send(self.Prev_state)

        debug_print("RDT class MSG: Resetting state, ready to restart!")
        self.state_reset()
        return packet_data # output for server

    def ACK_send(self, state): # Send ACK (#5)
        debug_print("RDT-class ACK send MSG: Sending ACK" + str(state) + "\n")
        ACK_convert = self.ACK.to_bytes(1, 'big')
        ack_packet = self.create_header(ACK_convert, state) # Make header for ACK, seqNum, data (0x00), cs
        self.send_sock.sendto(ack_packet, (self.send_address, self.send_port)) 

    def ACK_recv(self):
        received_packet, sender_address = None, None
        while not received_packet:
            received_packet, sender_address = self.recv_sock.recvfrom(1024)
        SeqNum, data, checksum = self.split_packet(received_packet) # Split packet for ACK, seqNum, data (0x00), cs

        # Validate the ACK packet and else if based on options (#4)
        if not (self.is_ACK_Corrupted(received_packet)):
            # If ACK is corrupted return False with State
            debug_print("RDT-class ACK recv MSG: Corrupted ACK Packet")
            return False, SeqNum
        else:
            # If ACK is not corrupted return True with State
            if (SeqNum == self.Cur_state) and (int.from_bytes(data, 'big') == self.ACK):
                debug_print("RDT-class ACK recv MSG: Recieved ACK" + str(SeqNum) + "\n")
                return True, SeqNum
            elif (SeqNum != self.Cur_state) and (int.from_bytes(data, 'big') == self.ACK):
                debug_print("RDT-class ACK recv MSG: Recieved ACK with wrong state")
                return True, SeqNum
    
    def is_Corrupted(self, packet):
        # Conditional check for corruption and option selected
        packet_out = self.corrupt_packet(packet, self.corruption_rate)
        return (self.test_checksum(packet) and ((not ((self.corruption_test()) and (3 in self.option))) or (1 in self.option) or (4 in self.option) or (5 in self.option)))
    
    def is_ACK_Corrupted(self, packet):
        # Conditional check for ACK corruption and option selected
        packet_out = self.corrupt_packet(packet, self.corruption_rate)
        return (self.test_checksum(packet) and ((not ((self.corruption_test()) and (2 in self.option))) or (1 in self.option) or (4 in self.option) or (5 in self.option)))

    def create_header(self, packet, state):
        # Create header for packet
        SeqNum = state.to_bytes(1, 'big')
        header_checksum = self.create_checksum(SeqNum + packet)
        header_packet = SeqNum + packet + header_checksum
        return header_packet

    def split_packet(self, packet):
        # Parse header for packet
        SeqNum = packet[0]
        data, checksum = packet[1:-2], packet[-2:]
        return SeqNum, data, checksum

    def corruption_test(self):
        # Return chance that packet is corrupted, True if corrupted, False if not corrupted
        return self.corruption_rate >= randrange(1, 101)

    def is_packet_loss(self):
        # Return chance that packet is loss during transmission, True if loss, False if not loss
        return self.corruption_rate >= randrange(1, 101)

    def corrupt_packet(self, packet, corruption_rate):
        # Generate a random number between 1 and 100 to create a chance if corruption should happen or not.
        random_value = randrange(1, 101)

        if random_value <= corruption_rate:
            # Packet is corrupted, flip a random bit in the packet.
            position = randrange(len(packet))  # Choose a random position in the packet.
            byte_to_corrupt = packet[position]
            bit_position = randrange(8)  # Choose a random bit position within the byte.
            corrupted_byte = byte_to_corrupt ^ (1 << bit_position)
            # Replace the original byte with the corrupted byte.
            corrupted_packet = packet[:position] + bytes([corrupted_byte]) + packet[position + 1:]
            return corrupted_packet

        # If corruption doesn't occur, return the original packet.
        return packet
    
    def state_change(self):
        # Toggle the FSM state between 0 and 1
        self.Prev_state, self.Cur_state = self.Cur_state, self.Prev_state

    def state_reset(self):
        # Reset State
        self.Cur_state = 0

    def create_checksum(self, packet, bits=16):
        # Calculate the checksum for the packet, create 16-bit values
        total = sum(int.from_bytes(packet[i:i + 2], 'big') for i in range(0, len(packet), 2))

        # Apply bitwise AND operation, then invert with XOR operation
        checksum = (total & ((1 << bits) - 1))
        checksum = ((1 << bits) - 1) ^ checksum

        # Convert bit to byte and return
        return checksum.to_bytes(bits // 8, 'big')

    def test_checksum(self, packet):
        # Split data then return True/False base on checksum similarity
        packet_data, packet_checksum = packet[:-2], packet[-2:]
        return packet_checksum == self.create_checksum(packet_data)

## Useful Resources
## github.com/shihrer/csci466.project2/blob/master/RDT.py (debug_log function) (#1)
## github.com/CantOkan/BIL441_Computer_Networks/blob/master/RDT_Protocols/RDT2. (randint for corruption)

## Networks 5830 main - phase 3 - RDT class - (#2, #3, #4, #5 and method layout)
