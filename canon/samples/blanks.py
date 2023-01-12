[
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
]
