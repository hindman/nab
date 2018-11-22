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
from .utils import getitem, getnext, ValIter, Meta
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
    for s in opts.steps:
        s.begin(s.opts)

    # Discover phase.
    discover_results = []
    for s in opts.steps:
        r = s.discover(s.opts)
        discover_results.append(r)
    opts.fsets = get_file_sets(opts.paths, discover_results)
    opts.meta._set_n_files(len(opts.fsets))

    # Initialize, process, and finalize phases.
    process_lines(opts)

    # End phase.
    for s in opts.steps:
        s.end(s.opts, opts.meta)

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
        meta = Meta(),
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
            step = cls(sid = i + 1, name = sname, opts = sopts, meta = opts.meta)
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

def process_lines(opts):
    try:
        do_process_lines(opts)
    finally:
        for fset in opts.fsets:
            fset.close_handles()

def do_process_lines(opts):
    # This function executes the process and finalize phases of a nab run.
    # It uses a stack containing various types of data and continues
    # until the stack is empty:
    #
    # - FileSetCollection: An iterable of FileSet. This is always the first
    #   element in the stack (until the iterator is exhausted and we break
    #   out of the while loop).
    #
    # - FileSet: An object holding an input file handle, thus functioning
    #   as an iterator of input lines (a FileSet also holds the output and
    #   error file handles that should be used for an input file, but
    #   those details do not matter here).
    #
    # - Val: A val and the index of the next step to which it should be passed.
    #
    # - ValIter: An iterable of values returned by a step's process() method.
    #   Each val in the iterable will be forwarded to all downstream steps.
    #
    # - FinalVal: A pseudo-val holding a step index. This item in the stack
    #   is the signal to call the step's finalize() method. Any vals returned
    #   by that method are forwarded to the process() method of downstream steps.
    #
    # - Closer: A wrapper holding a FileSet. This item in the stack is the
    #   signal to close the file handles in the FileSet.

    # Setup.
    # - A Convenience var holding the global Meta instance.
    # - The index of the last Step in the run.
    # - A format string for printing information if a Step's process()
    #   or finalize() methods raise an exception.
    meta = opts.meta
    max_i = len(opts.steps) - 1
    error_fmt = '\n'.join((
        '',
        'Step error:',
        '  inp: {}',
        '  out: {}',
        '  err: {}',
        '  overall_num: {}',
        '  line_num: {}',
        '  orig: {!r}',
        '  val: {!r}',
        '',
        '',
    ))

    # Process the stack until the FileSetCollection is exhausted.
    stack = [FileSetCollection(opts.fsets)]
    while stack:

        # Get the next item from the stack.
        item = stack.pop()

        # Val or FinalVal: either run the val through the step's process()
        # method, or call the step's finalize() method. Either way, values
        # returned will flow through the process() methods of downstream steps.
        if isinstance(item, (Val, FinalVal)):

            # Unpack the Val/FinalVal.
            val = item
            i = val.step_index
            s = opts.steps[i]

            # Call process() or finalize().
            try:
                if isinstance(item, Val):
                    v = s.process(s.opts, meta, val.val)
                else:
                    v = s.finalize(s.opts, meta)
            except Exception:
                msg = error_fmt.format(
                    meta.inp.path,
                    meta.out.path,
                    meta.err.path,
                    meta.overall_num,
                    meta.line_num,
                    meta.orig,
                    val.val,
                )
                sys.stderr.write(msg)
                raise

            # Decide what to add to the stack.
            if i >= max_i:
                # There are no downstream steps: we are done with this val.
                pass
            elif v is None:
                # Got a null value: no need to pass it to downstream steps.
                pass
            elif isinstance(v, ValIter):
                # Got a ValIter: set its step_index and add it.
                vit = v
                vit.step_index = i + 1
                stack.append(vit)
            else:
                # Got a value: add it with the index for the next step.
                val2 = Val(v, i + 1)
                stack.append(val2)

        # ValIter: get the next value from the iterator. If the iterator
        # is not exhausted, add both the iterator and a Val to the stack.
        elif isinstance(item, ValIter):
            vit = item
            v = getnext(vit)
            if v is not None:
                val = Val(v, vit.step_index)
                stack.extend((vit, val))

        # FileSet: get the next input line from the file.
        elif isinstance(item, FileSet):
            fset = item
            line = getnext(fset)
            if line is None:
                # The file is exhausted: add a Closer for the FileSet to the
                # stack, followed by a FinalVal for every step. After all
                # finalize() methods are called, the FileSet will be closed.
                stack.append(Closer(fset))
                stack.extend(FinalVal(None, i) for i in reversed(range(max_i + 1)))
            else:
                # We got a line: set up the Meta instance and add both the
                # still-alive FileSet and a Val to the stack.
                meta._set_line(line)
                val = Val(line, 0)
                stack.extend((fset, val))

        # Closer: close the FileSet handles. All of input lines have been run
        # through the process() phase, and the finalize() phase for the FileSet
        # has also been completed.
        elif isinstance(item, Closer):
            fset = item.fset
            meta._unset_path()
            fset.close_handles()

        # FileSetCollection: get the next FileSet; open its handles, prepare
        # the Meta instance, execute the initialize() phase, and then add both
        # the still-alive FileSetCollection and the FileSet to the stack.
        elif isinstance(item, FileSetCollection):
            fcoll = item
            fset = getnext(fcoll)
            if fset is not None:
                fset.open_handles()
                meta._set_path(fset.inp, fset.out, fset.err)
                for s in opts.steps:
                    s.initialize(s.opts, opts.meta)
                stack.extend((fcoll, fset))

        # Sanity check. TODO: raise a NabException of some type.
        else:
            assert False, 'process_lines() got an unexpected data type'

####
# Wrapper objects used by process_lines().
#
# Also used, but defined elsewhere: FileSet and ValIter.
####

Val      = collections.namedtuple('Val', 'val step_index')
FinalVal = collections.namedtuple('FinalVal', 'val step_index')
Closer   = collections.namedtuple('Closer', 'fset')

class FileSetCollection(object):

    def __init__(self, files):
        self.it = iter(files)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.it)

    def next(self):
        return self.__next__()

####
# Utility functions used to process a nab run.
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

####
# FileHandle and FileSet.
####

class FileHandle(object):
    # An object to hold a file handle and metadata associated with it.

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

class FileSet(object):
    # An object holding an input FileHandle and the associated FileHandle
    # instances that should be used when writing to normal or error output for
    # this input FileHandle.
    #
    # The object also functions as an iterator over the lines from the
    # input FileHandle.

    INP = 'inp'
    OUT = 'out'
    ERR = 'err'

    STREAMS = {
        INP: (':STDIN:', sys.stdin, 'r'),
        OUT: (':STDOUT:', sys.stdout, 'w'),
        ERR: (':STDERR:', sys.stdout, 'w'),
    }

    def __init__(self, inp, out = None, err = None):
        self.inp = self.new_fh(self.INP, inp)
        self.out = self.new_fh(self.OUT, out)
        self.err = self.new_fh(self.ERR, err)

    @classmethod
    def new(cls, obj):
        xs = padded_tuple(obj, 3)
        return FileSet(*xs)

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

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return '{}({!r}, {!r}, {!r})'.format(
            self.__class__.__name__,
            self.inp.path,
            self.out.path,
            self.err.path,
        )

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

    def next(self):
        return self.__next__()

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

def temp_file_path(n = 30):
    suffix = ''.join(random.choices(string.ascii_lowercase, k = n))
    return '/tmp/nab-' + suffix

