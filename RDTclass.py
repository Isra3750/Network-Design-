# RDTclass - phase 5 - network 4830

# imports the python socket library that allows for socket programming
import socket
import threading
from time import time
from random import randrange

DEBUG = True

class RDTclass:
    ACK = 0x00

    def __init__(self, send_address, send_port, recv_address, recv_port, window_size, mss=500,corruption=0, corruption_option=[1, 2, 3], loss=0, loss_option=[1, 2, 3], timeout=None):
        # Public Parameters
        self.base           = 0
        # Base number is set to index the GBN
        self.window_size    = window_size
        # window size is defined to introduce the number of packets to be transmitted in single window.
        self.send_address   = send_address
        # Sending Socket Address
        self.recv_address   = recv_address
        # Receiving socket Address
        self.send_port      = send_port
        # Sending data Port
        self.recv_port      = recv_port
        # Receiving data port

        ##
        self.corruption         = corruption
        # For estimating the corruption percentage
        self.corruption_option  = corruption_option
        # Corruption options are established

        ##
        self.loss               = loss
        # For estimating the loss percentage
        self.loss_option        = loss_option
        # Loss options are established
        self.timeout            = timeout
        # Timeout value is initilized
        self._seqnum             = 0
        # sequence number is initialized
        self._ack_pending_timers = []
        self._ack_pending_buffer = []
        for i in range(self.window_size):
            self._ack_pending_buffer.append(i)

        # Sockets
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Sending socket.
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Receiving socket.
        self.recv_sock.bind((self.recv_address, self.recv_port))
        
        # Threads and Locks
        self._base_l        = threading.Lock()
        self._send_l        = threading.Lock()
        self._ack_pending_l = threading.Lock()

        # Flags
        self._send_complete_f    = False
        return

    def send(self, data):
        # Getting the number of packets to be transmitted and let the receiver know and informing the receiver side the value
        self._send_complete_f = False
        send_t      = threading.Thread(target=self._send, args=(data,))
        # Sending thread
        recv_ack_t  = threading.Thread(target=self._recv_ack)
        # ACK receiving thread

        if DEBUG:
            print(f"GBN: Starting ACK Receiving Process.")
        recv_ack_t.start()

        if DEBUG:
            print(f"GBN: Starting Sending Process.")
        send_t.start()

        send_t.join()
        recv_ack_t.join()
        return

    def recv(self):
        # Receive the number of bytes of data to be added
        data_buffer     = []
        total_packets   = 0xFFFF_FFFF
        
        # This loop is introduced to find the number of that are remaining for transmittion
        while self.base < total_packets:
            packet, address         = self.recv_sock.recvfrom(2048)
            header, packet_cnt, rcvd_data, cs  = self._parse_packet(packet)
            header                  = int.from_bytes(header, 'big')         # Sequence number.
            cs                      = int.from_bytes(cs, 'big')             # Packet checksum.

            # Verify the integrity of the received packet.
            if self.verify_checksum(packet) and ((not ((self.packet_corrupted(self.corruption)) and (3 in self.corruption_option))) or (1 in self.corruption_option)):
                total_packets = int.from_bytes(packet_cnt, 'big')  # Total number of packets in the transfer.

                # When the data packet's sequence number is equal to the base number, buffer the data,
                # increment the base number to request the next packet, and send the ACK for the packet.
                if header == self.base:
                    if DEBUG:
                        print(f"GBN: Buffering data {header}")
                    data_buffer.append(rcvd_data)
                    self.base += 1
                
                self._send_ack(self.base, total_packets)
            else:
                if DEBUG:
                    print(f"GBN: Checksum Invalid.")
                continue

        if DEBUG:
            print(f"GBN: Receive complete. (base = {self.base}, total_packets = {total_packets})")
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
                if DEBUG:
                    print("GBN: Connection closed by remote host.")
                break
            
            # Sequence used to monitor the sending window based on the end point of the window. When the base
            # packet of the sending window has been properly ACK'd, the sequence will add a new packet to the 
            # sending window.
            while self.seqnum < window_end:
                packet = self._add_header(data[self.seqnum], self.seqnum, len(data))

                if DEBUG: 
                    print(f"GBN: Sending Packet {self.seqnum}/{len(data) - 1}")
                else:
                    print(f"GBN: Sending Packet {self.seqnum}/{len(data) - 1}", end="\r")

                # Send the packet to the receiving host.
                if self.packet_lost(self.loss) and (3 in self.loss_option) and (not 1 in self.loss_option):
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


        if DEBUG:
            print(f"GBN: Data transfer complete.")
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

            header, packet_cnt, rcvd_data, cs  = self._parse_packet(packet)
            header                  = int.from_bytes(header, 'big')     # Sequence number.
            total_packets           = int.from_bytes(packet_cnt, 'big')
            rcvd_data               = int.from_bytes(rcvd_data, 'big')  # Packet data.
            cs                      = int.from_bytes(cs, 'big')         # Packet checksum.
            
            # If the checkusm is invalid for the received packet, discard the received packet
            # and wait to receive more ACKs from the receiving host.
            if (not self.verify_checksum(packet)) or (self.packet_corrupted(self.corruption) and (2 in self.corruption_option) and (not 1 in self.corruption_option)) and (header != total_packets):
                if DEBUG:
                    print(f"GBN: Checksum invalid.")
                continue
            else:
                total_data = int.from_bytes(packet_cnt, 'big') # Total number of packets in the transfer.

            # Stop the timeout process associated with the received ACK.
            self._base_l.acquire()
            while (header > self.base):
                
                self._ack_pending_l.acquire()
                if DEBUG:
                    print(f"GBN: ACK{header} received.")  
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

        if DEBUG:
            print(f"GBN: ACK{seqnum} receive timed out. Resending window (base = {self.base}), (retry = {retry}).")

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
        if DEBUG:
            print(f"GBN: Sending ACK{state}/{total_packets}")
        else:
            print(f"GBN: Sending ACK{state}/{total_packets}", end="\r")

        if (self.packet_lost(self.loss) and (2 in self.loss_option)) and (state != total_packets):
            return

        packet = self._add_header(self.ACK.to_bytes(1, 'big'), state, total_packets)
        self.send_sock.sendto(packet, (self.send_address, self.send_port))
        return
