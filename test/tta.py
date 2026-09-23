#top=tta::tta

import cocotb
from spade import SpadeExt
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

@cocotb.test()
async def test_reset(dut):
    """Tick output is None after reset"""
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())

    s.i.rst = True
    s.i.insn = "Instr(Move(Src::Zero, Dst::ALU_OpA, false), Move(Src::Zero, Dst::ALU_OpA, false))"
    await FallingEdge(clk)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")



#// 1) r2 = r0 + r1
#//    Cycle N:
#//      BUS0: RF(0)  -> ALU_OpA
#//      BUS1: RF(1)  -> ALU_Add_Trig
#//    Cycle N+1:
#//      BUS0: ALU_Res -> RF(2)
#//      BUS1: Zero    -> RF(0) (or NOP)
#//
#// 2) Jump to 0x0042 using an immediate on BUS0:
#//      BUS0: Imm(0x0042) -> PC_Trig
#//      BUS1: Zero        -> RF(0) (or NOP)
#//


@cocotb.test()
async def test_reg_store_read(dut):
    """simple program"""
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())

    s.i.rst = True
    s.i.insn = "Instr(Move(Src::Zero, Dst::ALU_OpA, false), Move(Src::Zero, Dst::ALU_OpA, false))" #NOP
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(0)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)

    s.i.rst = False
    s.i.insn = "Instr(Move(Src::Immediate(19), Dst::RegisterFile(0), true), Move(Src::Zero, Dst::ALU_OpA, false))" #immediate into ALU opA
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(1)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("Some((0,19))")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(19)
    s.o.rd1.assert_eq(19)

    s.i.rst = False
    s.i.insn = "Instr(Move(Src::RegisterFile(0), Dst::RegisterFile(1), true), Move(Src::Zero, Dst::ALU_OpA, false))" #move it back so we can see in debug
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(2)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("Some((1,19))")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(19)
    s.o.rd1.assert_eq(19)



@cocotb.test()
async def test_add_two_immediate(dut):
    """simple program"""
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())

    s.i.rst = True
    s.i.insn = "Instr(Move(Src::Zero, Dst::ALU_OpA, false), Move(Src::Zero, Dst::ALU_OpA, false))" #NOP
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(0)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)

    s.i.rst = False
    s.i.insn = "Instr(Move(Src::Immediate(19), Dst::ALU_OpA, true), Move(Src::Zero, Dst::ALU_OpA, false))" #immediate into ALU opA
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(1)
    s.o.alu_a_comb.assert_eq("Some(19)")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)

    s.i.rst = False
    s.i.insn = "Instr(Move(Src::Immediate(1), Dst::ALU_Add_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false))" #immediate into Add trigger
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(2)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("Some((AluOp::Add(),1))")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.alu_res.assert_eq("Some(20)")

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::ALU_Res, Dst::RegisterFile(0), true), Move(Src::Zero, Dst::ALU_OpA, false) )" #Move result to r0
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(3)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(20)   #we'll see the memory read as a side effect here
    s.o.rd1.assert_eq(20)
    s.o.alu_res.assert_eq("None)")

    s.i.rst = False
    s.i.insn = "Instr(Move(Src::RegisterFile(0), Dst::ALU_OpA, true), Move(Src::Zero, Dst::ALU_OpA, false))" #move it back so we can see in debug
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(4)
    s.o.alu_a_comb.assert_eq("Some(20)") # value is back in OpA
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(20)
    s.o.rd1.assert_eq(20)


@cocotb.test()
async def test_store_load_register(dut):
    """simple program"""
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())


    s.i.rst = True
    s.i.insn = "Instr(Move(Src::Zero, Dst::ALU_OpA, false), Move(Src::Zero, Dst::ALU_OpA, false))" #NOP
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(0)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")

    s.i.rst = False
    s.i.insn = "Instr(Move(Src::Immediate(0), Dst::LSU_AddrA, true), Move(Src::Zero, Dst::ALU_OpA, false))" #immediate 0 into LSU address
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(1)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")
    s.o.lsu_set_addr.assert_eq("Some(0)") # matches addr 0

    s.i.rst = False
    s.i.insn = "Instr(Move(Src::Immediate(19), Dst::LSU_Store_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false))" #immediate 19 into LSU Load
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(2)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")
    s.o.lsu_store.assert_eq("Some(19)") # matches value 19

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::Immediate(0), Dst::LSU_Load_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false) )" # Load from LSU
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(3)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("Some(19)") # No data yet
    s.o.lsu_load.assert_eq("Some(0)") # matches address offset 0

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::LSU_Res, Dst::RegisterFile(0u4), true), Move(Src::Zero, Dst::ALU_OpA, false) )" # Load into Reg 0
    await FallingEdge(clk)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(19)
    s.o.rd1.assert_eq(19)
    s.o.lsu_res.assert_eq("None")

