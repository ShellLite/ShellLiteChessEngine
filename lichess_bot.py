"""
Lichess Bot Bridge for ShellLite ChessEngine
=============================================
Connects the ShellLite UCI chess engine to Lichess via the Bot API.

Usage:
    1. Edit lichess_config.json with your API token
    2. Run: python lichess_bot.py
"""

import json
import os
import subprocess
import sys
import threading
import time

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package is required. Install it with:")
    print("  pip install requests")
    sys.exit(1)

LICHESS_API = "https://lichess.org"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "lichess_config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERROR: Config file not found: {CONFIG_PATH}")
        print("Create lichess_config.json with your API token.")
        sys.exit(1)

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    token = os.environ.get("LICHESS_TOKEN", config.get("token", ""))
    if not token or token == "YOUR_LICHESS_API_TOKEN_HERE":
        print("ERROR: Please set your Lichess API token in lichess_config.json")
        print("       or set the LICHESS_TOKEN environment variable.")
        sys.exit(1)

    config["token"] = token
    return config

class UCIEngine:
    """Manages the ShellLite engine subprocess via UCI protocol."""

    def __init__(self):
        self.process = None
        self.lock = threading.Lock()
        self._queue = None
        self._reader_thread = None

    def start(self):
        """Start the engine subprocess."""
        from queue import Queue, Empty

        shelllite_path = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "ShellLite"))
        env = os.environ.copy()
        for k in list(env.keys()):
            if k.upper() == "PYTHONPATH":
                env.pop(k)
        env["PYTHONPATH"] = shelllite_path

        main_py = os.path.join(SCRIPT_DIR, "main.py")

        self.process = subprocess.Popen(
            [sys.executable, main_py],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
            cwd=SCRIPT_DIR,
        )

        self._queue = Queue()

        def _reader():
            try:
                for line in self.process.stdout:
                    self._queue.put(line.rstrip("\n").rstrip("\r"))
            except ValueError:
                pass

        self._reader_thread = threading.Thread(target=_reader, daemon=True)
        self._reader_thread.start()

        time.sleep(1)

        self._send("uci")
        self._read_until("uciok")

        self._send("isready")
        self._read_until("readyok")

        print("[Engine] Started and ready.")

    def stop(self):
        """Stop the engine subprocess."""
        if self.process and self.process.poll() is None:
            try:
                self._send("quit")
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()
        print("[Engine] Stopped.")

    def _send(self, cmd):
        """Send a command to the engine."""
        if self.process and self.process.poll() is None:
            self.process.stdin.write(cmd + "\n")
            self.process.stdin.flush()

    def _read_line(self, timeout=10):
        """Read a single line from the engine, with timeout."""
        from queue import Empty
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    def _read_until(self, target, timeout=15):
        """Read lines until we see one containing target string."""
        start = time.time()
        lines = []
        while time.time() - start < timeout:
            remaining = timeout - (time.time() - start)
            if remaining <= 0:
                break
            line = self._read_line(timeout=min(remaining, 2))
            if line is not None:
                lines.append(line)
                if target in line:
                    return lines
        return lines

    def get_best_move(self, position_cmd, go_cmd):
        """
        Send a position + go command and return the best move string.
        Thread safe.
        """
        with self.lock:
            print(f"[DEBUG ENGINE] Sending position: {position_cmd}")
            print(f"[DEBUG ENGINE] Sending go: {go_cmd}")
            self._send("ucinewgame")
            self._send("isready")
            self._read_until("readyok")

            self._send(position_cmd)
            self._send(go_cmd)

            lines = self._read_until("bestmove", timeout=120)
            print(f"[DEBUG ENGINE] Received lines:")
            for line in lines:
                print(f"  > {line}")
                if line.startswith("bestmove"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]
            return None

