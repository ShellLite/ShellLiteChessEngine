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
time = STD_MODULES['time']
from book import *
PAWN_PST = [0, 0, 0, 0, 0, 0, 0, 0, 50, 50, 50, 50, 50, 50, 50, 50, 10, 10, 20, 30, 30, 20, 10, 10, 5, 5, 10, 25, 25, 10, 5, 5, 0, 0, 0, 20, 20, 0, 0, 0, 5, (0 - 5), (0 - 10), 0, 0, (0 - 10), (0 - 5), 5, 5, 10, 10, (0 - 20), (0 - 20), 10, 10, 5, 0, 0, 0, 0, 0, 0, 0, 0]
KNIGHT_PST = [(0 - 50), (0 - 40), (0 - 30), (0 - 30), (0 - 30), (0 - 30), (0 - 40), (0 - 50), (0 - 40), (0 - 20), 0, 0, 0, 0, (0 - 20), (0 - 40), (0 - 30), 0, 10, 15, 15, 10, 0, (0 - 30), (0 - 30), 5, 15, 20, 20, 15, 5, (0 - 30), (0 - 30), 0, 15, 20, 20, 15, 0, (0 - 30), (0 - 30), 5, 10, 15, 15, 10, 5, (0 - 30), (0 - 40), (0 - 20), 0, 5, 5, 0, (0 - 20), (0 - 40), (0 - 50), (0 - 40), (0 - 30), (0 - 30), (0 - 30), (0 - 30), (0 - 40), (0 - 50)]
BISHOP_PST = [(0 - 20), (0 - 10), (0 - 10), (0 - 10), (0 - 10), (0 - 10), (0 - 10), (0 - 20), (0 - 10), 0, 0, 0, 0, 0, 0, (0 - 10), (0 - 10), 0, 5, 10, 10, 5, 0, (0 - 10), (0 - 10), 5, 5, 10, 10, 5, 5, (0 - 10), (0 - 10), 0, 10, 10, 10, 10, 0, (0 - 10), (0 - 10), 10, 10, 10, 10, 10, 10, (0 - 10), (0 - 10), 5, 0, 0, 0, 0, 5, (0 - 10), (0 - 20), (0 - 10), (0 - 10), (0 - 10), (0 - 10), (0 - 10), (0 - 10), (0 - 20)]
ROOK_PST = [0, 0, 0, 0, 0, 0, 0, 0, 5, 10, 10, 10, 10, 10, 10, 5, (0 - 5), 0, 0, 0, 0, 0, 0, (0 - 5), (0 - 5), 0, 0, 0, 0, 0, 0, (0 - 5), (0 - 5), 0, 0, 0, 0, 0, 0, (0 - 5), (0 - 5), 0, 0, 0, 0, 0, 0, (0 - 5), (0 - 5), 0, 0, 0, 0, 0, 0, (0 - 5), 0, 0, 0, 5, 5, 0, 0, 0]
KING_PST = [(0 - 30), (0 - 40), (0 - 40), (0 - 50), (0 - 50), (0 - 40), (0 - 40), (0 - 30), (0 - 30), (0 - 40), (0 - 40), (0 - 50), (0 - 50), (0 - 40), (0 - 40), (0 - 30), (0 - 30), (0 - 40), (0 - 40), (0 - 50), (0 - 50), (0 - 40), (0 - 40), (0 - 30), (0 - 30), (0 - 40), (0 - 40), (0 - 50), (0 - 50), (0 - 40), (0 - 40), (0 - 30), (0 - 20), (0 - 30), (0 - 30), (0 - 40), (0 - 40), (0 - 30), (0 - 30), (0 - 20), (0 - 10), (0 - 20), (0 - 20), (0 - 20), (0 - 20), (0 - 20), (0 - 20), (0 - 10), 20, 20, 0, 0, 0, 0, 20, 20, 20, 30, 10, 0, 0, 10, 30, 20]
KING_ENDGAME_PST = [(0 - 50), (0 - 40), (0 - 30), (0 - 20), (0 - 20), (0 - 30), (0 - 40), (0 - 50), (0 - 30), (0 - 20), (0 - 10), 0, 0, (0 - 10), (0 - 20), (0 - 30), (0 - 30), (0 - 10), 20, 30, 30, 20, (0 - 10), (0 - 30), (0 - 30), (0 - 10), 30, 40, 40, 30, (0 - 10), (0 - 30), (0 - 30), (0 - 10), 30, 40, 40, 30, (0 - 10), (0 - 30), (0 - 30), (0 - 10), 20, 30, 30, 20, (0 - 10), (0 - 30), (0 - 30), (0 - 30), 0, 0, 0, 0, (0 - 30), (0 - 30), (0 - 50), (0 - 30), (0 - 30), (0 - 30), (0 - 30), (0 - 30), (0 - 30), (0 - 50)]
tt_table = {}
def tt_lookup(key, depth, alpha, beta):
    _slang_ret = None
    if contains(tt_table, key):
            entry = tt_table[key]
            if (entry['depth'] >= depth):
                        val = entry['val']
                        flag = entry['flag']
                        if (flag == 0):
                                        return val
                        if (flag == 1):
                                        if (val >= beta):
                                                            return val
                        if (flag == 2):
                                        if (val <= alpha):
                                                            return val
    return null
    return _slang_ret
