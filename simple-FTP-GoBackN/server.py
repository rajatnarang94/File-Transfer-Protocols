from constants import TYPE_ACK, TYPE_DATA, TYPE_EOF, ACK_PORT, DATA_PAD
import pickle
from random import random
import sys
import os
from socket import socket, AF_INET, SOCK_DGRAM


def compute_checksum_for_chuck(chunk,checksum):
    for byte in range(0, len(chunk), 2):
        byte1 = ord(chunk[byte])
        if byte+1 < len(chunk):
            byte2 = ord(chunk[byte+1])
        else:
            byte2 = 0xffff
        merged_bytes = (byte1<<8) + byte2
        checksum_add = checksum + merged_bytes
        checksum = (checksum_add&0xffff) + (checksum_add>>16)

    return (checksum^0xffff)


def send_acknowledgement(ack_number, ACK_HOST_NAME):
    ack_packet = pickle.dumps([ack_number, DATA_PAD, TYPE_ACK])
    ack_socket = socket(AF_INET, SOCK_DGRAM)
    ack_socket.sendto(ack_packet, (ACK_HOST_NAME, ACK_PORT))
    ack_socket.close()


def main(PACKET_LOSS_PROB):
    last_received_packet = -1
    completed = False
    while not completed:
        received_data, addr = server_socket.recvfrom(65535)
        ACK_HOST_NAME = addr[0]
        received_data = pickle.loads(received_data)
        packet_sequence_number, packet_checksum, packet_type, packet_data = received_data
        if packet_type == TYPE_DATA:
            if random() >= PACKET_LOSS_PROB:
                if compute_checksum_for_chuck(packet_data, packet_checksum) != 0:
                    print("Packet ", packet_sequence_number, " has been dropped due to improper checksum")
                else:
                    if packet_sequence_number == last_received_packet+1:
                        send_acknowledgement(packet_sequence_number+1, ACK_HOST_NAME)
                        last_received_packet += 1

                        with open(FILE_NAME, 'ab') as file:
                            file.write(packet_data)
                    else:
                        expected_packet = last_received_packet + 1
                        send_acknowledgement(expected_packet, ACK_HOST_NAME)
            else:
                print("Packet loss, sequence number = ", packet_sequence_number)
        elif packet_type == TYPE_EOF:
            completed = True
            server_socket.close()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print('Need 3 arguments: 1) Server Port Number 2) File Name 3) MSS Value')
    else:
        SERVER_PORT, FILE_NAME, PACKET_LOSS_PROB = int(sys.argv[1]), sys.argv[2], float(sys.argv[3])
        server_socket = socket(AF_INET, SOCK_DGRAM)
        HOST_NAME = '0.0.0.0'

        server_socket.bind((HOST_NAME, SERVER_PORT))
        if os.path.isfile(FILE_NAME):
            os.remove(FILE_NAME)
        main(PACKET_LOSS_PROB)