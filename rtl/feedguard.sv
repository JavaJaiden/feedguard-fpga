// SPDX-License-Identifier: MIT
`default_nettype none
// One byte per accepted clock. Input begins at the OMD-C UDP payload header.
// Only a fully validated packet can produce error==0 commit metadata.
module omdc_envelope #(
    parameter integer MAX_BYTES=1500
) (
    input wire clk, rst,
    input wire in_valid,
    output wire in_ready,
    input wire [7:0] in_data,
    input wire in_last,
    output reg out_valid,
    input wire out_ready,
    output reg [31:0] out_seq,
    output reg [7:0] out_count,
    output reg [63:0] out_timestamp,
    output reg [15:0] out_first_type,
    output reg [3:0] out_error
);
    reg [15:0] pos, size, msg_size, remaining, first_type;
    reg [7:0] count;
    reg [31:0] seq;
    reg [63:0] stamp;
    reg [8:0] completed;
    reg [2:0] phase;
    reg [3:0] errors;
    reg [15:0] n_pos, n_size, n_msg_size, n_remaining, n_first_type;
    reg [7:0] n_count;
    reg [31:0] n_seq;
    reg [63:0] n_stamp;
    reg [8:0] n_completed;
    reg [2:0] n_phase;
    reg [3:0] n_errors, final_errors;
    wire [16:0] length_now = {1'b0, pos}+17'd1;
    assign in_ready = !out_valid || out_ready;
    always @* begin
        n_pos = (pos == 16'hffff) ? pos : pos+1'b1;
        n_size=size; n_msg_size=msg_size; n_remaining=remaining;
        n_first_type=first_type; n_count=count; n_seq=seq; n_stamp=stamp;
        n_completed=completed; n_phase=phase; n_errors=errors;
        if (length_now > MAX_BYTES) n_errors[3]=1;
        case (pos)
            0: n_size[7:0]=in_data;
            1: n_size[15:8]=in_data;
            2: n_count=in_data;
            3: begin end // Reserved filler is ignored, not treated as a version.
            4: n_seq[7:0]=in_data;
            5: n_seq[15:8]=in_data;
            6: n_seq[23:16]=in_data;
            7: n_seq[31:24]=in_data;
            8: n_stamp[7:0]=in_data;
            9: n_stamp[15:8]=in_data;
            10: n_stamp[23:16]=in_data;
            11: n_stamp[31:24]=in_data;
            12: n_stamp[39:32]=in_data;
            13: n_stamp[47:40]=in_data;
            14: n_stamp[55:48]=in_data;
            15: n_stamp[63:56]=in_data;
            default: begin
                case (phase)
                    0: begin n_msg_size={8'b0,in_data}; n_phase=1; end
                    1: begin
                        n_msg_size[15:8]=in_data;
                        n_phase=2;
                        if ({in_data,msg_size[7:0]} < 16'd4) begin
                            n_errors[2]=1; n_remaining=0;
                        end else n_remaining={in_data,msg_size[7:0]}-16'd4;
                    end
                    2: begin
                        if (completed == 0) n_first_type[7:0]=in_data;
                        n_phase=3;
                    end
                    3: begin
                        if (completed == 0) n_first_type[15:8]=in_data;
                        if (remaining == 0) begin
                            n_phase=0;
                            if (completed != 9'h1ff) n_completed=completed+1'b1;
                            else n_errors[2]=1;
                        end else n_phase=4;
                    end
                    4: begin
                        n_remaining=remaining-1'b1;
                        if (remaining == 1) begin
                            n_phase=0;
                            if (completed != 9'h1ff) n_completed=completed+1'b1;
                            else n_errors[2]=1;
                        end
                    end
                    default: begin n_errors[2]=1; n_phase=0; end
                endcase
            end
        endcase
        final_errors=n_errors;
        if (length_now < 17'd16) final_errors[0]=1;
        if ((length_now >= 2) && ({1'b0,n_size} != length_now)) final_errors[1]=1;
        if ((length_now >= 16) && ((n_phase != 0) || (n_completed != {1'b0,n_count})))
            final_errors[2]=1;
    end
    always @(posedge clk) begin
        if (rst) begin
            pos<=0; size<=0; msg_size<=0; remaining<=0; first_type<=0;
            count<=0; seq<=0; stamp<=0; completed<=0; phase<=0; errors<=0;
            out_valid<=0; out_seq<=0; out_count<=0; out_timestamp<=0;
            out_first_type<=0; out_error<=0;
        end else begin
            if (out_valid && out_ready) out_valid<=0;
            if (in_valid && in_ready) begin
                if (in_last) begin
                    out_valid<=1; out_seq<=n_seq; out_count<=n_count;
                    out_timestamp<=n_stamp; out_first_type<=n_first_type; out_error<=final_errors;
                    pos<=0; size<=0; msg_size<=0; remaining<=0; first_type<=0;
                    count<=0; seq<=0; stamp<=0; completed<=0; phase<=0; errors<=0;
                end else begin
                    pos<=n_pos; size<=n_size; msg_size<=n_msg_size; remaining<=n_remaining;
                    first_type<=n_first_type; count<=n_count; seq<=n_seq; stamp<=n_stamp;
                    completed<=n_completed; phase<=n_phase; errors<=n_errors;
                end
            end
        end
    end
endmodule

// One logical channel; connect redundant lines to the SAME guard after arbitration.
// A gap freezes expected. Buffering, refresh, body decoding and recovery are external.
module sequence_guard (
    input wire clk, rst,
    input wire in_valid,
    output wire in_ready,
    input wire [31:0] in_seq,
    input wire [7:0] in_count,
    input wire in_bad,
    output reg out_valid,
    input wire out_ready,
    output reg [2:0] out_kind,
    output reg [7:0] out_skip, out_take,
    output reg [32:0] out_expected
);
    reg initialized;
    reg [32:0] expected;
    wire [32:0] finish_seq={1'b0,in_seq}+{25'b0,in_count};
    reg [2:0] kind;
    reg [7:0] skip, take;
    reg [32:0] next_expected;
    reg next_initialized;
    assign in_ready=!out_valid || out_ready;
    always @* begin
        kind=6; skip=0; take=0;
        next_expected=expected; next_initialized=initialized;
        if (in_bad) kind=6;
        else if (in_count == 0) kind=5;
        else if ((finish_seq > 33'h100000000) || (initialized && expected == 33'h100000000)) kind=7;
        else if (!initialized) begin
            kind=0; take=in_count; next_expected=finish_seq; next_initialized=1;
        end else if ({1'b0,in_seq} > expected) kind=4;
        else if (finish_seq <= expected) kind=3;
        else if ({1'b0,in_seq} < expected) begin
            kind=2; skip=expected-{1'b0,in_seq}; take=finish_seq-expected; next_expected=finish_seq;
        end else begin kind=1; take=in_count; next_expected=finish_seq; end
    end
    always @(posedge clk) begin
        if (rst) begin
            initialized<=0; expected<=0; out_valid<=0;
            out_kind<=0; out_skip<=0; out_take<=0; out_expected<=0;
        end else begin
            if (out_valid && out_ready) out_valid<=0;
            if (in_valid && in_ready) begin
                initialized<=next_initialized; expected<=next_expected;
                out_valid<=1; out_kind<=kind; out_skip<=skip; out_take<=take; out_expected<=next_expected;
            end
        end
    end
endmodule
`default_nettype wire

`default_nettype none
module feedguard_top (
    input wire clk, rst,
    input wire in_valid,
    output wire in_ready,
    input wire [7:0] in_data,
    input wire in_last,
    output wire out_valid,
    input wire out_ready,
    output wire [2:0] out_kind,
    output wire [7:0] out_skip, out_take,
    output wire [32:0] out_expected
);
    wire env_valid, env_ready;
    wire [31:0] seq;
    wire [7:0] count;
    wire [3:0] errors;
    wire [63:0] unused_stamp;
    wire [15:0] unused_type;
    omdc_envelope envelope (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_ready(in_ready), .in_data(in_data), .in_last(in_last),
        .out_valid(env_valid), .out_ready(env_ready), .out_seq(seq), .out_count(count),
        .out_timestamp(unused_stamp), .out_first_type(unused_type), .out_error(errors)
    );
    sequence_guard guard (
        .clk(clk), .rst(rst), .in_valid(env_valid), .in_ready(env_ready),
        .in_seq(seq), .in_count(count), .in_bad(|errors),
        .out_valid(out_valid), .out_ready(out_ready), .out_kind(out_kind),
        .out_skip(out_skip), .out_take(out_take), .out_expected(out_expected)
    );
endmodule
`default_nettype wire