def tt_store(key, depth, val, flag, move):
    _slang_ret = None
    entry = {'depth': depth, 'val': val, 'flag': flag, 'move': move}
    tt_table[key] = entry
    return _slang_ret
killer_table = {}
def add_killer(ply, move):
    _slang_ret = None
    if (not contains(killer_table, ply)):
            killer_table[ply] = []
    killers = killer_table[ply]
    already_exists = False
    for km in killers:
            if (((km . from_sq) == (move . from_sq)) and ((km . to_sq) == (move . to_sq))):
                        already_exists = True
    if (not already_exists):
            _slang_ret = add(killers, move)
            _web_builder.add_text(_slang_ret)
            if (len(killers) > 2):
                        _slang_ret = pop(killers, 0)
                        _web_builder.add_text(_slang_ret)
    return _slang_ret
def is_endgame(board):
    _slang_ret = None
    white_pieces = 0
    black_pieces = 0
    white_queens = 0
    black_queens = 0
    sqs = (board . squares)
    for i in range(0, 64):
            p = sqs[i]
            if (p != 0):
                        ptype = get_piece_type(p)
                        color = get_piece_color(p)
                        if ((ptype != PAWN) and (ptype != KING)):
                                        if (color == WHITE):
                                                            white_pieces = (white_pieces + 1)
                                                            if (ptype == QUEEN):
                                                                                    white_queens = (white_queens + 1)
                                        else:
                                                            black_pieces = (black_pieces + 1)
                                                            if (ptype == QUEEN):
                                                                                    black_queens = (black_queens + 1)
    if ((white_queens == 0) and (black_queens == 0)):
            return True
    if ((white_pieces <= 2) and (black_pieces <= 2)):
            return True
    return False
    return _slang_ret
