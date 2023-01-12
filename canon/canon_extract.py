import os
import sys

from canon_base import *


class ExtractConfig(ConfigBase):
    def __init__(self, cmd_args):
        super().__init__(cmd_args)

        self.input_dir = cmd_args.input_dir

        #
        # canon_base expects these values, so set them to defaults.
        #
        # Alternately, they could be exposed as options.
        #

        self.max_line_length = 0

        # No limits
        self.diff_limit = 0
        self.file_limit = 0
        self.func_limit = 0

        self.include_all_blank_lines = True
        self.include_debug_info = True
        self.include_fntable = True
        self.include_references = True
        self.only_functions = True


class ExtractTool:
    def parse_args(args):
        (
            cmd_parser,
            required_group,
            config_group,
            filter_group,
            debug_group,
        ) = get_base_parser()

        required_group.add_argument(
            "-i", "--input-dir", help="Set input directory", required=True
        )

        cmd_args = cmd_parser.parse_args(args)
        config = ExtractConfig(cmd_args)

        return config

    def main(args):
        #
        # This is still mostly boilerplate despite a round of canon_base factoring.
        #

        config = ExtractTool.parse_args(args)
        extracttool = ExtractTool()
        extracttool.config = config
        extracttool.stats = Stats("Total")

        extracttool.parser = parser_map()[config.kind]()
        extracttool.parser.config = config
        if not config.filespecs:
            config.filespecs = [extracttool.parser.default_filespec()]

        controller = Controller(config, extracttool.stats, extracttool.do_extract)
        controller.go()

        print(extracttool.stats.report(indent=4))

    def do_extract(self, controller):
        input_dir = self.config.input_dir

        #
        # Find input files
        #

        rel_dir_dict = {}
        with self.stats.timers[TimeKind.Walk]:
            HasFile.add_dirwalk(
                rel_dir_dict,
                input_dir,
                HasFile.BASE,
                self.config.filespecs,
                self.config.exclude_filespecs,
            )

        #
        # Queue a job for each file
        #

        for dirpath in sorted(rel_dir_dict.keys()):
            print("Extract directory {} ".format(dirpath))
            inner_dir = os.path.basename(dirpath)

            extract_subdir = os.path.join(self.config.output_dir, dirpath)

            file_dict = rel_dir_dict[dirpath]
            for file in sorted(file_dict.keys()):
                has_file = file_dict[file]
                assert has_file == HasFile.BASE

                rel_file = os.path.join(dirpath, file)
                input_file = os.path.join(input_dir, rel_file)

                file_label = get_without_ext(file)
                controller.queue_job(
                    self.process_file, input_file, extract_subdir, inner_dir, file_label
                )

    def process_file(self, input_file, extract_subdir, inner_dir, file_label):
        try:
            return self.process_file2(input_file, extract_subdir, inner_dir, file_label)
        except:
            print("exception while processing ", file_label)
            raise

    def process_file2(self, input_file, extract_subdir, inner_dir, file_label):
        print(" Process {}".format(file_label))
        os.makedirs(extract_subdir, exist_ok=True)

        stats = Stats(file_label)
        funcs = self.parser.split_file(stats, input_file, inner_dir, file_label)

        return self.process_file_contents(
            stats, input_file, funcs, extract_subdir, file_label
        )

    def process_file_contents(
        self, stats, input_file, funcs, extract_subdir, file_label
    ):
        with stats.timers[TimeKind.WriteFunc]:
            if funcs:
                print("  Writing {}".format(file_label))
                _, filename = os.path.split(input_file)
                output_file = os.path.join(extract_subdir, filename)

                with open(output_file, "w") as f:
                    first = True
                    for funcname, function in funcs.items():
                        if first:
                            first = False
                        else:
                            f.write("\n")

                        f.writelines(function.lines)

        print(stats.report(indent=4))
        return extract_subdir, {}, {}, stats


if __name__ == "__main__":
    ExtractTool.main(sys.argv[1:])
