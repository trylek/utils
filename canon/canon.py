import collections
import filecmp
import importlib.util
import itertools
import os
import re
import shutil
import subprocess
import sys

from canon_base import *
from canon_util import *


# Avoid maximum file length problems.  (I don't remember what I was hitting, but
# apparently both Windows and Linux have maximums.)


def shorten_long_filename(file):
    base, ext = os.path.splitext(file)
    do_shorten = len(base) > 245  # guess
    if do_shorten:
        file_to_use = base[:235] + "_h_" + hex(hash_str(base))[2:] + ext
    else:
        file_to_use = file
    return file_to_use


def open_long_filename_to_write(file):
    path, filename = os.path.split(file)
    filename_to_use = shorten_long_filename(filename)
    f = open(os.path.join(path, filename_to_use), "w")
    if filename != filename_to_use:
        f.write("Long filename: " + filename)
    return f


class DiffConfig(ConfigBase):
    def __init__(self, cmd_args):
        super().__init__(cmd_args)

        self.base_dir = cmd_args.base_dir
        self.diff_dir = cmd_args.diff_dir
        self.max_line_length = cmd_args.max_line_length
        self.strategy_filenames = list(itertools.chain(*cmd_args.strategy_filenames))

        self.partition_files = cmd_args.partition_files
        self.compare_base_name = cmd_args.compare_base_name
        self.compare_diff_name = cmd_args.compare_diff_name
        self.diff_limit = cmd_args.diff_limit
        self.file_limit = cmd_args.file_limit
        self.func_limit = cmd_args.func_limit
        self.include_all_blank_lines = cmd_args.include_all_blank_lines
        self.include_debug_info = cmd_args.include_debug_info
        self.include_fntable = cmd_args.include_fntable
        self.include_references = cmd_args.include_references
        self.include_missing = not cmd_args.omit_missing_functions
        self.only_functions = cmd_args.only_functions

        self.debug_patterns = cmd_args.debug_patterns

    def load_strategies(self):
        print("strategy files:", self.strategy_filenames)
        is_debug_patterns = self.debug_patterns is not None
        self.filter_diff_skips, self.filter_diff_strategies = load_strategy_files(
            self.strategy_filenames, is_debug_patterns
        )

        print("skips:", [s.name for s in self.filter_diff_skips])
        print("strategies:", [s.name for s in self.filter_diff_strategies])


