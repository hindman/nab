####
# Imports and constants.
####

from __future__ import absolute_import, unicode_literals, print_function

from inspect import getmembers, isclass
import argparse
import collections
import os
import random
import string
import sys

if sys.version_info >= (3, 5):
    from importlib.util import spec_from_file_location, module_from_spec
elif sys.version_info >= (3, 3):
    from importlib.machinery import SourceFileLoader
else:
    from imp import load_source

from . import core_steps
from .step import Step
from .helpers import getitem, getnext, ValIter
from .version import __version__

####
# Entry point.
####

def main(args = None):

    # Parse command-line arguments.
    args = sys.argv[1:] if args is None else args
    opts = parse_args(args)
    if opts.help:
        print_help(opts)
        exit(0)

    # Begin phase.
    execute_phase(opts.steps, 'begin')

    # Discover phase.
    discover_results = execute_phase(opts.steps, 'discover')
    opts.fsets = get_file_sets(opts.paths, discover_results)
    opts.ln._set_n_files(len(opts.fsets))

    # Initialize, process, and finalize phases.
    process_lines(opts)

    # End phase.
    execute_phase(opts.steps, 'end')

def print_help(opts):
    msg = 'Usage: m [--help] STEP... -- [PATH...]'
    print(msg)
    print('\nSteps:')
    for sname in opts.valid_steps:
        print('  ' + sname)

####
# CLI argument parsing.
####

def parse_args(orig_args):
    # Example:
    #
    #   CLI input = nab -s split '\s+' -s head 12 -s pr -- A B C
    #   orig_args =     -s split '\s+' -s head 12 -s pr -- A B C
    #   args      =     -s split '\s+' -s head 12 -s pr
    #   indexes   =     0              3          6
    #   pairs     =    (0, 3)         (3, 6)     (6, None)

    # Initialize the top-level Opts data structure.
    opts = Opts(
        help = False,
        steps = [],
        paths = [],
        fsets = [],
        valid_steps = get_known_steps(),
        ln = Line(),
    )

    # Handle --help (it can appear anywhere).
    val = '--help'
    args = list(orig_args)
    args = [a for a in args if a != val]
    opts.help = len(orig_args) > len(args)

    # Handle paths (must appear at the end, after the `--` marker).
    val = '--'
    if val in args:
        i = args.index(val)
        opts.paths = args[i + 1:]
        args[i:] = []

    # Get indexes of --step.
    js = [
        i
        for i, a in enumerate(args)
        if a in ('--step', '-s')
    ]

    # Convert that list of a list of index pairs ready for use as a range.
    pairs = [
        (getitem(js, i), getitem(js, i + 1))
        for i in range(len(js))
    ]

    # Use those index pairs to disassemble the full list of args into
    # a list of (STEP_NAME, STEP_ARGS) tuples.
    step_args = [
        (args[i + 1], args[i + 2 : j])
        for i, j in pairs
    ]

    # For each step, create an instance and parse its options.
    # Add that instance to opts.steps.
    for i, (sname, xs) in enumerate(step_args):
        if sname in opts.valid_steps:
            # Get the step class.
            cls = opts.valid_steps[sname]
            # Parse the step's args.
            ap = get_opt_parser(cls.OPTS_CONFIG or [], sname)
            d = vars(ap.parse_args(xs))
            sopts = Opts(**d)
            # Create the instance and store it.
            step = cls(sid = i + 1, name = sname, opts = sopts, ln = opts.ln)
            opts.steps.append(step)
        else:
            msg = 'Invalid step: {}'.format(sname)
            exit(2, msg)

    return opts

def get_opt_parser(configs, sname = None):
    prog = '--step {}'.format(sname) if sname else None
    ap = argparse.ArgumentParser(add_help = False, prog = prog)
    xs = []
    for obj in configs:
        if isinstance(obj, dict):
            ap.add_argument(*xs, **obj)
            xs = []
        else:
            xs.append(obj)
    return ap

