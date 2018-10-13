####
# Imports and constants.
####

from __future__ import absolute_import, unicode_literals, print_function

from contextlib import contextmanager
from inspect import getmembers, isclass
import argparse
import collections
import sys

from . import core_steps
from .step import Step
from .version import __version__

STDIN = 'STDIN'

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
    results = execute_phase(opts.steps, 'discover')
    paths = list(filter(None, results))
    if paths:
        opts.paths = paths[-1]
    opts.paths = (
        [(STDIN, None, None)] if not opts.paths else
        [(STDIN, None, None)] if opts.paths == ['-'] else
        [p if isinstance(p, tuple) else (p, None, None) for p in opts.paths]
    )

    # File-begin, run, and file-end phases.
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

def process_lines(opts):
    # Setup.
    STEP_ERROR_FMT = '\n'.join((
        'Step error:',
        '  input_path: {}',
        '  outut_path: {}',
        '  error_path: {}',
        '  overall_num: {}',
        '  line_num: {}',
        '  original_line: {!r}',
        '  val: {!r}',
        '',
    ))
    steps_with_run = [
        s
        for s in opts.steps
        if step_has_phase(s, 'run')
    ]
    ln = opts.ln

    # Process each input file.
    for ipath, opath, epath in opts.paths:

        # File-begin phase.
        ln._set_path(ipath, opath, epath)
        execute_phase(opts.steps, 'file_begin', ln)

        # Run phase.
        with open_file(ipath) as fh:
            for line in fh:
                ln._set_line(line)
                for s in steps_with_run:
                    try:
                        ln.val = s.run(s.opts, ln)
                    except Exception:
                        msg = STEP_ERROR_FMT.format(
                            ln.input_path,
                            ln.output_path,
                            ln.error_path,
                            ln.overall_num,
                            ln.line_num,
                            ln.original_line,
                            ln.val,
                        )
                        sys.stderr.write(msg)
                        raise
                    if ln.val is None:
                        break

        # File-end phase.
        execute_phase(opts.steps, 'file_end', ln)
        ln._set_path(None, None, None)

class Line(object):
    # A class to hold one line's worth of data as it travels
    # through the processing pipeline. The whole program uses
    # a single Line instance and simply resets attributes
    # as we go from file to file and line to line.

    def __init__(self):
        self.input_path    = None
        self.output_path   = None
        self.error_path    = None
        self.original_line = None
        self.val           = None
        self.line_num      = 0
        self.overall_num   = 0

    def _set_path(self, ipath, opath, epath):
        self.input_path    = ipath
        self.output_path   = opath
        self.error_path    = epath
        self.original_line = None
        self.val           = None
        self.line_num      = 0

    def _set_line(self, line):
        self.original_line = line
        self.val           = line
        self.line_num      += 1
        self.overall_num   += 1

####
# General helpers.
####

def get_known_steps():
    return {
        x.NAME or name.lower() : x
        for name, x in getmembers(core_steps)
        if isclass(x)
        and issubclass(x, Step)
        and x is not Step
    }

def getitem(xs, i, default = None):
    try:
        return xs[i]
    except Exception:
        return default

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

@contextmanager
def open_file(path):
    # A context manager that allow code reading from either
    # a file or STDIN to have the same structure.
    if path is STDIN:
        fh = sys.stdin
    else:
        fh = open(path)
    try:
        yield fh
    finally:
        if path is not STDIN:
            fh.close()

def execute_phase(steps, phase, *xs):
    results = []
    for s in steps:
        if step_has_phase(s, phase):
            f = getattr(s, phase)
            r = f(s.opts, *xs)
        else:
            r = None
        results.append(r)
    return results