class DiffTool:
    def parse_args(args):
        (
            cmd_parser,
            required_group,
            config_group,
            filter_group,
            debug_group,
        ) = get_base_parser()

        required_group.add_argument(
            "-b", "--base-dir", help="Set base directory", required=True
        )
        required_group.add_argument(
            "-d", "--diff-dir", help="Set diff directory", required=True
        )

        config_group.add_argument(
            "-m",
            "--max-line-length",
            metavar="N",
            help="trim lines to maximum N characters - intended for broken diff viewers - may produce spurious diffs if canonicalization changes line length",
            type=int,
            default=8191,
        )
        config_group.add_argument(
            "-s",
            "--strategy",
            metavar="FILE",
            dest="strategy_filenames",
            help="Specify file containing pattern matching strategy/ies",
            nargs="*",
            action="append",
            default=[],
        )
        config_group.add_argument(
            "--partition-files",
            help="Put function files for each input file in separate directories",
            action="store_true",
            default=False,
        )
        config_group.add_argument(
            "--compare-base-name",
            help="Set output compare subdirectory name for base",
            default="base",
        )
        config_group.add_argument(
            "--compare-diff-name",
            help="Set output compare subdirectory name for diff",
            default="diff",
        )
        config_group.add_argument(
            "--include-all-blank-lines",
            help="keep all blank lines in output files",
            action="store_true",
            default=False,
        )
        config_group.add_argument(
            "--include-debug-info",
            help="include debug information in output files",
            action="store_true",
            default=False,
        )
        config_group.add_argument(
            "--include-fntable",
            help="include contents of function table (SbtFnTable)",
            action="store_true",
            default=False,
        )
        config_group.add_argument(
            "--include-references",
            help="include references in output filter",
            action="store_true",
            default=False,
        )
        config_group.add_argument(
            "--omit-missing-functions",
            help="only include functions in both base and diff",
            action="store_true",
            default=False,
        )
        config_group.add_argument(
            "--only-functions",
            help="only include lines in functions",
            action="store_true",
            default=False,
        )

        filter_group.add_argument(
            "--file-limit",
            help="Set approximate maximum number of input files with diffs to report",
            type=int,
            default=0,
        )
        filter_group.add_argument(
            "--func-limit",
            help="Set approximate maximum number of functions with diffs to report",
            type=int,
            default=0,
        )
        filter_group.add_argument(
            "--diff-limit",
            help="Set approximate maximum number of diffs to report",
            type=int,
            default=0,
        )

        debug_group.add_argument(
            "--debug-patterns",
            metavar="N",
            help="dump information about failed RE matches after N tokens (note: was useful for debugging patterns but untested in the current version)",
            type=int,
            default=None,
        )

        cmd_args = cmd_parser.parse_args(args)
        config = DiffConfig(cmd_args)
        config.load_strategies()

        return config

    def main(args):
        #
        # This is still mostly boilerplate despite a round of canon_base factoring.
        #

        config = DiffTool.parse_args(args)
        difftool = DiffTool()
        difftool.config = config
        difftool.stats = Stats("Total")

        difftool.parser = parser_map()[config.kind]()
        difftool.parser.config = config
        if not config.filespecs:
            config.filespecs = [difftool.parser.default_filespec()]

        controller = Controller(config, difftool.stats, difftool.do_canon)
        controller.go()

        # All jobs have been launched and finished (see the 'wait' and the 'with' in
        # Controller.  Now look at the 'extras' -- functions that potentially moved (e.g.,
        # from sqlmin5 to sqlmin6).
        #
        # This is potentially rather inefficient.  It is done sequentially after all other
        # jobs, and all 'extra' file contents are pickled from child process back to the
        # main one.
        difftool.process_extras(controller)

        print(difftool.stats.report(indent=4))

    def do_canon(self, controller):
        base_dir = self.config.base_dir
        diff_dir = self.config.diff_dir

        #
        # Find input files
        #

        rel_dir_dict = {}
        with self.stats.timers[TimeKind.Walk]:
            HasFile.add_dirwalk(
                rel_dir_dict,
                base_dir,
                HasFile.BASE,
                self.config.filespecs,
                self.config.exclude_filespecs,
            )
            HasFile.add_dirwalk(
                rel_dir_dict,
                diff_dir,
                HasFile.DIFF,
                self.config.filespecs,
                self.config.exclude_filespecs,
            )

        #
        # Queue a job to compare each file across base/diff
        #

        for dirpath in sorted(rel_dir_dict.keys()):
            print("Canonicalize directory {} ".format(dirpath))
            inner_dir = os.path.basename(dirpath)

            compare_subdir = os.path.join(self.config.output_dir, dirpath)
            compare_subdir_base = os.path.join(
                compare_subdir, self.config.compare_base_name
            )
            compare_subdir_diff = os.path.join(
                compare_subdir, self.config.compare_diff_name
            )

            file_dict = rel_dir_dict[dirpath]
            for file in sorted(file_dict.keys()):
                has_file = file_dict[file]

                rel_file = os.path.join(dirpath, file)
                base_file = os.path.join(base_dir, rel_file)
                diff_file = os.path.join(diff_dir, rel_file)

                # If a file only exists on one side (and include_missing is set),
                # create an empty file for the other to complete the pair.
                if has_file == HasFile.BASE:
                    with self.stats.timers[TimeKind.Copy]:
                        print(" Only in base: {}".format(rel_file))
                        if self.config.include_missing:
                            os.makedirs(compare_subdir_base, exist_ok=True)
                            os.makedirs(compare_subdir_diff, exist_ok=True)
                            compare_base_file = os.path.join(
                                compare_subdir_base, change_ext(file, ".asm")
                            )
                            shutil.copy(base_file, compare_base_file)
                            create_empty_file(diff_file)
                            has_file == HasFile.BOTH
                elif has_file == HasFile.DIFF:
                    with self.stats.timers[TimeKind.Copy]:
                        print(" Only in diff: {}".format(rel_file))
                        if self.config.include_missing:
                            os.makedirs(compare_subdir_base, exist_ok=True)
                            os.makedirs(compare_subdir_diff, exist_ok=True)
                            compare_diff_file = os.path.join(
                                compare_subdir_diff, change_ext(file, ".asm")
                            )
                            shutil.copy(diff_file, compare_diff_file)
                            create_empty_file(base_file)
                            has_file == HasFile.BOTH

                if has_file == HasFile.BOTH:
                    # Optimization to bypass identical files
                    with self.stats.timers[TimeKind.Compare]:
                        if filecmp.cmp(base_file, diff_file, shallow=False):
                            print(" Identical {}".format(rel_file))
                            continue

                    # In both and different
                    file_label = get_without_ext(file)
                    file_for_subdir = file_label if self.config.partition_files else ""
                    controller.queue_job(
                        self.process_file,
                        base_file,
                        diff_file,
                        compare_subdir,
                        inner_dir,
                        file_for_subdir,
                        file_label,
                    )

    def process_extras(self, controller):
        # controller.extra_funcs is
        # { compare_subdir -> ( base_funcs, diff_funcs ) }
        # base_funcs and diff_funcs are { func_name -> Function }

        # Find matching functions and process them.

        if controller.hit_any_limit():
            return

        stats = Stats("extra")

        for compare_subdir, (base_funcs, diff_funcs) in controller.extra_funcs.items():
            len_base = len(base_funcs)
            len_diff = len(diff_funcs)
            matched_funcs = {
                func for func in base_funcs.keys() if func in diff_funcs.keys()
            }
            matched_base_funcs = {func: base_funcs[func] for func in matched_funcs}
            matched_diff_funcs = {func: diff_funcs[func] for func in matched_funcs}
            assert len(matched_base_funcs) == len(matched_diff_funcs)
            print(
                "extras: for {} there are {} in base, {} in diff, and {} matches".format(
                    compare_subdir,
                    len(base_funcs),
                    len(diff_funcs),
                    len(matched_base_funcs),
                )
            )

            _, _, _, extra_stats = self.process_file_contents(
                stats,
                matched_base_funcs,
                matched_diff_funcs,
                compare_subdir,
                "",
                "extras",
            )
            stats.add(extra_stats)

        self.stats.add(stats)

    # funcs is { func -> (lines, canon_lines) }.
    # canon_lines is empty and will be filled in here.
    def canon_file(self, stats, funcs, file_label):
        print("  Canon {}".format(file_label))
        for (func, (lines, canon_lines)) in funcs.items():
            stats.incr(CounterKind.CanonCount)
            for line in lines:
                with stats.timers[TimeKind.Canon]:
                    canoned_line = self.parser.canon_line(line)

                with stats.timers[TimeKind.Append]:
                    canon_lines.append(canoned_line)

    # funcs is a dict: name (str) -> Function
    def write_files(self, output_dir, base_diff, funcs, file_for_subdir):
        output_dir = os.path.join(output_dir, file_for_subdir, base_diff)
        os.makedirs(output_dir, exist_ok=True)
        for funcname, function in funcs.items():
            with open_long_filename_to_write(
                os.path.join(output_dir, funcname + ".asm")
            ) as asm:
                asm.writelines(function.lines)
            with open_long_filename_to_write(
                os.path.join(output_dir, funcname + ".canon")
            ) as canon:
                canon.writelines(function.canon_lines)

    # When we diff two files, we get a list of differences encoded as DiffCommands.
    # Position is an index into that list except that it can also store a DiffCommand
    # that replaces the current one.  This can be used to represent the state of
    # having partially processed a DiffCommand.  See MatchContext.get_command.
    class Position:
        def __init__(self, command_index, updated_current_command=None):
            self.command_index = command_index
            self.updated_current_command = updated_current_command

        def next_command(self):
            return DiffTool.Position(self.command_index + 1)

        def with_updated(self, updated):
            return DiffTool.Position(self.command_index, updated)

        def __eq__(self, other):
            return (
                self.command_index == other.command_index
                and self.updated_current_command == other.updated_current_command
            )

        def __repr__(self):
            return "Position({}, {})".format(
                repr(self.command_index), repr(self.updated_current_command)
            )

    # Information that is constant while processing the diffs in a file:
    # The lines in the base/diff files, the DiffCommands that show the differences
    # between them, and the strategies/skips being used to prune the diffs.
    class MatchContext:
        def __init__(
            self, stats, base_file_lines, diff_file_lines, commands, strategies, skips
        ):
            self.stats = stats
            self.base_file_lines = base_file_lines
            self.diff_file_lines = diff_file_lines
            self.commands = commands
            self.strategies = strategies
            self.skips = skips

        def get_command(self, position):
            updated = position.updated_current_command
            return (
                updated
                if updated is not None
                else self.commands[position.command_index]
            )

        def has_command(self, position):
            return (
                position.updated_current_command is not None
                or position.command_index < len(self.commands)
            )

    # After a Diff is matched in a Strategy, the line numbers in the base and diff files
    # are stored in an ExpectedLines so that the next Diff can be checked to start at an
    # expected location.  A Gap will be used to allow Space between the Diffs (and is
    # necessary because if there is no space, then the Diffs could just be combined).
    class ExpectedLines:
        def __init__(self, diff, base, gap=None):
            self.diff = diff
            self.base = base
            self.gap = gap if gap else Gap(Range(0))

        def with_gap(self, gap):
            # might be worth checking this: assert self.gap is None
            return DiffTool.ExpectedLines(self.diff, self.base, gap)

        def with_shift(self, value, is_base):
            if is_base:
                return DiffTool.ExpectedLines(self.diff, self.base + value, self.gap)
            else:
                return DiffTool.ExpectedLines(self.diff + value, self.base, self.gap)

        def __repr__(self):
            return "ExpectedLines({}, {}, {})".format(
                repr(self.diff), repr(self.base), repr(self.gap)
            )

    # Skips, as the name suggestes, are used to represent things that should be skipped in the
    # diffs.  They have looser matching requirements than normal Strategies/Diffs.  (It's an
    # open question whether Strategies/Diffs are too strict.)  They are intended to represent
    # short code snippets that are added/removed/moved in arbitrary locations.
    #
    # "skips" is a list of independent Diffs.  If only one of base_lines or diff_lines is
    # non-empty in the Diffs, then the skip is a remove or add.  If both are non-empty, then
    # it is a move.  The lines in a Diff do not need to be contiguous.
    #
    # Beyond store the skip patterns themselves, SkipState stores the amount of matching that
    # has been done.  For moves, match_differences store how many extra occurrences have been
    # seen on the diff side (if positive) or the base side (if negative).  A proper move will
    # result in zero.  Partial matches of a pattern are stored in base/diff_progress.  Note
    # that a second copy of a skip can not begin to be processed until the previous one is
    # finished.
    #
    # mappings stores any assigned variables just like with Strategies.
    class SkipState:
        def __init__(self, skips):
            size = len(skips)
            self.skips = skips
            self.match_differences = [0] * size
            self.base_progress = [0] * size
            self.diff_progress = [0] * size
            self.mappings = [{} for _ in range(size)]

        def __str__(self):
            d = {}
            if any(self.match_differences):
                d["match_differences"] = self.match_differences
            if any(self.base_progress):
                d["base_progress"] = self.base_progress
            if any(self.diff_progress):
                d["diff_progress"] = self.diff_progress
            return str(d)

        def __len__(self):
            return len(self.skips)

        def is_complete(self):
            return not (
                any(self.match_differences)
                or any(self.base_progress)
                or any(self.diff_progress)
            )

        def diff_is_complete(self):
            return not (
                any(d > 0 for d in self.match_differences) or any(self.diff_progress)
            )

        def base_is_complete(self):
            return not (
                any(d < 0 for d in self.match_differences) or any(self.base_progress)
            )

        def needs_progress(self, is_base, index):
            if is_base and self.match_differences[index] > 0:
                return True
            if (not is_base) and self.match_differences[index] < 0:
                return True
            return False

        def get_progress(self, is_base, index):
            if is_base:
                return self.base_progress[index], self.mappings[index]
            else:
                return self.diff_progress[index], self.mappings[index]

        # pattern_index may be len(skips.{base,diff}_lines, in which case it set
        # match_differences and reset progress.
        def set_progress(self, is_base, index, pattern_index):
            if is_base:
                patterns = self.skips[index].base_lines
                other = self.skips[index].diff_lines
                progress = self.base_progress
                incr = -1
            else:
                patterns = self.skips[index].diff_lines
                other = self.skips[index].base_lines
                progress = self.diff_progress
                incr = 1

            if pattern_index >= len(patterns):
                if len(other) > 0:
                    self.match_differences[index] += incr
                progress[index] = 0
                self.mappings[index] = {}
            else:
                progress[index] = pattern_index

    # Try to match one "pattern line" (from either the base or diff of a strategy element)
    @indent_decorator("check pattern {} at line {}", 2, 4)
    def match_pattern_line(
        self, mapping, diff, pattern_number, lines, line_number, is_base
    ):
        re, labels, converters, default_values = diff.lines(is_base)[pattern_number]
        line = lines[line_number]
        self.config.print("re: {}...", re.pattern[:80].rstrip())
        self.config.print("ln: {}", line[:80].rstrip())
        match = re.match(line)  # match means at start of line
        if not match:
            self.config.print("no match")
            return None
        indexed_groups = match.groups()
        if self.config.debug_patterns and not all(
            g is not None for g in indexed_groups
        ):
            if self.config.debug_patterns:
                # NOTE: This hasn't been used since updating it after changing how named groups
                # are used.
                if (
                    sum(1 for _ in filter(bool, indexed_groups))
                    >= self.config.debug_patterns
                ):
                    print(
                        "partial pattern match:\n  N: {}\nre: {}\n  ln: {}\n  pr: {}".format(
                            sum(
                                1
                                for _ in itertools.takewhile(
                                    lambda x: x, indexed_groups
                                )
                            ),
                            re.pattern,
                            line,
                            match.group(0),
                        )
                    )
                    for g in indexed_groups:
                        print("  {}".format(g))
            self.config.print("missing groups")
            return None

        dict_groups = match.groupdict()
        new_mapping = mapping.copy()
        mapping_diffs = {}
        for label, group_names in labels.items():
            for group_name in group_names:
                group = dict_groups[group_name]
                if group is None:
                    group = default_values.get(group_name)

                converter = converters.get(group_name)
                if group and converter:
                    # The pattern said that the found value was VAR+k, so we subtract
                    # k from the found value to get the intended value for VAR.
                    converter_function, plus_value = converter
                    if type(plus_value) is int:
                        to_subtract = plus_value
                    else:
                        assert type(plus_value) is str
                        # There might be an ordering issue here
                        to_subtract = get_arm_register_size(new_mapping[plus_value])
                    group = converter_function(group) - to_subtract

                old_group = new_mapping.get(label)
                if old_group is None:
                    mapping_diffs[label] = group
                    new_mapping[label] = group
                elif old_group != group:
                    self.config.print(
                        "mapping mismatch for {}, {} vs {}", label, group, old_group
                    )
                    return None

        new_pattern_number = pattern_number + 1
        new_line_number = line_number + 1
        self.config.print(
            "pattern matched, now p={} l={}, adding {}",
            new_pattern_number,
            new_line_number,
            mapping_diffs,
        )
        mapping.update(mapping_diffs)
        return new_pattern_number, new_line_number

    @indent_decorator("check skips for {} in is_base={}", 2, (3, "is_base"))
    def match_skip_lines(self, skip_state, lines, line_range, is_base):
        for i in range(len(skip_state)):
            # This should be checked when compiling the skips but isn't yet.
            #
            # skips can already be repeated
            # the purpose of skips is to skip parts of diffs (so not filler)
            assert skip_state.skips[i].repeat == Range(1)
            assert not skip_state.skips[i].is_filler

        for i in range(len(skip_state)):
            if skip_state.needs_progress(is_base, i):
                result = self.match_skip_lines2(
                    skip_state, i, lines, line_range, is_base
                )
                if result is not None:
                    return result

        for i in range(len(skip_state)):
            if not skip_state.needs_progress(is_base, i):
                result = self.match_skip_lines2(
                    skip_state, i, lines, line_range, is_base
                )
                if result is not None:
                    return result

        return None

    # helper for match_skip_lines
    def match_skip_lines2(self, skip_state, skip_index, lines, line_range, is_base):
        skip_diff = skip_state.skips[skip_index]
        if is_base:
            skip = skip_diff.base_lines
        else:
            skip = skip_diff.diff_lines

        if len(skip) > 0:
            pattern_start, mapping = skip_state.get_progress(is_base, skip_index)
            # depends on mapping being mutated by match_pattern_lines_skip
            #
            # also note that partial success in match_pattern_lines_skip might mutate mapping
            # and then fail - this is one of probably several places that could use more
            # sophisticated handling of branches in the search path (but they rarely/never
            # show up, at least for now)
            result = self.match_pattern_lines_skip(
                mapping, skip_diff, pattern_start, lines, line_range, is_base
            )
            if result is not None:
                pattern_number, line_number = result
                skip_state.set_progress(is_base, skip_index, pattern_number)
                return line_number

    # Try to match a skip that occurs outside of a pattern (i.e., it is a standalone diff
    # region).
    def match_skip_element(self, skip_state, expected_lines, position, context):
        if not context.has_command(position):
            return None
        command = context.get_command(position)

        for is_base in [True, False]:
            lines = context.base_file_lines if is_base else context.diff_file_lines
            line_range = command.base_range if is_base else command.diff_range
            while not line_range.empty():
                result = self.match_skip_lines(skip_state, lines, line_range, is_base)
                if result is None:
                    return None
                if expected_lines is not None:
                    expected_lines = expected_lines.with_shift(
                        line_range.size(), is_base
                    )
                line_range = Range(result, line_range.end)

        return expected_lines, position.next_command()

    # Try to match a list of "pattern lines" (either the base or diff of a strategy element)
    # against the lines at lines[start,end).  This may include skips.
    #
    # Returns new_line_number, new_positon.  new_line_number is after consuming lines for the match.
    # new_position does not since the position specifies information for both the base and diff.
    # new_position can be updated, however, to combine additional DiffCommands if more are needed
    # for the pattern.
    #
    # Example 1
    # ---------
    #
    # Pattern:
    #
    #   Diff(
    #     [],
    #     [
    #       r"  add   x17, x2, #[[#,imm:]]"
    #     ]
    #   )
    #   Gap(Range(0,4)),
    #   Diff(
    #     [
    #       r"  blr   x[[#,16':]]"
    #     ],
    #     [
    #       r"  mov   x2, x16",
    #       r"  bl    S_SbtGlobalDispatchDll",
    #     ]
    #
    # Diff:
    #
    #     .Ltmp2455:                         |     .Ltmp2455:
    # D1:   str   x17, [x1, #-8]!            | D1:   add   x17, x2, #19
    # D1: .Ltmp2456:                         |
    # D1:   blr   x16                        |
    #     .Ltmp2457:                         |     .Ltmp2456:
    #       mov   w16, #52684                |       mov   w29, #52684
    #                                        | D2:   str   x17, [x1, #-8]!
    #                                        | D2: .Ltmp2457:
    #                                        | D2:   mov   x2, x16
    #       movk  w16, #633, lsl #16         |       movk  w29, #633, lsl #16
    #                                        | D3:   bl S_SbtGlobalDispatchDll
    #                                        | D3: .Ltmp2458:
    #
    # The first pattern matches part of D1.  (TODO: check how the Gap fits in - it shouldn't
    # be relevant here.)  Then the second pattern only sees the 'blr' in the diff, so we extend
    # to include D2 (and then D3) to find the 'mov' and the 'bl'.  This elevates the non-diff
    # '.Ttmp2456', 'mov', and 'movk' into a diff, so skips are needed for them.
    #
    # Example 2
    # ---------
    #
    # Pattern:
    #
    #   Diff(
    #     [
    #       r"  stp   [[1:~r~]], [[2:~r~]], [[[3:~r~]]]"
    #     ],
    #     [
    #       r"  str   [[2:~r~]], [[[3:~r~]], #[[#]]]",
    #       r"  str   [[1:~r~]], [[[3:~r~]]]",
    #     ],
    #   )
    #
    # Diff:
    #
    # D1:   stp   x3, x3, [x3]               | D1:   str   x3, [x3, #8]
    #     .Ltmp582:                          |     .Ltmp635:
    #                                        | D2:   str   x3, [x3]
    #
    # D1 gives a partial match to the pattern.  When we extend to D2, we pick up the
    # Ltmp on both sides.  We must process the base side in order to get to the second
    # 'str' instruction, but we don't need to process the diff side in order to finish
    # the pattern.  This can leave Ltmp as a stray diff.
    #
    # For now, I am going to try to implement "global skips" as a workaround for this.
    # This will be useful for Ltmp anyway because it has been repeated in almost every
    # pattern so far.  However, if a different line appeared here, it would be
    # unfortunate to have to make it a global skip in order to avoid the stray diff.
    @indent_decorator("check {} in is_base={}", 5, (7, "is_base"))
    def match_pattern_lines(
        self,
        skip_state,
        mapping,
        diff,
        lines,
        get_line_range,
        position,
        context,
        is_base,
    ):
        line_range = get_line_range(context.get_command(position))
        self.config.print("line range is {}", line_range)
        patterns = diff.lines(is_base)
        # if len(patterns) > 0 and line_range.empty():
        #    return None

        line_number = line_range.start
        pattern_number = 0

        while pattern_number < len(patterns):
            if line_number >= line_range.end:
                # Have used all lines in line_range but not used up all of 'patterns'
                self.config.print(
                    "matched all lines but only to pattern {}", pattern_number
                )
                if pattern_number == 0:
                    # Avoiding this case:
                    #
                    # Line ranges diff=[34, 34), base=[22, 23)
                    # (diff is empty)
                    # Next line ranges diff=[38, 39), base=[27, 31)
                    #
                    # global skip=Diff([r".Ltmp[[#]]:"], [])
                    # Line 34=.Ltmp3276:
                    #
                    # With the empty range, we extend to [34, 39), match line 34,
                    # and leave behind [35, 39) as well as the extension on the
                    # base side.
                    #
                    # Problems:
                    # - If the base matches at this point and the diff needs the
                    #   extension, then we'll miss the match.  (likewise with
                    #   base and diff swapped)
                    # - This is only a crude way to detect extraneous matches.  The
                    #   general problem could be artitrarily complicated.
                    return None
                position = self.extend_diff_command(position, context)
                if position is None:
                    return None
                line_range = get_line_range(context.get_command(position))
                continue

            result = self.match_pattern_line(
                mapping, diff, pattern_number, lines, line_number, is_base
            )
            if result is not None:
                pattern_number, line_number = result
            else:
                # if pattern_number > 0:
                result = self.match_skip_lines(
                    skip_state, lines, Range(line_number, line_range.end), is_base
                )
                if result is None:
                    self.config.print("failed to match pattern or skip")
                    return None
                line_number = result

        self.config.print(
            "matched pattern, now line={} (range went to {})",
            line_number,
            line_range.end,
        )
        return line_number, position

    # Simpler version of match_pattern_lines (no skip logic - it's used for skips already)
    @indent_decorator("skip check {}", 4)
    def match_pattern_lines_skip(
        self, mapping, diff, pattern_start, lines, line_range, is_base
    ):
        patterns = diff.lines(is_base)
        # if len(patterns) > 0 and line_range.empty():
        #    return None

        line_number = line_range.start
        pattern_number = pattern_start

        while pattern_number < len(patterns):
            if line_number >= line_range.end:
                # Have used all lines in line_range but not used up all of 'patterns'
                self.config.print(
                    "matched all lines but only to pattern {}", pattern_number
                )
                if pattern_number == pattern_start:
                    return None
                return pattern_number, line_number

            result = self.match_pattern_line(
                mapping, diff, pattern_number, lines, line_number, is_base
            )
            if result is not None:
                pattern_number, line_number = result
            elif line_number != line_range.start:
                self.config.print(
                    "matched part of pattern, now line={} (range went to {}), pattern={} (of {})",
                    line_range,
                    line_range.end,
                    pattern_number,
                    len(patterns),
                )
                return pattern_number, line_number
            else:
                self.config.print("failed to match any patterns in the skip")
                return None

        self.config.print(
            "matched pattern, now line={} (range went to {})",
            line_number,
            line_range.end,
        )
        return pattern_number, line_number

    # When a diff that we're trying to match is combined with code movement, the
    # diff can appear as two diffs to diff tools.  In that case, the diff pattern
    # will match (or at least begin to match) for just one of the base or diff.
    # In that case, we can extend the DiffCommand by adding the next DiffCommand
    # to it.  We also add the lines between the DiffCommands (which will also need
    # to be matched - skips are useful for this), though this might prove to be
    # overly restrictive.
    def extend_diff_command(self, position, context):
        # check for room for both the current position and the next one
        if position.command_index + 1 >= len(context.commands):
            return None

        command = context.get_command(position)
        position = position.next_command()
        next_command = context.get_command(position)
        combined_command = DiffCommand(
            Range(command.diff_range.start, next_command.diff_range.end),
            Range(command.base_range.start, next_command.base_range.end),
        )
        combined_position = position.with_updated(combined_command)
        self.config.print(
            "extending {} with {} to get {}", command, next_command, combined_command
        )

        return combined_position

    # Try to match the given element (one 'repeat' only) (of a strategy)
    # to the lines referred to by the diff command at 'position'.
    @indent_decorator("check {} expect {}", 4, 3)
    def match_element_once(
        self, skip_state, mapping, element, expected_lines, position, context
    ):
        assert type(element) is Diff

        command = context.get_command(position)
        self.config.print("command is {}", command)
        if len(element.diff_lines) > 0:
            self.config.print(
                "diff_lines: {}...",
                element.diff_lines[0][0].pattern.replace("\\", "")[:40],
            )
        if len(element.base_lines) > 0:
            self.config.print(
                "base_lines: {}...",
                element.base_lines[0][0].pattern.replace("\\", "")[:40],
            )

        if expected_lines is not None:
            gap = expected_lines.gap.gap_range
            if not gap.is_valid_candidate(
                expected_lines.diff, command.diff_range.start
            ):
                self.config.print(
                    "diff invalid candidate gap={} exp={} cmd_start={}".format(
                        gap, expected_lines.diff, command.diff_range.start
                    )
                )
                return None
            if not gap.is_valid_candidate(
                expected_lines.base, command.base_range.start
            ):
                self.config.print(
                    "base invalid candidate gap={} exp={} cmd_start={}".format(
                        gap, expected_lines.base, command.base_range.start
                    )
                )
                return None

        result = self.match_pattern_lines(
            skip_state,
            mapping,
            element,
            context.diff_file_lines,
            lambda command: command.diff_range,
            position,
            context,
            is_base=False,
        )
        if result is None:
            self.config.print("diff match fail")
            return None
        diff_match_end, position = result

        result = self.match_pattern_lines(
            skip_state,
            mapping,
            element,
            context.base_file_lines,
            lambda command: command.base_range,
            position,
            context,
            is_base=True,
        )
        if result is None:
            self.config.print("base match fail")
            return None
        base_match_end, position = result

        # Important since the position can be updated
        command = context.get_command(position)

        new_expected_lines = DiffTool.ExpectedLines(
            diff=diff_match_end, base=base_match_end
        )

        if (
            diff_match_end == command.diff_range.end
            and base_match_end == command.base_range.end
        ):
            new_position = position.next_command()
        else:
            new_diff_range = Range(diff_match_end, command.diff_range.end)
            new_base_range = Range(base_match_end, command.base_range.end)
            new_position = position.with_updated(
                DiffCommand(new_diff_range, new_base_range)
            )

        return new_expected_lines, new_position

    # Try to match the given element (including a possible 'repeat' value) (of a strategy)
    # to the lines referred to by the diff command at 'position'.
    def match_element(
        self, skip_state, mapping, element, expected_lines, position, context
    ):
        if type(element) is Gap:
            self.config.print("gap: {}", element)
            if expected_lines is None:
                print("Gap isn't after a Diff")
                return None
            return expected_lines.with_gap(element), position

        assert type(element) is Diff

        if element.is_filler:
            # Note: don't put a filler after a partial match of a Diff to a DiffCommand
            if position.updated_current_command is None:
                command = context.get_command(position)

                # Handles case of Gap followed by Diff(is_filler)
                # but discards end (assume min value of range)
                gap = expected_lines.gap.gap_range.start

                new_diff_range = Range(
                    expected_lines.diff + gap, command.diff_range.start
                )
                new_base_range = Range(
                    expected_lines.base + gap, command.base_range.start
                )

                self.config.print(
                    "filler - updating {} with d={}, b={}",
                    command,
                    new_diff_range,
                    new_base_range,
                )
                position = DiffTool.Position(
                    position.command_index - 1,
                    DiffCommand(new_diff_range, new_base_range),
                )

        # The logic with 'matches' is to handle a possible repeat value for the element.
        matches = 0
        # note: The "<" and "- 1" look suspicious but is necessary.
        # "end - 1" is the maximum value of the range, and we continue until we have that many.
        while matches < element.repeat.end - 1:
            if not context.has_command(position):
                break

            result = self.match_element_once(
                skip_state, mapping, element, expected_lines, position, context
            )
            if result is not None:
                matches += 1
            else:
                # I'm not a big fan of how this works.  If some skips appear within a diff block,
                # then processing of the diff block (in match_element_once) can find them.  But if they
                # appear as separate diffs, then it will fail to match the pattern and therefore we
                # need the extra check here.
                result = self.match_skip_element(
                    skip_state, expected_lines, position, context
                )
                if result is None:
                    break

            expected_lines, position = result
            if element.is_filler and position.updated_current_command is None:
                break

        if matches < element.repeat.start:
            self.config.print("failed repetition {} of {}", matches + 1, element.repeat)
            return None

        # This is messy.  However, is_filler hasn't been very useful, so it's likely that
        # the best course of action is to delete it rather than clean up this special case.
        if element.is_filler and matches == 0:
            # is_filler Diff (successfully - repeat.start was 0) didn't match a Diff,
            # but we set up position for it
            position = position.next_command()

        return expected_lines, position

    # Try to match the given strategy to the lines referred to by the diff command at 'position'.
    #
    # If it matches, return the new position (which could be an updated diff command).
    # Otherwise, return None.
    def match_strategy(self, strategy, position, context):
        expected_lines = None
        mapping = {}
        skip_state = DiffTool.SkipState(strategy.skips)

        for element_index, element in enumerate(strategy.patterns):
            with self.config.indent("element {} at {}", element_index, position):
                result = self.match_element(
                    skip_state, mapping, element, expected_lines, position, context
                )
                if result is None:
                    return None
                self.config.print("result: {}", str(result))
                self.config.print("mapping: {}", str(mapping))
                expected_lines, position = result

        base_line_number = expected_lines.base
        diff_line_number = expected_lines.diff

        self.config.print(position)
        while not skip_state.is_complete():
            with self.config.indent(
                "finished strategy but skip_state {} is not complete", skip_state
            ):
                # if position.updated_current_command is not None:
                result = self.match_skip_element(
                    skip_state, expected_lines, position, context
                )
                if result is not None:
                    expected_lines, position = result
                    continue

                # want something like this if we need to look at lines past the last DiffCommand
                # (including any extensions) - may need to consider identical lines as a move
                # if not skip_state.diff_is_complete():
                #     next_command = context.get_command(position)
                #     if expected_lines.gap.size():
                #         # Don't want to deal with this right now
                #         # (also why does a pattern end with a gap?)
                #         self.config.print("found gap when looking for unmatched skip in diff")
                #         return None
                #     if diff_line_number < next_command.diff_range.start:
                #         next_diff_line = Range(diff_line_number, diff_line_number + 1)
                #         result = self.match_skip_lines(skip_state, diff_file_lines, next_diff_line, is_base=False)
                #         if result is None:
                #             self.config.print("failed to process unmatched skip in diff")
                #             return None
                #         diff_line_number = result
                #         continue

                self.config.print("No progress made on completing unmatched skip")
                return None

        return position

    # Try to match any of the strategies (stop after finding one) (in context.strategies)
    # to the lines referred to by the diff command at 'position'.
    #
    # If a match is found, return the new position (which could be an updated diff command).
    # Otherwise, return None.
    def match_strategies(self, position, context):
        for strategy_index, strategy in enumerate(context.strategies):
            with self.config.indent(
                "strategy {} - {} at {}", strategy_index, strategy.name, position
            ):
                result = self.match_strategy(strategy, position, context)
                if result:
                    context.stats.incr_strategy(strategy.name)
                    self.config.print("success")
                    return result

        for skip_index, skip in enumerate(context.skips):
            with self.config.indent(
                "skip {} - {} at {}", skip_index, skip.name, position
            ):
                result = self.match_strategy(skip, position, context)
                if result:
                    context.stats.incr_strategy(skip.name)
                    self.config.print("success")
                    return result

        return None

    # Remove the diff commands (out of context.commands) that are matched by
    # patterns (in context.strategies)
    def filter_diff(self, context):
        self.config.print(context.commands)
        new_commands = []
        position = DiffTool.Position(0)

        while position.command_index < len(context.commands):
            # print(context.get_command(position))
            result = self.match_strategies(position, context)
            if result is None:
                new_command = context.get_command(position)
                # print("--> {}".format(new_command))
                new_commands.append(new_command)
                position = position.next_command()
                continue

            # found match
            position = result

        self.config.print(new_commands)
        return new_commands

    # Write a file with the useful differences between the base and diff files.
    #
    # First we do a normal diff of the canonicalized versions of the base and diff
    # files.  Then we filter those diffs using the user-specified strategies
    # to skip common patterns.
    def write_d_file(
        self, stats, compare_subdir, file_for_subdir, funcname, base_func, diff_func
    ):
        base_output_dir = os.path.join(
            compare_subdir, file_for_subdir, self.config.compare_base_name
        )
        diff_output_dir = os.path.join(
            compare_subdir, file_for_subdir, self.config.compare_diff_name
        )
        filename = shorten_long_filename(funcname + ".canon")
        base_canon_file = os.path.join(base_output_dir, filename)
        diff_canon_file = os.path.join(diff_output_dir, filename)
        diff_file = change_ext(diff_canon_file, ".d")
        self.config.print("Function {}", funcname)

        with stats.timers[TimeKind.WriteDiff]:
            # look into package difflib
            completed = subprocess.run(
                ["diff", diff_canon_file, base_canon_file],
                stdout=subprocess.PIPE,
                encoding="utf-8",
            )
            diff_output = completed.stdout.splitlines(keepends=True)

        with stats.timers[TimeKind.FilterDiff]:
            diff_commands = [
                parse_diff_command(d)
                for d in diff_output
                if d[:1] not in ["<", ">", "-"]
            ]
            stats.incr(CounterKind.RawDiff, len(diff_commands))
            context = DiffTool.MatchContext(
                stats,
                base_func.lines,
                diff_func.lines,
                diff_commands,
                self.config.filter_diff_strategies,
                self.config.filter_diff_skips,
            )
            diff_commands = self.filter_diff(context)
            stats.incr(CounterKind.FinalDiff, len(diff_commands))

            if diff_commands:
                stats.incr(CounterKind.FuncDiff)
                self.config.print("  writing {}".format(diff_file))
                output_diff_commands = [output_diff_command(d) for d in diff_commands]
                with open(diff_file, "w") as write_diff_file:
                    write_diff_file.writelines(output_diff_commands)
            else:
                os.remove(change_ext(base_canon_file, ".asm"))
                os.remove(change_ext(diff_canon_file, ".asm"))
                os.remove(base_canon_file)
                os.remove(diff_canon_file)

                # Remove a .d file if it exists from an earlier run
                if os.path.exists(diff_file):
                    os.remove(diff_file)

    def process_file(
        self,
        base_file,
        diff_file,
        compare_subdir,
        inner_dir,
        file_for_subdir,
        file_label,
    ):
        try:
            return self.process_file2(
                base_file,
                diff_file,
                compare_subdir,
                inner_dir,
                file_for_subdir,
                file_label,
            )
        except:
            print("exception while processing ", file_label)
            raise

    def process_file2(
        self,
        base_file,
        diff_file,
        compare_subdir,
        inner_dir,
        file_for_subdir,
        file_label,
    ):
        print(" Process {}".format(file_label))
        os.makedirs(compare_subdir, exist_ok=True)

        stats = Stats(file_label)
        base_funcs = self.parser.split_file(stats, base_file, inner_dir, file_label)
        diff_funcs = self.parser.split_file(stats, diff_file, inner_dir, file_label)

        return self.process_file_contents(
            stats, base_funcs, diff_funcs, compare_subdir, file_for_subdir, file_label
        )

    def process_file_contents(
        self, stats, base_funcs, diff_funcs, compare_subdir, file_for_subdir, file_label
    ):
        base_extra_funcs = {}
        diff_extra_funcs = {}

        with stats.timers[TimeKind.EarlyMatch]:
            to_delete = []

            print("  Early matching {}".format(file_label))
            for funcname, base_func in base_funcs.items():
                diff_func = diff_funcs.get(funcname)
                if diff_func:
                    if base_func.lines == diff_func.lines:
                        stats.incr(CounterKind.EarlyMatch)
                        to_delete.append(funcname)
                else:
                    stats.incr(CounterKind.EarlySolo)
                    to_delete.append(funcname)
                    if self.config.include_missing:
                        base_extra_funcs[funcname] = base_func
            for funcname, diff_func in diff_funcs.items():
                if funcname not in base_funcs:
                    stats.incr(CounterKind.EarlySolo)
                    to_delete.append(funcname)
                    if self.config.include_missing:
                        diff_extra_funcs[funcname] = diff_func

            for funcname in to_delete:
                base_funcs.pop(funcname, None)
                diff_funcs.pop(funcname, None)

        # At this point, a function is either in both base_funcs and diff_funcs or neither.

        self.canon_file(stats, base_funcs, file_label)
        self.canon_file(stats, diff_funcs, file_label)

        with stats.timers[TimeKind.CanonMatch]:
            to_delete = []
            print("  Canon matching {}".format(file_label))

            for funcname, base_func in base_funcs.items():
                diff_func = diff_funcs.get(funcname)
                if diff_func:
                    if base_func.canon_lines == diff_func.canon_lines:
                        stats.incr(CounterKind.CanonMatch)
                        to_delete.append(funcname)

            for funcname in to_delete:
                base_funcs.pop(funcname, None)
                diff_funcs.pop(funcname, None)

        with stats.timers[TimeKind.WriteFunc]:
            print("  Writing function files for {}".format(file_label))
            self.write_files(
                compare_subdir,
                self.config.compare_base_name,
                base_funcs,
                file_for_subdir,
            )
            self.write_files(
                compare_subdir,
                self.config.compare_diff_name,
                diff_funcs,
                file_for_subdir,
            )

        print("  Writing .d function files for {}".format(file_label))
        for funcname, base_func in base_funcs.items():
            try:
                self.write_d_file(
                    stats,
                    compare_subdir,
                    file_for_subdir,
                    funcname,
                    base_func,
                    diff_funcs.get(funcname),
                )
            except:
                print("exception while processing ", funcname)
                raise

        print(stats.report(indent=4))
        return compare_subdir, base_extra_funcs, diff_extra_funcs, stats


