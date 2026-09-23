# top=chip_top

import cocotb
from spade import SpadeExt
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer
import struct

import re
import os

# =========================================================
# Configuration
# =========================================================
CLK_PERIOD_NS = 10
EXT_CLK_PERIOD_NS = 40  # Slower clock for bootloader interface

# Magic Bytes 'B' 'T'
MAGIC = b'BT'
VERSION = 1

Src = None
Dst = None



# =========================================================
# Dynamic Token Loading
# =========================================================

class TokenNamespace:
    """
    Helper to expose tokens as attributes (Src.ALU_Res) or methods (Src.RegisterFile(0)).
    """
    def __init__(self, name, general_map, rf_map, reverse_map):
        self.name = name
        self._map = general_map      # {"ALU_Res": 11, ...}
        self._rf_map = rf_map        # {0: 0, 1: 1, ...} (index -> token)
        self._rev_map = reverse_map  # {11: ("ALU_Res", None), 0: ("RegisterFile", 0), ...}

    def __getattr__(self, key):
        if key in self._map:
            return self._map[key]
        raise AttributeError(f"{self.name} has no token '{key}'")

    def RegisterFile(self, idx):
        if idx in self._rf_map:
            return self._rf_map[idx]
        raise ValueError(f"RegisterFile index {idx} not found in {self.name} map")

    def get_str(self, token, imm_val=0):
        """Reconstruct Spade string from token ID using reverse map."""
        if token not in self._rev_map:
            return f"{self.name}::Zero" # Fallback/Default

        name, arg = self._rev_map[token]

        if name == "RegisterFile":
            return f"{self.name}::{name}({arg})"
        elif name == "Immediate":
            return f"{self.name}::{name}({imm_val})"
        else:
            return f"{self.name}::{name}"

