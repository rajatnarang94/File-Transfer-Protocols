from constants import TYPE_ACK, TYPE_DATA, TYPE_EOF, ACK_PORT, DATA_PAD, TYPE_NACK
import pickle
from random import random
import sys
import os
from socket import socket, AF_INET, SOCK_DGRAM


last_received_packet=-1


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
    ack_packet = pickle.dumps((ack_number, DATA_PAD, TYPE_ACK))
    ack_socket = socket(AF_INET, SOCK_DGRAM)
    ack_socket.sendto(ack_packet,(ACK_HOST_NAME, ACK_PORT))
    ack_socket.close()


def send_negative_acknowledgement(packet_sequence_number, ACK_HOST_NAME):
    nack_packet = pickle.dumps((packet_sequence_number, DATA_PAD, TYPE_NACK))
    nack_socket = socket(AF_INET, SOCK_DGRAM)
    nack_socket.sendto(nack_packet, (ACK_HOST_NAME, ACK_PORT))
    nack_socket.close()


def main(PACKET_LOSS_PROB, window_minimum, window_maximum, server_window_buffer):
    global last_received_packet
    completed=False
    while not completed:
        received_data, addr = server_socket.recvfrom(65535)
        ACK_HOST_NAME = addr[0]
        received_data = pickle.loads(received_data)
        packet_sequence_number, packet_checksum, packet_type, packet_data = received_data
        if packet_type == TYPE_EOF:
            completed=True
            server_socket.close()
        elif packet_type == TYPE_DATA:
            if random()>=PACKET_LOSS_PROB:
                if compute_checksum_for_chuck(packet_data, packet_checksum) != 0:
                    print("Packet ", packet_sequence_number, " has been dropped due to improper checksum")
                else:
                    if packet_sequence_number >= window_minimum and packet_sequence_number <= window_maximum:
                        server_window_buffer[packet_sequence_number] = packet_data
                        if packet_sequence_number == window_minimum:
                            temp = packet_sequence_number
                            while True:
                                if temp not in server_window_buffer:
                                    break
                                else:
                                    window_minimum += 1
                                    window_maximum += 1
                                    with open(FILE_NAME, 'ab') as file:
                                        file.write(packet_data)
                                    server_window_buffer.pop(temp)
                                    temp += 1
                            send_acknowledgement(temp, ACK_HOST_NAME)
                        else:
                            temp = window_minimum
                            while temp <= window_maximum:
                                if temp not in server_window_buffer:
                                    send_negative_acknowledgement(temp, ACK_HOST_NAME)
                                    temp += 1
                                else:
                                    break
                    elif packet_sequence_number > window_maximum:
                        temp = window_minimum
                        while temp <= window_maximum:
                            send_negative_acknowledgement(temp, ACK_HOST_NAME)
                            temp += 1
            else:
                print("Packet loss, sequence number = ", packet_sequence_number)

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print('Need 4 arguments: 1) Server Port Number 2) File Name 3) MSS Value 4) Window Size')
    else:
        SERVER_PORT, FILE_NAME, PACKET_LOSS_PROB, N = int(sys.argv[1]), sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
        server_socket = socket(AF_INET, SOCK_DGRAM)
        HOST_NAME = '0.0.0.0'

        server_socket.bind((HOST_NAME, SERVER_PORT))
        if os.path.isfile(FILE_NAME):
            os.remove(FILE_NAME)
        window_minimum = 0
        window_maximum = N
        server_window_buffer = dict()
        main(PACKET_LOSS_PROB, window_minimum, window_maximum, server_window_buffer)