diff_add = re.compile(r"^(\d+)a(\d+)(?:,(\d+))?$", re.ASCII)
diff_replace = re.compile(r"^(\d+)(?:,(\d+))?c(\d+)(?:,(\d+))?$", re.ASCII)
diff_delete = re.compile(r"^(\d+)(?:,(\d+))?d(\d+)$", re.ASCII)


# A description of a diff between two files (or more generally betweens two
# sequences of lines).  The use of the naming "Command" is from diff tool,
# which describes add/deletes/changes, or a set of changes to get from one
# file to another.
class DiffCommand:
    def __init__(self, diff_range, base_range):
        self.diff_range = diff_range
        self.base_range = base_range

    def __eq__(self, other):
        return (
            self.diff_range == other.diff_range and self.base_range == other.base_range
        )

    def __str__(self):
        return "diff={}, base={}".format(self.diff_range, self.base_range)

    def __repr__(self):
        return "DiffCommand({}, {})".format(
            repr(self.diff_range), repr(self.base_range)
        )


# Parse the output of the 'diff' command into DiffCommands
def parse_diff_command(line):
    # note: order is diff..base, so add/delete are backwards
    # note: converting from one-based to zero-based line numbers
    # note: converting from inclusive end index to exclusive one
    # note: for add/remove, the diff command lists the line before the addition/removal
    #       for the side without the content.  We add one to refer to the line -after-.

    one_based = 1
    after_adjust = 1
    exclusive_adjust = 1

    add = diff_add.match(line)
    if add:
        diff_loc = int(add.group(1)) - one_based + after_adjust
        base_start = int(add.group(2)) - one_based
        base_end = (
            (int(add.group(3)) - one_based + exclusive_adjust)
            if (add.group(3) is not None)
            else (base_start + exclusive_adjust)
        )

        return DiffCommand(Range(diff_loc, diff_loc), Range(base_start, base_end))

    replace = diff_replace.match(line)
    if replace:
        diff_start = int(replace.group(1)) - one_based
        diff_end = (
            (int(replace.group(2)) - one_based + exclusive_adjust)
            if (replace.group(2) is not None)
            else (diff_start + exclusive_adjust)
        )
        base_start = int(replace.group(3)) - one_based
        base_end = (
            (int(replace.group(4)) - one_based + exclusive_adjust)
            if (replace.group(4) is not None)
            else (base_start + exclusive_adjust)
        )

        return DiffCommand(Range(diff_start, diff_end), Range(base_start, base_end))

    delete = diff_delete.match(line)
    if delete:
        diff_start = int(delete.group(1)) - one_based
        diff_end = (
            (int(delete.group(2)) - one_based + exclusive_adjust)
            if (delete.group(2) is not None)
            else (diff_start + exclusive_adjust)
        )
        base_loc = int(delete.group(3)) - one_based + after_adjust

        return DiffCommand(Range(diff_start, diff_end), Range(base_loc, base_loc))

    assert False


