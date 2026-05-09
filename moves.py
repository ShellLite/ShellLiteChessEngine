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
math = STD_MODULES['math']
def get_row(sq):
    _slang_ret = None
    return int((sq / 8))
    return _slang_ret
def get_col(sq):
    _slang_ret = None
    return (sq % 8)
    return _slang_ret
def get_sq(r, c):
    _slang_ret = None
    return ((r * 8) + c)
    return _slang_ret
class Move(Instance):
    def __init__(self, from_sq, to_sq, piece, captured=0, flags=0):
        self.from_sq = from_sq
        self.to_sq = to_sq
        self.piece = piece
        self.captured = captured
        self.flags = flags

def generate_pseudo_legal_moves(board):
    _slang_ret = None
    moves = []
    sqs = (board . squares)
    for i in range(0, 64):
            piece = sqs[i]
            if (piece == EMPTY):
                        continue
            color = 0
            if (piece < BLACK):
                        color = WHITE
            else:
                        color = BLACK
            if (color != (board . turn)):
                        continue
            piece_type = 0
            if (piece < BLACK):
                        piece_type = (piece - WHITE)
            else:
                        piece_type = (piece - BLACK)
            if (piece_type == PAWN):
                        _slang_ret = generate_pawn_moves(board, i, moves)
                        _web_builder.add_text(_slang_ret)
            else:
                        if (piece_type == KNIGHT):
                                        _slang_ret = generate_knight_moves(board, i, moves)
                                        _web_builder.add_text(_slang_ret)
                        else:
                                        if (piece_type == BISHOP):
                                                            bishop_dirs = [7, (0 - 7), 9, (0 - 9)]
                                                            _slang_ret = generate_sliding_moves(board, i, bishop_dirs, moves)
                                                            _web_builder.add_text(_slang_ret)
                                        else:
                                                            if (piece_type == ROOK):
                                                                                    rook_dirs = [1, (0 - 1), 8, (0 - 8)]
                                                                                    _slang_ret = generate_sliding_moves(board, i, rook_dirs, moves)
                                                                                    _web_builder.add_text(_slang_ret)
                                                            else:
                                                                                    if (piece_type == QUEEN):
                                                                                                                queen_dirs = [1, (0 - 1), 8, (0 - 8), 7, (0 - 7), 9, (0 - 9)]
                                                                                                                _slang_ret = generate_sliding_moves(board, i, queen_dirs, moves)
                                                                                                                _web_builder.add_text(_slang_ret)
                                                                                    else:
                                                                                                                if (piece_type == KING):
                                                                                                                                                _slang_ret = generate_king_moves(board, i, moves)
                                                                                                                                                _web_builder.add_text(_slang_ret)
    return moves
    return _slang_ret
def generate_pawn_moves(board, sq, moves):
    _slang_ret = None
    r = get_row(sq)
    if ((r == 0) or (r == 7)):
            return False
    c = get_col(sq)
    sqs = (board . squares)
    p_orig = sqs[sq]
    color = get_piece_color(p_orig)
    if (color == WHITE):
            target = get_sq((r - 1), c)
            if ((r > 0) and (sqs[target] == EMPTY)):
                        _slang_ret = add(moves, Move(sq, target, p_orig))
                        _web_builder.add_text(_slang_ret)
                        target2 = get_sq((r - 2), c)
                        if ((r == 6) and (sqs[target2] == EMPTY)):
                                        m = Move(sq, target2, p_orig, 0, 1)
                                        _slang_ret = add(moves, m)
                                        _web_builder.add_text(_slang_ret)
            for dc in [(0 - 1), 1]:
                        nc = (c + dc)
                        if ((nc >= 0) and (nc < 8)):
                                        target = get_sq((r - 1), nc)
                                        tp = sqs[target]
                                        if ((tp != EMPTY) and (get_piece_color(tp) == BLACK)):
                                                            m = Move(sq, target, p_orig, tp, 0)
                                                            _slang_ret = add(moves, m)
                                                            _web_builder.add_text(_slang_ret)
                                        else:
                                                            if (target == (board . ep_square)):
                                                                                    m = Move(sq, target, p_orig, (PAWN + BLACK), 2)
                                                                                    _slang_ret = add(moves, m)
                                                                                    _web_builder.add_text(_slang_ret)
    else:
            target = get_sq((r + 1), c)
            if ((r < 7) and (sqs[target] == EMPTY)):
                        _slang_ret = add(moves, Move(sq, target, p_orig))
                        _web_builder.add_text(_slang_ret)
                        target2 = get_sq((r + 2), c)
                        if ((r == 1) and (sqs[target2] == EMPTY)):
                                        m = Move(sq, target2, p_orig, 0, 1)
                                        _slang_ret = add(moves, m)
                                        _web_builder.add_text(_slang_ret)
            for dc in [(0 - 1), 1]:
                        nc = (c + dc)
                        if ((nc >= 0) and (nc < 8)):
                                        target = get_sq((r + 1), nc)
                                        tp = sqs[target]
                                        if ((tp != EMPTY) and (get_piece_color(tp) == WHITE)):
                                                            m = Move(sq, target, p_orig, tp, 0)
                                                            _slang_ret = add(moves, m)
                                                            _web_builder.add_text(_slang_ret)
                                        else:
                                                            if (target == (board . ep_square)):
                                                                                    m = Move(sq, target, p_orig, (PAWN + WHITE), 2)
                                                                                    _slang_ret = add(moves, m)
                                                                                    _web_builder.add_text(_slang_ret)
    return _slang_ret