@cocotb.test()
async def test_store_load_add(dut):
    """simple program"""
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())


    s.i.rst = True
    s.i.insn = "Instr(Move(Src::Zero, Dst::ALU_OpA, false), Move(Src::Zero, Dst::ALU_OpA, false))" #NOP
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(0)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")

    s.i.rst = False
    s.i.insn = "Instr(Move(Src::Immediate(0), Dst::LSU_AddrA, true), Move(Src::Zero, Dst::ALU_OpA, false))" #immediate 0 into LSU address
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(1)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")
    s.o.lsu_set_addr.assert_eq("Some(0)") # matches addr 0

    s.i.rst = False
    s.i.insn = "Instr(Move(Src::Immediate(19), Dst::LSU_Store_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false))" #immediate 19 into LSU Load
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(2)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")
    s.o.lsu_store.assert_eq("Some(19)") # matches value 19

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::Immediate(0), Dst::LSU_Load_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false) )" # Load from LSU
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(3)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("Some(19)") # No data yet
    s.o.lsu_load.assert_eq("Some(0)") # matches address offset 0

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::LSU_Res, Dst::ALU_OpA, true), Move(Src::Zero, Dst::ALU_OpA, false) )" # Load into Reg 0
    await FallingEdge(clk)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::Immediate(1), Dst::ALU_Add_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false) )" # Load into Reg 0
    await FallingEdge(clk)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("Some((AluOp::Add(),1))")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::ALU_Res, Dst::RegisterFile(1u4), true), Move(Src::Zero, Dst::ALU_OpA, false) )" # Load into Reg 1
    await FallingEdge(clk)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::RegisterFile(1u4), Dst::LSU_Store_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false) )" # Store from Reg 1
    await FallingEdge(clk)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(20)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")
    s.o.lsu_store.assert_eq("Some(20)")

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::Immediate(0), Dst::LSU_Load_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false) )" # Load from LSU
    await FallingEdge(clk)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("Some(20)")
    s.o.lsu_load.assert_eq("Some(0)")



@cocotb.test()
async def test_gpi(dut):
    """simple program"""
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())


    s.i.rst = True
    s.i.insn = "Instr(Move(Src::Zero, Dst::ALU_OpA, false), Move(Src::Zero, Dst::ALU_OpA, false))" #NOP
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(0)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)

    s.i.rst = False
    s.i.gpi16 = 19
    await FallingEdge(clk)
    await FallingEdge(clk) #two clock cycles to register GPI

    s.i.insn = "Instr(Move(Src::GPI_In, Dst::ALU_OpA, true), Move(Src::Zero, Dst::ALU_OpA, false))" #GPI into ALU opA
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(3)
    s.o.alu_a_comb.assert_eq("Some(19)")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::Immediate(1), Dst::ALU_Add_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false) )" # Load into Reg 0
    await FallingEdge(clk)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("Some((AluOp::Add(),1))")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::ALU_Res, Dst::RegisterFile(1u4), true), Move(Src::Zero, Dst::ALU_OpA, false) )" # Load into Reg 1
    await FallingEdge(clk)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")

    s.i.rst = False
    s.i.insn = "Instr( Move(Src::RegisterFile(1u4), Dst::LSU_Store_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false) )" # Store from Reg 1
    await FallingEdge(clk)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(20)
    s.o.rd1.assert_eq(0)
    s.o.lsu_res.assert_eq("None")
    s.o.lsu_store.assert_eq("Some(20)")