def output_diff_range(range):
    one_based = 1
    after_adjust = 1
    exclusive_adjust = 1

    if range.empty():
        return str(range.start + one_based - after_adjust)

    if range.size() == 1:
        return str(range.start + one_based)

    return (
        str(range.start + one_based) + "," + str(range.end + one_based - after_adjust)
    )


def output_diff_command(command):
    # reversing everything in parse_diff_command
    command_char = (
        "d"
        if command.base_range.empty()
        else "a"
        if command.diff_range.empty()
        else "c"
    )
    return (
        output_diff_range(command.diff_range)
        + command_char
        + output_diff_range(command.base_range)
        + "\n"
    )


class Gap:
    def __init__(self, gap_range):
        self.gap_range = gap_range  # avoid conflict with 'range'

    def __repr__(self):
        return "Gap({})".format(repr(self.gap_range))


# The main component of diff patterns.  A Diff is a sequence of base lines and a
# sequence of diff lines (if one is empty, then it represents an addition or
# deletion).  The lines are FileCheck-like in format.  It can be specified that
# they can/must repeat, and including zero in the range of allowed number of
# repetitions makes them optional.
class Diff:
    # is_filler means the Diff is matching an area between two diff commands
    # (add/delete/change).  This is used for more checking than a simple Gap in
    # the middle of a diff pattern.  is_filler hasn't proven to be particularly
    # useful and should probably be considered deprecated.
    def __init__(self, diff_lines, base_lines, repeat=None, is_filler=False):
        self.diff_lines = diff_lines
        self.base_lines = base_lines
        self.repeat = repeat if repeat else Range(1)
        self.is_filler = is_filler

    def lines(self, is_base):
        return self.base_lines if is_base else self.diff_lines


