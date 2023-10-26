from socket import * # socket libary for server and client binding
from random import * # import randrange for corruption methods

# On / Off print statement, save time if off
debug = True
def debug_print(message):
    if debug:
        print(message)

class RDTclass:
    ACK = 0x00  # 8-bit ACK value, hexadecimal
    packet_size = 1024 # packet size of 1024 byte as default

    def __init__(self, send_address, recv_address, send_port, recv_port, corruption=0, option=[1,2,3]):
        # Initialize the connection and configuration parameters
        self.send_address, self.recv_address = send_address, recv_address
        self.send_port, self.recv_port = send_port, recv_port
        self.corruption, self.option = corruption, option

        # Initialize FSM state and header size
        self.Current_state, self.Prev_state, self.Header_size = 0, 1, 3

        # Create sender and receiver sockets
        self.send_sock = socket(AF_INET, SOCK_DGRAM)
        self.recv_sock = socket(AF_INET, SOCK_DGRAM)
        self.recv_sock.bind((self.recv_address, self.recv_port))

    def send(self, packets):
        # Inform the user about the total number of packets to be sent
        debug_print("RDT-class sender MSG: Amount of packet to be sent = " + str(len(packets)))

        # Create a header with the number of packets to be transmitted and send it
        packet_count = len(packets).to_bytes(1024, 'big')
        self.send_sock.sendto(self.create_header(packet_count, self.Current_state), (self.send_address, self.send_port))

        # Handshake, for the packet len
        while True:
            # Wait for acknowledgment and its associated state
            ack, state = self.ACK_recv()
            if ack and state == self.Current_state:
                self.state_change()
                break
            debug_print("RDT-class sender handshake MSG: Wrong current state, resending")

        packet_number = 0
        while packet_number < len(packets):
            # Inform the user about the packet being sent
            debug_print(f"RDT-class sender counting MSG: Sending packet number = " + str(packet_number) + " / " + str(len(packets) - 1))

            # Send the packet
            self.send_sock.sendto(self.create_header(packets[packet_number], self.Current_state), (self.send_address, self.send_port))

            ack, state = self.ACK_recv()
            if ack and state == self.Current_state:
                self.state_change()
                packet_number += 1
            else:
                debug_print("RDT-class sender counting MSG: Wrong current state, resending")
        # Reset state after all packet has been sent for next trail
        debug_print("RDT class MSG: Resetting state, ready to restart!")
        self.state_reset()

    def recv(self):
        packet_data, packet_number = [], 0
        while True:
            debug_print("RDT-class recv handhshake MSG: Receiving packet length...")

            # Unpack first packet
            packet, address = self.recv_sock.recvfrom(1024 + self.Header_size)
            SeqNum, data, checksum = self.split_packet(packet)
            data, checksum = int.from_bytes(data, 'big'), int.from_bytes(checksum, 'big') # Get int from bytes

            # Validate the packet and perform actions based on options
            if ((not ((self.corruption_test()) and (3 in self.option))) or (1 in self.option)) and self.test_checksum(packet):
                if SeqNum == self.Current_state:
                    # Get packet amount
                    packet_count = data
                    debug_print("RDT-class recv counting MSG: Received packet amount is " + str(packet_count))

                    # Send ACK with current state before switching state
                    self.ACK_send(self.Current_state)
                    self.state_change()
                    break
                else:
                    debug_print("RDT-class recv counting MSG: Received packet with wrong state")
                    self.ACK_send(self.Prev_state)
            else:
                debug_print("RDT-class recv counting MSG: Received corrupted packet")
                self.ACK_send(self.Prev_state)

        while packet_number < packet_count:
            debug_print("RDT-class recv counting MSG: Receiving packet number - " + str(packet_number) + " of " + str(packet_count - 1))

            # Unpack all packets -> SeqNum, data, cs
            packet, address = self.recv_sock.recvfrom(self.packet_size + self.Header_size)
            SeqNum, data, checksum = self.split_packet(packet)
            checksum = int.from_bytes(checksum, 'big') # unpack checksum to int, no need for data since data is appended to packet_data

            # Validate the packet and perform actions based on options
            if ((not ((self.corruption_test()) and (3 in self.option))) or (1 in self.option)) and self.test_checksum(packet):
                if SeqNum == self.Current_state:
                    # If not problem with packet, print current num, append, and shift to next packet
                    debug_print("RDT-class recv counting MSG: Received packet number - " + str(packet_number))
                    packet_data.append(data) 
                    packet_number += 1

                    # Send ACK with current state before switching state
                    self.ACK_send(self.Current_state)
                    self.state_change()
                else:
                    debug_print("RDT-class recv counting MSG: Received packet with wrong state")
                    self.ACK_send(self.Prev_state)
            else:
                debug_print("RDT-class recv counting MSG: Received corrupted packet")
                self.ACK_send(self.Prev_state)

        debug_print("RDT class MSG: Resetting state, ready to restart!")
        self.state_reset()
        return packet_data

    def ACK_send(self, state):
        debug_print(f"RDT-class ACK send MSG:  Sending ACK {state}")
        ack_packet = self.create_header(self.ACK.to_bytes(1, 'big'), state)
        self.send_sock.sendto(ack_packet, (self.send_address, self.send_port))

    def ACK_recv(self):
        received_packet, sender_address = None, None
        while received_packet is None:
            received_packet, sender_address = self.recv_sock.recvfrom(1024)
        SeqNum, data, checksum = self.split_packet(received_packet)

        # Validate the acknowledgment packet and perform actions based on options
        if ((not ((self.corruption_test()) and (2 in self.option))) or (1 in self.option)) and self.test_checksum(received_packet):
            if SeqNum == self.Current_state and int.from_bytes(data, 'big') == self.ACK:
                debug_print("RDT-class ACK recv MSG: Recieved ACK")
                return True, SeqNum
            elif SeqNum != self.Current_state and int.from_bytes(data, 'big') == self.ACK:
                debug_print("RDT-class ACK recv MSG: Recieved ACK with wrong state")
                return True, SeqNum
            else:
                debug_print("RDT-class ACK recv MSG: Recieved Unknown response")
                return False, SeqNum
        else:
            debug_print("RDT-class ACK recv MSG: Corrupted ACK Packet")
            return False, SeqNum

    def create_header(self, packet, state):
        SeqNum = state.to_bytes(1, 'big')
        header_checksum = self.create_checksum(SeqNum + packet)
        header_packet = SeqNum + packet + header_checksum
        return header_packet

    def split_packet(self, packet):
        SeqNum = packet[0]
        data, checksum = packet[1:-2], packet[-2:]
        return SeqNum, data, checksum

    def corruption_test(self):
        # Return chance that packet is corrupted, True if not corrupted, False if corrupted
        return self.corruption >= randrange(1, 101)

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
        self.Prev_state, self.Current_state = self.Current_state, self.Prev_state

    def state_reset(self):
        # Reset State
        self.Current_state = 0

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
