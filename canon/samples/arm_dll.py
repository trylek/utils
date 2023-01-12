# Strategies used to analyze the dll import optimization at the ARM64 assembly code level
[
    Strategy(
        "full call",
        # "Skips" are diffs that should be ignored while trying to find the core pattern
        # of the strategy.  These are scoped to the specific strategy.
        skips=[
            # Adding an .Ltmp123: label
            Diff(
                [
                    r".Ltmp[[#]]:",
                ],
                [],
            ),
            # Removing an .Ltmp123: label
            Diff(
                [],
                [
                    r".Ltmp[[#]]:",
                ],
            ),
            # Moving a str x1, [x2, #-8] instruction.
            # Can be different registers but the -8 is fixed.
            Diff([r"	str	x[[#]], [x[[#]], #-8]!"], [r"	str	x[[#]], [x[[#]], #-8]!"]),
            # Moving an assignment of a constant.
            # Can be a different register but must be the same constant.
            Diff(
                [
                    r"	mov	w[[#,rd:]], #[[#,imm1:]]",
                    r"	movk	w[[#,rd:]], #[[#,imm2:]], lsl #16",
                ],
                [
                    r"	mov	w[[#,rb:]], #[[#,imm1:]]",
                    r"	movk	w[[#,rb:]], #[[#,imm2:]], lsl #16",
                ],
            ),
            # Moving the zeroing of x4
            Diff([r"	mov	x4, xzr"], [r"	mov	x4, xzr"]),
        ],
        # Replacing
        #     ...
        #     add
        #     ...
        #     mov
        #     bl
        #     ...
        # with
        #     adrp
        #     ldr
        #     add
        #     ldr
        #     and
        #     add
        #     ...
        #     blr
        patterns=[
            Diff(
                [
                    r"	adrp	x[[#,16:]], :got:SbtImportData_[[#,r:]]",
                    r"                                        //   fixup A - offset: 0, value: :got:SbtImportData_[[#,r:]], kind: fixup_aarch64_pcrel_adrp_imm21",
                    r"	ldr	x[[#,16:]], [x[[#,16:]], :got_lo12:SbtImportData_[[#,r:]]]",
                    r"                                        //   fixup A - offset: 0, value: :got_lo12:SbtImportData_[[#,r:]], kind: fixup_aarch64_ldst_imm12_scale8",
                    r"	add	x[[#,17:]], x[[#,2:]], #[[#,imm:]]",
                    r"                                        // =[[#,imm:]]",
                    r"	ldr	x[[#,16':]], [x[[#,16:]]]",
                    r"	and	x[[#,18:]], x[[#,16':]], x[[#,17:]], lsr #62",
                    r"	add	x[[#,18:]], x[[#,2:]], x[[#,18:]]",
                ],
                [],
            ),
            Gap(Range(4, 8)),
            Diff(
                [],
                [
                    r"	add	x17, x2, #[[#,imm:]]",
                    r"                                        // =[[#,imm:]]",
                ],
            ),
            Gap(Range(0, 6)),
            Diff(
                [
                    r"	blr	x[[#,16':]]",
                ],
                [
                    r"	mov	x2, x16",
                    r"	bl	S_SbtGlobalDispatchDll",
                    r"                                        //   fixup A - offset: 0, value: S_SbtGlobalDispatchDll, kind: fixup_aarch64_pcrel_call26",
                ],
            ),
        ],
    ),
    Strategy(
        name="cse call",
        # Many of the skips are the same as in the above strategy, so these should
        # probably be global skips...
        skips=[
            Diff(
                [
                    r".Ltmp[[#]]:",
                ],
                [],
            ),
            Diff(
                [],
                [
                    r".Ltmp[[#]]:",
                ],
            ),
            Diff([r"	str	x[[#]], [x[[#]], #-8]!"], [r"	str	x[[#]], [x[[#]], #-8]!"]),
            Diff(
                [
                    r"	mov	w[[#,rd:]], #[[#]]",
                    r"	movk	w[[#,rd:]], #[[#]], lsl #16",
                ],
                [
                    r"	mov	w[[#,rb:]], #[[#]]",
                    r"	movk	w[[#,rb:]], #[[#]], lsl #16",
                ],
            ),
            # Moving a stur instruction (registers are fixed in this example)
            Diff([r"	stur	x3, [x16, #11]"], [r"	stur	x3, [x16, #11]"]),
        ],
        patterns=[
            # Variation on the above pattern where part of the computation
            # was CSEed.
            Diff(
                [
                    r"	ldr	x[[#,16':]], [x[[#,16:]]]",
                    r"	add	x[[#,17:]], x[[#,2:]], #[[#,imm:]]",
                    r"                                        // =[[#,imm:]]",
                    r"	and	x[[#,18:]], x[[#,16':]], x[[#,17:]], lsr #62",
                    r"	add	x[[#,18:]], x[[#,2:]], x[[#,18:]]",
                ],
                [],
            ),
            Gap(Range(4, 8)),
            Diff(
                [],
                [
                    r"	add	x17, x2, #[[#,imm:]]",
                    r"                                        // =[[#,imm:]]",
                ],
            ),
            Gap(Range(0, 6)),
            Diff(
                [
                    r"	blr	x[[#,16':]]",
                ],
                [
                    r"	mov	x2, x16",
                    r"	bl	S_SbtGlobalDispatchDll",
                    r"                                        //   fixup A - offset: 0, value: S_SbtGlobalDispatchDll, kind: fixup_aarch64_pcrel_call26",
                ],
            ),
        ],
    ),
]
