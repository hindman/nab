####
# Imports and constants.
####

from __future__ import absolute_import, unicode_literals, print_function

import argparse
import sys
import collections

from .core_steps import *   # TODO: fix.
from .step import Step
from .version import __version__

STDIN = 'STDIN'

####
# Entry point.
####

def main(args = None):

    # Parse command-line arguments and handle --help.
    args = sys.argv[1:] if args is None else args
    opts = parse_args(args)
    if opts.help:
        print_help(opts)
        exit(0)

    # Run BEGIN code. Although most begin hooks return nothing, it can return a
    # dict, is used to create a modified Action. This allow a begin hook to
    # define its run hook dynamically.
    for i, a in enumerate(opts.actions):
        if a.begin:
            d = a.begin(a.opts)
            if d:
                ad = a._asdict()
                ad.update(d)
                opts.actions[i] = Action(*ad.values())

    # Process lines.
    for ln in process_lines(opts):
        if opts.auto_print and ln.val is not None:
            print(ln.val, end = '')

    # Run END code.
    for a in opts.actions:
        if a.end:
            a.end(a.opts)

def print_help(opts):
    msg = 'Usage: m [--help] ACTION... -- [PATH...]'
    print(msg)
    print('\nActions:')
    for aname in opts.valid_actions:
        print('  ' + aname)

####
# CLI argument parsing.
####

def parse_args(orig_args):

    # Initialize the top-level Opts data structure.
    opts = Opts(
        help = False,
        auto_print = True,
        actions = [],
        paths = [],
        valid_actions = get_known_actions(),
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

    # Get indexes of --action.
    js = [
        i
        for i, a in enumerate(args)
        if a in ('--action', '-a')
    ]

    # Convert that list of a list of index pairs ready for use as a range.
    pairs = [(getitem(js, i), getitem(js, i + 1)) for i in range(len(js))]

    # Split the args into a dict mapping each action name to its list of args.
    action_args = {
        args[i + 1] : args[i + 2 : j]
        for i, j in pairs
    }

    def create_action(aname, xs):
        ad = get_action_def(aname)
        ap = get_opt_parser(ad.configs, aname)
        d = vars(ap.parse_args(xs))
        a = Action(aname, ap, Opts(**d), *ad)
        return a

    # Parse each actions options.
    autoline = False
    for aname, xs in action_args.items():

        if aname == 'anl':
            autoline = True
            continue

        if aname not in opts.valid_actions:
            msg = 'Invalid action: {}'.format(aname)
            exit(2, msg)

        a = create_action(aname, xs)
        opts.actions.append(a)

    if autoline:
        a1 = create_action('chomp', [])
        a2 = create_action('nl', [])
        opts.actions = [a1] + opts.actions + [a2]

    return opts

def get_opt_parser(configs, aname = None):
    prog = '--action {}'.format(aname) if aname else None
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

    def __str__(self):
        d = {k : v for k, v in vars(self).items() if k != '_parser'}
        return str(d)

####
# Action discovery.
####

ACTION_DEF_ATTRS = ('configs', 'begin', 'run', 'end')
ACTION_ATTRS = ('name', 'parser', 'opts') + ACTION_DEF_ATTRS

ActionDef = collections.namedtuple('ActionDef', ACTION_DEF_ATTRS)
Action = collections.namedtuple('Action', ACTION_ATTRS)

def get_known_actions():
    U = '_'
    tups = [k.rsplit(U, 1) for k in globals() if U in k]
    return sorted(set(
        name for name, suffix in tups
        if suffix in ('begin', 'run', 'end')
    ))

def get_action_def(aname):
    d = globals()
    return ActionDef(
        d.get(aname + '_opts', []),
        d.get(aname + '_begin', None),
        d.get(aname + '_run', None),
        d.get(aname + '_end', None),
    )

####
# Line processing.
####

def process_lines(opts):
    for ln in read_lines(opts):
        for a in opts.actions:
            if a.run:
                try:
                    ln.val = a.run(ln, a.opts)
                except Exception:
                    sys.stderr.write('Action error:\n')
                    sys.stderr.write('  path: {}\n'.format(ln.path))
                    sys.stderr.write('  overall_num: {}\n'.format(ln.overall_num))
                    sys.stderr.write('  line_num: {}\n'.format(ln.line_num))
                    sys.stderr.write('  original_line: {!r}\n'.format(ln.original_line))
                    sys.stderr.write('  val: {!r}\n'.format(ln.val))
                    raise
            if ln.val is None:
                break
        yield ln

def read_lines(opts):
    ln = Line()
    if opts.paths and opts.paths != ['-']:
        for p in opts.paths:
            ln.set_path(p)
            with open(p) as fh:
                for line in fh:
                    ln.set_line(line)
                    yield ln
    else:
        ln.set_path(STDIN)
        for line in sys.stdin:
            ln.set_line(line)
            yield ln

class Line(object):
    # A class to hold one line's worth of data as it travels
    # through the processing pipeline.

    def __init__(self):
        self.path = None
        self.original_line = None
        self.val = None
        self.line_num = 0
        self.overall_num = 0

    def set_path(self, path):
        self.line_num = 0
        self.path = path

    def set_line(self, line):
        self.line_num += 1
        self.overall_num += 1
        self.original_line = line
        self.val = line

####
# General helpers.
####

def getitem(xs, i, default = None):
    try:
        return xs[i]
    except Exception:
        return default

def exit(code, msg = None):
    fh = sys.stderr if code else sys.stdout
    if msg:
        msg = msg if msg.endswith('\n') else msg + '\n'
        fh.write(msg)
    sys.exit(code)