class Opts(object):
    # A class to hold command-line option values.

    def __init__(self, **kws):
        for k, v in kws.items():
            setattr(self, k, v)

    def __getitem__(self, k):
        return getattr(self, k)

    def __repr__(self):
        d = {
            k : v
            for k, v in vars(self).items()
            if k != '_parser'
        }
        return str(d)

    def __str__(self):
        return repr(self)

####
# Line processing.
####

def process_lines_OLD(opts):
    # Setup.
    STEP_ERROR_FMT = '\n'.join((
        'Step error:',
        '  inp: {}',
        '  out: {}',
        '  err: {}',
        '  overall_num: {}',
        '  line_num: {}',
        '  orig: {!r}',
        '  val: {!r}',
        '',
    ))
    # steps_with_process = [
    #     s
    #     for s in opts.steps
    #     if step_has_phase(s, 'process')
    # ]
    steps_with_process = opts.steps
    ln = opts.ln

    # Process each input file.
    for fset in opts.fsets:

        # Process phase.
        with fset:

            # Initialize phase.
            ln._set_path(fset.inp, fset.out, fset.err)
            execute_phase(opts.steps, 'initialize')

            for line in fset.inp.handle:
                ln._set_line(line)
                for s in steps_with_process:
                    try:
                        ln.val = s.process(s.opts, ln)
                    except Exception:
                        msg = STEP_ERROR_FMT.format(
                            ln.inp.path,
                            ln.out.path,
                            ln.err.path,
                            ln.overall_num,
                            ln.line_num,
                            ln.orig,
                            ln.val,
                        )
                        sys.stderr.write(msg)
                        raise
                    if ln.val is None:
                        break

            # Finalize phase.
            execute_phase(opts.steps, 'finalize')
            ln._unset_path()

def process_lines(opts):
    try:
        do_process_lines(opts)
    finally:
        for fset in opts.fsets:
            fset.close_handles()

def do_process_lines(opts):

    ln = opts.ln
    max_i = len(opts.steps) - 1

    # We will use a stack with 4 types of data and will continue
    # until the stack is empty:
    #
    # - FileSetCollection: An iterable of FileSet.
    # - FileSet: An iterable of input vals (plus other stuff too).
    # - ValIter: An iterable of values (returned by a step).
    # - Val: A val and the index of the step to which it should be passed.
    #
    # We bootstrap the stack with the FileSetCollection.
    #
    # Every conditional branch is either terminal (meaning an iterator is
    # exhausted or no further processing is needed for a val) or we should add
    # one or multiple items to the stack -- multiple in cases where we get
    # a non-null value from a still-alive iterator (in that case, we add
    # both the iterator and a Val of the value).
    #
    stack = [FileSetCollection(opts.fsets)]
    while stack:

        # Get the next item from the stack.
        item = stack.pop()

        # Val or FinalVal: either run the val through the step's process()
        # method, or call the steps finalize() method. Either way, values
        # returned will flow through the process() methods of downstream steps.
        if isinstance(item, (Val, FinalVal)):

            # Unpack the Val/FinalVal.
            val = item
            i = val.step_index
            s = opts.steps[i]

            # Call process() or finalize().
            ln.val = val.val
            method = s.process if isinstance(item, Val) else s.finalize
            v = method(s.opts, ln)
            ln.val = v

            # Decide what to add to the stack.
            if i >= max_i:
                # There are no downstream steps: we are done with this val.
                pass
            elif v is None:
                # Got a null value: no need to pass it to downstream steps.
                pass
            elif isinstance(v, ValIter):
                # Got a ValIter: set its step_index.
                vit = v
                vit.step_index = i + 1
                stack.append(vit)
            else:
                # Got some other value: prepare it for the next downstream step.
                val2 = Val(v, i + 1)
                stack.append(val2)

        # ValIter: get the next value from it.
        elif isinstance(item, ValIter):
            vit = item
            v = getnext(vit)
            if v is None:
                pass
            else:
                val = Val(v, vit.step_index)
                stack.extend((vit, val))

        # FileSet: get the next line from its input.
        elif isinstance(item, FileSet):
            fset = item
            line = getnext(fset)
            if line is None:
                # Finalize phase.
                stack.extend(FinalVal(None, i) for i in reversed(range(max_i + 1)))
                ln._unset_path()
                # Close file handles.
                fset.close_handles()

            else:
                ln._set_line(line)
                val = Val(line, 0)
                stack.extend((fset, val))

        # FileSetCollection: get the next FileSet.
        elif isinstance(item, FileSetCollection):
            fcoll = item
            fset = getnext(fcoll)
            if fset is None:
                pass
            else:
                # Open file handles.
                fset.open_handles()
                # Initialize phase.
                ln._set_path(fset.inp, fset.out, fset.err)
                execute_phase(opts.steps, 'initialize')
                # Add to stack.
                stack.extend((fcoll, fset))

        else:
            assert False, 'Should never happen'

