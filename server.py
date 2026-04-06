import socket
import threading
import sys

from protocol import send_json, receive_json

BOARD_WIDTH = 30
BOARD_HEIGHT = 20


# FUNCTION LIST 
#==============================================================



#collision go boom
def apply_collision_damage():
    global current_match
    with match_lock:
        if current_match is None: 
            return
        for player in [current_match["player1"], current_match["player2"]]:
            head = current_match["snakes"][player][0]
            if hit_wall_or_obstacle(head, current_match["obstacles"]):
                current_match["scores"][player] -= 20

            if current_match["scores"][player] <= 0:
                current_match["status"] = "finished"

#collision detection
def hit_wall_or_obstacle(head, obstacles):
    x, y = head
    if x < 0 or x >= BOARD_WIDTH: return True
    if y < 0 or y >= BOARD_HEIGHT: return True
    if head in obstacles: return True
    return False

# match updating 
def advance_match():
    with match_lock:
        if current_match is None or current_match["status"] != "running": return
        players = [current_match["player1"], current_match["player2"]]
    for player in players:
        move_one_snake(player)

#snake moving 
def move_one_snake(username):
    with match_lock:
        if current_match is None:
            return
        snake = current_match["snakes"][username]

        new_head = next_head_position(snake[0], current_match["directions"][username])

        snake.insert(0, new_head)

        if new_head in current_match["pies"]:
             current_match["scores"][username] += 10; current_match["pies"].remove(new_head)
        else:
            snake.pop()

#direction handeling 
def next_head_position(head, direction):
    x, y = head
    if direction == "UP": return (x, y - 1)
    if direction == "DOWN": return (x, y + 1)
    if direction == "LEFT": return (x - 1, y)
    if direction == "RIGHT": return (x + 1, y)
    return head

#handles client inputs 
def handle_input(username, direction):
    if direction not in {"UP", "DOWN", "LEFT", "RIGHT"}: return
    with match_lock:
        if current_match is None or current_match["status"] != "running": return
        if username not in current_match["directions"]: return
        current_match["directions"][username] = direction

#mgame state helper
def send_match_state():
    with match_lock:
        if current_match is None: return
        state = current_match.copy()
    p1, p2 = state["player1"], state["player2"]
    with clients_lock:
        if p1 in clients: send_json(clients[p1], {"type": "state", **state, "you": p1, "opponent": p2})
        if p2 in clients: send_json(clients[p2], {"type": "state", **state, "you": p2, "opponent": p1})

#shows player list to all players
def broadcast_player_lists():
    with clients_lock:
        usernames = list(clients.keys())
        for name, conn in clients.items():
            send_json(conn, {"type": "player_list", "players": [u for u in usernames if u != name]})

#client handeling fucntion
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
        broadcast_player_lists()
        print(f"User registered: {username}")

        while True:
            message = receive_json(sock_file)
            msg_type = message.get("type")

            if msg_type == "challenge":
                target = message.get("target", "").strip()
                handle_challenge(conn, username, target)
                continue

            if msg_type == "input":
                direction = message.get("direction", "").strip().upper()
                handle_input(username, direction)
                advance_match()
                apply_collision_damage()
                send_match_state()
                continue


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
                broadcast_player_lists()
            print(f"Removed user: {username}") #removes 

        conn.close()
        print(f"Connection closed for {addr}")

#challenge handeling 
def handle_challenge(conn, challenger, target):
    with clients_lock:
      target_conn = clients.get(target)

    if target == "" or target == challenger or target_conn is None : #rject request incase we are not challenging another valid player 
        send_json(conn, {"type": "error", "message": "Invalid target "})
        return
    

    global current_match
    with match_lock:
        if current_match is not None:
            send_json(conn, {"type": "error", "message": "A match is already running"})
            return
        current_match = {
            "player1": challenger, "player2": target,
            "scores": {challenger: 100, target: 100},
            "directions": {challenger: "RIGHT", target: "LEFT"},
            "snakes": {challenger: [(5, 10), (4, 10), (3, 10)], target: [(24, 10), (25, 10), (26, 10)]},
            "pies": [(15, 10)],
            "obstacles": [(10, 6), (10, 7), (20, 12), (20, 13)],
            "status": "running"
        }




    send_json(conn, {"type": "match_started", "role": "player1", "opponent": target})
    send_json(target_conn, {"type": "match_started", "role": "player2", "opponent": challenger})
    send_match_state()
    broadcast_player_lists()
    print(f"Match started: {challenger} vs {target}")



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


