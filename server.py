import socket
import threading
import sys

from protocol import send_json, receive_json

#listening on all available interfaces#

HOST = "0.0.0.0"

#accepts command line
PORT = int(sys.argv[1])


#clients list#
clients = {} 
clients_lock = threading.Lock()  

#match list#
current_match = None
match_lock = threading.Lock()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.binf((HOST,PORT))
server.listen

#main server accept loop do not touch this or server dies #
print(f"sever listening on {HOST}:{PORT}")



while True:
    conn, addr = server.accept()
    print(f"New connection from {addr}")

    thread = threading.Thread(target=handle_client, args=(conn, addr))
    thread.start()


def handle_client(conn, addr):
    print(f"Started handler for {addr}")
    sock_file = conn.makefile("r")

    try:
        while True:
            message = receive_json(sock_file)
            if message is None:
                break

            print(f"Received from {addr}: {message}")

    except Exception as e:
        print(f"Error with {addr}: {e}")

    finally:
        conn.close()
        print(f"Connection closed for {addr}")
