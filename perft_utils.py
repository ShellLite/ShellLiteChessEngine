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
def perft(board, depth):
    _slang_ret = None
    if (depth == 0):
            return [1, 0, 0, 0, 0, 0, 0, 0, 0]
    n = 0
    c = 0
    ep = 0
    ca = 0
    pr = 0
    ch = 0
    disc = 0
    dbl = 0
    cm = 0
    moves = generate_legal_moves(board)
    for m in moves:
            is_cap = False
            if ((m . captured) != 0):
                        is_cap = True
            is_ep = False
            if ((m . flags) == 2):
                        is_ep = True
            is_cas = False
            if ((m . flags) == 4):
                        is_cas = True
            is_pro = False
            if ((m . flags) == 8):
                        is_pro = True
            _slang_ret = (board . make_move(m))
            _web_builder.add_text(_slang_ret)
            sub_stats = perft(board, (depth - 1))
            n = (n + sub_stats[0])
            c = (c + sub_stats[1])
            ep = (ep + sub_stats[2])
            ca = (ca + sub_stats[3])
            pr = (pr + sub_stats[4])
            ch = (ch + sub_stats[5])
            disc = (disc + sub_stats[6])
            dbl = (dbl + sub_stats[7])
            cm = (cm + sub_stats[8])
            if (depth == 1):
                        if is_cap:
                                        c = (c + 1)
                        if is_ep:
                                        ep = (ep + 1)
                        if is_cas:
                                        ca = (ca + 1)
                        if is_pro:
                                        pr = (pr + 1)
                        opp_color = (board . turn)
                        if is_in_check(board, opp_color):
                                        ch = (ch + 1)
                                        ksq = (board . get_king_square(opp_color))
                                        my_color = (24 - opp_color)
                                        attackers = get_attackers(board, ksq, my_color)
                                        if (len(attackers) >= 2):
                                                            dbl = (dbl + 1)
                                        else:
                                                            att_sq = attackers[0]
                                                            if (att_sq != (m . to_sq)):
                                                                                    disc = (disc + 1)
                                        opp_moves = generate_legal_moves(board)
                                        if (len(opp_moves) == 0):
                                                            cm = (cm + 1)
            _slang_ret = (board . undo_move())
            _web_builder.add_text(_slang_ret)
    return [n, c, ep, ca, pr, ch, disc, dbl, cm]
    return _slang_ret
def real_perft(board, depth):
    _slang_ret = None
    print('Wait...')
    total_nodes = 0
    moves = generate_legal_moves(board)
    for m in moves:
            _slang_ret = (board . make_move(m))
            _web_builder.add_text(_slang_ret)
            sub_stats = perft(board, (depth - 1))
            print(((move_to_str(m) + ': ') + str(sub_stats[0])))
            total_nodes = (total_nodes + sub_stats[0])
            _slang_ret = (board . undo_move())
            _web_builder.add_text(_slang_ret)
    print('')
    print(('Nodes searched: ' + str(total_nodes)))
    return total_nodes
    return _slang_ret