def parse_spade_tokens(filename):
    """
    Parses imem.spade to extract decode_src_tok and decode_dst_tok mappings.
    Returns (SrcNamespace, DstNamespace).
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Could not find {filename}")

    with open(filename, 'r') as f:
        content = f.read()

    def parse_func(func_name, namespace_prefix):
        general_map = {}
        rf_map = {}
        rev_map = {}

        # Regex to find match block inside specific function
        # Finds: fn name(...) -> ... { match t { ... } }
        func_regex = re.search(f"fn {func_name}.*?match t \{{(.*?)\}}", content, re.DOTALL)
        if not func_regex:
            print(f"Warning: Could not find function {func_name}")
            return TokenNamespace(namespace_prefix, {}, {}, {})

        block_content = func_regex.group(1)

        # Parse lines like: 10u8 => Src::Immediate(zext(imm16)),
        # Captures: (token_id, type_prefix, variant_name, args)
        # e.g. ('10', 'Src', 'Immediate', 'zext(imm16)')
        # e.g. ('00', 'Src', 'RegisterFile', '0u4')
        pattern = re.compile(r'(\d+)u8\s*=>\s*(\w+)::(\w+)(?:\((.*?)\))?')

        for line in block_content.split('\n'):
            line = line.split('//')[0].strip() # Remove comments
            m = pattern.search(line)
            if m:
                tok_id = int(m.group(1))
                variant = m.group(3)
                args = m.group(4)

                # Store for reverse lookup
                # Determine "arg type": None, index (for RF), or "imm" (for Immediate)
                rev_arg = None

                if variant == "RegisterFile":
                    # Extract index from "0u4" -> 0
                    idx_match = re.search(r'(\d+)', args if args else "0")
                    idx = int(idx_match.group(1)) if idx_match else 0
                    rf_map[idx] = tok_id
                    rev_arg = idx
                elif variant == "Immediate":
                    general_map[variant] = tok_id
                    rev_arg = "imm"
                else:
                    general_map[variant] = tok_id
                    rev_arg = None

                rev_map[tok_id] = (variant, rev_arg)

        return TokenNamespace(namespace_prefix, general_map, rf_map, rev_map)

    src = parse_func("decode_src_tok", "Src")
    dst = parse_func("decode_dst_tok", "Dst")
    return src, dst


def setup_token_maps():
    global Src
    global Dst
    # Load tokens relative to this test file
    if Src is None or Dst is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        spade_file = os.path.join(current_dir, "../../src/imem.spade")
        Src, Dst = parse_spade_tokens(spade_file)

# =========================================================
# Helpers
# =========================================================

def pack_move(guard, src_tok, dst_tok, Immediate):
    return ((guard & 1) << 31) | ((src_tok & 0x7F) << 24) | ((dst_tok & 0x7F) << 17) | (Immediate & 0xFFFF)

def fmt_move(guard, src_tok, dst_tok, imm):
    global Src
    global Dst
    # Use dynamic reverse lookup
    s_str = Src.get_str(src_tok, imm & 0xFFFF)
    d_str = Dst.get_str(dst_tok)
    return f"Move({s_str}, {d_str}, {'true' if guard else 'false'})"

def fmt_instr(m0, m1):
    (g0, s0, d0, i0) = m0
    (g1, s1, d1, i1) = m1
    return f"Some(Instr({fmt_move(g0, s0, d0, i0)}, {fmt_move(g1, s1, d1, i1)}))"

async def start_clock(clk):
    await cocotb.start(Clock(clk, period=CLK_PERIOD_NS, units="ns").start())

async def reset_dut(dut):
    s = SpadeExt(dut)
    s.i.rst = True
    s.i.boot_mode = True
    s.i.fetch_pc = 0
    s.i.wr_addr = "None"
    s.i.wr_slot0 = "None"
    s.i.wr_slot1 = "None"
    await FallingEdge(dut.clk)
    s.i.rst = False
    await FallingEdge(dut.clk)
    return s

async def write_instr(s, clk, addr: int, w0: int, w1: int):
    """Pulse a write for one cycle while boot_mode is True."""
    s.i.wr_addr  = f"Some({addr})"
    s.i.wr_slot0 = f"Some({(w0 & 0xFFFFFFFF)})"
    s.i.wr_slot1 = f"Some({(w1 & 0xFFFFFFFF)})"
    await FallingEdge(clk)






def create_program_binary(moves, entry_pc=0):
    """
    Creates a byte stream for the program.
    Format: Magic(2) | Ver(2) | Count(2) | Entry(2) | [Slot0(4) | Slot1(4)]...
    """
    count = len(moves)
    # Header: BT (2), Ver (2), Cnt (2), Entry (2)
    # struct format '<2sHHH' = 2 char bytes, unsigned short, unsigned short, unsigned short (Little Endian)
    header = struct.pack('<2sHHH', MAGIC, VERSION, count, entry_pc)

    body = bytearray()
    for (m0, m1) in moves:
        w0 = pack_move(*m0)
        w1 = pack_move(*m1)
        # Each instruction is 2 words (8 bytes)
        body += struct.pack('<II', w0, w1)

    return header + body

async def drive_parallel_byte( s, byte_val):
    """
    Sends one byte using the parallel boot protocol.
    Data set on Falling Edge of parallel_clock.
    Captured by Chip on Rising Edge of parallel_clock (when Strobe is High).
    """
    # Setup Data
    s.i.parallel_clock = False
    await Timer(EXT_CLK_PERIOD_NS // 2, units='ns')

    s.i.parallel_in = f"{byte_val}"
    s.i.parallel_strobe = True

    # Hold for setup time
    await Timer(EXT_CLK_PERIOD_NS // 2, units='ns')

    # Rising Edge (Capture)
    s.i.parallel_clock = True
    await Timer(EXT_CLK_PERIOD_NS // 2, units='ns')

    # Falling Edge (End of Cycle)
    s.i.parallel_clock = False
    s.i.parallel_strobe = False

    await Timer(EXT_CLK_PERIOD_NS // 2, units='ns')

async def load_program(dut, s, binary_data):
    """Streams the binary data into the chip."""
    dut._log.info(f"Loading {len(binary_data)} bytes...")
    for b in binary_data:
        await drive_parallel_byte(s, b)
    dut._log.info("Load complete.")

# =========================================================
# Tests
# =========================================================

@cocotb.test()
async def test_boot_and_run(dut):
    """
    1. Resets chip.
    2. Loads a program via parallel interface.
    3. Checks execution trace (PC and Instructions).
    """
    global Src
    global Dst
    setup_token_maps()

    # Start System Clock
    await cocotb.start(Clock(dut.clk, period=CLK_PERIOD_NS, units="ns").start())

    # Init Signals
    s = SpadeExt(dut)
    s.i.rst = True
    s.i.uart_rx = "true"
    s.i.uart_tick16 = False
    s.i.miso = "0"
    s.i.gpi16 = "0"
    s.i.parallel_in = "0"
    s.i.parallel_strobe = False
    s.i.parallel_clock = False

    await FallingEdge(dut.clk)
    s.i.rst = False
    await FallingEdge(dut.clk)

    # --- 1. Define Program ---
    # 0: ALU_OpA = 10
    # 1: ALU_Add_Trig = 5 (Result 15) -> ALU_Res available next
    # 2: GPO = ALU_Res (Should output 15)
    # 3: Jump to 0

    prog_moves = [
        # Instr 0: Slot0(Imm(10) -> OpA), Slot1(NOP)
        ((1, Src.Immediate, Dst.ALU_OpA, 10), (0, Src.Immediate, Dst.ALU_OpA, 0)),

        # Instr 1: Slot0(Imm(5) -> Add), Slot1(NOP)
        ((1, Src.Immediate, Dst.ALU_Add_Trig, 5), (0, Src.Immediate, Dst.ALU_OpA, 0)),

        # Instr 2: Slot0(ALU_Res -> GPO), Slot1(NOP)
        ((1, Src.ALU_Res, Dst.GPO_Out, 5), (0, Src.Immediate, Dst.ALU_OpA, 0)),

        # Instr 3: Slot0(Imm(0) -> PC), Slot1(NOP) -> Loop
        ((1, Src.Immediate, Dst.PC_Trig, 0), (0, Src.Immediate, Dst.ALU_OpA, 0)),
    ]

    binary = create_program_binary(prog_moves, entry_pc=0)

    # --- 2. Load Program ---
    await load_program(dut, s, binary)

    # --- 3. Verify Execution ---
    dut._log.info("Program Loaded. Waiting for execution...")

    # Wait until we see PC=0 (Program Start)
    # We might see Reset state first.

    found_pc0 = False
    for _ in range(50):
        await FallingEdge(dut.clk)
        # Check ChipDbg struct
        # s.o.pc accesses the 'pc' field of the struct
        if s.o.pc == "0":
            found_pc0 = True
            break

    assert found_pc0, "Core did not reset to PC=0 after bootload."



    # two clock delay to get going
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)


    dut._log.info(f"Cycle 0: PC={s.o.pc.value()}, GPO={s.o.gpo16.value()}")
    s.o.pc.assert_eq(0)
    await FallingEdge(dut.clk)


    dut._log.info(f"Cycle 1: PC={s.o.pc.value()}, GPO={s.o.gpo16.value()}")
    s.o.pc.assert_eq(1)

    await FallingEdge(dut.clk)
    dut._log.info(f"Cycle 2: PC={s.o.pc.value()}, GPO={s.o.gpo16.value()}")
    s.o.pc.assert_eq(2)

    await FallingEdge(dut.clk)
    dut._log.info(f"Cycle 3: PC={s.o.pc.value()}, GPO={s.o.gpo16.value()}")
    s.o.pc.assert_eq(3)


    await FallingEdge(dut.clk)
    dut._log.info(f"Cycle 4: PC={s.o.pc.value()}, GPO={s.o.gpo16.value()}")
    s.o.pc.assert_eq(4)

    await FallingEdge(dut.clk)
    dut._log.info(f"Cycle 5: PC={s.o.pc.value()}")
    s.o.pc.assert_eq(5)
    s.o.gpo16.assert_eq(15)

    await FallingEdge(dut.clk)
    dut._log.info(f"Cycle 5: PC={s.o.pc.value()}")
    s.o.pc.assert_eq(0)

    # do it again

    dut._log.info(f"Cycle 0: PC={s.o.pc.value()}, GPO={s.o.gpo16.value()}")
    s.o.pc.assert_eq(0)
    await FallingEdge(dut.clk)


    dut._log.info(f"Cycle 1: PC={s.o.pc.value()}, GPO={s.o.gpo16.value()}")
    s.o.pc.assert_eq(1)

    await FallingEdge(dut.clk)
    dut._log.info(f"Cycle 2: PC={s.o.pc.value()}, GPO={s.o.gpo16.value()}")
    s.o.pc.assert_eq(2)

    await FallingEdge(dut.clk)
    dut._log.info(f"Cycle 3: PC={s.o.pc.value()}, GPO={s.o.gpo16.value()}")
    s.o.pc.assert_eq(3)


    await FallingEdge(dut.clk)
    dut._log.info(f"Cycle 4: PC={s.o.pc.value()}, GPO={s.o.gpo16.value()}")
    s.o.pc.assert_eq(4)

    await FallingEdge(dut.clk)
    dut._log.info(f"Cycle 5: PC={s.o.pc.value()}")
    s.o.pc.assert_eq(5)
    s.o.gpo16.assert_eq(15)

    await FallingEdge(dut.clk)
    dut._log.info(f"Cycle 5: PC={s.o.pc.value()}")
    s.o.pc.assert_eq(0)
