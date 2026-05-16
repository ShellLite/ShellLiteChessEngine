import sys
import os
import re
import llvmlite.binding as llvm
import ctypes
import ctypes.util

def run_llvm(files):
    if not files:
        print("Usage: python run_llvm.py <file1.ll> <file2.ll> ...")
        return

    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    target = llvm.Target.from_default_triple()
    target_machine = target.create_target_machine()
    tm_layout = str(target_machine.target_data)
    
    print(f"DEBUG: Host Triple: {llvm.get_process_triple()}")
    print(f"DEBUG: TM Data Layout: {tm_layout}")
    
    msvcrt_path = ctypes.util.find_library("msvcrt")
    if msvcrt_path:
        llvm.load_library_permanently(msvcrt_path)

    _prevent_gc = []
    
    all_ir = []
    all_declared = set()
    all_defined = set()
    
    for ll_file in files:
        with open(ll_file, "r") as f:
            ir_text = f.read()
        ir_text = re.sub(
            r'target datalayout = ".*?"',
            f'target datalayout = "{tm_layout}"',
            ir_text
        )
        all_ir.append((ll_file, ir_text))
        
        for m in re.finditer(r'declare\s+\S+\s+@"?(\w+)"?\s*\(', ir_text):
            all_declared.add(m.group(1))
        for m in re.finditer(r'define\s+(?:weak\s+)?\S+\s+@"?(\w+)"?\s*\(', ir_text):
            all_defined.add(m.group(1))
    c_runtime = {
        "printf", "puts", "malloc", "free", "strlen", "strcpy", "strcat",
        "fopen", "fclose", "fwrite", "fread", "fgets", "fseek", "ftell",
        "rewind", "getchar", "realloc", "system", "memcpy", "memset",
        "atoi", "atof", "sprintf", "sscanf", "fprintf", "time",
        "clock", "abs",
    }
    
    need_stub = all_declared - all_defined - c_runtime
    
    if need_stub:
        print(f"DEBUG: Auto-stubbing {len(need_stub)} unresolved functions:")
        for name in sorted(need_stub):
            print(f"  - {name}")
    
    def make_stub(name):
        @ctypes.CFUNCTYPE(ctypes.c_int64)
        def stub():
            print(f"  [stub] {name}() called")
            sys.stdout.flush()
            return 0
        return stub

    for name in need_stub:
        cb = make_stub(name)
        _prevent_gc.append(cb)
        llvm.add_symbol(name, ctypes.cast(cb, ctypes.c_void_p).value)

    @ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_char_p)
    def my_puts(s):
        try:
            txt = s.decode("utf-8") if s else "(null)"
        except Exception:
            txt = "(decode error)"
        print(f"  [puts] {txt}")
        sys.stdout.flush()
        return 0
    _prevent_gc.append(my_puts)
    llvm.add_symbol("puts", ctypes.cast(my_puts, ctypes.c_void_p).value)

    main_mod = llvm.parse_assembly("")

    for ll_file, ir_text in all_ir:
        print(f"Loading {ll_file}...")
        try:
            mod = llvm.parse_assembly(ir_text)
            mod.verify()
            main_mod.link_in(mod)
        except Exception as e:
            print(f"ERROR loading {ll_file}: {e}")
            return

    main_mod.verify()

    engine = llvm.create_mcjit_compiler(main_mod, target_machine)
    engine.finalize_object()

    create_board_ptr = engine.get_function_address("create_board")
    create_board = ctypes.CFUNCTYPE(ctypes.c_int64)(create_board_ptr)

    find_best_move_ptr = engine.get_function_address("find_best_move")
    find_best_move = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64, ctypes.c_int64, ctypes.c_int64)(find_best_move_ptr)

    move_to_str_ptr = engine.get_function_address("move_to_str")
    move_to_str = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64)(move_to_str_ptr)

    board_set_fen_ptr = engine.get_function_address("Board_set_fen")
    board_set_fen = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64, ctypes.c_int64)(board_set_fen_ptr)

    def to_c_str(s):
        b = s.encode("utf-8")
        buf = ctypes.create_string_buffer(b)
        _prevent_gc.append(buf)
        return ctypes.cast(buf, ctypes.c_void_p).value

    def from_c_str(ptr):
        if not ptr: return ""
        return ctypes.cast(ptr, ctypes.c_char_p).value.decode("utf-8", errors="ignore")

    print("--- Starting Engine (JIT) ---")
    sys.stdout.flush()

    try:
        init_ptr = engine.get_function_address("__init_main_shl")
        if init_ptr:
            ctypes.CFUNCTYPE(ctypes.c_int64)(init_ptr)()
        
        board = create_board()
        print("info string engine ready")
        sys.stdout.flush()

        while True:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            if line == "uci":
                print("id name run_engine")
                print("id author Shrey Naithani")
                print("uciok")
                sys.stdout.flush()
            elif line == "isready":
                print("readyok")
                sys.stdout.flush()
            elif line == "ucinewgame":
                engine.get_function_address("Board_reset") # if needed
                create_board_ptr = engine.get_function_address("create_board")
                board = ctypes.CFUNCTYPE(ctypes.c_int64)(create_board_ptr)()
                print("info string board reset")
                sys.stdout.flush()
            elif line.startswith("position"):
                if "startpos" in line:
                    board = ctypes.CFUNCTYPE(ctypes.c_int64)(create_board_ptr)()
                elif "fen" in line:
                    parts = line.split()
                    try:
                        fen_idx = parts.index("fen")
                        fen_parts = []
                        for p in parts[fen_idx+1:]:
                            if p == "moves": break
                            fen_parts.append(p)
                        fen_str = " ".join(fen_parts)
                        board_set_fen(board, to_c_str(fen_str))
                    except ValueError:
                        pass
                
                if "moves" in line:
                    parts = line.split()
                    try:
                        moves_idx = parts.index("moves")
                        for m in parts[moves_idx+1:]:
                            pass
                    except ValueError:
                        pass
                        
            elif line.startswith("go"):
                parts = line.split()
                search_depth = 6
                allocated_time = 100000000.0

                try:
                    if "depth" in parts:
                        search_depth = int(parts[parts.index("depth")+1])
                    if "movetime" in parts:
                        allocated_time = float(parts[parts.index("movetime")+1])
                except (ValueError, IndexError):
                    pass

                best_move = find_best_move(board, search_depth, int(allocated_time))
                if best_move:
                    print(f"bestmove {from_c_str(move_to_str(best_move))}")
                else:
                    print("bestmove 0000")
                sys.stdout.flush()
            elif line == "quit":
                break
    except Exception as e:
        print(f"--- Engine Error: {e} ---")

if __name__ == "__main__":
    run_llvm(sys.argv[1:])