def generate_knight_moves(board, sq, moves):
    _slang_ret = None
    r = get_row(sq)
    c = get_col(sq)
    sqs = (board . squares)
    piece = sqs[sq]
    color = get_piece_color(piece)
    offsets = [[(0 - 2), (0 - 1)], [(0 - 2), 1], [(0 - 1), (0 - 2)], [(0 - 1), 2], [1, (0 - 2)], [1, 2], [2, (0 - 1)], [2, 1]]
    for off in offsets:
            nr = (r + off[0])
            nc = (c + off[1])
            if ((((nr >= 0) and (nr < 8)) and (nc >= 0)) and (nc < 8)):
                        target = get_sq(nr, nc)
                        tp = sqs[target]
                        if (tp == EMPTY):
                                        _slang_ret = add(moves, Move(sq, target, piece))
                                        _web_builder.add_text(_slang_ret)
                        else:
                                        if (get_piece_color(tp) != color):
                                                            m = Move(sq, target, piece, tp, 0)
                                                            _slang_ret = add(moves, m)
                                                            _web_builder.add_text(_slang_ret)
    return _slang_ret
def generate_sliding_moves(board, sq, directions, moves):
    _slang_ret = None
    r = get_row(sq)
    c = get_col(sq)
    sqs = (board . squares)
    piece = sqs[sq]
    color = get_piece_color(piece)
    for d in directions:
            dr = 0
            dc = 0
            if (d == 1):
                        dc = 1
            else:
                        if (d == (0 - 1)):
                                        dc = (0 - 1)
                        else:
                                        if (d == 8):
                                                            dr = 1
                                        else:
                                                            if (d == (0 - 8)):
                                                                                    dr = (0 - 1)
                                                            else:
                                                                                    if (d == 7):
                                                                                                                dr = 1
                                                                                                                dc = (0 - 1)
                                                                                    else:
                                                                                                                if (d == (0 - 7)):
                                                                                                                                                dr = (0 - 1)
                                                                                                                                                dc = 1
                                                                                                                else:
                                                                                                                                                if (d == 9):
                                                                                                                                                                                    dr = 1
                                                                                                                                                                                    dc = 1
                                                                                                                                                else:
                                                                                                                                                                                    if (d == (0 - 9)):
                                                                                                                                                                                                                            dr = (0 - 1)
                                                                                                                                                                                                                            dc = (0 - 1)
            nr = (r + dr)
            nc = (c + dc)
            while ((((nr >= 0) and (nr < 8)) and (nc >= 0)) and (nc < 8)):
                        target = get_sq(nr, nc)
                        tp = sqs[target]
                        if (tp == EMPTY):
                                        _slang_ret = add(moves, Move(sq, target, piece))
                                        _web_builder.add_text(_slang_ret)
                        else:
                                        if (get_piece_color(tp) != color):
                                                            m = Move(sq, target, piece, tp, 0)
                                                            _slang_ret = add(moves, m)
                                                            _web_builder.add_text(_slang_ret)
                                        break
                        nr = (nr + dr)
                        nc = (nc + dc)
    return _slang_ret
