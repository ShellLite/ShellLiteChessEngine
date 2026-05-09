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
class Board(Instance):
    def __init__(self, dummy=0, squares=[], turn=WHITE, castling={'WK': True, 'WQ': True, 'BK': True, 'BQ': True}, ep_square=(0 - 1), halfmove=0, fullmove=1, history=[]):
        self.dummy = dummy
        self.squares = squares
        self.turn = turn
        self.castling = castling
        self.ep_square = ep_square
        self.halfmove = halfmove
        self.fullmove = fullmove
        self.history = history

    def get_king_square(self, color):
        for i in range(0, 64):
                    p = self.squares[i]
                    if (((p != EMPTY) and (get_piece_type(p) == KING)) and (get_piece_color(p) == color)):
                                    return i
        return (0 - 1)
    def reset(self):
        self.squares = []
        for _ in range(64):
                    _slang_ret = add(self.squares, EMPTY)
                    _web_builder.add_text(_slang_ret)
        self.squares[0] = (ROOK + BLACK)
        self.squares[1] = (KNIGHT + BLACK)
        self.squares[2] = (BISHOP + BLACK)
        self.squares[3] = (QUEEN + BLACK)
        self.squares[4] = (KING + BLACK)
        self.squares[5] = (BISHOP + BLACK)
        self.squares[6] = (KNIGHT + BLACK)
        self.squares[7] = (ROOK + BLACK)
        for i in range(8, 16):
                    self.squares[i] = (PAWN + BLACK)
        for i in range(48, 56):
                    self.squares[i] = (PAWN + WHITE)
        self.squares[56] = (ROOK + WHITE)
        self.squares[57] = (KNIGHT + WHITE)
        self.squares[58] = (BISHOP + WHITE)
        self.squares[59] = (QUEEN + WHITE)
        self.squares[60] = (KING + WHITE)
        self.squares[61] = (BISHOP + WHITE)
        self.squares[62] = (KNIGHT + WHITE)
        self.squares[63] = (ROOK + WHITE)
        self.turn = WHITE
        self.ep_square = (0 - 1)
        self.halfmove = 0
        self.fullmove = 1
        self.history = []
    def set_fen(self, fen_str):
        self.squares = []
        for _ in range(64):
                    _slang_ret = add(self.squares, EMPTY)
                    _web_builder.add_text(_slang_ret)
        self.history = []
        parts = split(fen_str)
        if empty(parts):
                    return False
        placement = parts[0]
        row = 0
        col = 0
        n = len(placement)
        for i in range(0, n):
                    char_val = placement[i]
                    if (char_val == '/'):
                                    row = (row + 1)
                                    col = 0
                    else:
                                    if ((((((((char_val == '1') or (char_val == '2')) or (char_val == '3')) or (char_val == '4')) or (char_val == '5')) or (char_val == '6')) or (char_val == '7')) or (char_val == '8')):
                                                        col = (col + int(char_val))
                                    else:
                                                        piece = EMPTY
                                                        if (char_val == 'p'):
                                                                                piece = (PAWN + BLACK)
                                                        else:
                                                                                if (char_val == 'n'):
                                                                                                            piece = (KNIGHT + BLACK)
                                                                                else:
                                                                                                            if (char_val == 'b'):
                                                                                                                                            piece = (BISHOP + BLACK)
                                                                                                            else:
                                                                                                                                            if (char_val == 'r'):
                                                                                                                                                                                piece = (ROOK + BLACK)
                                                                                                                                            else:
                                                                                                                                                                                if (char_val == 'q'):
                                                                                                                                                                                                                        piece = (QUEEN + BLACK)
                                                                                                                                                                                else:
                                                                                                                                                                                                                        if (char_val == 'k'):
                                                                                                                                                                                                                                                                    piece = (KING + BLACK)
                                                                                                                                                                                                                        else:
                                                                                                                                                                                                                                                                    if (char_val == 'P'):
                                                                                                                                                                                                                                                                                                                    piece = (PAWN + WHITE)
                                                                                                                                                                                                                                                                    else:
                                                                                                                                                                                                                                                                                                                    if (char_val == 'N'):
                                                                                                                                                                                                                                                                                                                                                                        piece = (KNIGHT + WHITE)
                                                                                                                                                                                                                                                                                                                    else:
                                                                                                                                                                                                                                                                                                                                                                        if (char_val == 'B'):
                                                                                                                                                                                                                                                                                                                                                                                                                                piece = (BISHOP + WHITE)
                                                                                                                                                                                                                                                                                                                                                                        else:
                                                                                                                                                                                                                                                                                                                                                                                                                                if (char_val == 'R'):
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            piece = (ROOK + WHITE)
                                                                                                                                                                                                                                                                                                                                                                                                                                else:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            if (char_val == 'Q'):
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            piece = (QUEEN + WHITE)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            else:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            if (char_val == 'K'):
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                piece = (KING + WHITE)
                                                        self.squares[((row * 8) + col)] = piece
                                                        col = (col + 1)
        self.turn = WHITE
        if (len(parts) > 1):
                    if (parts[1] == 'b'):
                                    self.turn = BLACK
        self.castling = {'WK': False, 'WQ': False, 'BK': False, 'BQ': False}
        if (len(parts) > 2):
                    c_rights = parts[2]
                    n_c = len(c_rights)
                    for i in range(0, n_c):
                                    c_char = c_rights[i]
                                    if (c_char == 'K'):
                                                        self.castling['WK'] = True
                                    else:
                                                        if (c_char == 'Q'):
                                                                                self.castling['WQ'] = True
                                                        else:
                                                                                if (c_char == 'k'):
                                                                                                            self.castling['BK'] = True
                                                                                else:
                                                                                                            if (c_char == 'q'):
                                                                                                                                            self.castling['BQ'] = True
        self.ep_square = (0 - 1)
        if (len(parts) > 3):
                    ep_str = parts[3]
                    if ((ep_str != '-') and (len(ep_str) == 2)):
                                    f_idx = (ord(ep_str[0]) - ord('a'))
                                    r_idx = (8 - int(ep_str[1]))
                                    self.ep_square = ((r_idx * 8) + f_idx)
        self.halfmove = 0
        if (len(parts) > 4):
                    self.halfmove = int(parts[4])
        self.fullmove = 1
        if (len(parts) > 5):
                    self.fullmove = int(parts[5])
    def get_piece(self, square):
        return self.squares[square]
    def set_piece(self, square, piece):
        self.squares[square] = piece
    def is_empty(self, square):
        return (self.squares[square] == EMPTY)
    def get_color(self, piece):
        if (piece == EMPTY):
                    return 0
        if (piece < BLACK):
                    return WHITE
        else:
                    return BLACK
    def get_type(self, piece):
        if (piece == EMPTY):
                    return EMPTY
        if (piece < BLACK):
                    return (piece - WHITE)
        else:
                    return (piece - BLACK)
    def set_turn(self, t):
        self.turn = t
    def set_ep_square(self, sq):
        self.ep_square = sq
    def make_move(self, move):
        state = {'turn': self.turn, 'castling': {'WK': self.castling['WK'], 'WQ': self.castling['WQ'], 'BK': self.castling['BK'], 'BQ': self.castling['BQ']}, 'ep_square': self.ep_square, 'halfmove': self.halfmove, 'move': move}
        _slang_ret = add(self.history, state)
        _web_builder.add_text(_slang_ret)
        self.squares[(move . to_sq)] = (move . piece)
        if (get_piece_type((move . piece)) == PAWN):
                    to_row = int(((move . to_sq) / 8))
                    if (to_row == 0):
                                    self.squares[(move . to_sq)] = (QUEEN + WHITE)
                    else:
                                    if (to_row == 7):
                                                        self.squares[(move . to_sq)] = (QUEEN + BLACK)
        self.squares[(move . from_sq)] = EMPTY
        if ((move . flags) == 2):
                    if (self.turn == WHITE):
                                    self.squares[((move . to_sq) + 8)] = EMPTY
                    else:
                                    self.squares[((move . to_sq) - 8)] = EMPTY
        if ((move . flags) == 4):
                    if ((move . to_sq) == 62):
                                    self.squares[61] = (ROOK + WHITE)
                                    self.squares[63] = EMPTY
                    else:
                                    if ((move . to_sq) == 58):
                                                        self.squares[59] = (ROOK + WHITE)
                                                        self.squares[56] = EMPTY
                                    else:
                                                        if ((move . to_sq) == 6):
                                                                                self.squares[5] = (ROOK + BLACK)
                                                                                self.squares[7] = EMPTY
                                                        else:
                                                                                if ((move . to_sq) == 2):
                                                                                                            self.squares[3] = (ROOK + BLACK)
                                                                                                            self.squares[0] = EMPTY
        if ((move . from_sq) == 60):
                    self.castling['WK'] = False
                    self.castling['WQ'] = False
        else:
                    if ((move . from_sq) == 4):
                                    self.castling['BK'] = False
                                    self.castling['BQ'] = False
        if (((move . from_sq) == 56) or ((move . to_sq) == 56)):
                    self.castling['WQ'] = False
        if (((move . from_sq) == 63) or ((move . to_sq) == 63)):
                    self.castling['WK'] = False
        if (((move . from_sq) == 0) or ((move . to_sq) == 0)):
                    self.castling['BQ'] = False
        if (((move . from_sq) == 7) or ((move . to_sq) == 7)):
                    self.castling['BK'] = False
        self.ep_square = (0 - 1)
        if (get_piece_type((move . piece)) == PAWN):
                    if (abs(((move . to_sq) - (move . from_sq))) == 16):
                                    self.ep_square = int((((move . from_sq) + (move . to_sq)) / 2))
        if (self.turn == WHITE):
                    self.turn = BLACK
        else:
                    self.turn = WHITE
                    self.fullmove = (self.fullmove + 1)
    def undo_move(self):
        if empty(self.history):
                    return False
        state = (self.history . pop())
        move = state['move']
        self.squares[(move . from_sq)] = (move . piece)
        self.squares[(move . to_sq)] = (move . captured)
        if ((move . flags) == 2):
                    self.squares[(move . to_sq)] = EMPTY
                    if (state['turn'] == WHITE):
                                    self.squares[((move . to_sq) + 8)] = (PAWN + BLACK)
                    else:
                                    self.squares[((move . to_sq) - 8)] = (PAWN + WHITE)
        if ((move . flags) == 4):
                    if ((move . to_sq) == 62):
                                    self.squares[63] = (ROOK + WHITE)
                                    self.squares[61] = EMPTY
                    else:
                                    if ((move . to_sq) == 58):
                                                        self.squares[56] = (ROOK + WHITE)
                                                        self.squares[59] = EMPTY
                                    else:
                                                        if ((move . to_sq) == 6):
                                                                                self.squares[7] = (ROOK + BLACK)
                                                                                self.squares[5] = EMPTY
                                                        else:
                                                                                if ((move . to_sq) == 2):
                                                                                                            self.squares[0] = (ROOK + BLACK)
                                                                                                            self.squares[3] = EMPTY
        self.turn = state['turn']
        self.castling = state['castling']
        self.ep_square = state['ep_square']
        self.halfmove = state['halfmove']
        if (self.turn == BLACK):
                    self.fullmove = (self.fullmove - 1)
        return True
def create_board():
    _slang_ret = None
    b = Board(0)
    _slang_ret = (b . reset())
    _web_builder.add_text(_slang_ret)
    return b
    return _slang_ret