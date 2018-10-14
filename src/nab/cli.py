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
    opts.paths = get_path_tuples(opts.paths, results)

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

        # Run phase.
        with open_files(ipath, opath, epath) as fhs:

            # File-begin phase.
            ifh, ofh, efh = fhs
            ln._set_path(ipath, opath, epath, ifh, ofh, efh)
            execute_phase(opts.steps, 'file_begin')

            for line in ifh:
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
            execute_phase(opts.steps, 'file_end')
            ln._set_path(None, None, None, None, None, None)

class Line(object):
    # A class to hold one line's worth of data as it travels
    # through the processing pipeline. The whole program uses
    # a single Line instance and simply resets attributes
    # as we go from file to file and line to line.

    def __init__(self):
        self.input_path    = None
        self.output_path   = None
        self.error_path    = None
        self.input_fh      = None
        self.output_fh     = None
        self.error_fh      = None
        self.original_line = None
        self.val           = None
        self.line_num      = 0
        self.overall_num   = 0

    def _set_path(self, ipath, opath, epath, ifh, ofh, efh):
        self.input_path    = ipath
        self.output_path   = opath
        self.error_path    = epath
        self.input_fh      = ifh
        self.output_fh     = ofh
        self.error_fh      = efh
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
def open_files(ipath, opath, epath):
    # A context manager that allow code reading from either
    # a file or STDIN to have the same structure.
    #
    # x   | stdin | stdout | stderr | f1 | f2 | f3
    # --------------------------------------------
    # in  | Y     | .      | .      | Y  | .  | .
    # out | .     | Y      | .      | Y* | Y  | .
    # err | .     | Y      | Y      | Y* | Y  | Y
    #
    # Where * means replace the input file.
    #
    ipath, ifh = ipath
    opath, ofh = opath
    epath, efh = epath
    ifh = open(ipath) if ipath else sys.stdin
    ofh = open(opath) if opath else sys.stdout
    efh = open(epath) if epath else sys.stderr
    try:
        yield (ifh, ofh, efh)
    finally:
        if ipath is not None: ifh.close()
        if opath is not None: ofh.close()
        if epath is not None: efh.close()

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

def get_path_tuples(orig_paths, phase_results):
    # First get the new paths, if any, returned by the discover phase.
    # Then either use those or the original paths from the command line.
    new_paths = list(filter(None, phase_results))
    paths = new_paths[-1] if new_paths else orig_paths

    # Handle STDIN-only use case.
    if paths == ['-'] or not paths:
        paths = [None]

    # Convert that list of paths to 3-tuples.
    return [path2tuple(p) for p in paths]

def path2tuple(p):
    # Wrap the path in a list, ensure 3 elements, and return as tuple.
    if p is None or isinstance(p, str):
        xs = [p, None, None]
    else:
        xs = list(p)
        n = len(xs)
        maxn = 3
        if n > maxn:
            msg = 'Path-tuple cannot have more than 3 element'
            raise ValueError(msg)
        elif n < maxn:
            xs.extend([None] * (maxn - n))
    return tuple((x, None) for x in xs)


class File(object):

    STREAMS = {
        'in':  ('STDIN',  sys.stdin),
        'out': ('STDOUT', sys.stdout),
        'err': ('STDERR', sys.stdout),
    }

    def __init__(self, stream, path = None, fh = None):
        # Make sure the stream name is valid.
        if stream in self.STREAMS:
            self.stream = stream
        else:
            msg = 'Invalid stream name: {}'.format(stream)
            raise ValueError(msg)
        # Set other attributes.
        if fh:
            self.path = path
            self.fh = fh
            self.should_close = False
        elif path:
            self.path = path
            self.fh = None
            self.should_close = True
        else:
            path, fh = self.STREAMS[stream]
            self.path = path
            self.fh = fh
            self.should_close = False

    def open(self):
        if not self.fh:
            self.fh = open(self.path)

    def close(self):
        if self.fh and self.should_close:
            self.fh.close()

Stdin = File('in')
Stdout = File('out')
Stderr = File('err')

