//======================================================================
//
// timer.v
// --------
// Top level wrapper for the timer core.
//
//
// Author: Joachim Strombergson
// Copyright (C) 2022 - Tillitis AB
// SPDX-License-Identifier: GPL-2.0-only
//
//======================================================================

`default_nettype none

module timer(
             input wire           clk,
             input wire           reset_n,

             input wire           cs,
             input wire           we,

             input wire  [7 : 0]  address,
             input wire  [31 : 0] write_data,
             output wire [31 : 0] read_data,
	     output wire          ready
             );


  //----------------------------------------------------------------
  // Internal constant and parameter definitions.
  //----------------------------------------------------------------
  localparam ADDR_NAME0        = 8'h00;
  localparam ADDR_NAME1        = 8'h01;
  localparam ADDR_VERSION      = 8'h02;

  localparam ADDR_CTRL         = 8'h08;
  localparam CTRL_START_BIT    = 0;
  localparam CTRL_STOP_BIT     = 1;

  localparam ADDR_STATUS       = 8'h09;
  localparam STATUS_READY_BIT  = 0;

  localparam ADDR_PRESCALER    = 8'h0a;
  localparam ADDR_TIMER        = 8'h0b;

  localparam CORE_NAME0        = 32'h74696d65; // "time"
  localparam CORE_NAME1        = 32'h72202020; // "r   "
  localparam CORE_VERSION      = 32'h00000003;


  //----------------------------------------------------------------
  // Registers including update variables and write enable.
  //----------------------------------------------------------------
  reg [31 : 0] prescaler_reg;
  reg          prescaler_we;

  reg [31 : 0] timer_reg;
  reg          timer_we;

  reg          start_reg;
  reg          start_new;

  reg          stop_reg;
  reg          stop_new;


  //----------------------------------------------------------------
  // Wires.
  //----------------------------------------------------------------
  reg [31 : 0]  tmp_read_data;
  reg           tmp_ready;

  wire          core_ready;
  wire [31 : 0] core_curr_timer;


  //----------------------------------------------------------------
  // Concurrent connectivity for ports etc.
  //----------------------------------------------------------------
  assign read_data = tmp_read_data;
  assign ready = tmp_ready;


  //----------------------------------------------------------------
  // core instantiation.
  //----------------------------------------------------------------
  timer_core core(
                  .clk(clk),
                  .reset_n(reset_n),
                  .prescaler_value(prescaler_reg),
                  .timer_value(timer_reg),
                  .start(start_reg),
                  .stop(stop_reg),
		  .curr_timer(core_curr_timer),
                  .ready(core_ready)
                 );


  //----------------------------------------------------------------
  // reg_update
  //----------------------------------------------------------------
  always @ (posedge clk)
    begin : reg_update
      if (!reset_n) begin
	start_reg     <= 1'h0;
	stop_reg      <= 1'h0;
	prescaler_reg <= 32'h0;
	timer_reg     <= 32'h0;
      end

      else begin
	start_reg <= start_new;
	stop_reg  <= stop_new;

	if (prescaler_we) begin
	  prescaler_reg <= write_data;
	end

	if (timer_we) begin
	  timer_reg <= write_data;
	end
      end
    end // reg_update


  //----------------------------------------------------------------
  // api
  //
  // The interface command decoding logic.
  //----------------------------------------------------------------
  always @*
    begin : api
      start_new     = 1'h0;
      stop_new      = 1'h0;
      prescaler_we  = 1'h0;
      timer_we      = 1'h0;
      tmp_read_data = 32'h0;
      tmp_ready     = 1'h0;

      if (cs) begin
	tmp_ready = 1'h1;

        if (we) begin
          if (address == ADDR_CTRL) begin
            start_new = write_data[CTRL_START_BIT];
            stop_new  = write_data[CTRL_STOP_BIT];
	  end

	  if (core_ready) begin
            if (address == ADDR_PRESCALER) begin
	      prescaler_we = 1'h1;
	    end

            if (address == ADDR_TIMER) begin
	      timer_we = 1'h1;
	    end
	  end
        end

        else begin
	  if (address == ADDR_NAME0) begin
	    tmp_read_data = CORE_NAME0;
          end

	  if (address == ADDR_NAME1) begin
	    tmp_read_data = CORE_NAME1;
	  end

	  if (address == ADDR_VERSION) begin
	    tmp_read_data = CORE_VERSION;
	  end

	  if (address == ADDR_STATUS) begin
	    tmp_read_data = {31'h0, core_ready};
	  end

	  if (address == ADDR_PRESCALER) begin
	    tmp_read_data = prescaler_reg;
	  end

	  if (address == ADDR_TIMER) begin
	    tmp_read_data = core_curr_timer;
	  end
        end
      end
    end // addr_decoder
endmodule // timer

//======================================================================
// EOF timer.v
//======================================================================
