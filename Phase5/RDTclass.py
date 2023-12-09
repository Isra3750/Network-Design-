#----------------------------------------------------------------------------------------------------------------------------------------------------
#
# Network Design 4830 - Phase 5
# Implement Go-Back-N protocol over an unreliable UDP channel
#
#----------------------------------------------------------------------------------------------------------------------------------------------------
# Imports modules
from socket import * # socket libary for server and client binding
from random import * # corruption methods
from time import *
import threading

# Set parameters for class from instruction note (Phase 5.pdf):
# 1. Option 1 - No loss/bit-errors
# 2. Option 2 - ACK packet bit-error
# 3. Option 3 - Data packet bit-error
# 4. Option 4 - ACK packet loss
# 5. Option 5 - Data packet loss

# Class values
TIMEOUT = 0.03          # Timer value (seconds)
ERROR_RATE_VAL = 5     # percentage for loss and corruption rate
WINDOW_SIZE = 10       # size of window
OPTION = 4              # options
PRINT_OUTPUT = True    # print message

# On / Off print statement, save time if off (#1)
def debug_print(message):
    if PRINT_OUTPUT:
        print(message)

class RDTclass:
    def __init__(self, send_address, recv_address, send_port, recv_port):
        # Global Values
        self.ACK = 0x00 # 8-bit ACK value, hexadecimal
        self.packet_size = 1024 # packet size of 1024 byte as default
        self.Break_out = False # Break out flag

        # Initialize the connection and set parameters for rate, option, and timeout
        self.send_address, self.recv_address = send_address, recv_address
        self.send_port, self.recv_port = send_port, recv_port
        self.error_rate, self.option = ERROR_RATE_VAL, OPTION
        self.timeout_val = TIMEOUT

        # Go Back In parameters
        self.base = 0 # base value
        self.window_size = WINDOW_SIZE # sliding window size
        self.seqnum = 0 # current seq number

        # This is used to keep track of each packets timer ACKs
        self.ACK_timer_buffer = []

        # This is used to keep track of the seqnum of packets that are waiting for ACKs. 
        # It's basically a buffer containing the seqnum of the packets that have been sent and are awaiting ACKs. 
        self.ACK_pending_buffer = list(range(self.window_size))

        # Threads are use to synchronize access to shared resources amoung different threads
        # Base thread to handle self.base values, Send thread to handle self.send_sock, ACK thread to handle ACK operations
        self.thread_locks = [threading.Lock() for i in range(3)] # three threads declare
        self.Base_thread, self.Send_thread, self.ACK_pending_thread = self.thread_locks # set thread locks

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
    def send(self, packet):
        # Create thread for recieving ACK (#2)
        debug_print("Sender MSG: Starting ACK_recv thread...")
        ACK_recv_thread  = threading.Thread(target=self.recv_ACK)
        ACK_recv_thread.start()

        while True:            
            # Sliding window, send all packets within window size
            while (self.seqnum < (self.base + self.window_size)) and (self.seqnum < len(packet)):
                debug_print("Sender MSG: Sending packet number " + str(self.seqnum))
                # Create packets with header - this includes seqnum, data, and size
                cur_packet = self.create_header(packet[self.seqnum], self.seqnum, len(packet))

                # Send the packet to the receiving host.
                if (self.Datapacketloss()):
                    debug_print("Sender MSG: Data packet loss!")
                elif (self.ACKpacketloss()):
                    debug_print("Sender MSG: ACK packet loss!")
                else:
                    with self.Send_thread:
                        self.send_sock.sendto(cur_packet, (self.send_address, self.send_port))
                # Timer handling for each packet in the window size
                with self.ACK_pending_thread:
                    # Check if the sequence number is within the range of the ACK timer buffer
                    if self.seqnum in range(len(self.ACK_timer_buffer) - 1):
                        # If yes, update the existing timer for the current sequence number
                        self.update_timer()
                    else:
                        # If no, the seqnum is beyond the current buffer size, create timer
                        self.create_timer()
                # Timer starts
                try:
                    # Attempt to start the timer associated with the current seqnum
                    self.start_timer()
                # Handle the specific exception (RuntimeError) that might occur when starting the timer
                except RuntimeError as e:
                    debug_print("Sender MSG: Error starting timer: " + str(e))

                # Slide window seqnum
                self.seqnum += 1

            # Handle breakout
            with self.Base_thread:
                if self.base == len(packet):
                    debug_print("Sender MSG: Send method completed!")
                    sleep(0.25)
                    self.Break_out = True
                    break

        # Close ACK receive thread when done
        ACK_recv_thread.join()
    
    # waiting for the ACK response
    def recv_ACK(self):
        while True:
            # Check if send method has been completed
            if self.Break_out:
                sleep(0.25)
                break

            # check for recv and split each packet
            packet, address = self.recv_sock.recvfrom(self.packet_size)
            SeqNum, packet_count, checksum, data  = self.split_packet(packet)

            # Convert from bytes to int
            SeqNum, total_data= int.from_bytes(SeqNum, byteorder = 'big'), int.from_bytes(packet_count, byteorder = 'big')
            checksum, data = int.from_bytes(checksum, byteorder = 'big'), int.from_bytes(data, byteorder = 'big')
            
            # Check if ACK has a bit error, ensure not last packet
            if (self.ACKbiterror(packet)) and (SeqNum != total_packets):
                debug_print("Sender MSG: ACK packet bit-error - Checksum failed!")
                continue # skip iteration
            
            # Ensure thread isolation while looping 
            with self.Base_thread:
                while (SeqNum > self.base):
                    with self.ACK_pending_thread:
                        debug_print("Sender MSG: Received ACK" + str(SeqNum) + "\n")
                        # If ACK is received, timer must be cancel at base
                        self.ACK_timer_buffer[self.base].cancel()

                    debug_print("Sender MSG: Shifting Base value")
                    self.base += 1

            # Exit conditions - if size is over total data
            if (self.base >= total_data) or (self.Break_out):
                debug_print("Sender MSG: Recieve ACK method completed")
                break

    # this method is initialized to obtain the time-out value
    def handle_timeout(self, seqnum):
        debug_print("Sender MSG: ACK" + str(seqnum) + " has timed out")
        debug_print("Sender MSG: Resending Packet at base number = " + str(self.base))

        # Cancel timers for the remaining packets in the window
        with self.ACK_pending_thread:
            self.cancel_all_timer()

        # Reset the sequence number to the base
        with self.Base_thread:
            self.reset_seqnum()

    def reset_seqnum(self):
        # Set seqnum back to base
        self.seqnum = self.base

    def create_timer(self):
        # Create timer and append to buffer
        self.ACK_timer_buffer.append(threading.Timer(self.timeout_val, self.handle_timeout, (self.seqnum,)))

    def update_timer(self):
         # Update timer in buffer
        self.ACK_timer_buffer[self.seqnum] = (threading.Timer(self.timeout_val, self.handle_timeout, (self.seqnum,)))

    def cancel_all_timer(self):
        # loop through buffer
        for timer in self.ACK_timer_buffer[self.base:]:
            timer.cancel()

    def start_timer(self):
        # Start timer
        self.ACK_timer_buffer[self.seqnum].start()
 #----------------------------------------------------------------------------------------------------------------------------------------------------
 #
 # Server-side methods 
 #
 #---------------------------------------------------------------------------------------------------------------------------------------------------- 
    # Get packet on server side
    def recv(self):
        # Initialize very large number
        total_packets = float('inf')
        # Initialize an empty buffer to store received data
        packet_data = []

        # Continue receiving packets until the base reaches the total number of expected packets
        while self.base < total_packets:
            # Receive a packet and extract header, packet count, received data, and checksum
            packet, address = self.recv_sock.recvfrom(self.packet_size + 10)
            SeqNum, packet_count, checksum, data = self.split_packet(packet)
            SeqNum, total_packets = int.from_bytes(SeqNum, byteorder = 'big'), int.from_bytes(packet_count, byteorder = 'big')
            checksum = int.from_bytes(checksum, byteorder = 'big')

            # Check if the packet is corrupted or the checksum is invalid
            if not (self.Databiterror(packet)):
                debug_print("Receiver MSG: Data packet bit-error - Checksum failed!")
                continue

            # If the header matches the base, buffer the data and increment the base
            if SeqNum == self.base:
                debug_print("Receiver MSG: Writing packet " + str(SeqNum) + " to output\n")
                packet_data.append(data) # write to packet_data
                self.base += 1

            # Send an acknowledgment for the received packet
            debug_print("Receiver MSG: Sending ACK " + str(self.base))
            self.send_sock.sendto(self.create_header(self.ACK.to_bytes(1, 'big'), self.base, total_packets), (self.send_address, self.send_port))

        # Print a message for completion
        debug_print("Receiver MSG: Received all packets")

        # Return the received data buffer
        return packet_data

 #----------------------------------------------------------------------------------------------------------------------------------------------------
 #
 # Supporting methods
 #
 #----------------------------------------------------------------------------------------------------------------------------------------------------
    
    # Option 2 - ACK packet bit-error (#4)
    def ACKbiterror(self, packet):
        checksum_valid = self.test_checksum(packet)
        is_corrupted = (self.error_rate >= randrange(1, 101)) # randomize corrupt chance
        option_configured = (self.option == 2) # option 3 must be selected
        secondary_option = (self.option == 1) # return True right away
        bit_errors_not_simulated = not (is_corrupted and option_configured) or secondary_option
        return not (checksum_valid and bit_errors_not_simulated)
    
    # Option 3 - Data packet bit-error
    def Databiterror(self, packet): 
        checksum_valid = self.test_checksum(packet)
        is_corrupted = (self.error_rate >= randrange(1, 101)) # randomize corrupt chance
        option_configured = (self.option == 3) # option 3 must be selected
        secondary_option = (self.option == 1) # return True right away
        bit_errors_not_simulated = not (is_corrupted and option_configured) or secondary_option
        return checksum_valid and bit_errors_not_simulated
    
    # Option 4 - ACK packet loss
    def ACKpacketloss(self):
        packet_loss_simulated = (self.error_rate >= randrange(1, 101))
        option_configured = (self.option == 4)
        return packet_loss_simulated and option_configured

    # Option 5 - Data packet loss
    def Datapacketloss(self):
        packet_loss_simulated = (self.error_rate >= randrange(1, 101))
        option_configured = (self.option == 5)
        return packet_loss_simulated and option_configured

    def create_header(self, packet, Cur_num, total):
        # Create SeqNum, total_size, and checksum to each package
        SeqNum = Cur_num.to_bytes(4, byteorder='big') # Convert to byte
        total_count = total.to_bytes(4, byteorder='big') # Convert to byte
        checksum = self.create_checksum(SeqNum + total_count + packet)  # create checksum (2 bytes)
        header_packet = SeqNum + total_count + checksum + packet
        return header_packet

    def split_packet(self, header_packet):
        # Split packets into 4 sections, SeqNum, Total_count, checksum, data
        SeqNum, total_count, checksum = header_packet[0:4], header_packet[4:8], header_packet[8:10]
        data = header_packet[10:]
        return SeqNum, total_count, checksum, data

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
        SeqNum, total_count, checksum, packet_data = packet[0:4], packet[4:8], packet[8:10], packet[10:]
        calculated_checksum = self.create_checksum(SeqNum + total_count + packet_data)
        return checksum == calculated_checksum  # make sure both checksums are the same then return true else false

## Referenced Repos -----------------------------------------------------------------------------------------------------------------------------
## github.com/shihrer/csci466.project2/blob/master/RDT.py (debug_log function) (#1)
## github.com/haseeb-saeed/go-back-N/blob/master/sender.py (threads locking template) (#2,3)
## github.com/suryadev99/GoBack-N-Protocol/blob/main/GBN.py (self. class usage - loss/error functions (#4))
## github.com/CantOkan/BIL441_Computer_Networks/blob/master/RDT_Protocols/RDT2. (randint for corruption methods) (#5, 6)