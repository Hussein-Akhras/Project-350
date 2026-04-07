import socket
import threading
import sys
import pygame

from protocol import send_json, receive_json

SERVER_IP = sys.argv[1]
SERVER_PORT = int(sys.argv[2])