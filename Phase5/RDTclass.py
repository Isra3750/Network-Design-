 #----------------------------------------------------------------------------------------------------------------------------------------------------
 #
 # Network Design 4830 - Phase 5
 #
 #----------------------------------------------------------------------------------------------------------------------------------------------------

from socket import * # socket libary for server and client binding
from random import * # corruption methods
import threading
import time

# On / Off print statement, save time if off (#1)
debug = True
def debug_print(message):
    if debug:
        print(message)

class RDTclass:
    def __init__(self, send_address, recv_address, send_port, recv_port, corruption_rate, loss_rate, option=[1, 2, 3, 4, 5], window_size = 10, timeout_val = 0.25):
        # Global Values
        self.ACK = 0x00 # 8-bit ACK value, hexadecimal
        self.packet_size = 1024 # packet size of 1024 byte as default
        self.Break_out = False

        # Initialize the connection and set parameters
        self.send_address, self.recv_address = send_address, recv_address
        self.send_port, self.recv_port = send_port, recv_port

        # Option for loss
        self.option = option

        # Parameters for corruption/loss rate, timeout value
        self.corruption_rate = corruption_rate
        self.loss_rate = loss_rate
        self.timeout_val = timeout_val

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

 #----------------------------------------------------------------------------------------------------------------------------------------------------
 #
 # Client-side methods 
 #
 #---------------------------------------------------------------------------------------------------------------------------------------------------- 
    # Send packets from client side
    def send(self, data):
        # Create thread for recieving ACK
        debug_print("Sender MSG: Starting ACK_recv thread...")
        ACK_recv_thread  = threading.Thread(target=self.recv_ACK)
        ACK_recv_thread.start()

        while True:
            # thread isolation, window size adjustment
            with self.Base_thread:
                window_end = min((self.base + self.window_size), len(data))

            # Signal Flag for end of transmission
            if self.Break_out:
                debug_print("Sender MSG: Shut down...")
                break
            
            # Sliding window, send all packets within window size
            while self.seqnum < window_end:
                debug_print("Sender MSG: Sending packet number " + str(self.seqnum) + " / " + str(len(data) - 1))
                # Create packets with header - this includes seqnum, data, and size
                packet = self.create_header(data[self.seqnum], self.seqnum, len(data))

                # Send the packet to the receiving host.
                if not (self.Datapacketloss()):
                    with self.Send_thread:
                        self.send_sock.sendto(packet, (self.send_address, self.send_port))
                else:
                    debug_print("Sender MSG: Data packet loss!")

                # Timer handling for each packet in window size, including adjustment and creation
                with self.ACK_pending_thread:
                    # Check if the sequence number is within the bounds of the ACK timer buffer
                    if self.seqnum < (len(self.ACK_timer_buffer) - 1):
                        # If yes, update the existing timer for the current sequence number
                        self.ACK_timer_buffer[self.seqnum] = threading.Timer(self.timeout_val, self.handle_timeout, (self.seqnum,))
                    else:
                        # If no, the sequence number is beyond the current buffer size, so add a new timer
                        self.ACK_timer_buffer.append(threading.Timer(self.timeout_val, self.handle_timeout, (self.seqnum,)))
                    try:
                        # Attempt to start the timer associated with the current sequence number
                        self.ACK_timer_buffer[self.seqnum].start()
                    except RuntimeError as e:
                        # Handle the specific exception (RuntimeError) that may occur when starting the timer
                        debug_print("Error starting timer: " + str(e))
                self.seqnum += 1

            # Handle breakout
            with self.Base_thread:
                if self.base == len(data):
                    debug_print("Sender MSG: Send method completed!")
                    self.Break_out = True
                    break

        # Close ACK receive thread when done
        ACK_recv_thread.join()
    
    # waiting for the ACK response
    def recv_ACK(self):
        while True:
            # Check if send method has been completed
            if self.Break_out:
                return

            # check for recv
            packet, address = self.recv_sock.recvfrom(self.packet_size)

            # Split each packets
            SeqNum, packet_count, data, checksum  = self.split_packet(packet)

            # Convert from bytes to int
            SeqNum, total_packets= int.from_bytes(SeqNum, 'big'), int.from_bytes(packet_count, 'big')
            data, checksum = int.from_bytes(data, 'big'), int.from_bytes(checksum, 'big')
            
            # Check if ACK has a bit error, ensure not last packet
            if (self.ACKbiterror(packet)) and (SeqNum != total_packets):
                debug_print("Sender MSG: ACK packet bit-error - Checksum failed!")
                continue # skip iteration

            total_data = int.from_bytes(packet_count, 'big') # Total number of packets in the transfer.
            
            # Ensure thread isolation while looping 
            with self.Base_thread:
                while (SeqNum > self.base):
                    with self.ACK_pending_thread:
                        debug_print("Sender MSG: ACK" + str(SeqNum) + " has been received")  
                        self.ACK_timer_buffer[self.base].cancel()

                    debug_print("Sender MSG: Shifting Base!\n")
                    self.base += 1

            # Exit conditions - if size is over total data
            if (self.base >= total_data) or (self.Break_out):
                debug_print("Sender MSG: recieve ACK method completed!")
                break

    # this method is initialized to obtain the time-out value
    def handle_timeout(self, seqnum):
        debug_print("Sender MSG: ACK" + str(seqnum) + " has timed out")
        debug_print("Resending window of size = " + str(self.window_size) + ", with base number = " + str(self.base))

        # Cancel timers for the remaining packets in the window
        with self.ACK_pending_thread:
            self.cancel_timers_from_base()

        # Reset the sequence number to the base
        with self.Base_thread:
            self.reset_seqnum()

    def cancel_timers_from_base(self):
        # loop through buffer
        for timer in self.ACK_timer_buffer[self.base:]:
            timer.cancel()

    def reset_seqnum(self):
        # Set seqnum back to base
        self.seqnum = self.base

 #----------------------------------------------------------------------------------------------------------------------------------------------------
 #
 # Server-side methods 
 #
 #---------------------------------------------------------------------------------------------------------------------------------------------------- 
    # Get packet on server side
    def recv(self):
        # Initialize the total number of expected packets
        total_packets = 0xFFFF_FFFF
        # Initialize an empty buffer to store received data
        packet_data = []

        # Continue receiving packets until the base reaches the total number of expected packets
        while self.base < total_packets:
            # Receive a packet and extract header, packet count, received data, and checksum
            packet, address = self.recv_sock.recvfrom(self.packet_size + 10)
            SeqNum, packet_count, data, checksum = self.split_packet(packet)
            SeqNum = int.from_bytes(SeqNum, 'big')
            checksum = int.from_bytes(checksum, 'big')

            # Check if the packet is corrupted or the checksum is invalid
            if not (self.Databiterror(packet)):
                debug_print("Receiver MSG: Data packet bit-error - Checksum failed!")
                continue

            # Update the total number of packets based on the received packet count
            total_packets = int.from_bytes(packet_count, 'big')

            # If the header matches the base, buffer the data and increment the base
            if SeqNum == self.base:
                debug_print("Receiver MSG: Received packet number = " + str(SeqNum) + "\n")
                packet_data.append(data)
                self.base += 1

            # Send an acknowledgment for the received packet
            self.send_ACK(self.base, total_packets)

        # Print a message for completion
        debug_print("Receiver MSG: Receive method completed...")

        # Return the received data buffer
        return packet_data

    # checking for the ACK state
    def send_ACK(self, seqnum, total_count):
        # Introduce simulated packet loss. In the event of packet loss, skip the ACK/NAK response process.
        debug_print("Receiver MSG: Sending ACK " + str(seqnum) + "/" + str(total_count))

        if not (self.ACKpacketloss()):
            # Create header then send
            self.send_sock.sendto(self.create_header(self.ACK.to_bytes(1, 'big'), seqnum, total_count), (self.send_address, self.send_port))
        else:
            debug_print("Receiver MSG: ACK packet loss!")

 #----------------------------------------------------------------------------------------------------------------------------------------------------
 #
 # Supporting methods
 #
 #----------------------------------------------------------------------------------------------------------------------------------------------------
    
    # Option 2 - ACK packet bit-error
    def ACKbiterror(self, packet):
        checksum_invalid = not self.test_checksum(packet)
        bit_errors_simulated = (2 in self.option) and (not 1 in self.option) and self.packet_corrupted(self.corruption_rate)
        return checksum_invalid or bit_errors_simulated
    
    # Option 3 - Data packet bit-error
    def Databiterror(self, packet): 
        checksum_valid = self.test_checksum(packet)
        bit_errors_not_simulated = not ((self.packet_corrupted(self.corruption_rate)) and (3 in self.option)) or (1 in self.option)
        return checksum_valid and bit_errors_not_simulated
    
    # Option 4 - ACK packet loss
    def ACKpacketloss(self):
        packet_loss_simulated = self.packet_lost(self.loss_rate)
        option_configured = (4 in self.option)
        return packet_loss_simulated and option_configured

    # Option 5 - Data packet loss
    def Datapacketloss(self):
        packet_loss_simulated = self.packet_lost(self.loss_rate)
        option_configured = (5 in self.option)
        return packet_loss_simulated and option_configured

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

## Referenced Repos ---------------------------------------------------------------------------------------------------------------
## github.com/shihrer/csci466.project2/blob/master/RDT.py (debug_log function) (#1)
## github.com/haseeb-saeed/go-back-N/blob/master/sender.py (threads locking template) (#2,3)
## github.com/suryadev99/GoBack-N-Protocol/blob/main/GBN.py (self. class usage - settimeout (#))
## github.com/CantOkan/BIL441_Computer_Networks/blob/master/RDT_Protocols/RDT2. (randint for corruption methods) ()