# Incomplete set of tests for various functions in the canon tools.

import canon
import itertools
import unittest


class TestPatternCompiler(unittest.TestCase):
    def test_re_shortcuts(self):
        tests = [
            ("abc", "abc", False),
            ("a~C~b", "a(?P<ggg>call|invoke)b", True),
            ("~C~b", "(?P<ggg>call|invoke)b", True),
            ("a~C~", "a(?P<ggg>call|invoke)", True),
            ("a~C~b~C~c", "a(?P<ggg>call|invoke)b(?P<ggg>call|invoke)c", True),
            ("a~~b", "a~b", False),
            ("a~~~C~b", "a~(?P<ggg>call|invoke)b", True),
            ("a~g~b", "a(?:, !dbg !(?P<ggg>\d+))b", True),
        ]

        for index, test in enumerate(tests):
            with self.subTest(i=index):
                self.assertEqual(
                    canon.apply_re_shortcuts(test[0], group_name="ggg"),
                    (test[1], test[2]),
                )

    def test_re_shortcuts_fail(self):
        tests = [
            "~",
            "~~~",
            "~C~~",
            "~unknown~",
        ]

        for index, test in enumerate(tests):
            with self.subTest(i=index):
                with self.assertRaises(ValueError):
                    canon.apply_re_shortcuts(test, group_name="ggg")

    # Helper for testing compile_line
    #
    # pattern - pattern to test
    # debug_patterns - whether or not debug mode of compile_line should be tested
    # expected_labels - dict of label names to the list of locations in the pattern
    #                   where that label should be found
    # test_cases - list of tuples of string candidates and expected results
    #              result is None if it shouldn't match
    #              otherwise it is a tuple of the number of groups expected to match
    #                  (will be more in debug mode)
    #                  and the value(s) expected for each label
    #
    # A label may appear in more than one place, and the RE isn't expected to handle that.
    def _test_pattern(self, pattern, debug_patterns, expected_labels, test_cases):
        re, labels, converters, default_values = canon.compile_line(
            pattern, debug_patterns
        )
        self.assertEqual(len(labels), len(expected_labels))
        self.assertDictEqual(labels, expected_labels)

        for index, (test_string, expected_groups) in enumerate(test_cases):
            with self.subTest(i=index):
                match = re.match(test_string)
                self.assertEqual(match is None, expected_groups is None)
                if expected_groups is not None:
                    expected_num_groups, expected_group_values = expected_groups
                    indexed_groups = list(match.groups())
                    dict_groups = match.groupdict()
                    for group_name, default_value in default_values.items():
                        if dict_groups.get(group_name) is None:
                            dict_groups[group_name] = default_value

                    self.assertEqual(
                        sum(1 for _ in filter(bool, indexed_groups)),
                        expected_num_groups,
                    )
                    for (
                        expected_label,
                        expected_values,
                    ) in expected_group_values.items():
                        self.assertIn(expected_label, labels)
                        values = []
                        for group_name in labels[expected_label]:
                            value = dict_groups[group_name]
                            converter = converters.get(group_name)
                            if converter:
                                converter_function, plus_value = converter
                                if value:
                                    value = converter_function(value)
                                else:
                                    value = 0
                                if type(plus_value) is int:
                                    to_subtract = plus_value
                                else:
                                    assert type(plus_value) is str
                                    to_subtract = canon.get_arm_register_size(
                                        dict_groups[labels[plus_value][0]]
                                    )
                                value -= to_subtract
                            values.append(value)
                        if type(expected_values) is not list:
                            expected_values = [expected_values]
                        self.assertEqual(values, expected_values)

    def test_compile_line_literal(self):
        self._test_pattern(
            "abc",
            False,
            {},
            [
                ("abc", (0, {})),
                ("ab", None),
            ],
        )

    def test_compile_line_literal_d(self):
        self._test_pattern(
            "abc",
            True,
            {},
            [
                ("abc", (0, {})),
                ("ab", None),
            ],
        )

    def test_compile_line_nocapture(self):
        self._test_pattern(
            "abc[[#]]d",
            False,
            {},
            [
                ("abc1d", (0, {})),
                ("abc1", None),
                ("abc", None),
            ],
        )

    def test_compile_line_nocapture_d(self):
        self._test_pattern(
            "abc[[#]]d",
            True,
            {},
            [
                ("abc1d", (2, {})),
                ("abc1", (1, {})),
                ("cba", None),
                ("abc", (0, {})),
            ],
        )

    def test_compile_line_capture(self):
        self._test_pattern(
            "abc[[#x:]]d",
            False,
            {"x": ["__g_x"]},
            [
                ("abc12d", (1, {"x": 12})),
                ("abc12", None),
                ("abc", None),
            ],
        )

    def test_compile_line_capture_comma(self):
        self._test_pattern(
            "abc[[#,x:]]d",
            False,
            {"x": ["__g_x"]},
            [
                ("abc12d", (1, {"x": 12})),
                ("abc12", None),
                ("abc", None),
            ],
        )

    def test_compile_line_capture_d(self):
        self._test_pattern(
            "abc[[#x:]]d",
            True,
            {"x": ["__g_x"]},
            [
                ("abc12d", (3, {"x": 12})),
                ("abc12", (2, {"x": 12})),
                ("abc", (0, {})),
                ("cba", None),
            ],
        )

    def test_compile_line_several(self):
        self._test_pattern(
            "abc[[#,x:]]d[[#]]e[[#,41:]]f",
            False,
            {"x": ["__g_x"], "41": ["__g__not_id"]},
            [
                ("abc12d34e56f", (2, {"x": 12, "41": 56})),
                ("abc12d34e56", None),
                ("abc12d34e", None),
                ("abc12d34", None),
                ("abc12d", None),
                ("abc12", None),
                ("abc", None),
            ],
        )

    def test_compile_line_several_d(self):
        self._test_pattern(
            "abc[[#,x:]]d[[#]]e[[#,41:]]f",
            True,
            {"x": ["__g_x"], "41": ["__g__not_id"]},
            [
                ("abc12d34e56f", (8, {"x": 12, "41": 56})),
                ("abc12d34e56", (7, {"x": 12, "41": 56})),
                ("abc12d34e", (5, {"x": 12})),
                ("abc12d34", (4, {"x": 12})),
                ("abc12d", (3, {"x": 12})),
                ("abc12", (2, {"x": 12})),
                ("abc", (0, {})),
                ("cba", None),
            ],
        )

    # compile_line is not responsible for doing the checks when a label appears
    # more than once, so for these tests we expect a match with multiple values
    # at the different locations of a label
    def test_compile_line_dup(self):
        self._test_pattern(
            "abc[[#,x:]]d[[#,x:]]e",
            False,
            {"x": ["__g_x", "__g_x_2"]},
            [
                ("abc12d34e", (2, {"x": [12, 34]})),
                ("abc12d12e", (2, {"x": [12, 12]})),
            ],
        )

    def test_compile_line_dup_d(self):
        self._test_pattern(
            "abc[[#,x:]]d[[#,x:]]e",
            True,
            {"x": ["__g_x", "__g_x_2"]},
            [
                ("abc12d34e", (6, {"x": [12, 34]})),
                ("abc12d12e", (6, {"x": [12, 12]})),
            ],
        )

    # test the various helper REs.  _test_pattern isn't as targeted at it could be for this,
    # but we already have it.

    def test_re_C(self):
        self._test_pattern(
            "a [[x:~C~]] b [[y:~C~]] c",
            False,
            {"x": ["__g_x"], "y": ["__g_y"]},
            [
                ("a call b invoke c", (2, {"x": "call", "y": "invoke"})),
                ("a call b invok c", None),
            ],
        )

    def test_re_C_d(self):
        self._test_pattern(
            "a [[x:~C~]] b [[y:~C~]] c",
            True,
            {"x": ["__g_x"], "y": ["__g_y"]},
            [
                ("a call b invoke c", (6, {"x": "call", "y": "invoke"})),
                ("a call b invok c", (3, {"x": "call"})),
            ],
        )

    def test_re_N(self):
        self._test_pattern(
            "a [[#,x:]] b [[#,y:]] c",
            False,
            {"x": ["__g_x"], "y": ["__g_y"]},
            [
                ("a 32 b 123 c", (2, {"x": 32, "y": 123})),
                ("a 32 b  c", None),
                ("a  b 12 c", None),
                ("a  b  c", None),
            ],
        )

    def test_re_N_opt(self):
        self._test_pattern(
            "a [[#%d?,x:]] b [[#%d?,y:]] c",
            False,
            {"x": ["__g_x"], "y": ["__g_y"]},
            [
                ("a 32 b 123 c", (2, {"x": 32, "y": 123})),
                ("a 32 b  c", (1, {"x": 32, "y": 0})),
                ("a  b 12 c", (1, {"x": 0, "y": 12})),
                ("a  b  c", (0, {"x": 0, "y": 0})),
                ("a    c", None),
            ],
        )

    def test_re_N_re(self):
        self._test_pattern(
            "a [[#b%dc,x:]] d",
            False,
            {"x": ["__g_x"]},
            [
                ("a b32c d", (1, {"x": 32})),
                ("a bc d", None),
                ("a 12 d", None),
                ("a  d", None),
            ],
        )

    def test_re_h(self):
        self._test_pattern(
            "[[#%x,x:]]",
            False,
            {"x": ["__g_x"]},
            [
                ("123", (1, {"x": 0x123})),
                ("123a1", (1, {"x": 0x123A1})),
                ("123A1", (1, {"x": 0x123A1})),
                ("0x123A1", (1, {"x": 0x123A1})),
                ("0X123a1", (1, {"x": 0x123A1})),
                ("123g1", None),
            ],
        )

    def test_re_O(self):
        self._test_pattern(
            "[[x:~O~]]",
            False,
            {"x": ["__g_x"]},
            [
                ("%rax_in", (1, {"x": "%rax_in"})),
                ("%t17", (1, {"x": "%t17"})),
                # ("17", (1, {"x": "17"})),
                # ("-17", (1, {"x": "-17"})),
                # TODO? ("a %foo.bar b", (1, {"x": "%foo.bar"})),
                ("%foo.bar1", (1, {"x": "%foo.bar1"})),
                ("16x", None),
            ],
        )

    def test_re_r(self):
        self._test_pattern(
            "[[x:~r~]]",
            False,
            {"x": ["__g_x"]},
            [
                ("w12", (1, {"x": "w12"})),
                ("x12", (1, {"x": "x12"})),
                ("r12", (1, {"x": "r12"})),
                ("q12", (1, {"x": "q12"})),
                ("a12", None),
                ("w12x", None),
                ("wzr", (1, {"x": "wzr"})),
                ("xzr", (1, {"x": "xzr"})),
                ("rzr", (1, {"x": "rzr"})),
                ("qzr", (1, {"x": "qzr"})),
                ("azr", None),
                ("17", None),
            ],
        )

    def test_re_g(self):
        self._test_pattern(
            "[[x:~g~?]]",
            False,
            {"x": ["__g_x"]},
            [
                (", !dbg !123", (1, {"x": "123"})),
                ("", (0, {"x": None})),
                ("x", None),
            ],
        )

    def test_re_V(self):
        self._test_pattern(
            "[[x:~V~]]",
            False,
            {"x": ["__g_x"]},
            [
                ("i12", (1, {"x": "i12"})),
                ("float", (1, {"x": "float"})),
                ("double", (1, {"x": "double"})),
                ("x", None),
            ],
        )

    def test_re_brace(self):
        self._test_pattern(
            "a{{b+}}c",
            False,
            {},
            [
                ("abc", (0, {})),
                ("abbbc", (0, {})),
                ("ac", None),
                ("adc", None),
                ("bbc", None),
                ("abbbd", None),
            ],
        )

    def test_re_brace_d(self):
        self._test_pattern(
            "a{{b+}}c",
            True,
            {},
            [
                ("abc", (2, {})),
                ("abbbc", (2, {})),
                ("ac", (0, {})),
                ("adc", (0, {})),
                ("bbc", None),
                ("abbbd", (1, {})),
            ],
        )

    def test_re_brace_square(self):
        self._test_pattern(
            "a{{b}}c[[x:d]]e", False, {"x": ["__g_x"]}, [("abcde", (1, {"x": "d"}))]
        )

    def test_re_any(self):
        self._test_pattern(
            "[[x:.+]]",
            False,
            {"x": ["__g_x"]},
            [
                ("abc", (1, {"x": "abc"})),
                ("abc 123", (1, {"x": "abc 123"})),
                ("", None),
            ],
        )

    def test_re_any_opt(self):
        self._test_pattern(
            "[[x:.*]]",
            False,
            {"x": ["__g_x"]},
            [
                ("abc", (1, {"x": "abc"})),
                ("abc 123", (1, {"x": "abc 123"})),
                ("", (0, {"x": ""})),
            ],
        )

    def test_re_any_opt2(self):
        self._test_pattern(
            "[[x:(?:.+)?]]",
            False,
            {"x": ["__g_x"]},
            [
                ("abc", (1, {"x": "abc"})),
                ("abc 123", (1, {"x": "abc 123"})),
                ("", (0, {"x": ""})),
            ],
        )

    def test_re_bracket_match_incorrect(self):
        self._test_pattern(
            "[[[x:\d]]]",
            False,
            {"[x": ["__g__not_id"]},
            [
                ("5]", (1, {"[x": "5"})),
                ("[5]", None),
            ],
        )

    def test_re_bracket_match_correct(self):
        self._test_pattern(
            "[{{}}[[x:\d]]]",
            False,
            {"x": ["__g_x"]},
            [
                ("[5]", (1, {"x": "5"})),
                ("5]", None),
            ],
        )

    def test_re_expression_plus_k(self):
        self._test_pattern(
            "[[#x+1:]]",
            False,
            {"x": ["__g_x"]},
            [
                ("5", (1, {"x": 4})),
            ],
        )

    def test_re_expression_plus_size(self):
        self._test_pattern(
            "[[r:~r~]] [[#x+size(r):]]",
            False,
            {"r": ["__g_r"], "x": ["__g_x"]},
            [
                ("w12 5", (2, {"r": "w12", "x": 1})),
                ("x12 5", (2, {"r": "x12", "x": -3})),
                ("q12 5", (2, {"r": "q12", "x": -11})),
            ],
        )

    def test_re_legacy(self):
        self._test_pattern(
            "a<<?none:g:dbg>>b",
            False,
            {"dbg": ["__g_dbg"]},
            [
                ("a, !dbg !12b", (1, {"dbg": "12"})),
                ("ab", (0, {"dbg": "none"})),
                ("a, !dbg !12", None),
                (", !dbg !12b", None),
            ],
        )

    def test_re_legacy_d(self):
        self._test_pattern(
            "a<<?none:g:dbg>>b",
            True,
            {"dbg": ["__g_dbg"]},
            [
                ("a, !dbg !12b", (3, {"dbg": "12"})),
                ("ab", (2, {"dbg": "none"})),
                ("a, !dbg !12", (2, {"dbg": "12"})),
                (", !dbg !12b", None),
            ],
        )

    def test_re_no_format(self):
        with self.assertRaises(ValueError):
            canon.compile_line("[[#asdf,VAR:]]", None)

    def test_re_two_formats(self):
        with self.assertRaises(ValueError):
            canon.compile_line("[[#%d %d,VAR:]]", None)

    def test_re_shortcut_unknown(self):
        with self.assertRaises(ValueError):
            canon.compile_line("[[~unknown~]]", None)

    def test_re_nonnumeric_expr(self):
        with self.assertRaises(ValueError):
            canon.compile_line("[[VAR+1:.*]]", None)


