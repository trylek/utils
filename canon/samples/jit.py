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
]
