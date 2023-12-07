# RDTclass - phase 5 - network 4830
# imports the python socket library that allows for socket programming
import socket
import threading
from time import time
from random import randrange

# On / Off print statement, save time if off (#1)
debug = True
def debug_print(message):
    if debug:
        print(message)

class RDTclass:
    ACK = 0x00 # 8-bit ACK value, hexadecimal

    def __init__(self, send_address, send_port, recv_address, recv_port, window_size, corruption_rate, loss_rate, option=[1, 2, 3, 4, 5], timeout=None):
        # Initialize the connection and set parameters
        self.send_address   = send_address
        self.recv_address   = recv_address
        self.send_port      = send_port
        self.recv_port      = recv_port

        # Option for loss
        self.option = option

        # Parameters for corruption/loss rate, timeout value
        self.corruption_rate = corruption_rate
        self.loss_rate = loss_rate
        self.timeout = timeout

        # Go Back In parameters
        self.base = 0 # base value
        self.window_size = window_size # sliding window size
        self.seqnum = 0

        # sequence number is initialized
        self._ack_pending_timers = []
        self._ack_pending_buffer = []
        for i in range(self.window_size):
            self._ack_pending_buffer.append(i)

        # Threads and Locks
        self._base_l        = threading.Lock()
        self._send_l        = threading.Lock()
        self._ack_pending_l = threading.Lock()

        # Flags
        self._send_complete_f = False

        # Create sender and receiver sockets
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.recv_sock.bind((self.recv_address, self.recv_port))

    def send(self, data):
        # Getting the number of packets to be transmitted and let the receiver know and informing the receiver side the value
        self._send_complete_f = False

        # Two threads, one for send, one for recieving ACK
        send_t      = threading.Thread(target=self._send, args=(data,))
        recv_ack_t  = threading.Thread(target=self._recv_ack)

        debug_print(f"GBN: Starting ACK Receiving Process.")
        recv_ack_t.start()

        debug_print(f"GBN: Starting Sending Process.")
        send_t.start()

        # Close threads when done
        send_t.join()
        recv_ack_t.join()

    def recv(self):
        # Receive the number of bytes of data to be added
        data_buffer     = []
        total_packets   = 0xFFFF_FFFF
        
        # This loop is introduced to find the number of that are remaining for transmittion
        while self.base < total_packets:
            packet, address         = self.recv_sock.recvfrom(2048)
            header, packet_cnt, rcvd_data, cs  = self.split_packet(packet)
            header                  = int.from_bytes(header, 'big')         # Sequence number.
            cs                      = int.from_bytes(cs, 'big')             # Packet checksum.

            # Verify the integrity of the received packet.
            if self.test_checksum(packet) and ((not ((self.packet_corrupted(self.corruption_rate)) and (3 in self.option))) or (1 in self.option)):
                total_packets = int.from_bytes(packet_cnt, 'big')  # Total number of packets in the transfer.

                # When the data packet's sequence number is equal to the base number, buffer the data,
                # increment the base number to request the next packet, and send the ACK for the packet.
                if header == self.base:
                    debug_print(f"GBN: Buffering data {header}")
                    data_buffer.append(rcvd_data)
                    self.base += 1
                
                self._send_ack(self.base, total_packets)
            else:
                debug_print(f"GBN: Checksum Invalid.")
                continue

        debug_print(f"GBN: Receive complete. (base = {self.base}, total_packets = {total_packets})")

        return data_buffer

    ##
    # @fn       _send
    # @brief    This method sends data to a receiving host and creates a timeout process that is used to monitor
    #           if the packet will need to be resent.
    #
    # @param    data    - ByteArray object containing packet data.
    #
    # @return   None.
    def _send(self, data):
        self.base   = 0
        self.seqnum = 0

        while True:
            # Calculate the end of the data send window based on the current base value, and the configured 
            # window size. The window end is limited to a max value based on the total amount of data that 
            # is being sent to the receiving host.
            self._base_l.acquire()
            window_end = min((self.base + self.window_size), len(data))
            self._base_l.release()

            if self._send_complete_f:
                debug_print("GBN: Connection closed by remote host.")
                break
            
            # Sequence used to monitor the sending window based on the end point of the window. When the base
            # packet of the sending window has been properly ACK'd, the sequence will add a new packet to the 
            # sending window.
            while self.seqnum < window_end:
                packet = self.create_header(data[self.seqnum], self.seqnum, len(data))

                debug_print(f"GBN: Sending Packet {self.seqnum}/{len(data) - 1}")

                # Send the packet to the receiving host.
                if (self.packet_lost(self.loss_rate) and (4 in self.option)):
                    pass
                else:
                    self._send_l.acquire()
                    self.send_sock.sendto(packet, (self.send_address, self.send_port))
                    self._send_l.release()

                # Start the timeout monitor for the data send. When that packet's timeout is reached, the 
                # timeout process resends the packet and restarts the timer.
                self._ack_pending_l.acquire()
                if self.seqnum >= (len(self._ack_pending_timers) - 1):
                    self._ack_pending_timers.append(threading.Timer(self.timeout, self._timeout, (self.seqnum, 0,))) 
                else:
                    self._ack_pending_timers[self.seqnum] = threading.Timer(self.timeout, self._timeout, (self.seqnum, 0,))
                try:
                    self._ack_pending_timers[self.seqnum].start()
                except:
                    pass
                self._ack_pending_l.release()

                self.seqnum += 1

            # When the base value is equal to the the length of the data packet, this indicates
            # that the entire data packet has been recieved by the remote host.
            self._base_l.acquire()
            if self.base == len(data):
                break
            self._base_l.release()

        debug_print(f"GBN: Data transfer complete.")
        self._send_complete_f = True
        return

    # waiting for the ACK response
    def _recv_ack(self):
        # Timeout is used to stop the receiver, which is initilized to 30
        self.recv_sock.settimeout(30)

        while True:
            # Passively receive ACKs sent by the receiving host, and pass the ACKs
            # to be processed and buffered.
            try:
                packet, address = self.recv_sock.recvfrom(1024)
            except:
                if self._send_complete_f:
                    return
                else:
                    continue

            header, packet_cnt, rcvd_data, cs  = self.split_packet(packet)
            header                  = int.from_bytes(header, 'big')     # Sequence number.
            total_packets           = int.from_bytes(packet_cnt, 'big')
            rcvd_data               = int.from_bytes(rcvd_data, 'big')  # Packet data.
            cs                      = int.from_bytes(cs, 'big')         # Packet checksum.
            
            # If the checkusm is invalid for the received packet, discard the received packet
            # and wait to receive more ACKs from the receiving host.
            if (not self.test_checksum(packet)) or (self.packet_corrupted(self.corruption_rate) and (2 in self.option) and (not 1 in self.option)) and (header != total_packets):
                debug_print(f"GBN: Checksum invalid.")
                continue
            else:
                total_data = int.from_bytes(packet_cnt, 'big') # Total number of packets in the transfer.

            # Stop the timeout process associated with the received ACK.
            self._base_l.acquire()
            while (header > self.base):
                
                self._ack_pending_l.acquire()
                debug_print(f"GBN: ACK{header} received.")  
                try:
                    self._ack_pending_timers[self.base].cancel()
                except:
                    pass
                self._ack_pending_l.release()
            
                # Update the base value based on the sequence number of the received ACK.
                self.base += 1
            self._base_l.release()

            # If the send process is complete, exit the ACK reveiving process.
            if self.base >= total_data:
                break
            if self._send_complete_f:
                break
            
        return

    # this method is initialized to obtain the time-out value
    def _timeout(self, seqnum, retry):
        # Increment the retry count, and exiting on the 100th retry.
        retry_cnt = retry + 1
        if retry_cnt >= 100:
            self._send_complete_f = True
            return

        debug_print(f"GBN: ACK{seqnum} receive timed out. Resending window (base = {self.base}), (retry = {retry}).")

        self._ack_pending_l.acquire()
        # stopping all the running timers.
        for timer in self._ack_pending_timers[self.base:]:
            try:
                timer.cancel()
            except:
                continue
        self._ack_pending_l.release()

        # Resetting the base and the sequence number
        self._base_l.acquire()
        self.seqnum = self.base
        self._base_l.release()

        return

    # checking for the ACK state
    def _send_ack(self, state, total_packets):
        # Introduce simulated packet loss. In the event of packet loss, skip the ACK/NAK response process.
        debug_print(f"GBN: Sending ACK{state}/{total_packets}")

        if (self.packet_lost(self.loss_rate) and (5 in self.option)) and (state != total_packets):
            return

        packet = self.create_header(self.ACK.to_bytes(1, 'big'), state, total_packets)
        self.send_sock.sendto(packet, (self.send_address, self.send_port))
        return

    def create_header(self, packet, Cur_num, total):
        # Create SeqNum, total_size, and checksum to each package
        SeqNum = Cur_num.to_bytes(4, 'big')
        total_count = total.to_bytes(4, 'big')
        cs = self.create_checksum(SeqNum + total_count + packet) # create checksum

        return SeqNum + total_count + packet + cs

    def split_packet(self, packet):
        # Split packets into 4 sections, SeqNum, Total_count, data, checksum
        SeqNum = packet[0:4]
        total_count = packet[4:8]
        data = packet[8:-2]
        cs = packet[-2:]
        return SeqNum, total_count, data, cs

    def packet_corrupted(self, percentage):
        # Return chance that packet is corrupted, True if corrupted, False if not corrupted
        return self.corruption_rate >= randrange(1, 101)

    def packet_lost(self, percentage):
        # Return chance that packet is loss during transmission, True if loss, False if not loss
        return self.loss_rate >= randrange(1, 101)

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
        return packet_checksum == self.create_checksum(packet_data) # make sure both checksum are same then return true else false