def evaluate(board):
    _slang_ret = None
    score = 0
    sqs = (board . squares)
    turn = (board . turn)
    is_eg = is_endgame(board)
    white_pieces = 0
    black_pieces = 0
    for i in range(0, 64):
            p = sqs[i]
            if (p == 0):
                        continue
            color = get_piece_color(p)
            ptype = get_piece_type(p)
            if ((ptype != PAWN) and (ptype != KING)):
                        if (color == WHITE):
                                        white_pieces = (white_pieces + 1)
                        else:
                                        black_pieces = (black_pieces + 1)
            val = 0
            if (ptype == 1):
                        val = 100
                        if is_eg:
                                        r = int((i / 8))
                                        if (color == WHITE):
                                                            rank_num = (7 - r)
                                                            if (rank_num >= 4):
                                                                                    val = (val + (rank_num * 10))
                                        else:
                                                            rank_num = r
                                                            if (rank_num >= 4):
                                                                                    val = (val + (rank_num * 10))
            else:
                        if (ptype == 2):
                                        val = 300
                        else:
                                        if (ptype == 3):
                                                            val = 320
                                        else:
                                                            if (ptype == 4):
                                                                                    val = 500
                                                            else:
                                                                                    if (ptype == 5):
                                                                                                                val = 900
                                                                                    else:
                                                                                                                if (ptype == 6):
                                                                                                                                                val = 20000
            idx = i
            if (color == 16):
                        r = int((i / 8))
                        c = (i % 8)
                        idx = (((7 - r) * 8) + c)
            pst_val = 0
            if (ptype == 1):
                        pst_val = PAWN_PST[idx]
            else:
                        if (ptype == 2):
                                        pst_val = KNIGHT_PST[idx]
                        else:
                                        if (ptype == 3):
                                                            pst_val = BISHOP_PST[idx]
                                        else:
                                                            if (ptype == 4):
                                                                                    pst_val = ROOK_PST[idx]
                                                            else:
                                                                                    if (ptype == 6):
                                                                                                                if is_eg:
                                                                                                                                                pst_val = KING_ENDGAME_PST[idx]
                                                                                                                else:
                                                                                                                                                pst_val = KING_PST[idx]
            val = (val + pst_val)
            if (color == turn):
                        score = (score + val)
            else:
                        score = (score - val)
    if is_eg:
            if (white_pieces == 0):
                        wk_sq = (board . get_king_square(WHITE))
                        bk_sq = (board . get_king_square(BLACK))
                        if ((wk_sq != (0 - 1)) and (bk_sq != (0 - 1))):
                                        wk_r = int((wk_sq / 8))
                                        wk_c = (wk_sq % 8)
                                        dist_to_center = (abs((wk_r - 3.5)) + abs((wk_c - 3.5)))
                                        bk_r = int((bk_sq / 8))
                                        bk_c = (bk_sq % 8)
                                        dist_between_kings = (abs((wk_r - bk_r)) + abs((wk_c - bk_c)))
                                        mop_up = (int((dist_to_center * 10)) + int(((14 - dist_between_kings) * 5)))
                                        if (turn == BLACK):
                                                            score = (score + mop_up)
                                        else:
                                                            score = (score - mop_up)
            else:
                        if (black_pieces == 0):
                                        wk_sq = (board . get_king_square(WHITE))
                                        bk_sq = (board . get_king_square(BLACK))
                                        if ((wk_sq != (0 - 1)) and (bk_sq != (0 - 1))):
                                                            bk_r = int((bk_sq / 8))
                                                            bk_c = (bk_sq % 8)
                                                            dist_to_center = (abs((bk_r - 3.5)) + abs((bk_c - 3.5)))
                                                            wk_r = int((wk_sq / 8))
                                                            wk_c = (wk_sq % 8)
                                                            dist_between_kings = (abs((wk_r - bk_r)) + abs((wk_c - bk_c)))
                                                            mop_up = (int((dist_to_center * 10)) + int(((14 - dist_between_kings) * 5)))
                                                            if (turn == WHITE):
                                                                                    score = (score + mop_up)
                                                            else:
                                                                                    score = (score - mop_up)
    return score
    return _slang_ret
def generate_legal_captures(board):
    _slang_ret = None
    original_turn = (board . turn)
    pseudo = generate_pseudo_legal_moves(board)
    legal_captures = []
    for m in pseudo:
            if (((m . captured) == EMPTY) or ((m . captured) == 0)):
                        continue
            _slang_ret = (board . make_move(m))
            _web_builder.add_text(_slang_ret)
            if (not is_square_attacked(board, (board . get_king_square(original_turn)), (board . turn))):
                        _slang_ret = add(legal_captures, m)
                        _web_builder.add_text(_slang_ret)
            _slang_ret = (board . undo_move())
            _web_builder.add_text(_slang_ret)
    return legal_captures
    return _slang_ret
search_state = {'start_time': 0.0, 'time_limit': 100000000.0, 'aborted': False, 'node_count': 0}
def check_time():
    _slang_ret = None
    search_state['node_count'] = (search_state['node_count'] + 1)
    if ((search_state['node_count'] % 1024) == 0):
            elapsed = (((time . time()) * 1000.0) - search_state['start_time'])
            if (elapsed > search_state['time_limit']):
                        search_state['aborted'] = True
    return _slang_ret
def quiescence(board, alpha, beta):
    _slang_ret = None
    _slang_ret = check_time()
    _web_builder.add_text(_slang_ret)
    if (search_state['aborted'] == True):
            return 0
    stand_pat = evaluate(board)
    if (stand_pat >= beta):
            return beta
    if ((stand_pat + 975) < alpha):
            return alpha
    if (stand_pat > alpha):
            alpha = stand_pat
    moves = generate_legal_captures(board)
    ordered = order_moves(moves, null, 0)
    for m in ordered:
            _slang_ret = (board . make_move(m))
            _web_builder.add_text(_slang_ret)
            score = (0 - quiescence(board, (0 - beta), (0 - alpha)))
            _slang_ret = (board . undo_move())
            _web_builder.add_text(_slang_ret)
            if (score >= beta):
                        return beta
            if (score > alpha):
                        alpha = score
    return alpha
    return _slang_ret
def make_null_move(board):
    _slang_ret = None
    old_turn = (board . turn)
    old_ep = (board . ep_square)
    if ((board . turn) == WHITE):
            _slang_ret = (board . set_turn(BLACK))
            _web_builder.add_text(_slang_ret)
    else:
            _slang_ret = (board . set_turn(WHITE))
            _web_builder.add_text(_slang_ret)
    _slang_ret = (board . set_ep_square((0 - 1)))
    _web_builder.add_text(_slang_ret)
    return [old_turn, old_ep]
    return _slang_ret
