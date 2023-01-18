# Strategies used to analyze the JIT diffs at the X64 assembly code level
[
    # Always skip any added comment lines
    Skip(
        "add comment",
        skip=Diff(
            ["{{\s*;.*}}"],
            [],
        ),
    ),

    # Always skip any removed comment lines
    Skip(
        "remove comment",
        skip=Diff(
            [],
            ["{{\s*;.*}}"],
        ),
    ),

    # Strategy to ignore any added blank lines
    Strategy(
        "add blank",
        patterns=[
            Diff(
                [r""],
                [],
            )
        ],
    ),
    # Strategy to ignore any removed blank lines
    Strategy(
        "remove blank",
        patterns=[
            Diff(
                [],
                [r""],
            )
        ],
    ),

    # Strategy to ignore any added IG extend lines
    Strategy(
        "add extend",
        patterns=[
            Diff(
                ["G_{{.*}}:        ; {{.*}} extend"],
                [],
            )
        ],
    ),
    # Strategy to ignore any removed IG extend lines
    Strategy(
        "remove extend",
        patterns=[
            Diff(
                [],
                ["G_{{.*}}:        ; {{.*}} extend"],
            )
        ],
    ),

    # Strategy to ignore rsp adjustment
    Strategy(
        "rsp adjustment",
        patterns=[
            Diff(
                [r"       [[op:(add|sub)]]      rsp, {{\d+}}"],
                [r"       [[op:(add|sub)]]      rsp, {{\d+}}"]
            )
        ],
    ),

    Strategy(
        "static-inc",
        patterns=[
            Diff(
                [
                    r"       mov      [[r1:~xr~]], dword ptr [(reloc)]{{\s+}}; static handle",
                    r"       inc      [[r1:~xr~]]",
                    r"       mov      dword ptr [rbp-[[#%x,x:]]H], [[r1:~xr~]]",
                ],
                []
            ),
            Gap(Range(3,5)),
            Diff(
                [
                    r"       mov      [[r2:~xr~]], dword ptr [rbp-[[#%x,x:]]H]",
                    r"       mov      dword ptr [(reloc)], [[r2:~xr~]]"
                ],
                [
                    r"       inc      dword ptr [(reloc)]",
                ]
            ),
        ],
    ),

    Strategy(
        "jmp/jcc-widen",
        patterns=[
            Diff(
                [r"       [[j:(?:jmp|je )]]      G_M[[#,m:]]_IG[[#,ig:]]"],
                [r"       [[j:(?:jmp|je )]]      SHORT G_M[[#,m:]]_IG[[#,ig:]]"]
            )
        ]
    ),

    Strategy(
        "static-xmm",
        patterns=[
            Diff(
                [
                    r"       vmovapd  xmmword ptr [rbp-[[#%x,x:]]H], xmm0",
                ],
                []
            ),
            Gap(Range(1)),
            Diff(
                [
                    r"       mov      edx, 3",
                    r"       call     CORINFO_HELP_GETSHARED_NONGCSTATIC_BASE",
                    r"       mov      rcx, 0xD1FFAB1E      ; box for <unknown class>:<unknown field>",
                ],
                []
            ),
            Gap(Range(2)),
            Diff(
                [
                    r"       vmovapd  xmm0, xmmword ptr [rbp-[[#%x,x:]]H]",
                ],
                []
            ),
            Gap(Range(1)),
            Diff(
                [],
                [
                    r"       mov      rcx, 0xD1FFAB1E",
                    r"       ; gcrRegs -[rcx]",
                    r"       mov      edx, 3",
                    r"       call     CORINFO_HELP_GETSHARED_NONGCSTATIC_BASE",
                ]
            ),
        ],
    ),

    Strategy(
        "static-ymm",
        patterns=[
            Diff(
                [
                    r"       vmovupd  ymmword ptr[rbp-[[#%x,x:]]H], ymm0",
                ],
                []
            ),
            Gap(Range(1)),
            Diff(
                [
                    r"       mov      edx, 3",
                    r"       call     CORINFO_HELP_GETSHARED_NONGCSTATIC_BASE",
                    r"       mov      rcx, 0xD1FFAB1E      ; box for <unknown class>:<unknown field>",
                ],
                []
            ),
            Gap(Range(2)),
            Diff(
                [
                    r"       vmovupd  ymm0, ymmword ptr[rbp-[[#%x,x:]]H]",
                ],
                []
            ),
            Gap(Range(1)),
            Diff(
                [],
                [
                    r"       mov      rcx, 0xD1FFAB1E",
                    r"       ; gcrRegs -[rcx]",
                    r"       mov      edx, 3",
                    r"       call     CORINFO_HELP_GETSHARED_NONGCSTATIC_BASE",
                ]
            ),
        ],
    ),

    Strategy(
        "static-rax-gc",
        patterns=[
            Diff(
                [],
                [
                    r"       mov      edx, 3",
                    r"       call     CORINFO_HELP_GETSHARED_NONGCSTATIC_BASE",
                    r"       mov      rcx, 0xD1FFAB1E      ; <unknown class>",
                ]
            ),
            Gap(Range(3)),
            Diff(
                [
                    r"       mov      gword ptr [rbp-[[#%x,x:]]H], rax",
                ],
                []
            ),
            Gap(Range(1)),
            Diff(
                [
                    r"       mov      edx, 3",
                    r"       call     CORINFO_HELP_GETSHARED_NONGCSTATIC_BASE",
                ],
                [
                    r"       mov      rdx, rax"
                ]
            ),
            Gap(Range(1)),
            Diff(
                [
                    r"       mov      rdx, gword ptr [rbp-[[#%x,x:]]H]",
                    r"       ; gcrRegs +[rdx]",
                    r"       mov      rcx, 0xD1FFAB1E      ; data for <unknown class>:<unknown field>",
                ],
                [],
            ),
        ],
    ),

    Strategy(
        "static-spill",
        patterns=[
            Diff(
                [
                    r"       mov      qword ptr [rbp-20H], rax",
                ],
                [],
            ),
            Gap(Range(5)),
            Diff(
                [
                    r"       mov      rcx, gword ptr [rbp-18H]",
                    r"       ; gcrRegs +[rcx]",
                    r"       mov      gword ptr [rbp-20H], rcx",
                ],
                [],
            ),
        ],
    ),

    Strategy(
        "static-ld-st",
        patterns=[
            Diff(
                [
                    r"       mov      [[regD:~xr~]], dword ptr [(reloc)]      ; static handle",
                ],
                [],
            ),
            Gap(Range(4)),
            Diff(
                [
                    r"       mov      dword ptr [(reloc)], [[regD:~xr~]]",
                ],
                [
                    r"       mov      [[regB:~xr~]], dword ptr [(reloc)]      ; static handle",
                    r"       mov      dword ptr [(reloc)], [[regB:~xr~]]",
                ],
            ),
        ],
    ),

    Strategy(
        "static-add",
        patterns=[
            Diff(
                [
                    r"       mov      [[reg:~xr~]], dword ptr [(reloc)]      ; static handle",
                    r"       add      [[reg:~xr~]], [[#,amt:]]",
                ],
                []
            ),
            Gap(Range(4)),
            Diff(
                [
                    r"       mov      dword ptr [(reloc)], [[reg:~xr~]]",
                ],
                [
                    r"       add      dword ptr [(reloc)], [[#,amt:]]      ; data for <unknown class>:<unknown field>",
                ],
            ),
        ],
    ),

    Strategy(
        "static-inc",
        patterns=[
            Diff(
                [
                    r"       mov      [[reg:~xr~]], dword ptr [(reloc)]      ; static handle",
                    r"       inc      [[reg:~xr~]]",
                ],
                []
            ),
            Gap(Range(4)),
            Diff(
                [
                    r"       mov      dword ptr [(reloc)], [[reg:~xr~]]",
                ],
                [
                    r"       inc      dword ptr [(reloc)]",
                ],
            ),
        ],
    ),
]