class LichessClient:
    """Handles all communication with the Lichess API."""

    def __init__(self, token):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
        })

    def get_profile(self):
        r = self.session.get(f"{LICHESS_API}/api/account")
        r.raise_for_status()
        return r.json()

    def upgrade_to_bot(self):
        r = self.session.post(f"{LICHESS_API}/api/bot/account/upgrade")
        return r.status_code == 200

    def stream_events(self):
        """Generator that yields events from the event stream."""
        r = self.session.get(
            f"{LICHESS_API}/api/stream/event",
            stream=True,
        )
        r.raise_for_status()
        for line in r.iter_lines():
            if line:
                yield json.loads(line.decode("utf-8"))

    def stream_game(self, game_id):
        """Generator that yields events from a game stream."""
        r = self.session.get(
            f"{LICHESS_API}/api/bot/game/stream/{game_id}",
            stream=True,
        )
        r.raise_for_status()
        for line in r.iter_lines():
            if line:
                yield json.loads(line.decode("utf-8"))

    def accept_challenge(self, challenge_id):
        r = self.session.post(
            f"{LICHESS_API}/api/challenge/{challenge_id}/accept"
        )
        return r.status_code == 200

    def decline_challenge(self, challenge_id, reason="generic"):
        r = self.session.post(
            f"{LICHESS_API}/api/challenge/{challenge_id}/decline",
            json={"reason": reason},
        )
        return r.status_code == 200

    def make_move(self, game_id, move):
        for attempt in range(3):
            try:
                r = self.session.post(
                    f"{LICHESS_API}/api/bot/game/{game_id}/move/{move}"
                )
                if r.status_code == 200:
                    return True
                
                if r.status_code == 429:
                    wait_time = 2 * (attempt + 1)
                    print(f"[DEBUG LICHESS API] Rate limited (429) playing move {move}. Attempt {attempt + 1}/3. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                print(f"[DEBUG LICHESS API] Move {move} failed with status {r.status_code}: {r.text}")
                return False
            except Exception as e:
                wait_time = 1 + attempt
                print(f"[DEBUG LICHESS API] Network error playing move {move}: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        return False

    def send_chat(self, game_id, text, room="player"):
        self.session.post(
            f"{LICHESS_API}/api/bot/game/{game_id}/chat",
            json={"room": room, "text": text},
        )

    def resign(self, game_id):
        self.session.post(f"{LICHESS_API}/api/bot/game/{game_id}/resign")


def handle_game(game_id, bot_id, config, active_games):
    """Handle a single game from start to finish."""
    depth = config.get("engine_depth", 5)
    print(f"[Game {game_id}] Starting game handler...")

    client = LichessClient(config["token"])
    engine = UCIEngine()
    engine.start()

    initial_fen = None
    last_played_move_count = -1
    try:
        client.send_chat(game_id, "Good luck! I'm the ShellLite chess engine.", "player")

        retries = 0
        max_retries = 5
        while retries < max_retries:
            try:
                for event in client.stream_game(game_id):
                    event_type = event.get("type", "")

                    if event_type == "gameFull":
                        white_id = event.get("white", {}).get("id", "")
                        black_id = event.get("black", {}).get("id", "")

                        if white_id == bot_id:
                            bot_color = "white"
                        else:
                            bot_color = "black"

                        print(f"[Game {game_id}] Playing as {bot_color}")

                        state = event.get("state", {})
                        moves_str = state.get("moves", "")
                        move_count = len(moves_str.strip().split()) if moves_str.strip() else 0
                        status = state.get("status", "")
                        initial_fen = event.get("initialFen")

                        wtime = state.get("wtime")
                        btime = state.get("btime")
                        winc = state.get("winc")
                        binc = state.get("binc")

                        if status != "started":
                            print(f"[Game {game_id}] Game already finished: {status}")
                            break

                        if _is_our_turn(moves_str, bot_color):
                            if move_count > last_played_move_count:
                                last_played_move_count = move_count
                                _play_move(client, engine, game_id, moves_str, depth, initial_fen, wtime, btime, winc, binc)

                    elif event_type == "gameState":
                        moves_str = event.get("moves", "")
                        move_count = len(moves_str.strip().split()) if moves_str.strip() else 0
                        status = event.get("status", "")

                        wtime = event.get("wtime")
                        btime = event.get("btime")
                        winc = event.get("winc")
                        binc = event.get("binc")

                        if status != "started":
                            print(f"[Game {game_id}] Game ended: {status}")
                            break

                        if _is_our_turn(moves_str, bot_color):
                            if move_count > last_played_move_count:
                                last_played_move_count = move_count
                                _play_move(client, engine, game_id, moves_str, depth, initial_fen, wtime, btime, winc, binc)

                    elif event_type == "chatLine":
                        pass

                break

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    retries += 1
                    wait = 10 * retries
                    print(f"[Game {game_id}] Rate limited, retrying in {wait}s ({retries}/{max_retries})")
                    time.sleep(wait)
                else:
                    raise
            except Exception as e:
                retries += 1
                wait = min(2 * retries, 10)
                print(f"[Game {game_id}] Connection interrupted ({e}), reconnecting in {wait}s... ({retries}/{max_retries})")
                time.sleep(wait)

    except Exception as e:
        print(f"[Game {game_id}] Error: {e}")
    finally:
        engine.stop()
        active_games.discard(game_id)
        print(f"[Game {game_id}] Handler finished.")


def _is_our_turn(moves_str, bot_color):
    """Determine if it's the bot's turn based on move count."""
    if not moves_str.strip():
        move_count = 0
    else:
        move_count = len(moves_str.strip().split())

    if bot_color == "white":
        return move_count % 2 == 0
    else:
        return move_count % 2 == 1


def _play_move(client, engine, game_id, moves_str, depth, initial_fen=None, wtime=None, btime=None, winc=None, binc=None):
    """Calculate and play a move."""
    if initial_fen and initial_fen != "startpos":
        if moves_str.strip():
            position_cmd = f"position fen {initial_fen} moves {moves_str}"
        else:
            position_cmd = f"position fen {initial_fen}"
    else:
        if moves_str.strip():
            position_cmd = f"position startpos moves {moves_str}"
        else:
            position_cmd = "position startpos"

    if wtime is not None and btime is not None:
        winc_val = winc if winc is not None else 0
        binc_val = binc if binc is not None else 0
        go_cmd = f"go wtime {wtime} btime {btime} winc {winc_val} binc {binc_val}"
        print(f"[Game {game_id}] Thinking... (wtime={wtime}, btime={btime}, winc={winc_val}, binc={binc_val})")
    else:
        go_cmd = f"go depth {depth}"
        print(f"[Game {game_id}] Thinking... (depth {depth})")

    best_move = engine.get_best_move(position_cmd, go_cmd)

    if best_move and best_move != "0000":
        print(f"[Game {game_id}] Playing: {best_move}")
        success = client.make_move(game_id, best_move)
        if not success:
            print(f"[Game {game_id}] WARNING: Move {best_move} was rejected!")
            client.resign(game_id)
    else:
        print(f"[Game {game_id}] No legal move found, resigning.")
        client.resign(game_id)

def main():
    print("=" * 60)
    print("  ShellLite ChessEngine — Lichess Bot Bridge")
    print("=" * 60)

    config = load_config()
    client = LichessClient(config["token"])

    try:
        profile = client.get_profile()
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: Failed to authenticate with Lichess: {e}")
        sys.exit(1)

    bot_id = profile.get("id", "")
    bot_name = profile.get("username", bot_id)
    is_bot = profile.get("title", "") == "BOT"

    print(f"[Lichess] Logged in as: {bot_name}")

    if not is_bot:
        print("[Lichess] Account is not a BOT. Attempting upgrade...")
        if client.upgrade_to_bot():
            print("[Lichess] Successfully upgraded to BOT account!")
        else:
            print("ERROR: Failed to upgrade to BOT account.")
            print("       The account may have already played human games.")
            print("       Bot accounts must be created from fresh accounts.")
            sys.exit(1)

    accept_variants = config.get("accept_variants", ["standard"])
    accept_speeds = config.get("accept_speeds",
                               ["bullet", "blitz", "rapid", "classical", "correspondence"])

    active_games = set()

    print("[Lichess] Listening for challenges and games...")
    print("          Press Ctrl+C to stop.\n")

    try:
        while True:
            try:
                for event in client.stream_events():
                    event_type = event.get("type", "")

                    if event_type == "challenge":
                        challenge = event.get("challenge", {})
                        challenger = challenge.get("challenger", {}).get("name", "?")
                        variant = challenge.get("variant", {}).get("key", "standard")
                        speed = challenge.get("speed", "rapid")
                        ch_id = challenge.get("id", "")

                        print(f"[Challenge] From {challenger} — {variant} {speed}")

                        max_games = config.get("max_simultaneous_games", 1)
                        if len(active_games) >= max_games:
                            print(f"[Challenge] Declining (already in {len(active_games)} of {max_games} games)")
                            client.decline_challenge(ch_id, "later")
                        elif variant in accept_variants and speed in accept_speeds:
                            print(f"[Challenge] Accepting!")
                            client.accept_challenge(ch_id)
                        else:
                            print(f"[Challenge] Declining (unsupported variant/speed)")
                            client.decline_challenge(ch_id, "standard")

                    elif event_type == "gameStart":
                        game = event.get("game", {})
                        game_id = game.get("gameId", game.get("id", ""))

                        if game_id in active_games:
                            print(f"[Game] Ignoring duplicate gameStart: {game_id}")
                            continue

                        active_games.add(game_id)
                        print(f"\n[Game] New game started: {game_id}")

                        t = threading.Thread(
                            target=handle_game,
                            args=(game_id, bot_id, config, active_games),
                            daemon=True,
                        )
                        t.start()

                    elif event_type == "gameFinish":
                        game = event.get("game", {})
                        game_id = game.get("gameId", game.get("id", ""))
                        active_games.discard(game_id)
                        print(f"[Game] Game finished: {game_id}")

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    print("[Lichess] Rate limited (429). Waiting 60 seconds...")
                    time.sleep(60)
                else:
                    print(f"[Lichess] HTTP error: {e}. Retrying in 10 seconds...")
                    time.sleep(10)
            except Exception as e:
                print(f"[Lichess] Connection lost or error occurred ({e}). Reconnecting in 5 seconds...")
                time.sleep(5)

    except KeyboardInterrupt:
        print("\n[Bot] Shutting down...")

    print("[Bot] Goodbye!")


if __name__ == "__main__":
    main()
