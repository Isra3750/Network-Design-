from random import randrange
import socket

class RDT2_2:
    ACK = 0x00
    def __init__(self, send_address, send_port, recv_address, recv_port, packet_size=1024, corruption=0, option=[1, 2, 3]):
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
        self._header_size = 3

        # Create sender and receiver sockets
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock.bind((self.recv_address, self.recv_port))

    def send(self, packets):
        # Inform the user about the total number of packets to be sent
        print(f"RDT2_2 - packet count = {len(packets)}")

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
                print("RDT2_2: FSM STATE DOES NOT MATCH")
                continue

        packet_ide = 0

        while packet_ide < len(packets):
            # Inform the user about the packet being sent
            print(f"RDT2_2 - Sending packet : {packet_ide}/{len(packets) - 1}")

            # Send the packet
            self.send_sock.sendto(self._add_header(packets[packet_ide], self._state), (self.send_address, self.send_port))

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
                print("RDT2_2 - FSM STATE DOES NOT MATCH")

        # Reset the FSM state after sending all packets
        self._reset()

    def recv(self):
        # Receive the number of bytes od data to be added
        packet_data = []
        packet_ide = 0

        while True:
            print("RDT2_2 - Receiving packet count")

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
                    print(f"RDT2_2 - Packets that are receiving from sending process = {packet_cnt} packets")
                    self._send_ack(self._state)
                    self._change_state()
                    break
                else:
                    print("RDT2_2 - Packet with that are mismatched State are received.")
                    self._send_ack(self._prev_state)
            else:
                print("RDT2_2 - Corrupted packet is received.")
                self._send_ack(self._prev_state)
        # Receive the number of packets indicated by the sending process.
        while packet_ide < packet_cnt:
            print(f"RDT2_2 - Receiving packet {packet_ide}/{packet_cnt - 1} from sending process")

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
                    print(f"RDT2_2: Packet {packet_ide} Received.")
                    packet_data.append(data)
                    packet_ide += 1
                    self._send_ack(self._state)
                    self._change_state()
                else:
                    print("RDT2_2: Packet with Mismatched State Received.")
                    self._send_ack(self._prev_state)
            else:
                print("RDT2_2: Corrupted Packet Received.")
                self._send_ack(self._prev_state)

        self._reset()
        return packet_data

    def _is_packet_valid(self, packet, header):
        checksum = packet[-2:]
        return ((not self._corrupted() and 3 in self.option) or 1 in self.option) and self._verify_checksum(packet) and header == self._state

    # checking for the ACK state
    def _send_ack(self, state):
        print(f"RDT2_2 - Sending ACK{state}")
        packet = self._add_header(self.ACK.to_bytes(1, 'big'), state)
        self.send_sock.sendto(packet, (self.send_address, self.send_port))
        return

    # waiting for the ACK and NACK response
    def _recv_ack(self):
        msg = None
        while msg is None:
            msg, address = self.recv_sock.recvfrom(1024)

        # getting the data from the ACK
        header, data, checksum = self._parse_packet(msg)

        # validating the checksum of the packet and also the state ,ACK/NAK status of received response packet.
        if ((not ((self._corrupted()) and (2 in self.option))) or (1 in self.option)) and self._verify_checksum(msg):
            if (header == self._state) and (int.from_bytes(data, 'big') == self.ACK):
                print("RDT2_2 - ACK")
                return True, header
            elif (header != self._state) and (int.from_bytes(data, 'big') == self.ACK):
                print("RDT2_2 - ACK with Unmatch")
                return True, header
            else:
                print("RDT2_2 - Non-ACK Response")
                return False, header
        else:
            print("RDT2_2 - Corrupted packet")
            return False, header


   # getting the header messgae

    def _add_header(self, packet, state):
        header = state.to_bytes(1, byteorder='big')  # FSM State.
        checksum = self._checksum(header + packet)  # Checksum calculation.

        return header + packet + checksum

    def _parse_packet(self, packet):
        header = packet[0]  # Extract the header bytes.
        data = packet[1:(len(packet) - 2)]  # Extract the packet application data.
        checksum = packet[-2:]  # Extract the packet checksum bytes.
        return header, data, checksum


   # state is determined
    def _change_state(self):
        self._prev_state = self._state
        self._state = self._state ^ 1
        return

    # corruption range is estimated with the option selected
    def _corrupted(self):
        if self.corruption >= randrange(1, 101):
            return True
        else:
            return False


    def _reset(self):
        print("RDT2_2 - resetting the process.")
        self._state = 0

    # estimating the checksum
    def _checksum(self, packet):
        sum_ = 0
        k = 16

        # Dividing the packet into 2 bytes and calculate then sum of a packet
        for i in range(0, len(packet), 2):
            sum_ += int.from_bytes(packet[i:i + 2], 'big')

        sum_ = bin(sum_)[2:]
        # convert to binary

        # getting the overflow count
        while len(sum_) != k:
            if len(sum_) > k:
                x = len(sum_) - k
                sum_ = bin(int(sum_[0:x], 2) + int(sum_[x:], 2))[2:]
            if len(sum_) < k:
                sum_ = '0' * (k - len(sum_)) + sum_

        # get the complement
        checksum = ''
        for i in sum_:
            if i == '1':
                checksum += '0'
            else:
                checksum += '1'

        # Converting the 8 bits into 1 byte
        checksum = bytes(int(checksum[i: i + 8], 2) for i in range(0, len(checksum), 8))
        return checksum

    def _verify_checksum(self, packet):
        packet_data = packet[:-2]
        packet_cs = packet[-2:]
        # getting the original checksum.
        checksum = self._checksum(packet_data)
        # checking the original checksum.

        # checking for both the values
        if packet_cs == checksum:
            return True
        else:
            return False
