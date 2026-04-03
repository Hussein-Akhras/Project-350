import json 

def send_json(sock, data):
    message = json.dumps(data) + "\n"
    sock.sendall(message.encode("utf-8"))


def receive_json(sock_file):
    line = sock_file.readline()
    if line == "":
        return None
    return json.loads(line)



