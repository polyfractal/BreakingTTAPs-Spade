#top=pc::pc_fu

import cocotb
from spade import SpadeExt
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

#//============================================================
#// Program Counter unit
#// - PC_Val is the current PC (readable source)
#// - Writing PC_Trig with a value causes a jump (next cycle)
#//============================================================
#entity pc_unit(
#  clk: clock, rst: bool,
#  jump_to: Option<uint<16>>
#) -> uint<16>


@cocotb.test()
async def test_reset(dut):
    """pc_counter is 0 after reset"""
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())

    s.i.rst = True
    s.i.jump_to = "None"
    s.i.bt = "None"
    await FallingEdge(clk)
    s.o.assert_eq(0)

@cocotb.test()
async def test_jump(dut):
    """pc_counter is 10 after jump"""
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())

    s.i.rst = True
    s.i.jump_to = "None"
    s.i.bt = "None"
    await FallingEdge(clk)
    s.o.assert_eq(0)

    s.i.rst = False
    s.i.jump_to = "Some(10)"
    await FallingEdge(clk)
    s.o.assert_eq(10)

@cocotb.test()
async def test_jump_then_clock(dut):
    """pc_counter is 11 after jump and clock"""
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())

    s.i.rst = True
    s.i.jump_to = "None"
    s.i.bt = "None"
    await FallingEdge(clk)
    s.o.assert_eq(0)

    s.i.rst = False
    s.i.jump_to = "Some(10)"
    await FallingEdge(clk)
    s.o.assert_eq(10)

    s.i.rst = False
    s.i.jump_to = "None"
    await FallingEdge(clk)
    s.o.assert_eq(11)
