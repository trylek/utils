# Strategies used to analyze the dll import optimization at the LLVM (post-translation) level
[
    # Replaces calls to S_SbtGlobalDispatchDll with a computation to use a shadow slot
    # and then a call through a variable
    Strategy(
        "optcall",
        patterns=[
            Diff(
                [
                    r"  %[[#,0:]] = load { SphCCRegs } (SphCCRegs)*, { SphCCRegs } (SphCCRegs)** @SbtImportData_[[#]], !dbg ![[#,1:]]",
                    r"  %[[#,2:]] = lshr i64 %RIP.t[[#]], 62, !dbg ![[#,1:]]",
                    r"  %magicUpdate[[#?,3:]] = ptrtoint { SphCCRegs } (SphCCRegs)* %[[#,0:]] to i64, !dbg ![[#,1:]]",
                    r"  %newDepMagic[[#?,4:]] = and i64 %magicUpdate[[#?,3:]], %[[#,2:]], !dbg ![[#,1:]]",
                    r"  %addrVal[[#?]] = add i64 %addrVal[[#?]], %newDepMagic[[#?,4:]], !dbg ![[#,1:]]",
                ],
                [],
            ),
            Gap(Range(8, 30)),
            # This was an attempt to classify the instructions that could appear between the above
            # and below diffs.  After seeing enough of them, and especially that the order could
            # vary, I gave up and accept arbitrary instructions with the above "Gap".
            #
            # Diff(
            #    [r"  %[[#]] = zext i32 [[~O~]] to i64, !dbg ![[#,1:]]"],
            #    [r"  %[[#]] = zext i32 [[~O~]] to i64, !dbg ![[#]]"],
            #    repeat=Range(0,20),
            #    is_filler=True
            # ),
            # Diff(
            #    [r"  %[[#]] = bitcast <[[#]] x [[~V~]]> [[~O~]] to <4 x i32>, !dbg ![[#,1:]]"],
            #    [r"  %[[#]] = bitcast <[[#]] x [[~V~]]> [[~O~]] to <4 x i32>, !dbg ![[#]]"],
            #    repeat=Range(0,5),
            #    is_filler=True
            # ),
            Diff(
                [
                    r"  %[[#]] = [[c:~C~]] sapphire_cc { SphCCRegs } %[[#,0:]](%GuestCtx* [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]])[[`g`?]]",
                ],
                [
                    r"  %[[#]] = [[c:~C~]] sapphire_cc { SphCCRegs } @S_SbtGlobalDispatchDll(%GuestCtx* [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], i64 [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]], <4 x i32> [[~O~]])[[`g`?]]",
                ],
            ),
        ],
    ),
    Strategy(
        "import data def",
        patterns=[
            # An added definition
            Diff(
                [
                    r"@SbtImportData_[[#]] = global { SphCCRegs } (SphCCRegs)* @S_SbtImportFunction_[[#]], align 8"
                ],
                [],
            )
        ],
    ),
    Strategy(
        "import data ref",
        patterns=[
            # An added reference that appears in each code file
            Diff(
                [r"@SbtImportData_[[#]] = external global { SphCCRegs } (SphCCRegs)*"],
                [],
            )
        ],
    ),
    Strategy(
        "image base",
        patterns=[
            # An added definition
            Diff(
                [r"@SbtSingletonImageBase = external global i64"],
                [],
            )
        ],
    ),
]