# A Strategy is a complete pattern to search for and remove from the set of diffs.
# It consists of a list of patterns (Diffs, Gaps) and a list of skips (Skips).
# The patterns are what need to match for the strategy to succeed.  Skips are
# used for changes that appear in the middle of other diffs (a simple case is a
# new .Ltmp: label in LLVM IR) and would typically get in the way of matching a
# pattern; as the name implied they are skipped.
class Strategy:
    def __init__(self, name, patterns=[], skips=[]):
        self.name = name
        self.patterns = patterns
        self.skips = skips

    def __repr__(self):
        return "Strategy(name={}, patterns={}, skips={})".format(
            repr(self.name), repr(self.patterns), repr(self.skips)
        )


# A Skip is actually rather similar to a Strategy in that it is matched alone at the top-level
# (unlike skips embedded in a Strategy that must be matched along with that Strategy's pattern).
# However, a Skip can also be used as a skip within a Strategy.
#
# Also, skip is a single Diff rather than a list of Diff/Gaps.
class Skip:
    def __init__(self, name, skip):
        self.name = name
        self.skip = skip

    def __repr__(self):
        return "Skip(name={}, skip={})".format(repr(name), repr(self.skip))


# Directives are shortcuts to REs/format strings.
#
# directive_map maps directive strings to a record with the following possible entries:
#    "prefix" - text that can appear before "content" - an "uninteresting" part
#    "content" - content to possibly be placed in an RE capture group
#                (the "interesting" part, which can simplify further processing)
#    note: "suffix" could easily be handled but hasn't been needed
#    "numeric" - alternative specification of the "content" using
#                scanf-style (%d) instead of RE (\d+)
# An RE should be formed by concatenating them together, optionally with a capturing group
# around the "group" part.  If there isn't "interesting" content, put the whole value in
# "content".
#
# If "numeric" is used instead of "content", then the result isn't a normal RE but one
# expected by the [[#...]] logic below, which will eventually be converted back to an RE
# but in a way expected by that code.
directive_map = {
    # call or invoke
    "C": {"content": r"call|invoke"},
    # operand
    #
    # This is a bit too permissive - should this be the same as "LlvmParser.variable"?
    # but "variable" doesn't allow integer constants
    # "O": { "content" : r"(?:%|!)?\d+|(?:%[a-zA-Z.]+(?:[0-9]+[A-Za-z.]+)*)\d*" },
    #
    # Some other possibilities:
    # - Just allow anything -  something like .+ or [^, ]+
    # - Try to capture the "name" part of an operand so that
    #   variable123 and variable456 would match
    #   but variable123 and broken456 would not.
    "O": {"content": r"(?:%(?:[A-Za-z0-9]+(?:_|\.?[A-Za-z0-9]*)*))(?:-?\d+|in)?"},
    # Debug operand
    "g": {"prefix": r", !dbg !", "content": r"\d+", "numeric": r"%d"},
    # Register
    "r": {"content": r"[wxrq](?:\d+|zr)"},  # registers
    # Vector type elements
    "V": {"content": r"i\d+|float|double"},
    # ARM64 memory operand offset ", #123" in "[reg, #123]"
    "offset": {"prefix": r", #", "content": r"\d+", "numeric": r"%d"},
}

