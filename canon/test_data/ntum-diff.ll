1 keep
  %RCX.0.v = select i1 %RFLAGS_ZF.t12.not, %somethingD, i64 931597, !dbg !8386
2 discard
  %RCX.0.v = select i1 %RFLAGS_ZF.t12.not, i64 931805, i64 931725, !dbg !8386
3 keep
  %addrVal10 = add i64 %RIP_in, %somethingD, !dbg !42
4 discard
  %addrVal10 = add i64 %RIP_in, 2775684, !dbg !42
5 keep
  %somethingD = invoke sapphire_cc { SphCCRegs } @G_memset(%GuestCtx* %gstCtx_in, i64 %RSP.t1, i64 %RIP.t4, i64 undef, i64 %RCX_in, i64 0, i64 80, i64 %R9_in, i64 %RBX_in, i64 %RDI_in, i64 %RSI_in, i64 %RBP_in, i64 %R10_in, i64 %R11_in, i64 %R12_in, i64 %R13_in, i64 %R14_in, i64 %R15_in, <4 x i32> %XMM0_in, <4 x i32> %XMM1_in, <4 x i32> %XMM2_in, <4 x i32> %XMM3_in, <4 x i32> %XMM4_in, <4 x i32> %XMM5_in, <4 x i32> %XMM6_in, <4 x i32> %XMM7_in, <4 x i32> %XMM8_in, <4 x i32> %XMM9_in, <4 x i32> %XMM10_in, <4 x i32> %XMM11_in, <4 x i32> %XMM12_in, <4 x i32> %XMM13_in, <4 x i32> %XMM14_in, <4 x i32> %XMM15_in)
6 discard
  %9 = musttail call sapphire_cc { SphCCRegs } @G__0x38c1e8(%GuestCtx* %gstCtx_in, i64 %RSP_in, i64 %RIP.t5, i64 %RAX_in, i64 %RCX.t1, i64 %RDX_in, i64 %R8_in, i64 %R9_in, i64 %RBX_in, i64 %RDI_in, i64 %RSI_in, i64 %RBP_in, i64 %R10.t1, i64 %R11_in, i64 %R12_in, i64 %R13_in, i64 %R14_in, i64 %R15_in, <4 x i32> %XMM0_in, <4 x i32> %XMM1_in, <4 x i32> %XMM2_in, <4 x i32> %XMM3_in, <4 x i32> %XMM4_in, <4 x i32> %XMM5_in, <4 x i32> %XMM6_in, <4 x i32> %XMM7_in, <4 x i32> %XMM8_in, <4 x i32> %XMM9_in, <4 x i32> %XMM10_in, <4 x i32> %XMM11_in, <4 x i32> %XMM12_in, <4 x i32> %XMM13_in, <4 x i32> %XMM14_in, <4 x i32> %XMM15_in), !dbg !26148