@cocotb.test()
async def test_branch_if_true(dut):
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())


    s.i.rst = True
    s.i.insn = "Instr(Move(Src::Zero, Dst::ALU_OpA, false), Move(Src::Zero, Dst::ALU_OpA, false))" #NOP
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(0)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)

    s.i.rst = False
    await FallingEdge(clk)

    # set Branch-if-true target to 19
    s.i.insn = "Instr(Move(Src::Immediate(19), Dst::BT_Target, true), Move(Src::Zero, Dst::ALU_OpA, false))"
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(2)
    s.o.pc_jump_comb.assert_eq("None")

    # trigger BT with true (1)
    s.i.insn = "Instr( Move(Src::Immediate(1), Dst::BT_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false) )"
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(19)            # PC jumped to 19

@cocotb.test()
async def test_branch_if_true_false(dut):
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())


    s.i.rst = True
    s.i.insn = "Instr(Move(Src::Zero, Dst::ALU_OpA, false), Move(Src::Zero, Dst::ALU_OpA, false))" #NOP
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(0)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)

    s.i.rst = False
    await FallingEdge(clk)

    # set Branch-if-true target to 19
    s.i.insn = "Instr(Move(Src::Immediate(19), Dst::BT_Target, true), Move(Src::Zero, Dst::ALU_OpA, false))"
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(2)
    s.o.pc_jump_comb.assert_eq("None")

    # trigger BT with false (0)
    s.i.insn = "Instr( Move(Src::Immediate(0), Dst::BT_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false) )"
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(3)            # PC incremented to 3


@cocotb.test()
async def test_branch_precedence_over_unconditional(dut):
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())


    s.i.rst = True
    s.i.insn = "Instr(Move(Src::Zero, Dst::ALU_OpA, false), Move(Src::Zero, Dst::ALU_OpA, false))" #NOP
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(0)
    s.o.alu_a_comb.assert_eq("None")
    s.o.alu_t_comb.assert_eq("None")
    s.o.pc_jump_comb.assert_eq("None")
    s.o.rf_w0.assert_eq("None")
    s.o.rf_w1.assert_eq("None")
    s.o.rd0.assert_eq(0)
    s.o.rd1.assert_eq(0)

    s.i.rst = False
    await FallingEdge(clk)

    # set Branch-if-true target to 19
    s.i.insn = "Instr(Move(Src::Immediate(19), Dst::BT_Target, true), Move(Src::Zero, Dst::ALU_OpA, false))"
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(2)
    s.o.pc_jump_comb.assert_eq("None")

    # trigger BT with true (1)
    s.i.insn = "Instr( Move(Src::Immediate(1), Dst::BT_Trig, true), Move(Src::Immediate(1), Dst::PC_Trig, true) )"
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(19)            # PC jumped to 19 instead of 1 from unconditional move

    # invert slots, same trick. trigger BT with true (1)
    s.i.insn = "Instr(Move(Src::Immediate(1), Dst::PC_Trig, true), Move(Src::Immediate(1), Dst::BT_Trig, true))"
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(19)            # PC jumped to 19 instead of 1 from unconditional move


@cocotb.test()
async def test_clock_counter(dut):
    s = SpadeExt(dut) # Wrap the dut in the Spade wrapper

    clk = dut.clk

    await cocotb.start(Clock(
        clk,
        period=10,
        units='ns'
    ).start())


    s.i.rst = True
    s.i.insn = "Instr(Move(Src::Zero, Dst::ALU_OpA, false), Move(Src::Zero, Dst::ALU_OpA, false))" #NOP
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(0)

    s.i.rst = False
    await FallingEdge(clk)
    await FallingEdge(clk)
    await FallingEdge(clk)
    await FallingEdge(clk)
    await FallingEdge(clk)
    await FallingEdge(clk)
    await FallingEdge(clk)
    await FallingEdge(clk)
    await FallingEdge(clk)
    await FallingEdge(clk)

    s.i.insn = "Instr(Move(Src::CC_Res_Lo,  Dst::ALU_Add_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false))"
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(11)
    s.o.alu_t_comb.assert_eq("Some((AluOp::Add(),11))") # ALU trigger will show 11 clock cycles on the counter

    s.i.insn = "Instr(Move(Src::CC_Res_High,  Dst::ALU_Add_Trig, true), Move(Src::Zero, Dst::ALU_OpA, false))"
    await FallingEdge(clk)
    s.o.pc_val.assert_eq(12)
    s.o.alu_t_comb.assert_eq("Some((AluOp::Add(),0))") # ALU trigger will show 0 in the high bits
