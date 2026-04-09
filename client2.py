import socket
import threading
import sys
import pygame

from protocol import send_json, receive_json
FPS=60
CELL_SIZE = 30
GRID_WIDTH = 30
GRID_HEIGHT = 20
BOARD_OFFSET_Y = 130
SERVER_IP = sys.argv[1]
SERVER_PORT = int(sys.argv[2])

# client socket/clock /fonts 
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((SERVER_IP, SERVER_PORT))
sock_file = client.makefile("r")
pygame.init()
screen = pygame.display.set_mode((900, 700))
pygame.display.set_caption("Python Arena Client")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont(None, 32)
BIG_FONT = pygame.font.SysFont(None, 48)
SMALL_FONT = pygame.font.SysFont(None, 24)


#color helpers
BG = (30, 30, 30)
WHITE = (255, 255, 255)
GREEN = (0, 200, 0)
RED = (220, 60, 60)
YELLOW = (240, 220, 70)

#client state helpers
state_lock = threading.Lock()
running = True
my_username = ""
screen_name = "login"
available_players = []
selected_index = 0
status_message = "Enter username"
username_input = ""
match_state = None
game_result = None
my_role = ""
opponent_name = ""
snake_color = GREEN
control_keys = {pygame.K_UP: "UP", pygame.K_DOWN: "DOWN", pygame.K_LEFT: "LEFT", pygame.K_RIGHT: "RIGHT"}
is_registered = False

#Function list
#======================================================================

def draw_text(text, font, color, x, y):
    surf = font.render(text, True, color)
    screen.blit(surf, (x, y))

def grid_to_pixel(cell):
    x, y = cell
    return x * CELL_SIZE, y * CELL_SIZE


def cell_rect(cell):
    px, py = grid_to_pixel(cell)
    return pygame.Rect(px, py, CELL_SIZE, CELL_SIZE)


listener_running = True

def listen_to_server():
    global running, listener_running, available_players, status_message, is_registered, screen_name, my_role, opponent_name, match_state, game_result
    while listener_running:
        try:
            message = receive_json(sock_file)
            if message is None:
                status_message = "Disconnected from server"
                running = False
                break

            msg_type = message.get("type")

            if msg_type == "register_ok":
                is_registered = True
                status_message = "Registered successfully"
                screen_name = "lobby"

            elif msg_type == "register_failed":
                status_message = message.get("message", "Registration failed")

            elif msg_type == "player_list":

                with state_lock:
                    available_players = message.get("players", [])
                    
                if screen_name != "game":
                     screen_name = "lobby"


            elif msg_type == "match_started":
                my_role = message.get("role", "")
                opponent_name = message.get("opponent", "")
                game_result = None
                status_message = "Match started"
                screen_name = "game"


            elif msg_type == "state":
                with state_lock:
                    match_state = message

            elif msg_type == "game_over":
                with state_lock:
                    game_result = message

                winner = message.get("winner", "unknown")
                reason = message.get("reason", "")

                if winner == "draw":
                    status_message = "Match ended in a draw"
                elif winner == my_username:
                    status_message = "You won!"
                else:
                    status_message = f"{winner} won!"

                if reason:
                    status_message += f" ({reason})"

                screen_name = "result"
                match_state = None


 


            elif msg_type == "error":
                status_message = message.get("message", "Server error")


            else:
                status_message = f"Unknown message: {msg_type}"
            

        except Exception as e:
            status_message = f"Connection error: {e}"
            running = False
            break


listener_thread = threading.Thread(target=listen_to_server, daemon=True)
listener_thread.start()
def send_register():
    global my_username, status_message, username_input
    name = username_input.strip()
    if not name:
        status_message = "Username required"
        return
    my_username = name
    send_json(client, {"type": "register", "username": name})
    status_message = "Registering..."



def send_challenge():
    global status_message, selected_index
    with state_lock:
        if not available_players:
            return
        target = available_players[selected_index]
    send_json(client, {"type": "challenge", "target": target})
    status_message = f"Challenging {target}..."


def send_direction(direction):
    if screen_name != "game":
        return
    send_json(client, {"type": "input", "direction": direction})


def draw_login():
    screen.fill(BG)
    draw_text("Python Arena - Login", BIG_FONT, WHITE, 40, 40)
    pygame.draw.rect(screen, WHITE, (40, 140, 320, 45), 2)
    draw_text("Username:", FONT, WHITE, 40, 110)
    draw_text(username_input, FONT, WHITE, 50, 150)
    draw_text("Type your username and press ENTER", SMALL_FONT, YELLOW, 40, 210)
    draw_text(status_message, SMALL_FONT, GREEN if is_registered else YELLOW, 40, 250)