####
# General helpers.
####

def get_known_steps():
    mods = [core_steps] + get_user_step_modules()
    return {
        x.NAME or name.lower() : x
        for m in mods
        for name, x in getmembers(m)
        if isclass(x)
        and issubclass(x, Step)
        and x is not Step
    }

def get_user_step_modules():
    s = os.environ.get('NAB_MODULES', None)
    if s:
        return [
            import_from_path(p)
            for p in s.split(os.pathsep)
            if os.path.isfile(p)
        ]
    else:
        return []

def import_from_path(path):
    # Takes a string file path. Returns the imported module.
    name = os.path.basename(os.path.splitext(path)[0])
    if sys.version_info >= (3,5):
        spec = spec_from_file_location(name, path)
        m = module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    elif sys.version_info >= (3,3):
        return SourceFileLoader(name, path).load_module()
    else:
        return load_source(name, path)

def exit(code, msg = None):
    fh = sys.stderr if code else sys.stdout
    if msg is not None:
        msg = msg if msg.endswith('\n') else msg + '\n'
        fh.write(msg)
    sys.exit(code)

def step_has_phase(step, phase):
    return (
        phase in vars(step.__class__) or
        phase in vars(step)
    )

def execute_phase(steps, phase):
    results = []
    for s in steps:
        if step_has_phase(s, phase):
            f = getattr(s, phase)
            r = f(s.opts, s.ln)
        else:
            r = None
        results.append(r)
    return results

def get_file_sets(orig_paths, discover_results):
    # First get the new paths, if any, returned by the discover phase.
    # Then either use those or the original paths from the command line.
    new_paths = list(filter(None, discover_results))
    paths = new_paths[-1] if new_paths else orig_paths

    # Handle STDIN-only use case.
    if paths == ['-'] or not paths:
        paths = [None]

    # Convert that list of paths to 3-tuples.
    return [FileSet.new(p) for p in paths]

def padded_tuple(obj, padn):
    # Wrap or convert to a tuple.
    if obj is None or isinstance(obj, str):
        xs = (obj,)
    else:
        xs = tuple(obj)
    # Pad to desired length.
    n = len(xs)
    if n == padn:
        return xs
    elif n < padn:
        return xs + (None,) * (padn - n)
    else:
        raise ValueError('tuple too large')

