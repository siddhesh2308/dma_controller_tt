import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


# ============================================================
# Register addresses
# ============================================================

ADDR_SRC     = 0
ADDR_DEST    = 1
ADDR_SIZE    = 2
ADDR_CONTROL = 3
ADDR_STATUS  = 4
RAM_ADDR     = 5
RAM_WRITE    = 6
RAM_READ     = 7


# ============================================================
# Helper: Write register
# ============================================================

async def write_reg(dut, reg_sel, data):

    # Register select
    dut.uio_in.value = (dut.uio_in.value.integer & 0xF8) | reg_sel

    # Data
    dut.ui_in.value = data

    # Assert write enable
    dut.uio_in.value = dut.uio_in.value.integer | 0x08

    # Wait for clock edge
    await RisingEdge(dut.clk)

    # Small settling time
    await Timer(1, units="ns")

    # Deassert write enable
    dut.uio_in.value = dut.uio_in.value.integer & 0xF7

    # Wait another clock
    await RisingEdge(dut.clk)

    await Timer(1, units="ns")


# ============================================================
# Helper: Read register
# ============================================================

async def read_reg(dut, reg_sel):

    # Select register
    dut.uio_in.value = (dut.uio_in.value.integer & 0xF8) | reg_sel

    # Write enable = 0
    dut.uio_in.value = dut.uio_in.value.integer & 0xF7

    await Timer(1, units="ns")

    return dut.uo_out.value.integer


# ============================================================
# Helper: Write RAM
# ============================================================

async def write_ram(dut, address, data):

    # Select RAM address register
    await write_reg(dut, RAM_ADDR, address)

    # Write data to RAM
    await write_reg(dut, RAM_WRITE, data)


# ============================================================
# Helper: Read RAM
# ============================================================

async def read_ram(dut, address):

    # First select RAM address
    await write_reg(dut, RAM_ADDR, address)

    # Select RAM read register
    dut.uio_in.value = (
        (dut.uio_in.value.integer & 0xF8) | RAM_READ
    )

    # Make sure write enable = 0
    dut.uio_in.value = dut.uio_in.value.integer & 0xF7

    await Timer(1, units="ns")

    return dut.uo_out.value.integer


# ============================================================
# Main test
# ============================================================