def draw_lobby():
    screen.fill(BG)
    draw_text(f"Logged in as: {my_username}", FONT, WHITE, 40, 30)
    draw_text("Lobby - Select a player and press ENTER", BIG_FONT, WHITE, 40, 70)
    draw_text(status_message, SMALL_FONT, YELLOW, 40, 120)
    with state_lock:
        players_copy = available_players[:]
    if not players_copy:
        draw_text("No available players yet", FONT, RED, 40, 180)
    for i, player in enumerate(players_copy):
        color = GREEN if i == selected_index else WHITE
        prefix = "-> " if i == selected_index else "   "
        draw_text(prefix + player, FONT, color, 60, 180 + i*40)




def draw_game():
    screen.fill(BG)
    with state_lock:
        state = match_state
    if not state:
        draw_text("Waiting for match state...", FONT, YELLOW, 40, 40)
        return
    draw_text(f"You: {state.get('you', '')}", FONT, WHITE, 40, 20)
    draw_text(f"Opponent: {state.get('opponent', '')}", FONT, WHITE, 220, 20)
    draw_text(f"Score: {state['scores'].get(state.get('you', ''), 0)}", FONT, GREEN, 40, 60)
    draw_text(f"Enemy Score: {state['scores'].get(state.get('opponent', ''), 0)}", FONT, RED, 220, 60)
    draw_text(f"Health: {state['scores'].get(state.get('you', ''), 0)}", FONT, GREEN, 40, 60)
    draw_text(f"Enemy Health: {state['scores'].get(state.get('opponent', ''), 0)}", FONT, RED, 220, 60)  
    draw_text(status_message, SMALL_FONT, YELLOW, 40, 95)
    for cell in state.get("obstacles", []):
        rect = cell_rect(cell)
        rect.y += 130
        pygame.draw.rect(screen, RED, rect)
    for cell in state.get("pies", []):
        rect = cell_rect(cell)
        rect.y += 130
        pygame.draw.ellipse(screen, YELLOW, rect)
    pygame.draw.rect(screen, WHITE, pygame.Rect(0, 130, 30 * CELL_SIZE, 20 * CELL_SIZE), 2)
    snakes = state.get("snakes", {})
    my_name = state.get("you", "")
    enemy_name = state.get("opponent", "")
    for cell in snakes.get(my_name, []):
        rect = cell_rect(cell)
        rect.y += 130
        pygame.draw.rect(screen, GREEN, rect)
    for cell in snakes.get(enemy_name, []):
        rect = cell_rect(cell)
        rect.y += 130
        pygame.draw.rect(screen, WHITE, rect)


def draw_result():
    screen.fill(BG)
    if not game_result:
        draw_text("No result available", FONT, RED, 40, 40)
        return

    winner = game_result.get("winner", "unknown")
    scores = game_result.get("scores", {})
    reason = game_result.get("reason", "")

    if winner == "draw":
        title = "Draw!"
        title_color = YELLOW
    elif winner == my_username:
        title = "You Win!"
        title_color = GREEN
    else:
        title = f"{winner} Wins!"
        title_color = RED

    draw_text("Match Result", BIG_FONT, WHITE, 40, 40)
    draw_text(title, BIG_FONT, title_color, 40, 100)
    draw_text(f"Winner: {winner}", FONT, WHITE, 40, 160)
    draw_text(f"Your health: {scores.get(my_username, 0)}", FONT, WHITE, 40, 200)
    draw_text(f"Opponent health: {scores.get(opponent_name, 0)}", FONT, WHITE, 40, 240)

    if reason:
        draw_text(f"Reason: {reason}", SMALL_FONT, YELLOW, 40, 280)

    draw_text("Press ESC to quit", SMALL_FONT, WHITE, 40, 330)



while running:
    clock.tick(FPS)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

            elif screen_name == "login":
                if event.key == pygame.K_RETURN:
                    send_register()
                elif event.key == pygame.K_BACKSPACE:
                    username_input = username_input[:-1]
                elif event.unicode.isprintable() and len(username_input) < 16:
                    username_input += event.unicode

            elif screen_name == "lobby":
                with state_lock:
                    players_count = len(available_players)
                if event.key == pygame.K_UP and players_count > 0:
                    selected_index = (selected_index - 1) % players_count
                elif event.key == pygame.K_DOWN and players_count > 0:
                    selected_index = (selected_index + 1) % players_count
                elif event.key == pygame.K_RETURN and players_count > 0:
                    send_challenge()

            elif screen_name == "game":
                if event.key in control_keys:
                    send_direction(control_keys[event.key])

    if screen_name == "login":
        draw_login()
    elif screen_name == "lobby":
        draw_lobby()
    elif screen_name == "game":
        draw_game()
    elif screen_name == "result":
        draw_result()

    pygame.display.flip()

listener_running = False
try:
    client.shutdown(socket.SHUT_RDWR)
except:
    pass

client.close()

if listener_thread.is_alive():
    listener_thread.join(timeout=1)

pygame.quit()
sys.exit()