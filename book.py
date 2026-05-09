import sys
import os
import re
import time
import math
import random
import json
import threading
import concurrent.futures
from http.server import HTTPServer, BaseHTTPRequestHandler
from shell_lite.runtime import *

# Initialize Runtime Helpers
builtins_map = get_builtins()
globals().update(builtins_map)

class DotDict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)
    def __setattr__(self, key, value):
        self[key] = value

STD_MODULES = get_std_modules()
# Wrap modules
for k, v in STD_MODULES.items():
    if isinstance(v, dict): STD_MODULES[k] = DotDict(v)

# Async Executor
_executor = concurrent.futures.ThreadPoolExecutor()

# HTTP Server Support
GLOBAL_ROUTES = {}
GLOBAL_STATIC_ROUTES = {}

class ShellLiteHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.handle_req()
    def do_POST(self):
        self.handle_req()
    def handle_req(self):
        path = self.path
        # Static Routes
        for prefix, folder in GLOBAL_STATIC_ROUTES.items():
            if path.startswith(prefix):
                clean_path = path[len(prefix):]
                if clean_path.startswith('/'):
                    clean_path = clean_path[1:]
                if clean_path == '': clean_path = 'index.html'
                file_path = os.path.join(folder, clean_path)
                if os.path.exists(file_path) and \
                   os.path.isfile(file_path):
                     self.send_response(200)
                     # Simple mime type guessing
                     if file_path.endswith('.css'):
                         settings = 'text/css'
                     elif file_path.endswith('.js'):
                         settings = 'application/javascript'
                     elif file_path.endswith('.html'):
                         settings = 'text/html'
                     else:
                         settings = 'application/octet-stream'
                     self.send_header('Content-type', settings)
                     self.end_headers()
                     with open(file_path, 'rb') as f:
                         self.wfile.write(f.read())
                     return
        handler = GLOBAL_ROUTES.get(path)
        if handler:
            try:
                res = handler()
                self.send_response(200)
                self.end_headers()
                if res: self.wfile.write(str(res).encode())
                else: self.wfile.write(b'OK')
            except Exception as e:
                self.send_response(500)
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.wfile.write(b'Not Found')

# --- Web DSL Support ---
class Tag:
    def __init__(self, name, attrs=None):
        self.name = name
        self.attrs = attrs or {}
        self.children = []
    def add(self, child):
        self.children.append(child)
    def __str__(self):
        attr_str = ''.join([f' {k}="{v}"' for k,v in self.attrs.items()])
        inner = ''.join([str(c) for c in self.children])
        if self.name in ('img', 'br', 'hr', 'input', 'meta', 'link'):
            return f'<{self.name}{attr_str} />'
        return f'<{self.name}{attr_str}>{inner}</{self.name}>'

class WebBuilder:
    def __init__(self): self.stack = []
    def push(self, tag):
        if self.stack: self.stack[-1].add(tag)
        self.stack.append(tag)
    def pop(self): return self.stack.pop() if self.stack else None
    def add_text(self, text):
        if self.stack: self.stack[-1].add(text)
        else: pass # Top level text?

_web_builder = WebBuilder()

class BuilderContext:
    def __init__(self, tag): self.tag = tag
    def __enter__(self):
        _web_builder.push(self.tag)
        return self.tag
    def __exit__(self, *args): _web_builder.pop()

def _make_tag_fn(name):
    def fn(*args):
        attrs = {}
        content = []
        for arg in args:
            if isinstance(arg, dict):
                attrs.update(arg)
            elif isinstance(arg, str) and '=' in arg and ' ' not in arg:
                k, v = arg.split('=', 1)
                attrs[k] = v
            else:
                content.append(arg)
        t = Tag(name, attrs)
        for c in content:
            t.add(c)
        return t
    return fn

for t in ['div', 'p', 'h1', 'h2', 'h3', 'h4', 'span', 'a',
          'img', 'button', 'input', 'form', 'ul', 'li',
          'html', 'head', 'body', 'title', 'meta', 'link',
          'script', 'style', 'br', 'hr']:
    globals()[t] = _make_tag_fn(t)