@cocotb.test()
async def dma_test(dut):

    print("==============================================")
    print("        DMA CONTROLLER TESTBENCH")
    print("==============================================")

    errors = 0

    # ========================================================
    # Initial values
    # ========================================================

    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.ena.value = 0
    dut.rst_n.value = 1

    # ========================================================
    # Start clock
    # ========================================================

    cocotb.start_soon(
        Clock(dut.clk, 10, units="ns").start()
    )

    # ========================================================
    # TEST 1: RESET
    # ========================================================

    print("")
    print("TEST 1: Reset")

    await Timer(20, units="ns")

    # Assert reset
    dut.rst_n.value = 0

    await Timer(20, units="ns")

    # Release reset
    dut.rst_n.value = 1
    dut.ena.value = 1

    await RisingEdge(dut.clk)

    # ========================================================
    # Check UIO outputs
    # ========================================================

    uio_oe = dut.uio_oe.value.integer

    if uio_oe != 0:
        print(f"ERROR: uio_oe is not zero: {uio_oe:08b}")
        errors += 1
    else:
        print("PASS: uio_oe = 0")

    uio_out = dut.uio_out.value.integer

    if uio_out != 0:
        print(f"ERROR: uio_out is not zero: {uio_out:08b}")
        errors += 1
    else:
        print("PASS: uio_out = 0")

    # ========================================================
    # Initial status check
    # ========================================================

    status = await read_reg(dut, ADDR_STATUS)

    print(f"Status Check: {status:08b}")

    # ========================================================
    # Write data into RAM
    # ========================================================

    print("")
    print("Writing data into RAM...")

    await write_ram(dut, 0, 0xA1)
    await write_ram(dut, 1, 0xA3)
    await write_ram(dut, 2, 0xA4)
    await write_ram(dut, 3, 0xA5)

    print("RAM write completed.")

    # ========================================================
    # RAM read check
    # ========================================================

    print("")
    print("RAM READ CHECK")

    read_value = await read_ram(dut, 0)

    print(f"RAM[0] = 0x{read_value:02X}")

    # ========================================================
    # Status check
    # ========================================================

    status = await read_reg(dut, ADDR_STATUS)

    print(f"Status Check: {status:08b}")

    # ========================================================
    # Configure DMA
    #
    # SRC  = 1
    # DEST = 4
    # SIZE = 3
    #
    # Therefore:
    #
    # RAM[1] -> RAM[4]
    # RAM[2] -> RAM[5]
    # RAM[3] -> RAM[6]
    # ========================================================

    print("")
    print("Configuring DMA...")

    await write_reg(dut, ADDR_SIZE, 3)
    await write_reg(dut, ADDR_SRC, 1)
    await write_reg(dut, ADDR_DEST, 4)

    # ========================================================
    # START DMA
    # ========================================================

    print("Starting DMA...")

    await write_reg(dut, ADDR_CONTROL, 0x01)

    dut.ui_in.value = 0

    # ========================================================
    # Check destination register during transfer
    # ========================================================

    dest_value = await read_reg(dut, ADDR_DEST)

    print(
        f"Current Destination: "
        f"{dest_value:08b}"
    )

    # ========================================================
    # Wait for DMA transfer
    # ========================================================

    await Timer(100, units="ns")

    # ========================================================
    # Check transferred data
    # ========================================================

    print("")
    print("DMA TRANSFER CHECK")

    value4 = await read_ram(dut, 4)
    value5 = await read_ram(dut, 5)
    value6 = await read_ram(dut, 6)

    print(f"RAM[4] = 0x{value4:02X}")
    print(f"RAM[5] = 0x{value5:02X}")
    print(f"RAM[6] = 0x{value6:02X}")

    # ========================================================
    # Verify transferred values
    # ========================================================

    if value4 != 0xA3:
        print(
            f"ERROR: RAM[4] expected A3, "
            f"got {value4:02X}"
        )
        errors += 1
    else:
        print("PASS: RAM[4] = A3")

    if value5 != 0xA4:
        print(
            f"ERROR: RAM[5] expected A4, "
            f"got {value5:02X}"
        )
        errors += 1
    else:
        print("PASS: RAM[5] = A4")

    if value6 != 0xA5:
        print(
            f"ERROR: RAM[6] expected A5, "
            f"got {value6:02X}"
        )
        errors += 1
    else:
        print("PASS: RAM[6] = A5")

    # ========================================================
    # Status after DMA
    # ========================================================

    status = await read_reg(dut, ADDR_STATUS)

    print("")
    print(f"STATUS CHECK 3: {status:08b}")

    # ========================================================
    # SOURCE OVERFLOW TEST
    #
    # DEPTH = 8
    #
    # SRC = 6
    # SIZE = 5
    #
    # 6 + 5 = 11 > 8
    # ========================================================

    print("")
    print("SOURCE OVERFLOW TEST")

    await write_reg(dut, ADDR_SRC, 6)
    await write_reg(dut, ADDR_SIZE, 5)
    await write_reg(dut, ADDR_DEST, 2)

    await write_reg(dut, ADDR_CONTROL, 0x01)

    await Timer(20, units="ns")

    status = await read_reg(dut, ADDR_STATUS)

    print(f"STATUS CHECK 4: {status:08b}")

    # ========================================================
    # DESTINATION OVERFLOW TEST
    #
    # DEST = 6
    # SIZE = 3
    #
    # 6 + 3 = 9 > 8
    # ========================================================

    print("")
    print("DESTINATION OVERFLOW TEST")

    await write_reg(dut, ADDR_SRC, 3)
    await write_reg(dut, ADDR_SIZE, 3)
    await write_reg(dut, ADDR_DEST, 6)

    await write_reg(dut, ADDR_CONTROL, 0x01)

    await Timer(20, units="ns")

    # ========================================================
    # Status after overflow tests
    # ========================================================

    status = await read_reg(dut, ADDR_STATUS)

    print("")
    print(f"STATUS CHECK 5: {status:08b}")

    # ========================================================
    # Current source/destination registers
    # ========================================================

    src_value = await read_reg(dut, ADDR_SRC)

    print("")
    print(f"Current Source: {src_value:08b}")

    dest_value = await read_reg(dut, ADDR_DEST)

    print(
        f"Current Destination: "
        f"{dest_value:08b}"
    )

    # ========================================================
    # ENABLE SIGNAL TEST
    # ========================================================

    print("")
    print("ENABLE SIGNAL TEST")

    # Disable DUT
    dut.ena.value = 0

    await write_ram(dut, 7, 0xB5)

    disabled_value = await read_ram(dut, 7)

    print(
        f"RAM[7] with ena=0: "
        f"0x{disabled_value:02X}"
    )

    # Re-enable DUT
    dut.ena.value = 1

    await write_ram(dut, 7, 0xB5)

    enabled_value = await read_ram(dut, 7)

    print(
        f"RAM[7] with ena=1: "
        f"0x{enabled_value:02X}"
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print("")
    print("==============================================")

    if errors == 0:
        print("        ALL TESTS PASSED")
    else:
        print(
            f"        TEST FAILED: "
            f"{errors} error(s)"
        )

    print("==============================================")