# top=uart::uart_fu

import cocotb
from spade import SpadeExt
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

CLK_PERIOD_NS = 10
BIT_TICKS = 16

async def start_clock(clk):
    await cocotb.start(Clock(clk, period=CLK_PERIOD_NS, units="ns").start())

async def reset_dut(dut):
    s = SpadeExt(dut)
    s.i.rst = True
    s.i.tick16 = False
    s.i.rx_in = "true" # Idle High
    s.i.tx_data = "None"
    await FallingEdge(dut.clk)
    s.i.rst = False
    await FallingEdge(dut.clk)
    return s

async def pulse_tick16(s, clk):
    s.i.tick16 = True
    await FallingEdge(clk)
    s.i.tick16 = False
    await FallingEdge(clk)



@cocotb.test()
async def test_uart_loopback(dut):
    """Test RX receiving 0xA5 separately."""
    await start_clock(dut.clk)
    s = await reset_dut(dut)

    dut._log.info("Testing RX: 0xA5 (10100101)")
    byte_val = 0xA5
    clk = dut.clk

    # Start Bit
    s.i.rx_in = "false"
    for i in range(BIT_TICKS):
        await pulse_tick16(s, clk)
        dut._log.info(f"RX drive: start bit[{i}]: false")

    # Data Bits
    for i in range(8):
        bit = (byte_val >> i) & 1
        bit = str(bool(bit)).lower()

        dut._log.info(f"RX drive: bit[{i}]")

        s.i.rx_in = f"{bit}"
        for j in range(BIT_TICKS):
            await pulse_tick16(s, clk)
            dut._log.info(f"    sub tick[{j}]: {bit}")
            s.o.rx_data.assert_eq("None")

    # Stop Bit
    s.i.rx_in = "true"
    dut._log.info(f"RX drive: stop bit[{i}]: true")

    # send stop bit
    for i in range(8):
        await pulse_tick16(s, clk)
        dut._log.info(f"    sub tick[{i}]: true")
        s.o.rx_data.assert_eq("None")

    # Tick 15 (Last tick of Stop Bit)
    # We must check *while* tick is high
    s.i.tick16 = True
    await FallingEdge(clk)
    s.o.rx_data.assert_eq(f"Some({byte_val})") # Expect Data HERE


    s.i.tick16 = False
    await FallingEdge(clk)

    # Next cycle (Idle)
    s.o.rx_data.assert_eq("None")

    s.i.tick16 = True
    await FallingEdge(clk)

    # Next cycle (Idle)
    s.o.rx_data.assert_eq("None")


@cocotb.test()
async def test_send(dut):
    """Test TX sending 0x55."""
    await start_clock(dut.clk)
    s = await reset_dut(dut)

    # --- Test TX ---
    dut._log.info("Testing TX: 0x55 (01010101)")
    s.i.tx_data = "Some(85)" # 0x55
    await pulse_tick16(s, dut.clk)
    s.i.tx_data = "None"

    # Verify Start Bit (Low)
    await pulse_tick16(s, dut.clk)
    s.o.tx_out.assert_eq(False)

    # Wait full bit time (15 more ticks)
    for i in range(15):
        output_bit = s.o.tx_out.value()
        dut._log.info(f"start bit[{i}]: {output_bit}")
        s.o.tx_out.assert_eq(False)
        await pulse_tick16(s, dut.clk)


    # Verify Data Bits
    expected_bits = [1, 0, 1, 0, 1, 0, 1, 0]
    for (i, bit) in enumerate(expected_bits):
        output_bit = s.o.tx_out.value()
        dut._log.info(f"bit[{i}]: {output_bit}, expected: {bit}")
        s.o.tx_out.assert_eq(bool(bit))
        for j in range(16):
            output_subbit = s.o.tx_out.value()
            dut._log.info(f"  sub tick: {j} output: {output_subbit}")
            await pulse_tick16(s, dut.clk)

    # Verify Stop Bit (High)
    s.o.tx_out.assert_eq("true")
