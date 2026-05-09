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
from board import *
from moves import *
from search import *
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
    suffix = ''
    if (get_piece_type((move . piece)) == PAWN):
            to_row = int(((move . to_sq) / 8))
            if ((to_row == 0) or (to_row == 7)):
                        suffix = 'q'
    return ((square_to_str((move . from_sq)) + square_to_str((move . to_sq))) + suffix)
    return _slang_ret
def str_to_sq(s):
    _slang_ret = None
    f = (ord(s[0]) - ord('a'))
    r = (8 - int(s[1]))
    return ((r * 8) + f)
    return _slang_ret
def play_game():
    _slang_ret = None
    board = create_board()
    print('info string engine ready')
    while True:
            line = ask('')
            if (line == 'uci'):
                        print('id name run_engine')
                        print('id author Shrey Naithani')
                        print('uciok')
            else:
                        if (line == 'isready'):
                                        print('readyok')
                        else:
                                        if (line == 'ucinewgame'):
                                                            _slang_ret = (board . reset())
                                                            _web_builder.add_text(_slang_ret)
                                                            print('info string board reset')
                                        else:
                                                            if (line . startswith('position')):
                                                                                    if ('startpos' in line):
                                                                                                                _slang_ret = (board . reset())
                                                                                                                _web_builder.add_text(_slang_ret)
                                                                                    else:
                                                                                                                if ('fen' in line):
                                                                                                                                                parts = split(line)
                                                                                                                                                fen_parts = []
                                                                                                                                                found_fen = False
                                                                                                                                                n_parts = len(parts)
                                                                                                                                                for idx in range(0, n_parts):
                                                                                                                                                                                    p = parts[idx]
                                                                                                                                                                                    if (p == 'fen'):
                                                                                                                                                                                                                            found_fen = True
                                                                                                                                                                                                                            continue
                                                                                                                                                                                    if (p == 'moves'):
                                                                                                                                                                                                                            break
                                                                                                                                                                                    if found_fen:
                                                                                                                                                                                                                            _slang_ret = add(fen_parts, p)
                                                                                                                                                                                                                            _web_builder.add_text(_slang_ret)
                                                                                                                                                fen_str = ''
                                                                                                                                                first_flag = True
                                                                                                                                                for fp in fen_parts:
                                                                                                                                                                                    if first_flag:
                                                                                                                                                                                                                            fen_str = fp
                                                                                                                                                                                                                            first_flag = False
                                                                                                                                                                                    else:
                                                                                                                                                                                                                            fen_str = ((fen_str + ' ') + fp)
                                                                                                                                                _slang_ret = (board . set_fen(fen_str))
                                                                                                                                                _web_builder.add_text(_slang_ret)
                                                                                    if ('moves' in line):
                                                                                                                parts = split(line)
                                                                                                                found_moves = False
                                                                                                                for p in parts:
                                                                                                                                                if (p == 'moves'):
                                                                                                                                                                                    found_moves = True
                                                                                                                                                                                    continue
                                                                                                                                                if (found_moves and (len(p) >= 4)):
                                                                                                                                                                                    fsq = str_to_sq((p[0] + p[1]))
                                                                                                                                                                                    tsq = str_to_sq((p[2] + p[3]))
                                                                                                                                                                                    piece = (board . get_piece(fsq))
                                                                                                                                                                                    if (piece != EMPTY):
                                                                                                                                                                                                                            captured = (board . get_piece(tsq))
                                                                                                                                                                                                                            flags = 0
                                                                                                                                                                                                                            pt = get_piece_type(piece)
                                                                                                                                                                                                                            if (pt == KING):
                                                                                                                                                                                                                                                                        if ((fsq == 60) and ((((tsq == 62) or (tsq == 63)) or (tsq == 58)) or (tsq == 56))):
                                                                                                                                                                                                                                                                                                                        flags = 4
                                                                                                                                                                                                                                                                        else:
                                                                                                                                                                                                                                                                                                                        if ((fsq == 4) and ((((tsq == 6) or (tsq == 7)) or (tsq == 2)) or (tsq == 0))):
                                                                                                                                                                                                                                                                                                                                                                            flags = 4
                                                                                                                                                                                                                            if (pt == PAWN):
                                                                                                                                                                                                                                                                        diff = abs((tsq - fsq))
                                                                                                                                                                                                                                                                        if (diff == 16):
                                                                                                                                                                                                                                                                                                                        flags = 1
                                                                                                                                                                                                                                                                        else:
                                                                                                                                                                                                                                                                                                                        if (((diff == 7) or (diff == 9)) and (captured == EMPTY)):
                                                                                                                                                                                                                                                                                                                                                                            flags = 2
                                                                                                                                                                                                                                                                                                                                                                            if ((board . turn) == WHITE):
                                                                                                                                                                                                                                                                                                                                                                                                                                    captured = (PAWN + BLACK)
                                                                                                                                                                                                                                                                                                                                                                            else:
                                                                                                                                                                                                                                                                                                                                                                                                                                    captured = (PAWN + WHITE)
                                                                                                                                                                                                                            m = Move(fsq, tsq, piece, captured, flags)
                                                                                                                                                                                                                            _slang_ret = (board . make_move(m))
                                                                                                                                                                                                                            _web_builder.add_text(_slang_ret)
                                                            else:
                                                                                    if (line . startswith('go')):
                                                                                                                search_depth = 6
                                                                                                                allocated_time = 100000000.0
                                                                                                                parts = split(line)
                                                                                                                n_p = len(parts)
                                                                                                                idx = 0
                                                                                                                for p in parts:
                                                                                                                                                if ((p == 'depth') and ((idx + 1) < n_p)):
                                                                                                                                                                                    search_depth = int(parts[(idx + 1)])
                                                                                                                                                else:
                                                                                                                                                                                    if ((p == 'movetime') and ((idx + 1) < n_p)):
                                                                                                                                                                                                                            allocated_time = float(parts[(idx + 1)])
                                                                                                                                                idx = (idx + 1)
                                                                                                                if (('wtime' in line) or ('btime' in line)):
                                                                                                                                                my_time = 0.0
                                                                                                                                                my_inc = 0.0
                                                                                                                                                idx = 0
                                                                                                                                                for p in parts:
                                                                                                                                                                                    if ((board . turn) == WHITE):
                                                                                                                                                                                                                            if ((p == 'wtime') and ((idx + 1) < n_p)):
                                                                                                                                                                                                                                                                        my_time = float(parts[(idx + 1)])
                                                                                                                                                                                                                            else:
                                                                                                                                                                                                                                                                        if ((p == 'winc') and ((idx + 1) < n_p)):
                                                                                                                                                                                                                                                                                                                        my_inc = float(parts[(idx + 1)])
                                                                                                                                                                                    else:
                                                                                                                                                                                                                            if ((p == 'btime') and ((idx + 1) < n_p)):
                                                                                                                                                                                                                                                                        my_time = float(parts[(idx + 1)])
                                                                                                                                                                                                                            else:
                                                                                                                                                                                                                                                                        if ((p == 'binc') and ((idx + 1) < n_p)):
                                                                                                                                                                                                                                                                                                                        my_inc = float(parts[(idx + 1)])
                                                                                                                                                                                    idx = (idx + 1)
                                                                                                                                                if (my_time > 0.0):
                                                                                                                                                                                    search_depth = 30
                                                                                                                                                                                    if (my_time <= 10000.0):
                                                                                                                                                                                                                            allocated_time = ((my_time * 0.1) + (my_inc * 0.5))
                                                                                                                                                                                    else:
                                                                                                                                                                                                                            if (my_time <= 30000.0):
                                                                                                                                                                                                                                                                        allocated_time = ((my_time * 0.08) + (my_inc * 0.5))
                                                                                                                                                                                                                            else:
                                                                                                                                                                                                                                                                        if (my_time <= 120000.0):
                                                                                                                                                                                                                                                                                                                        allocated_time = ((my_time * 0.06) + (my_inc * 0.6))
                                                                                                                                                                                                                                                                        else:
                                                                                                                                                                                                                                                                                                                        if (my_time <= 300000.0):
                                                                                                                                                                                                                                                                                                                                                                            allocated_time = ((my_time * 0.04) + (my_inc * 0.7))
                                                                                                                                                                                                                                                                                                                        else:
                                                                                                                                                                                                                                                                                                                                                                            allocated_time = ((my_time * 0.03) + (my_inc * 0.8))
                                                                                                                                                                                    if (allocated_time > (my_time - 500.0)):
                                                                                                                                                                                                                            allocated_time = (my_time - 500.0)
                                                                                                                                                                                    if (allocated_time < 100.0):
                                                                                                                                                                                                                            allocated_time = 100.0
                                                                                                                                                                                    max_safe = (my_time * 0.8)
                                                                                                                                                                                    if (allocated_time > max_safe):
                                                                                                                                                                                                                            allocated_time = max_safe
                                                                                                                                                                                    if (allocated_time > 6000.0):
                                                                                                                                                                                                                            allocated_time = 6000.0
                                                                                                                if ('infinite' in line):
                                                                                                                                                search_depth = 10
                                                                                                                                                allocated_time = 100000000.0
                                                                                                                best_move = find_best_move(board, search_depth, allocated_time)
                                                                                                                if (best_move != null):
                                                                                                                                                out = ('bestmove ' + move_to_str(best_move))
                                                                                                                                                print(out)
                                                                                                                else:
                                                                                                                                                print('bestmove 0000')
                                                                                    else:
                                                                                                                if (line == 'quit'):
                                                                                                                                                break
                                                                                                                else:
                                                                                                                                                if (line == 'd'):
                                                                                                                                                                                    for r in range(0, 8):
                                                                                                                                                                                                                            row_str = ''
                                                                                                                                                                                                                            for c in range(0, 8):
                                                                                                                                                                                                                                                                        p = (board . get_piece(((r * 8) + c)))
                                                                                                                                                                                                                                                                        if (p == EMPTY):
                                                                                                                                                                                                                                                                                                                        row_str = (row_str + '. ')
                                                                                                                                                                                                                                                                        else:
                                                                                                                                                                                                                                                                                                                        row_str = ((row_str + str(p)) + ' ')
                                                                                                                                                                                                                            print(row_str)
    return _slang_ret
_slang_ret = play_game()
_web_builder.add_text(_slang_ret)