# --- User Script ---
from constants import *
from moves import *
def square_to_str(sq):
    _slang_ret = None
    r = int((sq / 8))
    c = (sq % 8)
    f = char((ord('a') + c))
    rank = str((8 - r))
    return (f + rank)
    return _slang_ret
def move_to_str(move):
    _slang_ret = None
    return (square_to_str((move . from_sq)) + square_to_str((move . to_sq)))
    return _slang_ret
opening_book = {'': ['e2e4', 'd2d4', 'g1f3', 'c2c4'], 'e2e4': ['e7e5', 'c7c5', 'e7e6', 'c7c6'], 'e2e4 e7e5': ['g1f3', 'f2f4', 'b1c3'], 'e2e4 e7e5 g1f3': ['b8c6', 'g8f6', 'd7d6'], 'e2e4 e7e5 g1f3 b8c6': ['f1b5', 'f1c4', 'd2d4'], 'e2e4 e7e5 g1f3 b8c6 f1b5': ['a7a6', 'g8f6'], 'e2e4 e7e5 g1f3 b8c6 f1c4': ['g8f6', 'f1c5'], 'e2e4 e7e5 g1f3 b8c6 d2d4': ['e5d4'], 'e2e4 e7e5 g1f3 b8c6 d2d4 e5d4': ['f3d4', 'c2c3'], 'e2e4 c7c5': ['g1f3', 'b1c3', 'c2c3'], 'e2e4 c7c5 g1f3': ['d7d6', 'e7e6', 'b8c6'], 'e2e4 c7c5 g1f3 d7d6': ['d2d4'], 'e2e4 c7c5 g1f3 d7d6 d2d4 c5d4': ['f3d4'], 'e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4': ['g8f6'], 'e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6': ['b1c3'], 'e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3': ['a7a6', 'g7g6', 'e7e6'], 'e2e4 e7e6': ['d2d4'], 'e2e4 e7e6 d2d4': ['d7d5'], 'e2e4 e7e6 d2d4 d7d5': ['b1c3', 'e4e5', 'e4d5'], 'e2e4 c7c6': ['d2d4'], 'e2e4 c7c6 d2d4': ['d7d5'], 'e2e4 c7c6 d2d4 d7d5': ['b1c3', 'e4e5', 'e4d5'], 'd2d4': ['d7d5', 'g8f6'], 'd2d4 d7d5': ['c2c4', 'g1f3'], 'd2d4 d7d5 c2c4': ['e7e6', 'c7c6', 'd5c4'], 'd2d4 d7d5 c2c4 e7e6': ['b1c3', 'g1f3'], 'd2d4 d7d5 c2c4 e7e6 b1c3': ['g8f6'], 'd2d4 g8f6': ['c2c4', 'g1f3'], 'd2d4 g8f6 c2c4': ['e7e6', 'g7g6'], 'd2d4 g8f6 c2c4 e7e6': ['g1f3', 'b1c3'], 'd2d4 g8f6 c2c4 g7g6': ['b1c3', 'g1f3'], 'd2d4 g8f6 c2c4 g7g6 b1c3': ['d7d5', 'e2e4']}
def is_starting_position(board):
    _slang_ret = None
    if ((((board . squares[0]) != (ROOK + BLACK)) or ((board . squares[4]) != (KING + BLACK))) or ((board . squares[7]) != (ROOK + BLACK))):
            return False
    if ((((board . squares[56]) != (ROOK + WHITE)) or ((board . squares[60]) != (KING + WHITE))) or ((board . squares[63]) != (ROOK + WHITE))):
            return False
    return True
    return _slang_ret
def get_book_move(board):
    _slang_ret = None
    if (not is_starting_position(board)):
            return null
    seq = ''
    for state in (board . history):
            m = state['move']
            m_str = move_to_str(m)
            if (seq == ''):
                        seq = m_str
            else:
                        seq = ((seq + ' ') + m_str)
    if contains(opening_book, seq):
            choices = opening_book[seq]
            n_choices = len(choices)
            if (n_choices > 0):
                        idx = randint(0, (n_choices - 1))
                        chosen_str = choices[idx]
                        legal_moves = generate_legal_moves(board)
                        for m in legal_moves:
                                        if (move_to_str(m) == chosen_str):
                                                            print(('info string Opening book play: ' + chosen_str))
                                                            return m
    return null
    return _slang_ret