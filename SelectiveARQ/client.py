from socket import socket, AF_INET, SOCK_DGRAM
import sys
import pickle
from constants import TYPE_ACK, TYPE_DATA, TYPE_EOF, ACK_HOST, ACK_PORT, RTT, TYPE_NACK
from signal import alarm, setitimer, SIGALRM, signal, ITIMER_REAL
from threading import Thread
import multiprocessing
from datetime import datetime

max_seq_number = 0
last_ack_packet = -1
last_send_packet = -1

SEND_HOST, SEND_PORT = '', ''

thread_lock = multiprocessing.Lock()
sliding_window = set()
client_buffer = dict()
client_socket = socket(AF_INET, SOCK_DGRAM)


sending_completed = False
t_start = 0
t_end = 0


def rdt_send(N, SEND_HOST, SEND_PORT):
    global last_send_packet, last_ack_packet, sliding_window,client_buffer, t_start

    t_start = datetime.now()
    size_client_buffer = len(client_buffer)

    while len(sliding_window) < min(size_client_buffer, N):
        if last_ack_packet == -1:
            packet = client_buffer.get(last_send_packet + 1)
            client_socket.sendto(packet, (SEND_HOST, SEND_PORT))
            alarm(0)
            setitimer(ITIMER_REAL, RTT)
            last_send_packet += 1
            sliding_window.add(last_send_packet)


def compute_checksum_for_chuck(chunk):
    checksum = 0
    chunk = str(chunk)
    for byte in range(0, len(chunk), 2):
        byte1 = ord(chunk[byte])
        if byte + 1 < len(chunk):
            byte2 = ord(chunk[byte + 1])
        else:
            byte2 = 0xffff
        merged_bytes = (byte1 << 8) + byte2
        checksum_add = checksum + merged_bytes
        checksum = (checksum_add & 0xffff) + (checksum_add >> 16)

    return (checksum ^ 0xffff)


def ack_process(N, SEND_HOST, SEND_PORT):
    global last_ack_packet, last_send_packet, sending_completed, t_end, t_start, sliding_window, client_buffer

    ack_socket = socket(AF_INET, SOCK_DGRAM)
    ack_socket.bind((ACK_HOST, ACK_PORT))

    while True:
        received_packet = ack_socket.recv(65535)
        reply = pickle.loads(received_packet)
        sequence_no, padding, type = reply
        if type == TYPE_ACK:
            current_ack_seq_number = sequence_no - 1
            print "Received ACK, sequence number = " + str(current_ack_seq_number)
            if last_ack_packet >= -1:
                thread_lock.acquire()

                if current_ack_seq_number == max_seq_number:
                    client_socket.sendto(pickle.dumps(["0", "0", TYPE_EOF, "0"]), (SEND_HOST, SEND_PORT))
                    thread_lock.release()
                    sending_completed = True
                    t_end = datetime.now()
                    t_total = t_end - t_start
                    print('t_total', t_total)
                    break
                elif current_ack_seq_number > last_ack_packet:
                    while last_ack_packet < current_ack_seq_number:
                        alarm(0)
                        setitimer(ITIMER_REAL, RTT)
                        last_ack_packet = last_ack_packet + 1
                        sliding_window.remove(last_ack_packet)
                        client_buffer.pop(last_ack_packet)
                        while len(sliding_window) < min(len(client_buffer), N):
                            if last_send_packet < max_seq_number:
                                packet = client_buffer.get(last_send_packet + 1)
                                client_socket.sendto(packet, (SEND_HOST, SEND_PORT))
                                sliding_window.add(last_send_packet + 1)
                                last_send_packet += 1
                    thread_lock.release()
                else:
                    thread_lock.release()
        elif type == TYPE_NACK:
            thread_lock.acquire()
            current_nack_seq_number = sequence_no
            print("Received NACK, sequence number = ", current_nack_seq_number)
            if current_nack_seq_number == last_ack_packet + 1:
                alarm(0)
                setitimer(ITIMER_REAL, RTT)
            packet = client_buffer[current_nack_seq_number]
            client_socket.sendto(packet, (SEND_HOST, SEND_PORT))
            thread_lock.release()


def timeout_thread(timeout_th, frame):
    global last_ack_packet
    if last_ack_packet == last_send_packet - len(sliding_window):
        print "Timeout, sequence number = " + str(last_ack_packet + 1)
        thread_lock.acquire()
        alarm(0)
        setitimer(ITIMER_REAL, RTT)
        packet = client_buffer[last_ack_packet + 1]
        client_socket.sendto(packet, (SEND_HOST, SEND_PORT))
        thread_lock.release()



if __name__ == "__main__":
    if len(sys.argv) < 6:
        print(
            'Need 5 arguments: 1) Server IP address 2) Server Port Number 3) File Name 4) Window Size 5) MSS Value')
    else:
        SEND_HOST, SEND_PORT, FILE_NAME, N, MSS = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(
            sys.argv[5])

        sequence_number = 0
        try:
            with open(FILE_NAME, 'rb') as f:
                while True:
                    chunk = f.read(MSS)
                    if chunk:
                        max_seq_number = sequence_number
                        chunk_checksum = compute_checksum_for_chuck(chunk)
                        client_buffer[sequence_number] = pickle.dumps(
                            [sequence_number, chunk_checksum, TYPE_DATA, chunk])
                        sequence_number += 1
                    else:
                        break
        except:
            sys.exit("Failed to open file!")

        signal(SIGALRM, timeout_thread)
        ack_thread = Thread(target=ack_process, args=(N, SEND_HOST, SEND_PORT,))
        ack_thread.start()
        rdt_send(N, SEND_HOST, SEND_PORT)
        while True:
            if sending_completed:
                break
        ack_thread.join()
        client_socket.close()