arm_register_size_map = {"q": 16, "x": 8, "w": 4}


def get_arm_register_size(reg_name):
    return arm_register_size_map[reg_name[0]]


# Get the RE corresponding to 'key'.  The return value will be enclosed in a named capture
# group iff a name is provided (not None).
def get_shortcut(key, is_numeric_extract, group_name):
    entry = directive_map.get(key)
    if entry is None:
        return None
    has_outer_wrapper = False
    result = entry["numeric" if is_numeric_extract else "content"]
    if group_name:
        result = "(?P<" + group_name + ">" + result + ")"
        has_outer_wrapper = True
    prefix = entry.get("prefix")
    if prefix:
        result = prefix + result
        has_outer_wrapper = False
    if not has_outer_wrapper:
        result = "(?:" + result + ")"
    return result


# [
#     (
#         [
#             re, [0, 1]
#             re, [2, 1]
#             re, [3, 0, 1]
#             re, [4, 3, 2, 1]
#             re, [5, 4, 1]
#         ],
#         [],
#         Range(start, end),
#     ),
#     (
#         [
#             re, [0]
#         ],
#         [
#             re, []
#         ],
#         None
#     )
# ]

# Replace ~name~ with get_shortcut(name).  Use ~~ to escape a ~.
# Returns (new regex, if a capture group was added).
def apply_re_shortcuts(regex, is_numeric_extract=False, group_name=None):
    capture_group_added = False
    index = 0
    re_parts = []

    while index < len(regex):
        tilde = regex.find("~", index)
        if tilde == -1:
            break

        re_parts.append(regex[index:tilde])

        next_tilde = regex.find("~", tilde + 1)
        if next_tilde == -1:
            raise ValueError("mismatched ~ in re")

        if tilde + 1 == next_tilde:
            re_parts.append("~")
            index = tilde + 2
            continue

        index = next_tilde + 1
        name = regex[tilde + 1 : next_tilde]
        value = get_shortcut(name, is_numeric_extract, group_name)
        if value is None:
            raise ValueError("Unknown type {}".format(name))

        if group_name:
            capture_group_added = True
        re_parts.append(value)

    re_parts.append(regex[index:])
    return ("".join(re_parts), capture_group_added)


