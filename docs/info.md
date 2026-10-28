<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This project implements a small, synthesizable 8-bit DMA (Direct Memory Access) controller designed for TinyTapeout.

The DMA controller performs memory-to-memory data transfers using an internal 8 x 8 test RAM. The source address, destination address, transfer size, and control information are configured through a simple register-based interface.

The controller operates using three main FSM states:

- **IDLE** – Waits for a DMA start command and validates the transfer parameters.
- **READ_MEM** – Reads one byte from the source memory location.
- **WRITE_MEM** – Writes the read byte to the destination memory location and updates the source and destination addresses.

For every byte transferred, the controller performs one memory read followed by one memory write. The transfer continues until the programmed number of bytes has been copied.
Since the TinyTapeout interface only gives you 8 dedicated inputs (`ui_in`), 8 dedicated outputs (`uo_out`), and 8 bidirectional pins (`uio`), the design multiplexes everything through a small register file selected by an address on the `uio` pins:

- `ui_in[7:0]` -- shared **write data bus** (register writes and RAM writes)
- `uo_out[7:0]` -- shared **read data bus** (whatever register/RAM location is currently selected)
- `uio[2:0]` -- **register/RAM address** select
- `uio[3]` -- **write strobe**: a 0-to-1 transition latches `ui_in` into the selected register
- `uio[7:4]` -- unused

### Register map (selected via `uio[2:0]`)

| Addr | Name        | Access | Description                                                        |
|------|-------------|--------|---------------------------------------------------------------------|
| 0    | `SRC`       | W      | Source address in `mem` for the next transfer (0-15)                |
| 1    | `DEST`      | W      | Destination address in `mem` for the next transfer (0-15)           |
| 2    | `SIZE`      | W      | Number of bytes to transfer                                         |
| 3    | `CONTROL`   | W      | Bit 0 = start transfer (self-clearing FSM trigger)                  |
| 4    | `STATUS`    | R      | `{mem_write_dbg, mem_read_dbg, state[1:0], busy, done, error[1:0]}` |
| 5    | `RAM_ADDR`  | W      | Address into `mem` for direct RAM access (used by 6 and 7 below)    |
| 6    | `RAM_WRITE` | W      | Writes `ui_in` into `mem[RAM_ADDR]` directly                        |
| 7    | `RAM_READ`  | R      | Reads back `mem[RAM_ADDR]`                                          |

## FSM IMPLEMENTATION
The controller operates using three main FSM states:

- **IDLE** – Waits for a DMA start command and validates the transfer parameters.
- **READ_MEM** – Reads one byte from the source memory location.
- **WRITE_MEM** – Writes the read byte to the destination memory location and updates the source and destination addresses.

For every byte transferred, the controller performs one memory read followed by one memory write. The transfer continues until the programmed number of bytes has been copied.

## STATUS SIGNAL INDICATION
The controller also provides status information such as:

- DMA busy status
- DMA completion status
- Source and destination address information
- Remaining transfer count
- Memory read/write activity
- Transfer error indication

The internal RAM can also be accessed through the control interface, allowing test data to be written into memory before starting a DMA transfer.

### Register Interface

| Register | Address | Description |
|----------|---------|-------------|
| SRC_ADDR | `0` | Source memory address |
| DEST_ADDR | `1` | Destination memory address |
| XFER_SIZE | `2` | Number of bytes to transfer |
| CONTROL | `3` | DMA control, including START |
| STATUS | `4` | DMA status and error information |
| RAM_ADDR | `5` | Internal RAM address |
| RAM_WRITE | `6` | Internal RAM data access |

The design uses the TinyTapeout `ui_in`, `uo_out`, and `uio_in` interfaces for configuration, control, and readback.

Then:

## How to test

The DMA controller can be tested by first loading data into the internal RAM and then configuring and starting a memory-to-memory transfer.

### 1. Reset the design

Assert `rst_n` low to reset the DMA controller and initialize its control and status registers.

### 2. Load data into the internal RAM

Use the `RAM_ADDR` register to select a memory location and then use the `RAM_WRITE` register to write an 8-bit data value.

For example:

1. Select `RAM_ADDR` and provide the desired memory address.
2. Select `RAM_WRITE` with the write-enable signal asserted.
3. Provide the 8-bit data on `ui_in`.
4. Repeat for the required memory locations.

### 3. Configure the DMA transfer

Program the following registers:

- `SRC_ADDR` – Starting address of the source data
- `DEST_ADDR` – Starting address of the destination
- `XFER_SIZE` – Number of bytes to transfer

### 4. Start the DMA

Write a `1` to the START control bit in the `CONTROL` register.

The DMA controller then:

1. Reads a byte from the source address.
2. Stores the byte temporarily.
3. Writes the byte to the destination address.
4. Increments the source and destination addresses.
5. Decrements the remaining transfer count.
6. Repeats until all requested bytes are transferred.

### 5. Monitor the transfer

The `STATUS` register can be read to monitor the DMA operation.

The `DONE` status bit indicates that the requested transfer has completed, while the `BUSY` bit indicates that a transfer is currently in progress.

After completion, the destination memory locations can be read back through the RAM interface to verify that the data was transferred correctly.
## External hardware

None -- this project only uses the standard TinyTapeout `ui_in`/`uo_out`/`uio` pins and needs no additional hardware to test.
