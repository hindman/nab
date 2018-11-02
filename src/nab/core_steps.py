from __future__ import absolute_import, unicode_literals, print_function

import collections
import json
import random
import re
import functools

from .step import Step

####
# Printing and writing.
####

class Pr(Step):

    def run(self, opts, ln):
        if ln.val is not None:
            self.out(ln.val)
        return ln.val

class Wr(Step):

    def run(self, opts, ln):
        if ln.val is not None:
            self.out(ln.val, end = '')
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
        dict(nargs = '?'),
    ]

    def begin(self, opts, ln):
        opts.rgx = re.compile(opts.rgx) if opts.rgx else None

    def run(self, opts, ln):
        if opts.rgx:
            return opts.rgx.split(ln.val)
        else:
            return ln.val.split()

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

    def begin(self, opts, ln):
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
# Head, skip, etc.
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
# Aggregations.
####

class Freq(Step):

    def begin(self, opts, ln):
        opts.freq = collections.Counter()

    def run(self, opts, ln):
        opts.freq[ln.val] += 1

    def end(self, opts, ln):
        for k in sorted(opts.freq):
            msg = '{}: {}'.format(k, opts.freq[k])
            self.out(msg)

class Sum(Step):

    def begin(self, opts, ln):
        opts.sum = 0

    def run(self, opts, ln):
        opts.sum += ln.val

    def end(self, opts, ln):
        self.out(opts.sum)

####
# Basic conversions: str, int, float.
####

class Str(Step):

    def run(self, opts, ln):
        return str(ln.val)

class Int(Step):

    def run(self, opts, ln):
        return int(float(ln.val))

class Float(Step):

    def run(self, opts, ln):
        return float(ln.val)

####
# Regex substitution, searching, grepping, and findall.
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
        '-i',
        dict(type = int, default = 4),
    ]

    def begin(self, opts, ln):
        opts.rgx = re.compile(opts.rgx)
        if opts.f:
            indent = ' ' * opts.i
            code = 'def _repl(m):\n{}{}'.format(indent, opts.repl)
            d = {}
            exec(code, globals(), d)
            opts.repl = d['_repl']

    def run(self, opts, ln):
        return opts.rgx.sub(opts.repl, ln.val, count = opts.n)

class Search(Step):

    OPTS_CONFIG = [
        'rgx',
        dict(),
        '-g',
        dict(type = int, default = 0),
        '-a',
        dict(action = 'store_true'),
    ]

    def begin(self, opts, ln):
        opts.rgx = re.compile(opts.rgx)

    def run(self, opts, ln):
        m = opts.rgx.search(ln.val)
        if m:
            if opts.a:
                return m.groups()
            else:
                return m.group(opts.g)

class Grep(Step):

    OPTS_CONFIG = [
        'rgx',
        dict(),
        '-i',
        dict(action = 'store_true'),
        '-v',
        dict(action = 'store_true'),
        '-s',
        dict(action = 'store_true'),
    ]

    def begin(self, opts, ln):
        if not opts.s:
            f = re.IGNORECASE if opts.i else 0
            opts.rgx = re.compile(opts.rgx, flags = f)

    def run(self, opts, ln):
        if opts.s:
            if opts.i:
                m = opts.rgx.lower() in ln.val.lower()
            else:
                m = opts.rgx in ln.val
        else:
            m = bool(opts.rgx.search(ln.val))
        return None if m == opts.v else ln.val

class FindAll(Step):

    OPTS_CONFIG = [
        'rgx',
        dict(),
    ]

    def begin(self, opts, ln):
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
        '-i',
        dict(type = int, default = 4),
    ]

    def begin(self, opts, ln):
        # Reference: https://stackoverflow.com/questions/972.
        indent = ' ' * opts.i
        fmt = 'def _run(self, opts, ln):\n{}{}\n'
        code = fmt.format(indent, opts.code)
        d = {}
        exec(code, globals(), d)
        self.run = functools.partial(d['_run'], self)

####
# JSON handling.
####

class JsonD(Step):

    OPTS_CONFIG = [
        '-i',
        dict(type = int, default = 4),
    ]

    def run(self, opts, ln):
        d = json.loads(ln.val)
        return json.dumps(d, indent = opts.i)

####
# Other.
####

class FlipFlop(Step):

    OPTS_CONFIG = [
        'rgx1',
        dict(),
        'rgx2',
        dict(),
    ]

    def begin(self, opts, ln):
        opts.rgx1 = re.compile(opts.rgx1)
        opts.rgx2 = re.compile(opts.rgx2)
        opts.on = False

    def run(self, opts, ln):
        if opts.on:
            m = opts.rgx2.search(ln.val)
            if m:
                opts.on = False
        else:
            m = opts.rgx1.search(ln.val)
            if m:
                opts.on = True
        if opts.on:
            return ln.val
        else:
            return None

