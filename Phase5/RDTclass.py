# RDTclass - phase 5 - network 4830

from socket import * # socket libary for server and client binding
from random import * # import randrange for corruption methods
import threading
from time import time

# On / Off print statement, save time if off (#1)
debug = True
def debug_print(message):
    if debug:
        print(message)

class RDTclass:
    def __init__(self, send_address, recv_address, send_port, recv_port, corruption_rate, loss_rate, option=[1, 2, 3, 4, 5], window_size = 10, timeout_val = 0.025):
        # Global Values
        self.ACK = 0x00 # 8-bit ACK value, hexadecimal
        self.packet_size = 1024 # packet size of 1024 byte as default

        # Initialize the connection and set parameters
        self.send_address, self.recv_address = send_address, recv_address
        self.send_port, self.recv_port = send_port, recv_port

        # Option for loss
        self.option = option

        # Parameters for corruption/loss rate, timeout value
        self.corruption_rate = corruption_rate
        self.loss_rate = loss_rate
        self.timeout_val = timeout_val

        # Flags
        self.Complete_Flag = False

        # Go Back In parameters
        self.base = 0 # base value
        self.window_size = window_size # sliding window size
        self.seqnum = 0

        # This list is used to keep track of timer objects associated with each packet's acknowledgment. 
        # Each element in this list corresponds to a packet's sequence number, and the timer associated with that sequence number. 
        self.ACK_timer_buffer = []

        # This list is used to keep track of the sequence numbers of packets that are waiting for acknowledgment. 
        # It is essentially a buffer containing the sequence numbers of the packets that have been sent and are awaiting acknowledgment. 
        # The size of this buffer is determined by the window size 
        self.ACK_pending_buffer = list(range(self.window_size))

        # Threads and Locks to synchronize access to shared resources amoung different threads
        self.Base_thread = threading.Lock()
        self.Send_thread = threading.Lock()
        self.ACK_pending_thread = threading.Lock()

        # Create sender and receiver sockets
        self.send_sock = socket(AF_INET, SOCK_DGRAM)
        self.recv_sock = socket(AF_INET, SOCK_DGRAM)
        self.recv_sock.bind((self.recv_address, self.recv_port))
    
    # Send packets from client side
    def send(self, data):
        # Create thread for recieving ACK
        debug_print(f"GBN: Starting ACK Receiving Process.")
        ACK_recv_thread  = threading.Thread(target=self.recv_ACK)
        ACK_recv_thread.start()

        self.base = 0
        self.seqnum = 0
        self.Complete_Flag = False

        while True:
            # Calculate the end of the data send window based on the current base value, and the configured 
            # window size. The window end is limited to a max value based on the total amount of data that 
            # is being sent to the receiving host.
            with self.Base_thread: # "with" is use to acquire and release threads
                window_end = min((self.base + self.window_size), len(data))

            if self.Complete_Flag:
                debug_print("GBN: Connection closed by remote host.")
                break
            
            # Sequence used to monitor the sending window based on the end point of the window. When the base
            # packet of the sending window has been properly ACK'd, the sequence will add a new packet to the 
            # sending window.
            while self.seqnum < window_end:
                debug_print(f"GBN: Sending Packet {self.seqnum}/{len(data) - 1}")
                packet = self.create_header(data[self.seqnum], self.seqnum, len(data))

                # Send the packet to the receiving host.
                if not (self.packet_lost(self.loss_rate) and (5 in self.option)):
                    with self.Send_thread:
                        self.send_sock.sendto(packet, (self.send_address, self.send_port))
                else:
                    debug_print("GBN: Data packet loss!")
                    pass

                # Start the timeout monitor for the data send. When that packet's timeout is reached, the 
                # timeout process resends the packet and restarts the timer.
                with self.ACK_pending_thread:

                    if self.seqnum >= (len(self.ACK_timer_buffer) - 1):
                        self.ACK_timer_buffer.append(threading.Timer(self.timeout_val, self._timeout, (self.seqnum, 0,))) 
                    else:
                        self.ACK_timer_buffer[self.seqnum] = threading.Timer(self.timeout_val, self._timeout, (self.seqnum, 0,))
                    try:
                        self.ACK_timer_buffer[self.seqnum].start()
                    except:
                        pass
                self.seqnum += 1

            # When the base value is equal to the the length of the data packet, this indicates
            # that the entire data packet has been recieved by the remote host.
            with self.Base_thread:
                if self.base == len(data):
                    break

        debug_print(f"GBN: Data transfer complete.")
        self.Complete_Flag = True

        # Close thread when done
        ACK_recv_thread.join()
    
    # waiting for the ACK response
    def recv_ACK(self):
        # Timeout is used to stop the receiver, which is initilized to 30
        self.recv_sock.settimeout(30)

        while True:
            # Passively receive ACKs sent by the receiving host, and pass the ACKs
            # to be processed and buffered.
            if self.Complete_Flag:
                return

            # check for recv
            packet, address = self.recv_sock.recvfrom(self.packet_size)

            # Split each packets and convert from bytes to int
            header, packet_cnt, rcvd_data, cs  = self.split_packet(packet)
            header, total_packets= int.from_bytes(header, 'big'), int.from_bytes(packet_cnt, 'big')
            rcvd_data, cs = int.from_bytes(rcvd_data, 'big'), int.from_bytes(cs, 'big')
            
            # If the checkusm is invalid for the received packet, discard the received packet
            # and wait to receive more ACKs from the receiving host.
            if (not self.test_checksum(packet)) or ((2 in self.option) and (not 1 in self.option) and self.packet_corrupted(self.corruption_rate)) and (header != total_packets):
                debug_print(f"GBN: ACK packet bit-error - Checksum failed!")
                continue
            else:
                total_data = int.from_bytes(packet_cnt, 'big') # Total number of packets in the transfer.

            # Stop the timeout process associated with the received ACK.
            with self.Base_thread:
                while (header > self.base):
                    with self.ACK_pending_thread:
                        debug_print(f"GBN: ACK{header} received.")  
                        try:
                            self.ACK_timer_buffer[self.base].cancel()
                        except:
                            pass
            
                    # Update the base value based on the sequence number of the received ACK.
                    debug_print(f"GBN: Shifting Base!\n")
                    self.base += 1

            # If the send process is complete, exit the ACK reveiving process.
            if (self.base >= total_data) or (self.Complete_Flag):
                break

    # this method is initialized to obtain the time-out value
    def _timeout(self, seqnum, retry):
        # Increment the retry count, and exiting on the 100th retry.
        retry_cnt = retry + 1
        if retry_cnt >= 100:
            self.Complete_Flag = True
            return

        debug_print(f"GBN: ACK{seqnum} receive timed out. Resending window (base = {self.base}), (retry = {retry}).")
        
        with self.ACK_pending_thread:
            # stopping all the running timers.
            for timer in self.ACK_timer_buffer[self.base:]:
                try:
                    timer.cancel()
                except:
                    continue

        # Resetting the base and the sequence number
        with self.Base_thread:
            self.seqnum = self.base
    
    # Get packet on server side
    def recv(self):
        # Initialize the total number of expected packets
        total_packets = 0xFFFF_FFFF
        # Initialize an empty buffer to store received data
        data_buffer = []

        # Continue receiving packets until the base reaches the total number of expected packets
        while self.base < total_packets:
            # Receive a packet and extract header, packet count, received data, and checksum
            packet, address = self.recv_sock.recvfrom(self.packet_size + 10)
            header, packet_count, data, checksum = self.split_packet(packet)
            header = int.from_bytes(header, 'big')
            checksum = int.from_bytes(checksum, 'big')

            # Check if the packet is corrupted or the checksum is invalid
            if not (self.test_checksum(packet) and 
                    (not ((self.packet_corrupted(self.corruption_rate)) and (3 in self.option)) or (1 in self.option))):
                debug_print("GBN: Data packet bit-error - Checksum failed!")
                continue

            # Update the total number of packets based on the received packet count
            total_packets = int.from_bytes(packet_count, 'big')

            # If the header matches the base, buffer the data and increment the base
            if header == self.base:
                debug_print(f"GBN: Buffering data {header}\n")
                data_buffer.append(data)
                self.base += 1

            # Send an acknowledgment for the received packet
            self.send_ACK(self.base, total_packets)

        # Print a message indicating the completion of the reception process
        debug_print(f"GBN: Receive complete. (base = {self.base}, total_packets = {total_packets})")

        # Return the received data buffer
        return data_buffer

    # checking for the ACK state
    def send_ACK(self, seqnum, total_count):
        # Introduce simulated packet loss. In the event of packet loss, skip the ACK/NAK response process.
        debug_print(f"GBN: Sending ACK{seqnum}/{total_count}")

        if not (self.packet_lost(self.loss_rate) and (4 in self.option)):
            # Create header then send
            self.send_sock.sendto(self.create_header(self.ACK.to_bytes(1, 'big'), seqnum, total_count), (self.send_address, self.send_port))
        else:
            debug_print("GBN: ACK packet loss!")

    def create_header(self, packet, Cur_num, total):
        # Create SeqNum, total_size, and checksum to each package
        SeqNum = Cur_num.to_bytes(4, 'big')
        total_count = total.to_bytes(4, 'big')
        checksum = self.create_checksum(SeqNum + total_count + packet) # create checksum
        header_packet = SeqNum + total_count + packet + checksum
        return header_packet

    def split_packet(self, header_packet):
        # Split packets into 4 sections, SeqNum, Total_count, data, checksum
        SeqNum, total_count = header_packet[0:4], header_packet[4:8]
        data = header_packet[8:-2]
        checksum = header_packet[-2:]
        return SeqNum, total_count, data, checksum

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

# Referenced Repos:
# github.com/haseeb-saeed/go-back-N/blob/master/sender.py
# github.com/suryadev99/GoBack-N-Protocol/blob/main/GBN.py