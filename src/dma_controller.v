module tt_um_dma_engine #(parameter WIDTH_RAM=8, parameter DEPTH_RAM=8) (
    input  wire [WIDTH_RAM-1:0] ui_in,
    output wire [WIDTH_RAM-1:0] uo_out,
    input  wire [WIDTH_RAM-1:0] uio_in,
    output wire [WIDTH_RAM-1:0] uio_out,
    output wire [WIDTH_RAM-1:0] uio_oe,
    input  wire        ena,
    input  wire        clk,
    input  wire        rst_n
);

    localparam ADDR_WIDTH = $clog2(DEPTH_RAM);
    localparam TRANSFER_SIZE = ADDR_WIDTH + 1;
 
    assign uio_oe = 0;
    assign uio_out = 0;
    wire [2:0] reg_addr  = uio_in[2:0];
    wire       write_en  = uio_in[3];

    // ---------------- registers -----------------------------------------
    reg [ADDR_WIDTH-1:0] src_addr;
    reg [ADDR_WIDTH-1:0] dest_addr;
    reg [TRANSFER_SIZE-1:0] xfer_size;
    reg [ADDR_WIDTH-1:0] ram_addr;
    reg       start_pulse;
    reg       busy;
    reg       done;
    reg [1:0] error;   // 00 - no error  01 - src address overflow,  10 - dest address overflow

    localparam ADDR_SRC     = 0;
    localparam ADDR_DEST    = 1;
    localparam ADDR_SIZE    = 2;
    localparam ADDR_CONTROL = 3;
    localparam ADDR_STATUS  = 4;
    localparam RAM_ADDR     = 5;
    localparam RAM_WRITE    = 6;
    localparam RAM_READ     = 7;
 
    // edge-detect the write strobe

    reg write_en_d;
    wire write_pulse = write_en & ~write_en_d;

    // ---------------- tiny on-chip demo RAM ------------------------------
    reg [WIDTH_RAM-1:0] mem [0:DEPTH_RAM-1];

    // ---------------- DMA FSM --------------------------------------------
    localparam IDLE      = 2'b00;
    localparam READ_MEM  = 2'b01;
    localparam WRITE_MEM = 2'b10;

    // Internal Registers
    reg [1:0] state;
    reg [ADDR_WIDTH-1:0] cur_src;
    reg [ADDR_WIDTH-1:0] cur_dest;
    reg [TRANSFER_SIZE-1:0] remaining;
    reg [WIDTH_RAM-1:0] read_data;
    reg       mem_read_dbg;
    reg       mem_write_dbg;
    integer j;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            write_en_d    <= 0;
            src_addr      <= 0;
            dest_addr     <= 0;
            xfer_size     <= 0;
            start_pulse   <= 0;
            busy          <= 0;
            done          <= 0;
            state         <= IDLE;
            cur_src       <= 0;
            cur_dest      <= 0;
            remaining     <= 0;
            read_data     <= 0;
            mem_read_dbg  <= 0;
            mem_write_dbg <= 0;
            ram_addr      <= 0;
            error <= 0;
            for(j = 0; j < DEPTH_RAM; j=j+1) begin
             mem[j] <= 0;
            end
         end
        else if (!ena) begin
            // design powered down / not selected: hold state
            write_en_d <= write_en;

        end
        else begin
            write_en_d  <= write_en;
            start_pulse <= 0;
            mem_read_dbg  <= 0;
            mem_write_dbg <= 0;

            // ---- register writes (only while IDLE, so a transfer's
            //      parameters can't be changed out from under it) ----

            if (write_pulse && state == IDLE) begin
                case (reg_addr)
                    ADDR_SRC:  src_addr  <= ui_in[ADDR_WIDTH-1:0];
                    ADDR_DEST: dest_addr <= ui_in[ADDR_WIDTH-1:0];
                    ADDR_SIZE: xfer_size <= ui_in[TRANSFER_SIZE-1:0];
                    ADDR_CONTROL: if (ui_in[0]) start_pulse <= 1;
                    RAM_ADDR: ram_addr <= ui_in[ADDR_WIDTH-1:0];
                    RAM_WRITE: mem[ram_addr] <= ui_in;
                    default: ; // STATUS is read-only
                endcase
            end
         
            // ---- DMA FSM ----
            case (state)
                IDLE: begin
                    if (start_pulse && xfer_size != 0) begin
                        if(src_addr + xfer_size >= DEPTH_RAM) begin
               		       error <= 2'b01;
	      		           state <= IDLE;
              		        busy <= 0;
            	        end
            	        else if(dest_addr + xfer_size >= DEPTH_RAM) begin
	       		            error <= 2'b10;
               		        state <= IDLE;
               		        busy <= 0;
            	        end
            	        else begin
                        cur_src   <= src_addr;
                        cur_dest  <= dest_addr;
                        remaining <= xfer_size;
                        busy      <= 1;
                        done      <= 0;
                        state     <= READ_MEM;
                       end
                    end
                end

                READ_MEM: begin
                      read_data    <= mem[cur_src];
                      mem_read_dbg <= 1;
                      state        <= WRITE_MEM;
                end

                WRITE_MEM: begin
                    mem[cur_dest] <= read_data;
                    mem_write_dbg <= 1;
                    cur_src       <= cur_src  + 1;
                    cur_dest      <= cur_dest + 1;
                    remaining     <= remaining - 1;

                    if (remaining == 1) begin
                        state <= IDLE;
                        busy  <= 0;
                        done  <= 1;
                        error <= 2'b00;
                    end 
                    else begin
                        state <= READ_MEM;
                    end
                end

                default: state <= IDLE;
            endcase
        end
    end

    // ---------------- register read-back (uo_out) ------------------------
    // CHanges to be made --> Expose current src, dest, remaining

    reg [WIDTH_RAM-1:0] rdata;
    always @(*) begin
        case (reg_addr)
            ADDR_SRC:     rdata = {{(WIDTH_RAM-ADDR_WIDTH){1'b0}}, cur_src};
            ADDR_DEST:    rdata = {{(WIDTH_RAM-ADDR_WIDTH){1'b0}}, cur_dest};
            ADDR_SIZE:    rdata = {{(WIDTH_RAM-TRANSFER_SIZE){1'b0}}, remaining};
            ADDR_CONTROL: rdata = 0;
            ADDR_STATUS:  rdata = {mem_write_dbg, mem_read_dbg, state, busy, done, error};
            RAM_ADDR:     rdata = {{(WIDTH_RAM-ADDR_WIDTH){1'b0}}, ram_addr};
            RAM_READ:    rdata = mem[ram_addr];
            default:      rdata = 0;
        endcase
    end
    assign uo_out = (!rst_n)? {WIDTH_RAM{1'b0}}:rdata;
 
    // ---------------- lint: tie off truly unused bits ---------------------
    wire _unused = &{uio_in[7:4], ui_in[7:5], 1'b0};

endmodule

