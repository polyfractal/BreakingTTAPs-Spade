# top=spi_master::spi_master

import cocotb
from spade import SpadeExt
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

CLK_PERIOD_NS = 10

async def start_clock(clk):
    await cocotb.start(Clock(clk, period=CLK_PERIOD_NS, units="ns").start())

async def reset_dut(dut):
    s = SpadeExt(dut)
    s.i.rst = True
    s.i.tick = False
    s.i.miso = "0"
    s.i.start_tx = "None"
    await FallingEdge(dut.clk)
    await FallingEdge(dut.clk)
    s.i.rst = False
    await FallingEdge(dut.clk)
    return s

async def pulse_tick(s, clk, expect_rx=None):
    """
    Pulses the 'tick' input for one clock cycle.
    Because 'rx' in the DUT is gated by 'tick' (combinatorial),
    we must check for the valid return value *during* the pulse.
    """
    s.i.tick = True
    await FallingEdge(clk)

    # Check rx while tick is High
    if expect_rx is not None:
        s.o.rx.assert_eq(f"Some({expect_rx})")
    else:
        s.o.rx.assert_eq("None")

    s.i.tick = False
    await FallingEdge(clk)

@cocotb.test()
async def test_spi_transaction(dut):
    """
    Verifies a full SPI Mode 0 transaction.
    - Sends 0xA5 (10100101) from Master -> Slave
    - Sends 0xC3 (11000011) from Slave -> Master
    """
    await start_clock(dut.clk)
    s = await reset_dut(dut)

    tx_data = 0xA5 #195
    rx_data = 0xC3 #165

    dut._log.info(f"Starting Transfer. TX: 0x{tx_data:02X}, Expecting RX: 0x{rx_data:02X}")

    # 1. Initiate Transfer
    # -----------------------------------------------------------
    s.i.start_tx = f"Some({tx_data})"

    # Pulse tick to load the data and transition to State::Transfer
    # This resets cnt to 0.
    await pulse_tick(s, dut.clk)

    s.i.start_tx = "None"

    # 2. Verify Initial State (cnt=0)
    # -----------------------------------------------------------
    # CS should be Low (Active), SCLK Low (Mode 0), MOSI = MSB of 0xA5 (1)
    s.o.cs.assert_eq(False)
    s.o.sclk.assert_eq(False)
    s.o.mosi.assert_eq(1) # MSB of 0xA5 is 1

    dut._log.info("State: Transfer initiated. CS asserted.")

    # 3. Bit Loop (Ticks 1..15)
    # -----------------------------------------------------------
    # We loop for the first 15 ticks (Bits 7 down to start of Bit 0)
    # Tick 16 (Bit 0 Falling/Shift) is special because RX Valid appears there.

    for tick_count in range(1, 16):
        # Determine which bit index we are working on (7 down to 0)
        # Ticks 1-2: Bit 7, Ticks 3-4: Bit 6, etc.
        bit_idx = 7 - ((tick_count - 1) // 2)

        # --- Prepare MISO Input ---
        if tick_count % 2 != 0:
            miso_bit = (rx_data >> bit_idx) & 1
            s.i.miso = f"{miso_bit}"
            dut._log.info(f"   [Bit {bit_idx}] Setting MISO to {miso_bit}")

        # Pulse the clock enable
        # We expect None here because transfer is not complete
        await pulse_tick(s, dut.clk, expect_rx=None)

        # --- Verify Outputs after Tick ---
        if tick_count % 2 != 0:
            # Odd Count: SCLK High
            s.o.sclk.assert_eq(True)
        else:
            # Even Count: SCLK Low
            s.o.sclk.assert_eq(False)

            # Check MOSI update
            next_bit_idx = bit_idx - 1
            expected_mosi = (tx_data >> next_bit_idx) & 1
            s.o.mosi.assert_eq(expected_mosi)
            dut._log.info(f"   [Bit {bit_idx}] Falling edge. MOSI updated to bit {next_bit_idx}: {expected_mosi}")

    # 4. Final Tick (Tick 16 - Bit 0 Falling Edge)
    # -----------------------------------------------------------
    # At the falling edge of tick 16:
    # 1. Logic shifts the last bit (Bit 0) into the register.
    # 2. State transitions to cnt=16.
    # 3. Since tick is High and cnt becomes 16, rx becomes Some(byte).

    dut._log.info("Performing final shift (Tick 16)...")

    # We expect the valid data NOW
    await pulse_tick(s, dut.clk, expect_rx=rx_data)

    # 5. Return to Idle (Tick 17)
    # -----------------------------------------------------------
    # State is currently cnt=16. We need one more tick to transition to Idle.
    # Note: Because cnt is still 16 at the start of this tick, rx might
    # still be valid during this pulse. We won't assert on it, just the transition.

    dut._log.info("Transitioning to Idle...")
    s.i.tick = True
    await FallingEdge(dut.clk)
    s.i.tick = False
    await FallingEdge(dut.clk)

    # 6. Verify Idle State
    # -----------------------------------------------------------
    s.o.cs.assert_eq(True)
    s.o.sclk.assert_eq(False)
    s.o.rx.assert_eq("None")

    dut._log.info("Test passed!")