class TestDiffParser(unittest.TestCase):
    def help_parse(self, diff_command, diff_start, diff_end, base_start, base_end):
        parsed = canon.parse_diff_command(diff_command)
        expected = canon.DiffCommand(
            canon.Range(diff_start, diff_end), canon.Range(base_start, base_end)
        )

        self.assertEqual(parsed, expected)

        roundtrip = canon.output_diff_command(expected)
        self.assertEqual(roundtrip[-1], "\n")
        self.assertEqual(roundtrip[:-1], diff_command)

    # add/delete reversed to follow diff..base pattern - suggests cleanup
    def test_parse_add_1(self):
        self.help_parse("1d0", 0, 1, 0, 0)

    def test_parse_add_n(self):
        self.help_parse("3,4d1", 2, 4, 1, 1)

    def test_parse_change_1(self):
        self.help_parse("6c3", 5, 6, 2, 3)

    def test_parse_change_n(self):
        self.help_parse("8,9c5,6", 7, 9, 4, 6)

    def test_parse_delete_1(self):
        self.help_parse("10a8", 10, 10, 7, 8)

    def test_parse_delete_n(self):
        self.help_parse("11a10,11", 11, 11, 9, 11)


class TestFuncNameSet(unittest.TestCase):
    class MockConfig(canon.ConfigBase):
        def __init__(self, funcnames):
            self.funcspecs = None
            self.funcnames = funcnames
            self.exclude_funcspecs = None
            self.exclude_funcnames = None

    # list of (
    #     command line arguments to --funcname,
    #     dir -> funcname mapping for those arguments,
    #     test data for calls to keep_func (funcnames part only)
    # )
    test_data = [
        (
            [],
            {},
            [
                ("other", "a", True),
                ("other", "b", True),
            ],
        ),
        (
            ["a", "b"],
            {None: {"a", "b"}},
            [
                ("other", "a", True),
                ("other", "b", True),
                ("other", "d1a", False),
                ("other", "d1b", False),
            ],
        ),
        (
            ["d1:d1a", "d1:d1b"],
            {"d1": {"d1a", "d1b"}},
            [
                ("other", "a", False),
                ("other", "b", False),
                ("other", "d1a", False),
                ("other", "d1b", False),
                ("d1", "a", False),
                ("d1", "b", False),
                ("d1", "d1a", True),
                ("d1", "d1b", True),
            ],
        ),
        (
            ["a", "b", "d1:d1a", "d1:d1b", "d2:d2a", "d2:d2b"],
            {None: {"a", "b"}, "d1": {"d1a", "d1b"}, "d2": {"d2a", "d2b"}},
            [
                ("other", "a", True),
                ("other", "b", True),
                ("other", "d1a", False),
                ("other", "d1b", False),
                ("other", "d2a", False),
                ("other", "d2b", False),
                ("d1", "a", True),
                ("d1", "b", True),
                ("d1", "d1a", True),
                ("d1", "d1b", True),
                ("d1", "d2a", False),
                ("d1", "d2b", False),
                ("d2", "a", True),
                ("d2", "b", True),
                ("d2", "d1a", False),
                ("d2", "d1b", False),
                ("d2", "d2a", True),
                ("d2", "d2b", True),
            ],
        ),
    ]

    def get_test_mapping(self):
        return {None: {"a", "b"}, "d1": {"d1a", "d1b"}, "d2": {"d2a", "d2b"}}

    def test_keep_func_funcnames(self):
        for index, (args, mapping, answers) in enumerate(TestFuncNameSet.test_data):
            with self.subTest(i=index):
                processed = canon.ConfigBase.process_arg_funcnames(args)
                self.assertEqual(processed, mapping)

                config = TestFuncNameSet.MockConfig(mapping)
                for dir_name, funcname, answer in answers:
                    self.assertEqual(config.keep_func(dir_name, funcname), answer)


if __name__ == "__main__":
    unittest.main()