def generate_king_moves(board, sq, moves):
    _slang_ret = None
    r = get_row(sq)
    c = get_col(sq)
    sqs = (board . squares)
    piece = sqs[sq]
    color = get_piece_color(piece)
    ks = (0 - 1)
    ke = 2
    for dr in range(ks, ke):
            for dc in range(ks, ke):
                        if ((dr == 0) and (dc == 0)):
                                        continue
                        nr = (r + dr)
                        nc = (c + dc)
                        if ((((nr >= 0) and (nr < 8)) and (nc >= 0)) and (nc < 8)):
                                        target = get_sq(nr, nc)
                                        tp = sqs[target]
                                        if (tp == EMPTY):
                                                            _slang_ret = add(moves, Move(sq, target, piece))
                                                            _web_builder.add_text(_slang_ret)
                                        else:
                                                            if (get_piece_color(tp) != color):
                                                                                    m = Move(sq, target, piece, tp, 0)
                                                                                    _slang_ret = add(moves, m)
                                                                                    _web_builder.add_text(_slang_ret)
    castl = (board . castling)
    if (color == WHITE):
            if castl['WK']:
                        if ((board . is_empty(61)) and (board . is_empty(62))):
                                        if (((not is_square_attacked(board, 60, BLACK)) and (not is_square_attacked(board, 61, BLACK))) and (not is_square_attacked(board, 62, BLACK))):
                                                            m = Move(60, 62, piece, EMPTY, 4)
                                                            _slang_ret = add(moves, m)
                                                            _web_builder.add_text(_slang_ret)
            if castl['WQ']:
                        if (((board . is_empty(59)) and (board . is_empty(58))) and (board . is_empty(57))):
                                        if (((not is_square_attacked(board, 60, BLACK)) and (not is_square_attacked(board, 59, BLACK))) and (not is_square_attacked(board, 58, BLACK))):
                                                            m = Move(60, 58, piece, EMPTY, 4)
                                                            _slang_ret = add(moves, m)
                                                            _web_builder.add_text(_slang_ret)
    else:
            if castl['BK']:
                        if ((board . is_empty(5)) and (board . is_empty(6))):
                                        if (((not is_square_attacked(board, 4, WHITE)) and (not is_square_attacked(board, 5, WHITE))) and (not is_square_attacked(board, 6, WHITE))):
                                                            m = Move(4, 6, piece, EMPTY, 4)
                                                            _slang_ret = add(moves, m)
                                                            _web_builder.add_text(_slang_ret)
            if castl['BQ']:
                        if (((board . is_empty(3)) and (board . is_empty(2))) and (board . is_empty(1))):
                                        if (((not is_square_attacked(board, 4, WHITE)) and (not is_square_attacked(board, 3, WHITE))) and (not is_square_attacked(board, 2, WHITE))):
                                                            m = Move(4, 2, piece, EMPTY, 4)
                                                            _slang_ret = add(moves, m)
                                                            _web_builder.add_text(_slang_ret)
    return _slang_ret
