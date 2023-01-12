# Attempt to analyze ARM64 asm diffs when voltable annotation were further trusted
# in order to remove LLVM volatile annotations.
[
    # Global skips - adding/removing .Ltmp labels and moving constant assignments
    #
    # ~r~ is a builtin that matches ARM64 register names
    Skip("Ltmp-add", skip=Diff([r".Ltmp[[#]]:"], [])),
    Skip("Ltmp-delete", skip=Diff([], [r".Ltmp[[#]]:"])),
    Skip(
        "mov const",
        skip=Diff(
            [r"	mov	{{~r~}}, #[[#,c:]]"],
            [r"	mov	{{~r~}}, #[[#,c:]]"],
        ),
    ),
    # Combining two ldr into an ldp.
    #
    # [{{}}[[blah
    #
    # is a hack because the FileCheck language doesn't deal with [[[
    # well.  It parses the first [[ as starting a block, but we want a literal [
    # followed by a block.  {{}} is an empty regex.
    #
    # [[#~offset~?,offset:]]
    #
    # ~offset~ is a predefined pattern to recognize ", #123" and extract the 123.
    # The ? is a normal regex postfix ? operator, and in this case we are able
    # to get the value zero if the entity is missing.
    #
    # ,offset+size(2):
    #
    # This is an expression that requires a match to be "size(2)" bigger than the
    # match on the previous line.  "size" is a built-in that converts a register
    # name to its size.
    Strategy(
        "load pair",
        patterns=[
            Diff(
                # Alternative form avoid the ~g~ notation but can't use "," because it is the
                # delimiter between pattern and variable name.  Note that the "<<" and "[["
                # forms can't be mixed if there is a numerical check because they return
                # strings vs numbers, respectively.
                # [r"	ldp	[[1:~r~]], [[2:~r~]], [{{}}[[3:~r~]][[#(?:\x2c #%d)?,offset1:]]]"],
                [r"	ldp	[[1:~r~]], [[2:~r~]], [{{}}[[3:~r~]][[#~offset~?,offset:]]]"],
                [
                    r"	ldr	[[1:~r~]], [{{}}[[3:~r~]][[#~offset~?,offset:]]]",
                    r"	ldr	[[2:~r~]], [{{}}[[3:~r~]][[#~offset~?,offset+size(2):]]]",
                ],
            )
        ],
        # This is probably redundant with the global skip and left over from factoring...
        skips=[
            Diff(
                [r"	mov	[[reg:~r~]], #[[#,num:]]"],
                [r"	mov	[[reg:~r~]], #[[#,num:]]"],
            )
        ],
    ),
    Strategy(
        "store pair",
        patterns=[
            Diff(
                [r"	stp	[[1:~r~]], [[2:~r~]], [{{}}[[3:~r~]][[#~offset~?,offset:]]]"],
                [
                    r"	str	[[1:~r~]], [{{}}[[3:~r~]][[#~offset~?,offset:]]]",
                    r"	str	[[2:~r~]], [{{}}[[3:~r~]][[#~offset~?,offset+size(2):]]]",
                ],
            )
        ],
    ),
    # This is the same as the others, but the "str" with the larger offset occurs first.
    Strategy(
        "store pair (reverse)",
        patterns=[
            Diff(
                [r"	stp	[[1:~r~]], [[2:~r~]], [{{}}[[3:~r~]][[#~offset~?,offset:]]]"],
                [
                    r"	str	[[2:~r~]], [{{}}[[3:~r~]][[#~offset~?,offset+size(2):]]]",
                    r"	str	[[1:~r~]], [{{}}[[3:~r~]][[#~offset~?,offset:]]]",
                ],
            )
        ],
    ),
    # Storing two zeroes at the same time using a q register instead of two "str"s.
    Strategy(
        "store q zero",
        patterns=[
            Diff(
                [
                    r"	movi	v[[#,rd:]].2d, #0000000000000000",
                ],
                [],
            ),
            Gap(Range(1, 2)),
            Diff(
                [
                    r"	str	q[[#,rd:]], [{{~r~}}, {{~r~}}]",
                ],
                [
                    r"	add	[[rb:~r~]], {{~r~}}, {{~r~}}",
                    r"	str	xzr, [{{}}[[rb:~r~]]]",
                    r"	str	xzr, [{{}}[[rb:~r~]], #8]",
                ],
            ),
        ],
    ),
    # Moving a constant assignment earlier
    Strategy(
        "const up",
        patterns=[
            Diff(
                [r"	mov	{{~r~}}, #[[#,c:]]"],
                [],
            ),
            Gap(Range(1, 10)),
            Diff(
                [],
                [r"	mov	{{~r~}}, #[[#,c:]]"],
            ),
        ],
    ),
    # Moving a constant assignment later
    Strategy(
        "const down",
        patterns=[
            Diff(
                [],
                [r"	mov	{{~r~}}, #[[#,c:]]"],
            ),
            Gap(Range(1, 10)),
            Diff(
                [r"	mov	{{~r~}}, #[[#,c:]]"],
                [],
            ),
        ],
    ),
    # Same but with movk
    Strategy(
        "const k up",
        patterns=[
            Diff(
                [r"	movk	{{~r~}}, #[[#,c:]], lsl #[[#,s:]]"],
                [],
            ),
            Gap(Range(1, 10)),
            Diff(
                [],
                [r"	movk	{{~r~}}, #[[#,c:]], lsl #[[#,s:]]"],
            ),
        ],
    ),
    Strategy(
        "const k down",
        patterns=[
            Diff(
                [],
                [r"	movk	{{~r~}}, #[[#,c:]], lsl #[[#,s:]]"],
            ),
            Gap(Range(1, 10)),
            Diff(
                [r"	movk	{{~r~}}, #[[#,c:]], lsl #[[#,s:]]"],
                [],
            ),
        ],
    ),
]
