####
# Imports and constants.
####

from __future__ import absolute_import, unicode_literals, print_function

import argparse
import json
import re
import sys
import collections
import random

STDIN = 'STDIN'

####
# TODO.
####

'''

Next steps:

    - Convert to a proper Python project:

        Unclaimed names:
            nab      | ####
            ax       | .
            pipework | .
            psa      | Python, sed, awk.
            rif      | Short for rifle.
            riff     | Short for riffle.
            saw      | .
            yank     | .

        src/NAME/
            __init__.py
            cli.py
            step.py
            core_steps.py

    - Add support for file-begin file-end.

    - Add support for file-based output and in-place editing.
        - Currently, we can process multiple files as inputs.
        - But the output is a single stream.
        - We might want each input file to go to a separate output file.
        - And we might want in-place editing.

    - Refactor to use a class-based approach.

        - Use "step" rather than "action".

        - Basic structure.

            class Step(object):
                ...

            class Range(Step):

                NAME = '...'

                DESC = '...'

                OPTS = [...]

                def begin(self, opts):
                    ...

                def run(self, ln, opts):
                    return ...

                def end(self, opts):
                    ...

        - Benefits:

            - Some namespacing and code layout benefits: easier to define multiple
            steps in one file.

            - More extensible when adding new features.

            - Steps can inherit from each other.

            - Provides a scope for step-writers to persist information.

    - Action docs.

    - Better --help: show step docs.

    - Some tests.

    - More steps:
        cols
        wrap
        flip-flop
        filename
        linenumber
        tail
        jsond
        dive

    - Also support leading-dot syntax:

        m .skip 1 .head 12 .findall '\d+' .str .nl

    - Switch PATHS to --paths?

    - Decide how to package the project.

'''

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

####
# Actions.
####

# Action: noprint.

def noprint_begin(opts):
    opts.auto_print = False

# Action: strip.

strip_opts = [
    's',
    dict(nargs = '?'),
]

def strip_run(ln, opts):
    ln.val = ln.val.strip(opts.s)
    return ln.val

# Action: lstrip.

lstrip_opts = strip_opts

def lstrip_run(ln, opts):
    ln.val = ln.val.lstrip(opts.s)
    return ln.val

# Action: lstrip.

rstrip_opts = strip_opts

def rstrip_run(ln, opts):
    ln.val = ln.val.rstrip(opts.s)
    return ln.val

# Action: chomp.

def chomp_run(ln, opts):
    ln.val = ln.val.rstrip('\n')
    return ln.val

# Action: split.

split_opts = [
    'rgx',
    dict(),
]

def split_begin(opts):
    opts.rgx = re.compile(opts.rgx)

def split_run(ln, opts):
    return opts.rgx.split(ln.val)

# Action: index.

index_opts = [
    'i',
    dict(type = int),
    '--strict',
    dict(action = 'store_true'),
]

def index_run(ln, opts):
    try:
        return ln.val[opts.i]
    except IndexError:
        if opts.strict:
            raise
        else:
            return None

# Action: rindex.

rindex_opts = index_opts

def rindex_begin(opts):
    opts.i = - opts.i

rindex_run = index_run

# Action: nl.

def nl_run(ln, opts):
    v = ln.val
    return v if v.endswith('\n') else v + '\n'

# Action: cat.

def cat_run(ln, opts):
    return ln.val

# Action: head.

head_opts = [
    'n',
    dict(type = int),
]

def head_run(ln, opts):
    if ln.line_num <= opts.n:
        return ln.val

# Action: prefix.

prefix_opts = [
    'pre',
    dict(),
]

def prefix_run(ln, opts):
    return opts.pre + ln.val

# Action: suffix.

suffix_opts = [
    'suff',
    dict(),
]

def suffix_run(ln, opts):
    return ln.val + opts.suff

# Action: freq.

def freq_run(ln, opts):
    opts.freq[ln.val] += 1

def freq_begin(opts):
    opts.freq = collections.Counter()

def freq_end(opts):
    for k in sorted(opts.freq):
        msg = '{}: {}'.format(k, opts.freq[k])
        print(msg)

# Action: sum.

def sum_run(ln, opts):
    opts.sum += ln.val

def sum_begin(opts):
    opts.sum = 0

def sum_end(opts):
    print(opts.sum)

# Action: int.

def int_run(ln, opts):
    return int(float(ln.val))

# Action: float.

def float_run(ln, opts):
    return float(ln.val)

# Action: sub.

sub_opts = [
    'rgx',
    dict(),
    'repl',
    dict(),
    '-n',
    dict(type = int, default = 0),
    '-f',
    dict(action = 'store_true'),
]

def sub_begin(opts):
    opts.rgx = re.compile(opts.rgx)
    if opts.f:
        code = 'def repl(m):\n    {}'.format(opts.repl)
        d = {}
        exec(code, globals(), d)
        opts.repl = d['repl']

def sub_run(ln, opts):
    return opts.rgx.sub(opts.repl, ln.val, count = opts.n)

# Action: join.

join_opts = [
    'j',
    dict(),
]

def join_run(ln, opts):
    return opts.j.join(ln.val)

# Action: range.

range_opts = [
    'i',
    dict(type = int),
    'j',
    dict(type = int),
    's',
    dict(nargs = '?', type = int, default = None),
]

def range_run(ln, opts):
    return ln.val[opts.i : opts.j : opts.s]

# Action: str.

def str_run(ln, opts):
    return str(ln.val)

# Action: skip.

skip_opts = [
    'n',
    dict(type = int),
]

def skip_run(ln, opts):
    if ln.line_num > opts.n:
        return ln.val

# Action: findall.

findall_opts = [
    'rgx',
    dict(),
]

def findall_begin(opts):
    opts.rgx = re.compile(opts.rgx)

def findall_run(ln, opts):
    return opts.rgx.findall(ln.val)

# Action: run.

run_opts = [
    'code',
    dict(),
]

def run_begin(opts):
    fmt = 'def run_run(ln, opts):\n   {}\n'
    code = fmt.format(opts.code)
    exec(code, globals())
    return dict(run = run_run)

# Action: jsond.

jsond_opts = [
    '-i',
    dict(type = int, default = 4),
]

def jsond_run(ln, opts):
    d = json.loads(ln.val)
    return json.dumps(d, indent = opts.i)