def is_square_attacked(board, sq, color):
    _slang_ret = None
    r = get_row(sq)
    c = get_col(sq)
    sqs = (board . squares)
    if (color == WHITE):
            dr = 1
    else:
            dr = (0 - 1)
    nr = (r + dr)
    nc = (c - 1)
    if ((((nr >= 0) and (nr < 8)) and (nc >= 0)) and (nc < 8)):
            idx = get_sq(nr, nc)
            p = sqs[idx]
            if ((get_piece_type(p) == PAWN) and (get_piece_color(p) == color)):
                        return True
    nc = (c + 1)
    if ((((nr >= 0) and (nr < 8)) and (nc >= 0)) and (nc < 8)):
            idx = get_sq(nr, nc)
            p = sqs[idx]
            if ((get_piece_type(p) == PAWN) and (get_piece_color(p) == color)):
                        return True
    dkr = (0 - 2)
    while (dkr <= 2):
            if (dkr == 0):
                        dkr = (dkr + 1)
                        continue
            dkc = (0 - 2)
            while (dkc <= 2):
                        if (dkc == 0):
                                        dkc = (dkc + 1)
                                        continue
                        if ((abs(dkr) + abs(dkc)) == 3):
                                        nr = (r + dkr)
                                        nc = (c + dkc)
                                        if ((((nr >= 0) and (nr < 8)) and (nc >= 0)) and (nc < 8)):
                                                            idx = get_sq(nr, nc)
                                                            p = sqs[idx]
                                                            if ((get_piece_type(p) == KNIGHT) and (get_piece_color(p) == color)):
                                                                                    return True
                        dkc = (dkc + 1)
            dkc = (0 - 2)
            dkr = (dkr + 1)
    for d in [1, (0 - 1), 8, (0 - 8)]:
            dr = 0
            dc = 0
            if (d == 1):
                        dc = 1
            else:
                        if (d == (0 - 1)):
                                        dc = (0 - 1)
                        else:
                                        if (d == 8):
                                                            dr = 1
                                        else:
                                                            if (d == (0 - 8)):
                                                                                    dr = (0 - 1)
            nr = (r + dr)
            nc = (c + dc)
            while ((((nr >= 0) and (nr < 8)) and (nc >= 0)) and (nc < 8)):
                        idx = get_sq(nr, nc)
                        p = sqs[idx]
                        if (p != EMPTY):
                                        if (get_piece_color(p) == color):
                                                            t = get_piece_type(p)
                                                            if ((t == ROOK) or (t == QUEEN)):
                                                                                    return True
                                        break
                        nr = (nr + dr)
                        nc = (nc + dc)
    for d in [7, (0 - 7), 9, (0 - 9)]:
            dr = 0
            dc = 0
            if (d == 7):
                        dr = 1
                        dc = (0 - 1)
            else:
                        if (d == (0 - 7)):
                                        dr = (0 - 1)
                                        dc = 1
                        else:
                                        if (d == 9):
                                                            dr = 1
                                                            dc = 1
                                        else:
                                                            if (d == (0 - 9)):
                                                                                    dr = (0 - 1)
                                                                                    dc = (0 - 1)
            nr = (r + dr)
            nc = (c + dc)
            while ((((nr >= 0) and (nr < 8)) and (nc >= 0)) and (nc < 8)):
                        idx = get_sq(nr, nc)
                        p = sqs[idx]
                        if (p != EMPTY):
                                        if (get_piece_color(p) == color):
                                                            t = get_piece_type(p)
                                                            if ((t == BISHOP) or (t == QUEEN)):
                                                                                    return True
                                        break
                        nr = (nr + dr)
                        nc = (nc + dc)
    r_start = (0 - 1)
    r_end = 2
    for dr in range(r_start, r_end):
            c_start = (0 - 1)
            c_end = 2
            for dc in range(c_start, c_end):
                        if ((dr == 0) and (dc == 0)):
                                        continue
                        nr = (r + dr)
                        nc = (c + dc)
                        if ((((nr >= 0) and (nr < 8)) and (nc >= 0)) and (nc < 8)):
                                        idx = get_sq(nr, nc)
                                        p = sqs[idx]
                                        if ((get_piece_type(p) == KING) and (get_piece_color(p) == color)):
                                                            return True
    return False
    return _slang_ret
def is_path_clear(board, from_sq, to_sq):
    _slang_ret = None
    r1 = get_row(from_sq)
    c1 = get_col(from_sq)
    r2 = get_row(to_sq)
    c2 = get_col(to_sq)
    dr = 0
    if (r2 > r1):
            dr = 1
    else:
            if (r2 < r1):
                        dr = (0 - 1)
    dc = 0
    if (c2 > c1):
            dc = 1
    else:
            if (c2 < c1):
                        dc = (0 - 1)
    curr_r = (r1 + dr)
    curr_c = (c1 + dc)
    while True:
            if ((curr_r == r2) and (curr_c == c2)):
                        break
            if ((((curr_r < 0) or (curr_r >= 8)) or (curr_c < 0)) or (curr_c >= 8)):
                        break
            sq = get_sq(curr_r, curr_c)
            if (not (board . is_empty(sq))):
                        return False
            curr_r = (curr_r + dr)
            curr_c = (curr_c + dc)
    return True
    return _slang_ret
def is_in_check(board, color):
    _slang_ret = None
    ksq = (board . get_king_square(color))
    return is_square_attacked(board, ksq, (24 - color))
    return _slang_ret
def generate_legal_moves(board):
    _slang_ret = None
    original_turn = (board . turn)
    pseudo = generate_pseudo_legal_moves(board)
    legal = []
    for m in pseudo:
            _slang_ret = (board . make_move(m))
            _web_builder.add_text(_slang_ret)
            if (not is_square_attacked(board, (board . get_king_square(original_turn)), (board . turn))):
                        _slang_ret = add(legal, m)
                        _web_builder.add_text(_slang_ret)
            _slang_ret = (board . undo_move())
            _web_builder.add_text(_slang_ret)
    return legal
    return _slang_ret