# Legacy support for the first iteration of the tool
# (though changed from {{...}} to <<...>> to avoid conflict with FileCheck format)
#
# <<?default:directive:var>>
# <<?default:directive>>
# <<directive:var>>
# <<directive>>
#
# Directives were shortcuts for REs.  There are now implemented as an extension to the
# FileCheck format by putting ~x~ in an RE.
#
# Some directives have been removed (e.g., <<d>> is now [[#]]).
#
# Some are a bit nicer without the generality of REs (e.g., <<g>> is now {{`g`}}
# or explicitly {{(?:, !dbg !\d+)}}), but the flexibility of arbitrary REs is probably
# better so this will likely be removed.  Left "just in case" for now.
def compile_angle(line, pattern_index, existing_groups):
    end_directive_index = line.find(">>", pattern_index)
    if end_directive_index == -1:
        raise ValueError("Missing >> after << for directive")
    next_index = end_directive_index + 2

    directive_index = pattern_index
    is_optional = False
    default_value = None
    if directive_index < end_directive_index and line[directive_index] == "?":
        is_optional = True
        directive_index += 1

        colon_index = line.find(":", directive_index, end_directive_index)
        if colon_index != -1:
            default_value = line[directive_index:colon_index]
            directive_index = colon_index + 1

    colon_index = line.find(":", directive_index + 1, end_directive_index)
    directive_label = None
    if colon_index != -1:
        start_label_index = colon_index + 1
        end_type_index = colon_index
        directive_label = line[start_label_index:end_directive_index]
        if directive_label == "":
            raise ValueError(
                "Empty directive label after ':' at character {} in {}".format(
                    start_label_index, line
                )
            )
    else:
        end_type_index = end_directive_index

    group_name = get_new_group_name(directive_label, existing_groups)

    directive_type = line[directive_index:end_type_index]
    if directive_type == "":
        raise ValueError(
            "Empty directive type at character {} in {}".format(directive_index, line)
        )

    directive_re = get_shortcut(directive_type, False, group_name)
    if directive_re is None:
        raise ValueError("Unknown type {}".format(directive_type))
    if is_optional:
        directive_re += "?"

    return next_index, directive_re, group_name, directive_label, None, default_value


def scan_d(s):
    return int(s, 10)


def scan_u(s):
    value = int(s, 10)
    if value < 0:
        value += 2 ** 32
    return value


def scan_x(s):
    return int(s, 16)


format_specs = {
    "d": {"name": "decimal", "prefix": "[+-]?", "digit": "\\d", "converter": scan_d},
    "u": {"name": "unsigned", "prefix": "[+-]?", "digit": "\\d", "converter": scan_u},
    "x": {
        "name": "hex",
        "prefix": "(?:0[xX])?",
        "digit": "[0-9a-fA-F]",
        "converter": scan_x,
    },
    "X": {
        "name": "Hex",
        "prefix": "(?:0[xX])?",
        "digit": "[0-9a-fA-F]",
        "converter": scan_x,
    },
}

#
# The various compile_* methods are used on Strategies/Skips.  The patterns are
# converted into REs and labeled capture groups, and those labels are recorded
# for the matching code to use.
#

