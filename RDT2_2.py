from random import *
from socket import *

debug = True
def debug_print(message):
    if debug:
        print(message)

class RDT2_2:
    ACK = 0x00  # 8-bit acknowledgment value
    packet_size = 1024

    def __init__(self, send_address, recv_address, send_port, recv_port, corruption=0, option=[1,2,3]):

        # Initialize the connection and configuration parameters
        self.send_address, self.recv_address = send_address, recv_address
        self.send_port, self.recv_port = send_port, recv_port
        self.corruption, self.option = corruption, option

        # Initialize FSM state and header size
        self._state, self._prev_state, self._header_size = 0, 1, 3

        # Create sender and receiver sockets
        self.send_sock = socket(AF_INET, SOCK_DGRAM)
        self.recv_sock = socket(AF_INET, SOCK_DGRAM)
        self.recv_sock.bind((self.recv_address, self.recv_port))

    def send(self, packets):
        # Inform the user about the total number of packets to be sent
        debug_print(f"RDT 2.2 - Total Number of Packets = {len(packets)}")

        # Create a header with the number of packets to be transmitted and send it
        header = len(packets).to_bytes(1024, 'big')
        self.send_sock.sendto(self.create_header(header, self._state), (self.send_address, self.send_port))

        while True:
            # Wait for acknowledgment and its associated state
            ack, state = self.ACK_recv()
            if ack and state == self._state:
                self.state_change()
                break
            debug_print("RDT 2.2: The State of The FSM Doesn't Match")

        packet_number = 0
        while packet_number < len(packets):
            # Inform the user about the packet being sent
            debug_print(f"RDT 2.2 - Sending Packet: {packet_number} of {len(packets) - 1}")

            # Send the packet
            self.send_sock.sendto(self.create_header(packets[packet_number], self._state),
                                  (self.send_address, self.send_port))

            if packet_number == (len(packets) - 1):
                # Turn off corruption for the last packet in the transmission
                self.corruption = 0

            ack, state = self.ACK_recv()
            if ack and state == self._state:
                self.state_change()
                packet_number = packet_number + 1
            else:
                debug_print("RDT 2.2 - The State of The FSM Doesn't Match")
        self.state_reset()

    def recv(self):
        packet_data, packet_number = [], 0
        while True:
            debug_print("RDT 2.2 - Receiving Packets")
            packet, address = self.recv_sock.recvfrom(1024 + self._header_size)
            header, data, checksum = self.split_packet(packet)
            data, checksum = int.from_bytes(data, 'big'), int.from_bytes(checksum, 'big')

            # Validate the packet and perform actions based on options
            if ((not (self.corruption_test() and 3 in self.option) or (1 in self.option)) and self.test_checksum(packet)):
                if header == self._state:
                    packet_count = data
                    debug_print(f"RDT 2.2 - Packets Received From Sender = {packet_count} Packets")
                    self.ACK_send(self._state)
                    self.state_change()
                    break
                else:
                    debug_print("RDT 2.2 - Packet With Mismatched State is Received.")
                    self.ACK_send(self._prev_state)
            else:
                debug_print("RDT 2.2 - Corrupted Packet is Received.")
                self.ACK_send(self._prev_state)
        while packet_number < packet_count:
            debug_print(f"RDT 2.2 - Receiving Packet {packet_number}/{packet_count - 1} From Sender")
            packet, address = self.recv_sock.recvfrom(self.packet_size + self._header_size)
            header, data, checksum = self.split_packet(packet)
            checksum = int.from_bytes(checksum, 'big')

            # Validate the packet and perform actions based on options
            if ((not (self.corruption_test() and 3 in self.option) or (1 in self.option)) and self.test_checksum(packet)):
                if header == self._state:
                    debug_print(f"RDT 2.2: Packet {packet_number} Received.")
                    packet_data.append(data)
                    packet_number = packet_number + 1
                    self.ACK_send(self._state)
                    self.state_change()
                else:
                    debug_print("RDT 2.2: Packet With Mismatched State is Received.")
                    self.ACK_send(self._prev_state)
            else:
                debug_print("RDT 2.2: Corrupted Packet is Received.")
                self.ACK_send(self._prev_state)
        self.state_reset()
        return packet_data

    def ACK_send(self, state):
        debug_print(f"RDT 2.2 - Sending ACK {state}")
        ack_packet = self.create_header(self.ACK.to_bytes(1, 'big'), state)
        self.send_sock.sendto(ack_packet, (self.send_address, self.send_port))

    def ACK_recv(self):
        received_packet, sender_address = None, None
        while received_packet is None:
            received_packet, sender_address = self.recv_sock.recvfrom(1024)
        header, data, checksum = self.split_packet(received_packet)

        # Validate the acknowledgment packet and perform actions based on options
        if ((not (self.corruption_test() and 2 in self.option) or (1 in self.option)) and self.test_checksum(
                received_packet)):
            if header == self._state and int.from_bytes(data, 'big') == self.ACK:
                debug_print("RDT 2.2 - ACK")
                return True, header
            elif header != self._state and int.from_bytes(data, 'big') == self.ACK:
                debug_print("RDT 2.2 - ACK With Unmatch")
                return True, header
            else:
                debug_print("RDT 2.2 - Non-ACK Response")
                return False, header
        else:
            debug_print("RDT 2.2 - Corrupted Packet")
            return False, header

    def create_header(self, packet, state):
        header = state.to_bytes(1, 'big')
        header_checksum = self.create_checksum(header + packet)
        header_packet = header + packet + header_checksum
        return header_packet

    def split_packet(self, packet):
        header = packet[0]
        data, checksum = packet[1:-2], packet[-2:]
        return header, data, checksum

    def state_change(self):
        # Toggle the FSM state between 0 and 1
        self._prev_state, self._state = self._state, self._prev_state

    def corruption_test(self):
        # Check if the packet should be considered corrupted based on the corruption rate
        return self.corruption >= randrange(1, 101)

    def state_reset(self):
        debug_print("RDT 2.2 - Resetting Process.")
        self._state = 0

    def create_checksum(self, packet, bits=16):
        # Calculate the checksum for the packet
        total = sum(int.from_bytes(packet[i:i + 2], 'big') for i in range(0, len(packet), 2))
        checksum = (total & ((1 << bits) - 1))
        checksum = ((1 << bits) - 1) ^ checksum
        return checksum.to_bytes(bits // 8, 'big')

    def test_checksum(self, packet):
        packet_data, packet_checksum = packet[:-2], packet[-2:]
        return packet_checksum == self.create_checksum(packet_data)