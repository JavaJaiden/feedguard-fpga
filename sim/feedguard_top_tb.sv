// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module feedguard_top_tb;
reg clk=0, rst=1, in_valid=0, in_last=0, out_ready=0;
reg [7:0] in_data=0;
wire in_ready, out_valid;
wire [2:0] out_kind;
wire [7:0] out_skip, out_take;
wire [32:0] out_expected;
feedguard_top dut(.*);
always #5 clk=~clk;
localparam N=__COUNT__;
reg [51:0] expected [0:N-1];
wire [51:0] result={out_kind,out_skip,out_take,out_expected};
reg [51:0] held;
reg stalled=0, active=0;
integer received=0,sent=0,cycles=0,input_stalls=0,output_stalls=0;
integer fd,rc,reset_flag,n,i;
reg [16383:0] packet;
always @(negedge clk) begin
 cycles=cycles+1;
 out_ready=active && (cycles%193>=150);
end
always @(posedge clk) begin
 if(rst) stalled<=0;
 else begin
  if(stalled && (!out_valid || result!==held)) $fatal(1,"stalled top output changed");
  stalled<=out_valid && !out_ready; held<=result;
  if(in_valid && !in_ready) input_stalls=input_stalls+1;
  if(out_valid && !out_ready) output_stalls=output_stalls+1;
  if(out_valid && out_ready) begin
   if(received>=N || result!==expected[received])
    $fatal(1,"top packet %0d got %h expected %h",received,result,expected[received]);
   received=received+1;
  end
 end
end
task send_byte(input [7:0] value,input last);
 begin
  @(negedge clk); in_valid=1; in_data=value; in_last=last;
  @(posedge clk); while(!in_ready) @(posedge clk);
  @(negedge clk); in_valid=0; in_last=0;
 end
endtask
initial begin
 $readmemh("integrated-expected.txt",expected);
 repeat(4) @(negedge clk); rst=0;
 // Reset must discard a partial header; it must never become a result.
 repeat(7) send_byte(8'hff,0);
 @(negedge clk); rst=1; @(negedge clk); rst=0;
 // Reset must also discard completed metadata waiting in both stages.
 // A valid heartbeat: length 16, all other header fields zero.
 for(i=0;i<16;i=i+1) send_byte(i==0?8'd16:8'd0,i==15);
 repeat(4) @(negedge clk);
 if(!out_valid) $fatal(1,"pre-reset result never arrived");
 rst=1; @(negedge clk); rst=0;
 repeat(4) @(negedge clk);
 if(out_valid) $fatal(1,"reset did not flush pending output");
 active=1;
 fd=$fopen("integrated-input.txt","r"); if(!fd) $fatal(1,"missing input");
 while(!$feof(fd)) begin
  rc=$fscanf(fd,"%d %d %h",reset_flag,n,packet);
  if(rc==3) begin
   if(reset_flag) begin
    while(received!=sent) @(negedge clk);
    @(negedge clk); rst=1; @(negedge clk); rst=0;
   end
   for(i=n-1;i>=0;i=i-1) begin
    send_byte(packet[i*8 +:8],i==0);
    if(i%11==0) repeat(2) @(negedge clk);
   end
   sent=sent+1;
  end
 end
 while(received!=N) @(negedge clk);
 repeat(400) @(negedge clk);
 if(received!=N || sent!=N || !input_stalls || !output_stalls)
  $fatal(1,"missing packets or stall coverage");
 $display("PASS integrated FeedGuard: %0d packets; %0d input / %0d output stall cycles; reset flush",received,input_stalls,output_stalls);
 $finish;
end
initial begin #100000000; $fatal(1,"top watchdog"); end
endmodule
