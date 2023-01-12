# Various utility functions

import time
import os


def create_empty_file(filename):
    with open(filename, "w"):
        pass


def change_ext(filename, new_extension):
    return os.path.splitext(filename)[0] + new_extension


def get_without_ext(filename):
    return os.path.splitext(filename)[0]


def get_ext(filename):
    return os.path.splitext(filename)[1]


def str_opt_concat(base, delim, suffix):
    return base + ((delim + suffix) if suffix else "")


# Somehow I couldn't find a decent string hash function in the Python libraries (?),
# so this is taken from
# https://referencesource.microsoft.com/#mscorlib/system/string.cs,0a17bbac4851d0d4
def hash_str(string):
    mod_value = 0x1_0000_0000
    hash1 = hash2 = 5381
    index = 0
    length = len(string)
    lengthMinus1 = length - 1
    while index < lengthMinus1:
        hash1 = (((hash1 << 5) + hash1) ^ ord(string[index])) % mod_value
        hash2 = (((hash2 << 5) + hash2) ^ ord(string[index + 1])) % mod_value
        index += 2
    if index < length:
        hash1 = (((hash1 << 5) + hash1) ^ ord(string[index])) % mod_value
    return (hash1 + (hash2 * 1566083941)) % mod_value


# Represents a range with inclusive start and exclusive end -- [start, end)
class Range:
    def __init__(self, start, end=None):
        self.start = start
        self.end = end if end is not None else start + 1

    def empty(self):
        return self.start == self.end

    def size(self):
        return self.end - self.start

    # checks if 'candidate' is a valid starting point after 'previous' plus this range
    # (i.e., candidate in [previous+start, previous_end)
    def is_valid_candidate(self, previous, candidate):
        return (previous + self.start) <= candidate < (previous + self.end)

    def __eq__(self, other):
        return (self.start, self.end) == (other.start, other.end)

    def __str__(self):
        return "[{}, {})".format(self.start, self.end)

    def __repr__(self):
        return "Range({}, {})".format(repr(self.start), repr(self.end))


# A fake implementation of ProcessPoolExecutor that blocks (and therefore runs
# everything sequentially).  It makes debugging and stack traces a bit simpler
# and is used by default by the canon tools when --jobs=1.
class FakeExecutor:
    class Future:
        def __init__(self, result):
            self._result = result

        def result(self):
            return self._result

        def add_done_callback(self, function):
            function(self)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        return False

    def submit(self, function, *args):
        return FakeExecutor.Future(function(*args))

    def shutdown(self, wait):
        pass


# Stopwatch for gathering timing measurements
class Stopwatch:
    def __init__(self, name):
        self.name = name
        self._start = None
        self._total = 0

    def start(self):
        assert not self._start
        self._start = time.monotonic()
        pass

    def stop(self):
        assert self._start
        self._total = self._total + time.monotonic() - self._start
        self._start = None
        pass

    def add(self, stopwatch):
        self._total = self._total + stopwatch._total

    def total(self):
        return self._total

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()
        return False


# Used to provide indented logging for a function.
#
# Unfortunately, I don't know a good way to specify arguments.  Options implemented here:
# - If the argument is an 'int', then the value of that positional argument is used
# - If the argument is an (int, str) tuple, then the positional argument is checked,
#   but if it does not exist, then the named argument given by the string is used.
# "arguments" here mean at the -call site-.  Named arguments in a function definition
# can be passed either way.
#
# Note that this is tied to canon details - it uses "self.config.debug" and
# "self.config.indent", so it probably doesn't belong in this file.
def indent_decorator(format, *args):
    def indenter(func):
        def impl(original_self, *original_args, **original_kvargs):
            def get_format_args(*original_args, **original_kvargs):
                format_args = []
                for i in args:
                    if type(i) is int:
                        format_args.append(original_args[i])
                    elif i[0] < len(original_args):
                        format_args.append(original_args[i[0]])
                    else:
                        format_args.append(original_kvargs[i[1]])
                return format_args

            format_args = []
            if original_self.config.debug:
                format_args = get_format_args(*original_args, **original_kvargs)
            with original_self.config.indent(format, *format_args):
                try:
                    return func(original_self, *original_args, **original_kvargs)
                except:
                    format_args = get_format_args(*original_args, **original_kvargs)
                    print("unwind: ", format.format(*format_args))
                    raise

        return impl

    return indenter