##
    # Adding the header and checksum value to each package
    def _add_header(self, packet, state, transfer_size):        
        header   = state.to_bytes(4, byteorder='big')
        header   = header + transfer_size.to_bytes(4, byteorder='big')
        # total number of packets in the transfer
        cs       = self.checksum(header + packet)
        # checksum calculation

        return header + packet + cs

##
    # Combining all the received packets
    def _parse_packet(self, packet):
        header          = packet[0:4]                  # Extract the header bytes.
        total_packets   = packet[4:8]                  # Extract the total number of packets in the transfer.
        data            = packet[8:(len(packet) - 2)]  # Extract the packet application data.
        cs              = packet[-2:]                  # Extract the packet checksum bytes.
        return header, total_packets, data, cs

    # corruption range is estimated with the option selected
    def packet_corrupted(self, percentage):
        if percentage >= randrange(1, 101):
            return True
        else:
            return False
    # packet loss is estimated with the option selected
    def packet_lost(self, percentage):
        if percentage >= randrange(1, 101):
            return True
        else:
            return False

    def checksum(self, packet):
        sum_    = 0
        cs_size = 16

        # Dividing the packet into 2 bytes and calculate then sum of a packet
        for i in range(0, len(packet), 2):
            sum_ += int.from_bytes(packet[i:i + 2], 'big')
        sum_ = bin(sum_)[2:]  # Change to binary
        while len(sum_) != cs_size:
            # convert to binary
            # getting the overflow coun
            if len(sum_) > cs_size:
                x = len(sum_) - cs_size
                sum_ = bin(int(sum_[0:x], 2) + int(sum_[x:], 2))[2:]
            if len(sum_) < cs_size:
                sum_ = '0' * (cs_size - len(sum_)) + sum_
        # get the compliment
        checksum = ''
        for i in sum_:
            if i == '1':
                checksum += '0'
            else:
                checksum += '1'
        # converting the 8 bit into 1 byte
        checksum = bytes(int(checksum[i: i + 8], 2) for i in range(0, len(checksum), 8))
        return checksum

    def verify_checksum(self, packet):
        packet_data = packet[:-2]
        packet_cs   = packet[-2:]
        # getting the original checksum
        # re-estimating the checksum to match with the original checksum
        cs          = self.checksum(packet_data)

        # verifying the two vales obtained from the checksum and returning the value
        if packet_cs == cs:
            return True
        else:
            return False