# Modeled after https://www.llvm.org/docs/CommandGuide/FileCheck.html
#
# Supported:
#   [[#var:]]
#   [[#re%<fmtspec>re,var:]]  -- The regexes currently can not contain commas
#                                (so ~g~ isn't expressible without using the shortcut...)
#   [[var:re]]
#   In the numeric cases, 'var' can be var+k or var+size(var2).
#   The latter is a special case - it converts an ARM register name or prefix to its size.
# Additional:
#   [[#re%<fmtspec>re?default,var:]]
#     (but perhaps always just using zero would be good enough and eliminate the need for this)
# Not supported:
#   Precision in a [[#...]]
#   Almost all expressions
#   Pseudo numeric variables
#   Newlines
# Differences:
#   If a variable is used more than once, each occurrence must be a definition.  They will then
#   be checked to have the same value.  Combining this with the "only definitions are supported"
#   difference, an expression (currently only var+k) is decomposed to produce a value.  So
#   matching "VAR+4" to the string "12" yields a value of 8 for "VAR".  FileCheck has the user
#   omit the RE on all but the first and just searches for whatever text was found.  FileCheck
#   has a non-expression define a variable first, and then expressions can be computed in other
#   to determine expected values.
def compile_square(line, pattern_index, existing_groups):
    end_directive_index = line.find("]]", pattern_index)
    if end_directive_index == -1:
        raise ValueError("Missing ]] after [[ for directive")
    next_index = end_directive_index + 2

    if pattern_index < end_directive_index and line[pattern_index] == "#":
        format_spec_index = None
        format_spec_end = None

        label_index = pattern_index + 1
        label_end = end_directive_index
        comma = line.find(",", label_index, label_end)
        if comma != -1:
            format_spec_index = label_index
            format_spec_end = comma
            label_index = comma + 1
            if line.find(",", label_index, label_end) != -1:
                raise ValueError("pattern contains more than one ,")

        format_prefix = ""
        format_spec_name = "u"
        format_suffix = ""

        is_optional = False
        default_value = 0

        if format_spec_index is not None:
            # if format_spec_index != format_spec_end:
            #     question = line.find("?", format_spec_index, format_spec_end)
            #     if question != -1:
            #         is_optional = True
            #         default_value = line[question+1:format_spec_end]
            #         format_spec_end = question
            if format_spec_index != format_spec_end:
                format_spec = line[format_spec_index:format_spec_end]
                format_spec, capture_group_added = apply_re_shortcuts(
                    format_spec, is_numeric_extract=True, group_name=None
                )
                assert not capture_group_added
                percent = format_spec.find("%")
                if percent == -1:
                    raise ValueError("fmtspec " + format_spec + " doesn't contain a %")
                if format_spec.find("%", percent + 1) != -1:
                    raise ValueError(
                        "fmtspec " + format_spec + " contains more than one %"
                    )

                # Length of "%" is 1.  Length of conversion specifiers are all currently 1 as well.
                conversion_specifier_index = percent + 1
                format_suffix_index = conversion_specifier_index + 1

                format_prefix = format_spec[:percent]
                format_spec_name = format_spec[conversion_specifier_index]
                format_suffix = format_spec[format_suffix_index:]

        format_spec = format_specs.get(format_spec_name)
        if format_spec is None:
            raise ValueError("unknown format specifier " + format_spec_name)

        directive_label = None
        plus_value = 0
        if label_index < label_end:
            if line[label_end - 1] != ":":
                raise ValueError(
                    "directive label in {} doesn't end with ':'".format(
                        line[pattern_index:end_directive_index]
                    )
                )
            label_end -= 1
            if label_index >= label_end:
                raise ValueError("empty directive label")

            # Just support for VAR+k, VAR+size(VAR2)
            plus_index = line.find("+", label_index, label_end)
            if plus_index != -1:
                plus_string = line[plus_index + 1 : label_end].strip()
                open_index = plus_string.find("(")
                if open_index != -1:
                    close_index = plus_string.find(")", open_index + 1)
                    if close_index == -1:
                        raise ValueError("( without ) in + expression")
                    if close_index != len(plus_string) - 1:
                        raise ValueError(") not last in + expression")
                    function_name = plus_string[:open_index]
                    function_arg = plus_string[open_index + 1 : close_index]
                    if function_name != "size":
                        raise ValueError("only function 'size' is supported")
                    plus_value = function_arg
                else:
                    plus_value = int(plus_string)
                label_end = plus_index
            directive_label = line[label_index:label_end]

        group_name = get_new_group_name(directive_label, existing_groups)
        if group_name:
            open_group = "(?P<" + group_name + ">"
            close_group = ")"
        else:
            open_group = ""
            close_group = ""
        min_digits = 1
        suffix = "{" + str(min_digits) + ",}"
        directive_re = (
            format_prefix
            + open_group
            + format_spec["prefix"]
            + format_spec["digit"]
            + suffix
            + close_group
            + format_suffix
        )
        converter = (format_spec["converter"], plus_value)

        if is_optional:
            directive_re = "(?:" + directive_re + ")?"
    else:
        # TODO: Can the # and non-# paths be merged?
        colon = line.find(":", pattern_index, end_directive_index)
        if colon == -1:
            raise ValueError("No colon in [[ without #")

        directive_label = line[pattern_index:colon]
        if "+" in directive_label:
            raise ValueError("expressions are not supported in non-numeric definitions")
        group_name = get_new_group_name(directive_label, existing_groups)
        directive_re = line[colon + 1 : end_directive_index]
        directive_re, has_capture_group = apply_re_shortcuts(
            directive_re, False, group_name=group_name
        )
        if not has_capture_group:
            directive_re = "(?P<" + group_name + ">" + directive_re + ")"
        converter = None
        default_value = None

    return (
        next_index,
        directive_re,
        group_name,
        directive_label,
        converter,
        default_value,
    )


# {{re}}
def compile_brace(line, pattern_index, existing_groups):
    end_directive_index = line.find("}}", pattern_index)
    if end_directive_index == -1:
        raise ValueError("Missing }} after {{ for directive")
    next_index = end_directive_index + 2

    directive_re = line[pattern_index:end_directive_index]
    directive_re, _ = apply_re_shortcuts(directive_re, False, group_name=None)

    return next_index, directive_re, None, None, None, None


pattern_re = re.compile(r"(?P<angle><<)|(?P<brace>\{\{)|(?P<square>\[\[)", re.ASCII)
group_prefix = "__g_"


def get_new_group_name(label, existing_groups):
    if label is None:
        return None
    if not label.isidentifier():
        label = "_not_id"
    candidate = base = group_prefix + label
    next = 2
    while candidate in existing_groups:
        candidate = base + "_" + str(next)
        next += 1
    existing_groups.add(candidate)
    return candidate


def compile_line(line, debug_patterns=False):
    index = 0
    next_group_index = 0
    line_parts = ["^"]
    labels = {}  # label name to list of groups
    converters = {}  # group name to conversion info
    default_values = {}  # group name to default value
    existing_groups = set()

    # number of components we've seen for debug_patterns purposes
    # also equal to the number of "(" we've opened plus 1
    component_count = 0

    # a[[#?,x:]]b[[#]]c
    # no pattern debugging -> a(?:(\d+))?b\d+c and group(1) maps to x
    # pattern debugging -> a((?:(\d+))?(b(\d+(c)?)?)?)?
    #  group(2) maps to x; groups 1, 3, 4, 5 are for partial matches
    #  in this example, 2 and 3 will match the same, but the matching
    #  group for a specific pattern might not be the entire pattern
    while index < len(line):
        marker_match = pattern_re.search(line, index)
        if marker_match is None:
            break

        marker_index, pattern_index = marker_match.span()

        # Match literal section

        if debug_patterns and component_count:
            line_parts.append("(")
        component_count += 1
        line_parts.append(re.escape(line[index:marker_index]))

        # Match directive

        if marker_match.group("angle"):
            compile_directive = compile_angle
        elif marker_match.group("square"):
            compile_directive = compile_square
        elif marker_match.group("brace"):
            compile_directive = compile_brace
        else:
            assert False

        (
            index,
            directive_re,
            group_name,
            label,
            converter,
            default_value,
        ) = compile_directive(line, pattern_index, existing_groups)
        if label is None and default_value:
            raise ValueError("Default value without a label")

        if debug_patterns:
            line_parts.append("(")
        component_count += 1

        if label is not None:
            labels.setdefault(label, []).append(group_name)
            default_values[group_name] = default_value
            next_group_index += 1

            if converter:
                converters[group_name] = converter

        line_parts.append(directive_re)

    remaining = line[index:]
    if remaining:
        if debug_patterns and component_count:
            line_parts.append("(")
        line_parts.append(re.escape(remaining))
        component_count += 1

    if debug_patterns and component_count:
        line_parts.append("(")
    line_parts.append("$")
    component_count += 1

    if debug_patterns:
        line_parts.append(")?" * (component_count - 1))

    return (re.compile("".join(line_parts)), labels, converters, default_values)


def compile_lines(lines, debug_patterns):
    return [compile_line(line, debug_patterns) for line in lines]


def compile_element(element, debug_patterns):
    if type(element) is Gap:
        return element
    assert type(element) is Diff
    return Diff(
        compile_lines(element.diff_lines, debug_patterns),
        compile_lines(element.base_lines, debug_patterns),
        element.repeat,
        element.is_filler,
    )


def compile_skip(skip, debug_patterns=False):
    return Strategy(
        name=skip.name, patterns=[compile_element(skip.skip, debug_patterns)]
    )


def compile_strategy(strategy, global_skips, debug_patterns=False):
    return Strategy(
        name=strategy.name,
        patterns=[compile_element(e, debug_patterns) for e in strategy.patterns],
        skips=[compile_element(s, debug_patterns) for s in strategy.skips]
        + global_skips,
    )


def load_strategy_file(strategy_filename):
    # 'eval' runs in the current context if globals/locals aren't specified.
    # This lets the strategy files use Strategy, Diff, etc., without any imports.
    with open(strategy_filename, "rb") as file:
        result = eval(file.read())
    if type(result) is Strategy or type(result) is Skip:
        result = [result]
    return result


def load_strategy_files(strategy_filenames, is_debug_patterns):
    strategies = []
    skips = []
    for s in strategy_filenames:
        for item in load_strategy_file(s):
            if type(item) is Strategy:
                strategies.append(item)
            else:
                assert type(item) is Skip
                skips.append(item)

    compiled_skips = [compile_skip(s, is_debug_patterns) for s in skips]
    embedded_skips = list(itertools.chain(*[s.patterns for s in compiled_skips]))
    compiled_strategies = [
        compile_strategy(s, embedded_skips, is_debug_patterns) for s in strategies
    ]

    return (compiled_skips, compiled_strategies)


def print_line(line):
    print("      (")
    print("        " + line[0].pattern)
    print("        " + str(line[1]))
    print("      )")


def print_lines(lines):
    print("    [")
    for line in lines:
        print_line(line)
    print("    ]")


def print_element(element):
    print("  (")
    print_lines(element[0])
    print_lines(element[1])
    print("    " + str(element[2]))
    print("  )")


def print_strategy(strategy):
    print("[")
    for element in strategy:
        print_element(element)
    print("]")


if __name__ == "__main__":
    DiffTool.main(sys.argv[1:])
