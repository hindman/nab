from __future__ import absolute_import, unicode_literals, print_function

def getitem(xs, i, default = None):
    # A non-raising __getitem__().
    try:
        return xs[i]
    except (IndexError, KeyError):
        return default

def getnext(it, default = None):
    # A non-raising next().
    try:
        return next(it)
    except StopIteration:
        return default

def iff(pred, t = True, f = False):
    return t if pred else f

class ValIter(object):

    def __init__(self, xs):
        self.it = iter(xs)
        self.step_index = None

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.it)

    def next(self):
        return self.__next__()

class Meta(object):
    # A class to hold metadata about the line and file
    # from which the current val came. The program uses
    # a single Meta instance and simply resets attributes
    # as we go from file to file and line to line.

    def __init__(self):
        # FileHandle instances.
        self.inp = None
        self.out = None
        self.err = None
        # The original line from which the current val arose.
        self.orig = None
        # Line numbers: within current file and overall.
        self.line_num = 0
        self.overall_num = 0
        # File numbers: current number and overall total.
        self.file_num = 0
        self.n_files = None

    def _set_n_files(self, n):
        self.n_files = n

    def _set_path(self, inp, out, err):
        self.inp = inp
        self.out = out
        self.err = err
        self.orig = None
        self.line_num = 0
        self.file_num += 1

    def _unset_path(self):
        self.inp = None
        self.out = None
        self.err = None
        self.orig = None
        self.line_num = 0

    def _set_line(self, line):
        self.orig = line
        self.line_num += 1
        self.overall_num += 1

    @property
    def is_last_file(self):
        return self.n_files == self.file_num

