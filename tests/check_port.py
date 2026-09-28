#!/usr/bin/env python3
"""Port checker used inside the sandbox: python3 check_port.py 2004"""
import socket
import sys
s = socket.socket()
s.settimeout(1)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