class FileSet(object):

    INP = 'inp'
    OUT = 'out'
    ERR = 'err'

    STREAMS = {
        INP: (':STDIN:', sys.stdin, 'r'),
        OUT: (':STDOUT:', sys.stdout, 'w'),
        ERR: (':STDERR:', sys.stdout, 'w'),
    }

    @classmethod
    def new(cls, obj):
        xs = padded_tuple(obj, 3)
        return FileSet(*xs)

    def __init__(self, inp, out = None, err = None):
        self.inp = self.new_fh(self.INP, inp)
        self.out = self.new_fh(self.OUT, out)
        self.err = self.new_fh(self.ERR, err)

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return '{}({!r}, {!r}, {!r})'.format(
            self.__class__.__name__,
            self.inp.path,
            self.out.path,
            self.err.path,
        )

    def new_fh(self, stream, obj):
        if stream in self.STREAMS:
            path, handle = padded_tuple(obj, 2)
            mode = self.STREAMS[stream][2]
            return (
                FileHandle(path, handle, mode) if (handle or path) else
                FileHandle(path, None, mode) if path else
                FileHandle(*self.STREAMS[stream])
            )
        else:
            raise ValueError('Invalid stream: {}'.format(stream))

    def open_handles(self):

        # For input, output, and error, open files for either reading or
        # or writing -- unless the user already supplied file handles.

        # Convenience vars for the FileHandle instances.
        ifh = self.inp
        ofh = self.out
        efh = self.err

        # Whether the user supplied an opened handle for them.
        ib, ob, eb = [bool(fh.handle) for fh in (ifh, ofh, efh)]

        # Input.
        if not ib:
            # Just open the file.
            self.open_fh(ifh)

        # Output.
        if not ob:
            # Open either the file or a temp file -- the latter
            # if the input/output paths are the same.
            self.open_or_temp(ofh, ifh)

        # Error.
        if not eb:
            if not ob:
                # If we had to open an output file (above), either open the
                # error file or reuse the output handle -- the latter if
                # output/error paths are the same.
                self.open_or_reuse(efh, ofh)
            else:
                # Open either the file or a temp file -- the latter
                # if the input/error paths are the same.
                self.open_or_temp(efh, ifh)

    def close_handles(self, *xs):
        for fh in (self.inp, self.out, self.err):
            if fh.should_close and fh.handle:
                fh.handle.close()

    def open_fh(self, fh, path = None):
        fh.handle = open(path or fh.path, fh.mode)

    def open_or_reuse(self, fh, other):
        if fh.path == other.path:
            fh.handle = other.handle
        else:
            self.open_fh(self, fh)

    def open_or_temp(self, fh, other):
        if fh.path == other.path:
            fh.temp_path = temp_file_path()
            self.open_fh(fh, path = fh.temp_path)
        else:
            self.open_fh(fh)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.inp.handle)

def temp_file_path(n = 15):
    suffix = ''.join(random.choices(string.ascii_lowercase, k = n))
    return '/tmp/nab-' + suffix

class FileHandle(object):

    def __init__(self, path, handle = None, mode = None):
        if not path:
            raise ValueError('FileHandle.path is required')
        self.path = path
        self.handle = handle
        self.mode = mode
        self.should_close = not handle
        self.temp_path = None

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return '{}({!r})'.format(
            self.__class__.__name__,
            self.path,
        )

class Line(object):
    # A class to hold one line's worth of data as it travels
    # through the processing pipeline. The whole program uses
    # a single Line instance and simply resets attributes
    # as we go from file to file and line to line.

    def __init__(self):
        self.inp = None
        self.out = None
        self.err = None
        self.orig = None
        self.val = None
        self.line_num = 0
        self.overall_num = 0
        self.file_num = 0
        self.n_files = None

    def _set_n_files(self, n):
        self.n_files = n

    def _set_path(self, inp, out, err):
        self.inp = inp
        self.out = out
        self.err = err
        self.orig = None
        self.val = None
        self.line_num = 0
        self.file_num += 1

    def _unset_path(self):
        self.inp = None
        self.out = None
        self.err = None
        self.orig = None
        self.val = None
        self.line_num = 0

    def _set_line(self, line):
        self.orig = line
        self.val = line
        self.line_num += 1
        self.overall_num += 1

    @property
    def is_last_file(self):
        return self.n_files == self.file_num

class FileSetCollection(object):

    def __init__(self, files):
        self.it = iter(files)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.it)

Val = collections.namedtuple('Val', 'val step_index')
FinalVal = collections.namedtuple('FinalVal', 'val step_index')

