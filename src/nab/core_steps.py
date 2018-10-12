from __future__ import absolute_import, unicode_literals, print_function

import collections
import json
import random
import re

from .step import Step

####
# Printing and writing.
####

class Pr(Step):

    def run(self, opts, ln):
        if ln.val is not None:
            print(ln.val)
        return ln.val

class Wr(Step):

    def run(self, opts, ln):
        if ln.val is not None:
            print(ln.val, end = '')
        return ln.val

####
# Chomping and stripping.
####

class Chomp(Step):

    def run(self, opts, ln):
        ln.val = ln.val.rstrip('\n')
        return ln.val

class Strip(Step):

    OPTS_CONFIG = [
        's',
        dict(nargs = '?'),
    ]

    def run(self, opts, ln):
        ln.val = ln.val.strip(opts.s)
        return ln.val

class LStrip(Step):

    OPTS_CONFIG = Strip.OPTS_CONFIG

    def run(self, opts, ln):
        ln.val = ln.val.lstrip(opts.s)
        return ln.val

class RStrip(Step):

    OPTS_CONFIG = Strip.OPTS_CONFIG

    def run(self, opts, ln):
        ln.val = ln.val.rstrip(opts.s)
        return ln.val

####
# Splitting and joining.
####

class Split(Step):

    OPTS_CONFIG = [
        'rgx',
        dict(),
    ]

    def begin(self, opts):
        opts.rgx = re.compile(opts.rgx)

    def run(self, opts, ln):
        return opts.rgx.split(ln.val)

class Join(Step):

    OPTS_CONFIG = [
        'j',
        dict(),
    ]

    def run(self, opts, ln):
        return opts.j.join(ln.val)

####
# Indexing.
####

class Index(Step):

    OPTS_CONFIG = [
        'i',
        dict(type = int),
        '--strict',
        dict(action = 'store_true'),
    ]

    def run(self, opts, ln):
        try:
            return ln.val[opts.i]
        except IndexError:
            if opts.strict:
                raise
            else:
                return None

class RIndex(Index):

    def begin(self, opts):
        opts.i = - opts.i

class Range(Index):

    OPTS_CONFIG = [
        'i',
        dict(type = int),
        'j',
        dict(type = int),
        's',
        dict(nargs = '?', type = int, default = None),
    ]

    def run(self, opts, ln):
        return ln.val[opts.i : opts.j : opts.s]

####
# Head.
####

class Head(Step):

    OPTS_CONFIG = [
        'n',
        dict(type = int),
    ]

    def run(self, opts, ln):
        if ln.line_num <= opts.n:
            return ln.val

class Skip(Step):

    OPTS_CONFIG = [
        'n',
        dict(type = int),
    ]

    def run(self, opts, ln):
        if ln.line_num > opts.n:
            return ln.val

####
# Prefix, suffix, and trailing newline.
####

class Nl(Step):

    def run(self, opts, ln):
        v = ln.val
        return v if v.endswith('\n') else v + '\n'

class Prefix(Step):

    OPTS_CONFIG = [
        'pre',
        dict(),
    ]

    def run(self, opts, ln):
        return opts.pre + ln.val

class Suffix(Step):

    OPTS_CONFIG = [
        'suff',
        dict(),
    ]

    def run(self, opts, ln):
        return ln.val + opts.suff

####
# Frequencies.
####

class Freq(Step):

    def begin(self, opts):
        opts.freq = collections.Counter()

    def run(self, opts, ln):
        opts.freq[ln.val] += 1

    def end(self, opts):
        for k in sorted(opts.freq):
            msg = '{}: {}'.format(k, opts.freq[k])
            print(msg)

####
# Sum.
####

class Sum(Step):

    def begin(self, opts):
        opts.sum = 0

    def run(self, opts, ln):
        opts.sum += ln.val

    def end(self, opts):
        print(opts.sum)

####
# Basic conversions: str, int, float.
####

class Int(Step):

    def run(self, opts, ln):
        return str(ln.val)

class Int(Step):

    def run(self, opts, ln):
        return int(float(ln.val))

class Float(Step):

    def run(self, opts, ln):
        return float(ln.val)

####
# Regex substitution and findall.
####

class Sub(Step):

    OPTS_CONFIG = [
        'rgx',
        dict(),
        'repl',
        dict(),
        '-n',
        dict(type = int, default = 0),
        '-f',
        dict(action = 'store_true'),
    ]

    def begin(self, opts):
        opts.rgx = re.compile(opts.rgx)
        if opts.f:
            code = 'def repl(m):\n    {}'.format(opts.repl)
            d = {}
            exec(code, globals(), d)
            opts.repl = d['repl']

    def run(self, opts, ln):
        return opts.rgx.sub(opts.repl, ln.val, count = opts.n)

class FindAll(Step):

    OPTS_CONFIG = [
        'rgx',
        dict(),
    ]

    def begin(self, opts):
        opts.rgx = re.compile(opts.rgx)

    def run(self, opts, ln):
        return opts.rgx.findall(ln.val)

####
# Run user-supplied code.
####

class Run(Step):

    OPTS_CONFIG = [
        'code',
        dict(),
    ]

    def begin(self, opts):
        fmt = 'def run(ln, opts):\n   {}\n'
        code = fmt.format(opts.code)
        exec(code, globals())
        return dict(run = run_run)

####
# JSON dumping.
####

class JsonD(Step):

    OPTS_CONFIG = [
        '-i',
        dict(type = int, default = 4),
    ]

    def run(self, opts, ln):
        d = json.loads(ln.val)
        return json.dumps(d, indent = opts.i)