def undo_null_move(board, state):
    _slang_ret = None
    _slang_ret = (board . set_turn(state[0]))
    _web_builder.add_text(_slang_ret)
    _slang_ret = (board . set_ep_square(state[1]))
    _web_builder.add_text(_slang_ret)
    return _slang_ret
def find_best_move(board, depth, allocated_time):
    _slang_ret = None
    book_move = get_book_move(board)
    if (book_move != null):
            return book_move
    moves = generate_legal_moves(board)
    if empty(moves):
            return null
    best_move = null
    _slang_ret = clear_dict(tt_table)
    _web_builder.add_text(_slang_ret)
    _slang_ret = clear_dict(killer_table)
    _web_builder.add_text(_slang_ret)
    search_state['start_time'] = ((time . time()) * 1000.0)
    search_state['time_limit'] = float(allocated_time)
    search_state['aborted'] = False
    search_state['node_count'] = 0
    last_completed_best_move = moves[0]
    end_depth = (depth + 1)
    for d in range(1, end_depth):
            key = ((str((board . squares)) + ',') + str((board . turn)))
            hash_move = null
            if contains(tt_table, key):
                        hash_move = tt_table[key]['move']
            ordered = order_moves(moves, hash_move, 0)
            best_val = (0 - 1000000)
            depth_best_move = null
            for m in ordered:
                        _slang_ret = (board . make_move(m))
                        _web_builder.add_text(_slang_ret)
                        val = (0 - negamax(board, (d - 1), (0 - 1000000), (0 - best_val), 1))
                        _slang_ret = (board . undo_move())
                        _web_builder.add_text(_slang_ret)
                        if (search_state['aborted'] == True):
                                        break
                        if (val > best_val):
                                        best_val = val
                                        depth_best_move = m
            if (search_state['aborted'] == True):
                        break
            last_completed_best_move = depth_best_move
            _slang_ret = tt_store(key, d, best_val, 0, depth_best_move)
            _web_builder.add_text(_slang_ret)
            elapsed = (((time . time()) * 1000.0) - search_state['start_time'])
            if ((elapsed * 2.0) > search_state['time_limit']):
                        break
    return last_completed_best_move
    return _slang_ret
def negamax(board, depth, alpha, beta, ply):
    _slang_ret = None
    _slang_ret = check_time()
    _web_builder.add_text(_slang_ret)
    if (search_state['aborted'] == True):
            return 0
    key = ((str((board . squares)) + ',') + str((board . turn)))
    tt_val = tt_lookup(key, depth, alpha, beta)
    if (tt_val != null):
            return tt_val
    if (depth == 0):
            return quiescence(board, alpha, beta)
    if ((depth >= 3) and (not is_in_check(board, (board . turn)))):
            null_state = make_null_move(board)
            score = (0 - negamax(board, (depth - 3), (0 - beta), ((0 - beta) + 1), (ply + 1)))
            _slang_ret = undo_null_move(board, null_state)
            _web_builder.add_text(_slang_ret)
            if (score >= beta):
                        return beta
    moves = generate_legal_moves(board)
    if empty(moves):
            if is_in_check(board, (board . turn)):
                        return ((0 - 100000) + ply)
            else:
                        return 0
    hash_move = null
    if contains(tt_table, key):
            hash_move = tt_table[key]['move']
    ordered = order_moves(moves, hash_move, ply)
    best_val = (0 - 1000000)
    best_move = null
    for m in ordered:
            _slang_ret = (board . make_move(m))
            _web_builder.add_text(_slang_ret)
            val = (0 - negamax(board, (depth - 1), (0 - beta), (0 - alpha), (ply + 1)))
            _slang_ret = (board . undo_move())
            _web_builder.add_text(_slang_ret)
            if (search_state['aborted'] == True):
                        break
            if (val > best_val):
                        best_val = val
                        best_move = m
            if (val > alpha):
                        alpha = val
            if (beta <= alpha):
                        if (((m . captured) == EMPTY) or ((m . captured) == 0)):
                                        _slang_ret = add_killer(ply, m)
                                        _web_builder.add_text(_slang_ret)
                        break
    if (search_state['aborted'] == True):
            return 0
    flag = 0
    if (best_val <= alpha):
            flag = 2
    else:
            if (best_val >= beta):
                        flag = 1
    _slang_ret = tt_store(key, depth, best_val, flag, best_move)
    _web_builder.add_text(_slang_ret)
    return best_val
    return _slang_ret