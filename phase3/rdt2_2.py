from random import randrange
import socket

# turn debug_print on/off to reduce time if needed
debug = True


def debug_print(message):
    if debug:
        print(message)


class RDT2_2:
    ACK = 0x00  # 8 bit / 1 byte size

    def __init__(self, send_address, send_port, recv_address, recv_port, packet_size=1024, corruption=0,
                 option=[1, 2, 3]):
        # Set the basic connection and configuration parameters
        self.send_address = send_address
        self.recv_address = recv_address
        self.send_port = send_port
        self.recv_port = recv_port
        self.packet_size = packet_size

        self.corruption = corruption
        self.option = option

        # Initialize FSM state and header size
        self._state = 0
        self._prev_state = 1
        self._header_size = 3  # size in byte

        # Create sender and receiver sockets
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock.bind((self.recv_address, self.recv_port))

    def send(self, packets):
        # Inform the user about the total number of packets to be sent
        debug_print(f"RDT2_2 - packet count = {len(packets)}")

        while True:
            # Send the header with the number of packets to be transmitted and wait for an acknowledgment
            header = len(packets).to_bytes(1024, 'big')
            self.send_sock.sendto(self._add_header(header, self._state), (self.send_address, self.send_port))

            # Wait for the acknowledgment and its associated state
            ack, state = self._recv_ack()

            if ack and state == self._state:
                # Acknowledgment received and state matches, proceed
                self._change_state()
                break
            else:
                # Handle the case where acknowledgment is not received or state does not match
                debug_print("RDT2_2: FSM STATE DOES NOT MATCH")
                continue

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

            # Wait for the acknowledgment and its associated state
            ack, state = self._recv_ack()

            if ack and state == self._state:
                # Acknowledgment received and state matches, proceed
                self._change_state()
                packet_ide += 1
            else:
                # Handle the case where acknowledgment is not received or state does not match
                debug_print("RDT2_2 - FSM STATE DOES NOT MATCH")

        # Reset the FSM state after sending all packets
        self._reset()

    def recv(self):
        # Receive the number of bytes od data to be added
        packet_data = []
        packet_ide = 0

        while True:
            debug_print("RDT2_2 - Receiving packet count")

            packet, address = self.recv_sock.recvfrom(1024 + self._header_size)
            header, data, checksum = self._parse_packet(packet)
            data = int.from_bytes(data, 'big')
            checksum = int.from_bytes(checksum, 'big')

            # validating the checksum
            # checking whether the state of the sending process matches the state of the sending process.
            # The selected option is acted
            if ((not ((self._corrupted()) and (3 in self.option))) or (1 in self.option)) and self._verify_checksum(
                    packet):
                if (header == self._state):
                    # Getting number of bytes to receive from the sending process
                    packet_cnt = data
                    debug_print(f"RDT2_2 - Packets that are receiving from sending process = {packet_cnt} packets")
                    self._send_ack(self._state)
                    self._change_state()
                    break
                else:
                    debug_print("RDT2_2 - Packet with that are mismatched State are received.")
                    self._send_ack(self._prev_state)
            else:
                debug_print("RDT2_2 - Corrupted packet is received.")
                self._send_ack(self._prev_state)
        # Receive the number of packets indicated by the sending process.
        while packet_ide < packet_cnt:
            debug_print(f"RDT2_2 - Receiving packet {packet_ide}/{packet_cnt - 1} from sending process")

            packet, address = self.recv_sock.recvfrom(self.packet_size + self._header_size)
            header, data, checksum = self._parse_packet(packet)
            checksum = int.from_bytes(checksum, 'big')

            # Validate the checksum of the packet.
            if ((not ((self._corrupted()) and (3 in self.option))) or (1 in self.option)) and self._verify_checksum(
                    packet):
                # Check if the state of the sending process matches the state of the sending process.
                # In the event that the FSM states of the sending and receiving processes do not match,
                # send an ACK with the current FSM state of the receiving process and skip the state
                # changing and packet data collection process.
                if (header == self._state):
                    # Add the received packet to the packet list.
                    debug_print(f"RDT2_2: Packet {packet_ide} Received.")
                    packet_data.append(data)
                    packet_ide += 1
                    self._send_ack(self._state)
                    self._change_state()
                else:
                    debug_print("RDT2_2: Packet with Mismatched State Received.")
                    self._send_ack(self._prev_state)
            else:
                debug_print("RDT2_2: Corrupted Packet Received.")
                self._send_ack(self._prev_state)

        self._reset()
        return packet_data

    # checking for the ACK state
    def _send_ack(self, state):
        # Inform the user about sending an acknowledgment
        debug_print(f"RDT2_2 - Sending ACK {state}")

        # Create an acknowledgment packet with the given state
        ack_packet = self._add_header(self.ACK.to_bytes(1, 'big'), state)

        # Send the acknowledgment packet to the sender
        self.send_sock.sendto(ack_packet, (self.send_address, self.send_port))

    # waiting for the ACK response
    def _recv_ack(self):
        received_packet, sender_address = None, None

        # Keep receiving packets until a valid ACK or NAK is received
        while received_packet is None:
            received_packet, sender_address = self.recv_sock.recvfrom(1024)

        # Parse the received acknowledgment packet
        header, data, checksum = self._parse_packet(received_packet)

        # Validate the checksum of the packet and check the state and ACK/NAK status
        if ((not ((self._corrupted()) and (2 in self.option))) or (1 in self.option)) and self._verify_checksum(
                received_packet):
            if header == self._state and int.from_bytes(data, 'big') == self.ACK:
                # Acknowledgment received successfully
                debug_print("RDT2_2 - ACK")
                return True, header
            elif header != self._state and int.from_bytes(data, 'big') == self.ACK:
                # Acknowledgment received with a mismatched state
                debug_print("RDT2_2 - ACK with Unmatch")
                return True, header
            else:
                # Non-ACK Response received
                debug_print("RDT2_2 - Non-ACK Response")
                return False, header
        else:
            # Corrupted packet received
            debug_print("RDT2_2 - Corrupted packet")
            return False, header

    # getting the header messgae
    def _add_header(self, packet, state):
        # Create a header with the FSM state
        header = state.to_bytes(1, 'big')

        # Calculate the checksum for the header and packet
        header_checksum = self._checksum(header + packet)

        # Combine the header, packet, and checksum to form the packet with header
        header_packet = header + packet + header_checksum

        return header_packet

    def _parse_packet(self, packet):
        # Extract the header, data, and checksum from the packet
        header = packet[0]
        data = packet[1:-2]
        checksum = packet[-2:]

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

    # estimating the checksum, from geekfromgeek
    def _checksum(self, packet, bits=16):
            # Calculate the sum of 16-bit words in the packet
            total = sum(int.from_bytes(packet[i:i + 2], 'big') for i in range(0, len(packet), 2))

            # Ensure the sum is within the specified number of bits
            checksum = total & ((1 << bits) - 1)

            # Calculate the one's complement (invert the bits)
            checksum = ((1 << bits) - 1) ^ checksum

            # Convert to bytes
            return checksum.to_bytes(bits // 8, 'big')

    def _verify_checksum(self, packet):
        packet_data, packet_cs = packet[:-2], packet[-2:]
        # Extract packet data and checksum

        return packet_cs == self._checksum(packet_data)