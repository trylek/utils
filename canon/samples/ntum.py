# Strategies used to analyze the post-translation LLVM code when seemingly irrelevant
# changes to ntum caused SQLPAL crashes.
#
# These eventually hid enough noise that an MSVC inlining change due to new code
# elsewhere in the source file was discovered.  (though, sadly for this example,
# that diff didn't matter)
[
    # (overly general) Addition of a different constant (RIP-relative address) (into anything)
    Strategy(
        "rip const",
        patterns=[
            Diff(
                [r"  [[dst:~O~]] = add i64 [[src:~O~]], [[#]]{{~g~?}}"],
                [r"  [[dst:~O~]] = add i64 [[src:~O~]], [[#]]{{~g~?}}"],
            )
        ],
    ),
    # Same (but with nsw) - now could probably be combined with the above pattern
    # by using something like {{(?: nsw)?}}
    Strategy(
        "rip const nsw",
        patterns=[
            Diff(
                [r"  [[dst:~O~]] = add nsw i64 [[src:~O~]], [[#]]{{~g~?}}"],
                [r"  [[dst:~O~]] = add nsw i64 [[src:~O~]], [[#]]{{~g~?}}"],
            )
        ],
    ),
    Strategy(
        "rip const nuw nsw",
        patterns=[
            Diff(
                [r"  [[dst:~O~]] = add nuw nsw i64 [[src:~O~]], [[#]]{{~g~?}}"],
                [r"  [[dst:~O~]] = add nuw nsw i64 [[src:~O~]], [[#]]{{~g~?}}"],
            )
        ],
    ),
    # Selecting different constants (RIP-relative addresses)
    Strategy(
        "ZF",
        patterns=[
            Diff(
                [
                    r"  [[dst:~O~]] = select i1 [[src:~O~]], i64 [[#]], i64 [[#]]{{~g~?}}"
                ],
                [
                    r"  [[dst:~O~]] = select i1 [[src:~O~]], i64 [[#]], i64 [[#]]{{~g~?}}"
                ],
            )
        ],
    ),
    # Changing calls to function names that include RVAs
    Strategy(
        "call 0x",
        patterns=[
            Diff(
                [
                    r"  [[1:.+]][[c:~C~]] sapphire_cc { SphCCRegs } @[[2:.+]]_0x[[#%x,x1:]]([[3:.+]]"
                ],
                [
                    r"  [[1:.+]][[c:~C~]] sapphire_cc { SphCCRegs } @[[2:.+]]_0x[[#%x,x2:]]([[3:.+]]"
                ],
            )
        ],
    ),
    # Similar except one function has a _0x suffix and the other doesn't
    Strategy(
        "call 0x add",
        patterns=[
            Diff(
                [
                    r"  [[1:.+]][[c:~C~]] sapphire_cc { SphCCRegs } @[[2:.+]]_0x[[#%x,x:]]([[3:.+]]"
                ],
                [r"  [[1:.+]][[c:~C~]] sapphire_cc { SphCCRegs } @[[2:.+]]([[3:.+]]"],
            )
        ],
    ),
    Strategy(
        "call 0x remove",
        patterns=[
            Diff(
                [r"  [[1:.+]][[c:~C~]] sapphire_cc { SphCCRegs } @[[2:.+]]([[3:.+]]"],
                [
                    r"  [[1:.+]][[c:~C~]] sapphire_cc { SphCCRegs } @[[2:.+]]_0x[[#%x,x:]]([[3:.+]]"
                ],
            )
        ],
    ),
    # A function that included a changing offset in its parameter list
    Strategy(
        "call NtReport",
        patterns=[
            Diff(
                [
                    r"  [[1:.+]][[c:~C~]] sapphire_cc { SphCCRegs } @G_NtReportUnimplementedEx({{.*}}"
                ],
                [
                    r"  [[1:.+]][[c:~C~]] sapphire_cc { SphCCRegs } @G_NtReportUnimplementedEx({{.*}}"
                ],
            )
        ],
    ),
]
