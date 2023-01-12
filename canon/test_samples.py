# Use the samples to provide some (almost) end-to-end testing.
# It's "almost" because it isn't doing most of the file-level processing.

import builtins
import canon_base
import canon
import unittest


class MockConfig:
    def __init__(self):
        self.debug = False
        self.debug_patterns = None
        self.indent_value = ""

    def print(self, msg, *args, always=False):
        if always or self.debug:
            if args:
                builtins.print(self.indent_value + msg.format(*args))
            else:
                builtins.print(self.indent_value + "{}".format(msg))

    def indent(self, msg=None, *args, always=False):
        if msg:
            self.print(msg, *args, always=always)
        return canon_base.ConfigBase.Indent(self)


class TestSamples(unittest.TestCase):
    def test_basic(self):
        base_lines = [
            "1",
            "diff-1-A",
            "2",
            "diff-2-A",
            "3",
        ]

        diff_lines = [
            "1",
            "diff-1-B",
            "2",
            "diff-2-B",
            "3",
        ]

        diff1 = canon.DiffCommand(canon.Range(1), canon.Range(1))
        diff2 = canon.DiffCommand(canon.Range(3), canon.Range(3))
        diff_commands = [diff1, diff2]

        strategies = [
            canon.Strategy(
                name="diff-1", patterns=[canon.Diff([r"diff-1-B"], [r"diff-1-A"])]
            )
        ]

        test_difftool = canon.DiffTool()
        test_difftool.config = MockConfig()

        stats = canon.Stats("basic")
        context = canon.DiffTool.MatchContext(
            stats=stats,
            base_file_lines=base_lines,
            diff_file_lines=diff_lines,
            commands=diff_commands,
            strategies=[canon.compile_strategy(s, global_skips=[]) for s in strategies],
            skips=[],
        )
        filtered_diff_commands = test_difftool.filter_diff(context)
        self.assertEqual(filtered_diff_commands, [diff2])

    def test_ntum(self):
        with open("test_data/ntum-base.ll", "r") as f:
            base_lines = f.readlines()
        with open("test_data/ntum-diff.ll", "r") as f:
            diff_lines = f.readlines()

        # automate this... (this is where the main tool calls 'diff')
        diff_commands = [
            canon.DiffCommand(canon.Range(x), canon.Range(x)) for x in range(1, 12, 2)
        ]
        skips, strategies = canon.load_strategy_files(
            ["samples/ntum.py"], is_debug_patterns=False
        )

        test_difftool = canon.DiffTool()
        test_difftool.config = MockConfig()

        stats = canon.Stats("ntum")
        context = canon.DiffTool.MatchContext(
            stats=stats,
            base_file_lines=base_lines,
            diff_file_lines=diff_lines,
            commands=diff_commands,
            strategies=strategies,
            skips=skips,
        )
        filtered_diff_commands = test_difftool.filter_diff(context)
        self.assertEqual(
            filtered_diff_commands,
            [diff_commands[0], diff_commands[2], diff_commands[4]],
        )

    def test_voltable(self):
        with open("test_data/voltable-base.ll", "r") as f:
            base_lines = f.readlines()
        with open("test_data/voltable-diff.ll", "r") as f:
            diff_lines = f.readlines()

        # automate this... (this is where the main tool calls 'diff')
        diff_commands = [
            canon.DiffCommand(canon.Range(1), canon.Range(1)),
            canon.DiffCommand(canon.Range(3), canon.Range(3, 3)),
            canon.DiffCommand(canon.Range(16, 16), canon.Range(15)),
            canon.DiffCommand(canon.Range(17), canon.Range(17, 17)),
            canon.DiffCommand(canon.Range(23, 23), canon.Range(22)),
            canon.DiffCommand(canon.Range(24), canon.Range(24, 26)),
            canon.DiffCommand(canon.Range(26), canon.Range(27, 29)),
        ]
        skips, strategies = canon.load_strategy_files(
            ["samples/voltable.py"], is_debug_patterns=False
        )

        test_difftool = canon.DiffTool()
        test_difftool.config = MockConfig()

        stats = canon.Stats("voltable")
        context = canon.DiffTool.MatchContext(
            stats=stats,
            base_file_lines=base_lines,
            diff_file_lines=diff_lines,
            commands=diff_commands,
            strategies=strategies,
            skips=skips,
        )
        filtered_diff_commands = test_difftool.filter_diff(context)
        self.assertEqual(
            filtered_diff_commands,
            [diff_commands[0], diff_commands[1], diff_commands[2], diff_commands[5]],
        )


if __name__ == "__main__":
    unittest.main()
