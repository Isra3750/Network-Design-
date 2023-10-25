from random import randrange
from socket import *

debug = True
def debug_print(message):
    if debug:
        print(message)

class RDT2_2:
    ACK = 0x00  # 8-bit acknowledgment value
    def __init__(self, send_address, send_port, recv_address, recv_port, packet_size=1024, corruption=0, option=[1, 2, 3]):
        # Initialize the connection and configuration parameters
        self.send_address, self.recv_address = send_address, recv_address
        self.send_port, self.recv_port = send_port, recv_port
        self.packet_size, self.corruption, self.option = packet_size, corruption, option

        # Initialize FSM state and header size
        self._state, self._prev_state, self._header_size = 0, 1, 3

        # Create sender and receiver sockets
        self.send_sock = socket(AF_INET, SOCK_DGRAM)
        self.recv_sock = socket(AF_INET, SOCK_DGRAM)
        self.recv_sock.bind((self.recv_address, self.recv_port))

    def send(self, packets):
        # Inform the user about the total number of packets to be sent
        debug_print(f"RDT2_2 - packet count = {len(packets)}")

        # Create a header with the number of packets to be transmitted and send it
        header = len(packets).to_bytes(1024, 'big')
        self.send_sock.sendto(self._add_header(header, self._state), (self.send_address, self.send_port))

        while True:
            # Wait for acknowledgment and its associated state
            ack, state = self._recv_ack()
            if ack and state == self._state:
                self._change_state()
                break
            debug_print("RDT2_2: FSM STATE DOES NOT MATCH")

        packet_ide = 0
        while packet_ide < len(packets):
            # Inform the user about the packet being sent
            debug_print(f"RDT2_2 - Sending packet : {packet_ide}/{len(packets) - 1}")

            # Send the packet
            self.send_sock.sendto(self._add_header(packets[packet_ide], self._state),
                                  (self.send_address, self.send_port))

            if packet_ide == (len(packets) - 1):
                # Turn off corruption for the last packet in the transmission
                self.corruption = 0

            ack, state = self._recv_ack()
            if ack and state == self._state:
                self._change_state()
                packet_ide += 1
            else:
                debug_print("RDT2_2 - FSM STATE DOES NOT MATCH")
        self._reset()

    def recv(self):
        packet_data, packet_ide = [], 0
        while True:
            debug_print("RDT2_2 - Receiving packet count")
            packet, address = self.recv_sock.recvfrom(1024 + self._header_size)
            header, data, checksum = self._parse_packet(packet)
            data, checksum = int.from_bytes(data, 'big'), int.from_bytes(checksum, 'big')

            # Validate the packet and perform actions based on options
            if ((not (self._corrupted() and 3 in self.option) or (1 in self.option)) and self._verify_checksum(packet)):
                if header == self._state:
                    packet_cnt = data
                    debug_print(f"RDT2_2 - Packets that are receiving from sending process = {packet_cnt} packets")
                    self._send_ack(self._state)
                    self._change_state()
                    break
                else:
                    debug_print("RDT2_2 - Packet with mismatched State is received.")
                    self._send_ack(self._prev_state)
            else:
                debug_print("RDT2_2 - Corrupted packet is received.")
                self._send_ack(self._prev_state)
        while packet_ide < packet_cnt:
            debug_print(f"RDT2_2 - Receiving packet {packet_ide}/{packet_cnt - 1} from sending process")
            packet, address = self.recv_sock.recvfrom(self.packet_size + self._header_size)
            header, data, checksum = self._parse_packet(packet)
            checksum = int.from_bytes(checksum, 'big')

            # Validate the packet and perform actions based on options
            if ((not (self._corrupted() and 3 in self.option) or (1 in self.option)) and self._verify_checksum(packet)):
                if header == self._state:
                    debug_print(f"RDT2_2: Packet {packet_ide} Received.")
                    packet_data.append(data)
                    packet_ide += 1
                    self._send_ack(self._state)
                    self._change_state()
                else:
                    debug_print("RDT2_2: Packet with Mismatched State is Received.")
                    self._send_ack(self._prev_state)
            else:
                debug_print("RDT2_2: Corrupted Packet is Received.")
                self._send_ack(self._prev_state)
        self._reset()
        return packet_data

    def _send_ack(self, state):
        debug_print(f"RDT2_2 - Sending ACK {state}")
        ack_packet = self._add_header(self.ACK.to_bytes(1, 'big'), state)
        self.send_sock.sendto(ack_packet, (self.send_address, self.send_port))

    def _recv_ack(self):
        received_packet, sender_address = None, None
        while received_packet is None:
            received_packet, sender_address = self.recv_sock.recvfrom(1024)
        header, data, checksum = self._parse_packet(received_packet)

        # Validate the acknowledgment packet and perform actions based on options
        if ((not (self._corrupted() and 2 in self.option) or (1 in self.option)) and self._verify_checksum(
                received_packet)):
            if header == self._state and int.from_bytes(data, 'big') == self.ACK:
                debug_print("RDT2_2 - ACK")
                return True, header
            elif header != self._state and int.from_bytes(data, 'big') == self.ACK:
                debug_print("RDT2_2 - ACK with Unmatch")
                return True, header
            else:
                debug_print("RDT2_2 - Non-ACK Response")
                return False, header
        else:
            debug_print("RDT2_2 - Corrupted packet")
            return False, header

    def _add_header(self, packet, state):
        header = state.to_bytes(1, 'big')
        header_checksum = self._checksum(header + packet)
        header_packet = header + packet + header_checksum
        return header_packet

    def _parse_packet(self, packet):
        header = packet[0]
        data, checksum = packet[1:-2], packet[-2:]
        return header, data, checksum

    def _change_state(self):
        # Toggle the FSM state between 0 and 1
        self._prev_state, self._state = self._state, self._prev_state

    def _corrupted(self):
        # Check if the packet should be considered corrupted based on the corruption rate
        return self.corruption >= randrange(1, 101)

    def _reset(self):
        debug_print("RDT2_2 - resetting the process.")
        self._state = 0

    def _checksum(self, packet, bits=16):
        # Calculate the checksum for the packet
        total = sum(int.from_bytes(packet[i:i + 2], 'big') for i in range(0, len(packet), 2))
        checksum = (total & ((1 << bits) - 1))
        checksum = ((1 << bits) - 1) ^ checksum
        return checksum.to_bytes(bits // 8, 'big')

    def _verify_checksum(self, packet):
        packet_data, packet_cs = packet[:-2], packet[-2:]
        return packet_cs == self._checksum(packet_data)
