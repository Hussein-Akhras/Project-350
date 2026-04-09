import socket
import threading
import sys
import random
import time

from protocol import send_json, receive_json

BOARD_WIDTH = 30
BOARD_HEIGHT = 20
MATCH_DURATION = 120
OPPOSITES = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}


# FUNCTION LIST 
#==============================================================



def head_to_head_collision():
    with match_lock:
        if current_match is None: return False
        p1, p2 = current_match["player1"], current_match["player2"]
        h1 = current_match["snakes"][p1][0]
        h2 = current_match["snakes"][p2][0]
        return h1 == h2

#time loop 
def run_match_loop():
    while True:
        time.sleep(0.15)
        with match_lock:
            if current_match is None or current_match["status"] != "running":
                break
            if time.time() >= current_match["end_time"]:
                current_match["status"] = "finished"
        result = finish_match_if_needed()
        if result is not None:
            with clients_lock:
                for player in result["players"]:
                    if player in clients: send_json(clients[player], result)
            broadcast_player_lists(); break
        

        advance_match()
        respawn_pie()
        apply_collision_damage()
        send_match_state()
        
        result = finish_match_if_needed()
        if result is not None:
            with clients_lock:
                for player in result["players"]:
                    if player in clients:
                        send_json(clients[player], result)
            broadcast_player_lists()
            break

# hrob min el match 
def abort_match_on_disconnect(username):
    global current_match
    with match_lock:
        if current_match is None or not player_in_current_match(username): return None
        p1, p2 = current_match["player1"], current_match["player2"]
        winner = p2 if username == p1 else p1
        result = {"type": "game_over", "winner": winner, "reason": "disconnect", "scores": current_match["scores"].copy(), "players": [p1, p2]}
        current_match = None
        return result

#check for the current players
def player_in_current_match(username):
    with match_lock:
        if current_match is None or current_match["status"] != "running":
            return False
        return username in {current_match["player1"], current_match["player2"]}

#cool addition randomly generated pie respawns so every match doesnt feel the same
def respawn_pie():
    with match_lock:
        if current_match is None or current_match["pies"]:
            return
        occupied = set(current_match["obstacles"])

        for snake in current_match["snakes"].values(): 
            occupied.update(snake)

        while True:
            pos = (random.randint(0, BOARD_WIDTH - 1), random.randint(0, BOARD_HEIGHT - 1))
            if pos not in occupied: current_match["pies"] = [pos];return

#damage detection
def hit_snake(player):
    with match_lock:
        if current_match is None: 
            return False
        head = current_match["snakes"][player][0]
        own_body = current_match["snakes"][player][1:]
        other = current_match["player2"] if player == current_match["player1"] else current_match["player1"]
        other_body = current_match["snakes"][other]
        return head in own_body or head in other_body

# match termination 
def finish_match_if_needed():
    global current_match
    with match_lock:
        if current_match is None or current_match["status"] != "finished": 
            return None
        p1, p2 = current_match["player1"], current_match["player2"]
        s1, s2 = current_match["scores"][p1], current_match["scores"][p2]
        winner = p1 if s1 > s2 else p2 if s2 > s1 else "draw"
        result = {"type": "game_over", "winner": winner, "scores": current_match["scores"].copy(), "players": [p1, p2]}
        current_match = None
        return result

#collision go boom
def apply_collision_damage():
    global current_match
    with match_lock:
        if current_match is None: 
            return
        if head_to_head_collision():

            current_match["scores"][current_match["player1"]] -= 25
            current_match["scores"][current_match["player2"]] -= 25

        for player in [current_match["player1"], current_match["player2"]]:

            head = current_match["snakes"][player][0]
            if hit_wall_or_obstacle(head, current_match["obstacles"]) or hit_snake(player):
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
    if direction not in OPPOSITES: return
    with match_lock:
        if current_match is None or current_match["status"] != "running": return
        if username not in current_match["directions"]: return
        current_dir = current_match["directions"][username]
        if direction != OPPOSITES[current_dir]: current_match["directions"][username] = direction

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
    for name in usernames:
        players = [u for u in usernames if u != name and not player_in_current_match(u)]
        with clients_lock:
            if name in clients:
                send_json(clients[name], {"type": "player_list", "players": players})
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
                continue

            if message is None:
                break

            print(f"Received from {username}: {message}")

    except Exception as e:
        print(f"Error with {addr}: {e}")

    finally:
        result = abort_match_on_disconnect(username)
        if result is not None:
            with clients_lock:
                for player in result["players"]:
                    if player in clients: send_json(clients[player], result)

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
    
    if player_in_current_match(challenger) or player_in_current_match(target):
        send_json(conn, {"type": "error", "message": "One of the players is already in a match"})
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
            "status": "running",
            "end_time": time.time() + MATCH_DURATION
        }

    send_json(conn, {"type": "match_started", "role": "player1", "opponent": target})
    send_json(target_conn, {"type": "match_started", "role": "player2", "opponent": challenger})
    send_match_state()
    match_thread = threading.Thread(target=run_match_loop, daemon=True)
    match_thread.start()
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
match_lock = threading.RLock()

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST,PORT))
server.listen()
print(f"sever listening on {HOST}:{PORT}")

#main server accept loop do not touch this or server go boom #
while True:
    conn, addr = server.accept()
    print(f"New connection from {addr}")
    thread = threading.Thread(target=handle_client, args=(conn, addr))
    thread.start()


