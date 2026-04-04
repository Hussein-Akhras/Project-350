import socket
import threading
import sys

from protocol import send_json, receive_json


# FUNCTION LIST 
#==============================================================


#client handeling loop 
def handle_client(conn, addr):
    print(f"Started handler for {addr}")

    sock_file = conn.makefile("r")    

    username = None   # remember username of client


    try:   # safety block to avoid server crashing 
        first_message = receive_json(sock_file)
        if first_message is None: #chekcs for disconnections
            return
        
        if first_message.get("type") != "register":     #saftey check for message type received 
            send_json(conn, {"type": "error", "message": "First message must be register"})
            return

        requested_username = first_message.get("username", "").strip() #get username from json

        if requested_username == "": #if username empty return error
            send_json(conn, {"type": "register_failed", "message": "Username cannot be empty"})
            return

        with clients_lock: #locks the list for safety 
            if requested_username in clients: #checks for duplicate username 
                send_json(conn, {"type": "register_failed", "message": "Username already in use"})
                return

            clients[requested_username] = conn   #save in clients list
            username = requested_username

        send_json(conn, {"type": "register_ok"})
        print(f"User registered: {username}")

        while True:
            message = receive_json(sock_file)
            if message is None:
                break

            print(f"Received from {username}: {message}")

    except Exception as e:
        print(f"Error with {addr}: {e}")

    finally:
        if username is not None:
            with clients_lock:
                if username in clients:
                    del clients[username]
            print(f"Removed user: {username}") #removes 

        conn.close()
        print(f"Connection closed for {addr}")
#===============================================================


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
print(f"sever listening on {HOST}:{PORT}")

#main server accept loop do not touch this or server go boom #
while True:
    conn, addr = server.accept()
    print(f"New connection from {addr}")
    thread = threading.Thread(target=handle_client, args=(conn, addr))
    thread.start()


