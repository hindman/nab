from __future__ import absolute_import, unicode_literals, print_function

import collections
import json
import random
import re
import functools

from .step import Step
from .utils import ValIter

####
# Printing and writing.
####

class Pr(Step):

    def process(self, opts, meta, val):
        self.out(val)
        return val

class Wr(Step):

    def process(self, opts, meta, val):
        self.out(val, end = '')
        return val

####
# Chomping and stripping.
####

class Chomp(Step):

    def process(self, opts, meta, val):
        return val.rstrip('\n')

class Strip(Step):

    OPTS_CONFIG = [
        's',
        dict(nargs = '?'),
    ]

    def process(self, opts, meta, val):
        return val.strip(opts.s)

class LStrip(Step):

    OPTS_CONFIG = Strip.OPTS_CONFIG

    def process(self, opts, meta, val):
        return val.lstrip(opts.s)

class RStrip(Step):

    OPTS_CONFIG = Strip.OPTS_CONFIG

    def process(self, opts, meta, val):
        return val.rstrip(opts.s)

####
# Splitting and joining.
####

class Split(Step):

    OPTS_CONFIG = [
        'rgx',
        dict(nargs = '?'),
    ]

    def begin(self, opts):
        opts.rgx = re.compile(opts.rgx) if opts.rgx else None

    def process(self, opts, meta, val):
        if opts.rgx:
            return opts.rgx.split(val)
        else:
            return val.split()

class Join(Step):

    OPTS_CONFIG = [
        'j',
        dict(),
    ]

    def process(self, opts, meta, val):
        return opts.j.join(val)

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

    def process(self, opts, meta, val):
        try:
            return val[opts.i]
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

    def process(self, opts, meta, val):
        return val[opts.i : opts.j : opts.s]

####
# Head, skip, etc.
####

class Head(Step):

    OPTS_CONFIG = [
        'n',
        dict(type = int, nargs = '?', default = 10),
    ]

    def process(self, opts, meta, val):
        if meta.line_num <= opts.n:
            return val

class Tail(Step):

    OPTS_CONFIG = [
        'n',
        dict(type = int, nargs = '?', default = 10),
    ]

    def begin(self, opts):
        self.deq = collections.deque()

    def process(self, opts, meta, val):
        if len(self.deq) >= opts.n:
            self.deq.popleft()
        self.deq.append(val)

    def finalize(self, opts, meta):
        if meta.is_last_file:
            return ValIter(self.deq)

class Skip(Step):

    OPTS_CONFIG = [
        'n',
        dict(type = int),
    ]

    def process(self, opts, meta, val):
        if meta.line_num > opts.n:
            return val

####
# Prefix, suffix, and trailing newline.
####

class Nl(Step):

    def process(self, opts, meta, val):
        return val if val.endswith('\n') else val + '\n'

class Prefix(Step):

    OPTS_CONFIG = [
        'pre',
        dict(),
    ]

    def process(self, opts, meta, val):
        return opts.pre + val

class Suffix(Step):

    OPTS_CONFIG = [
        'suff',
        dict(),
    ]

    def process(self, opts, meta, val):
        return val + opts.suff

####
# Aggregations.
####

class Freq(Step):

    def begin(self, opts):
        opts.freq = collections.Counter()

    def process(self, opts, meta, val):
        opts.freq[val] += 1

    def end(self, opts, meta):
        for k in sorted(opts.freq):
            msg = '{}: {}'.format(k, opts.freq[k])
            self.out(msg)

class Sum(Step):

    def begin(self, opts):
        opts.sum = 0

    def process(self, opts, meta, val):
        opts.sum += val

    def end(self, opts, meta):
        self.out(opts.sum)

####
# Basic conversions: str, int, float.
####

class Str(Step):

    def process(self, opts, meta, val):
        return str(val)

class Int(Step):

    def process(self, opts, meta, val):
        return int(float(val))

class Float(Step):

    def process(self, opts, meta, val):
        return float(val)

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

    def begin(self, opts):
        opts.rgx = re.compile(opts.rgx)
        if opts.f:
            indent = ' ' * opts.i
            code = 'def _repl(m):\n{}{}'.format(indent, opts.repl)
            d = {}
            exec(code, globals(), d)
            opts.repl = d['_repl']

    def process(self, opts, meta, val):
        return opts.rgx.sub(opts.repl, val, count = opts.n)

class Search(Step):

    OPTS_CONFIG = [
        'rgx',
        dict(),
        '-g',
        dict(type = int, default = 0),
        '-a',
        dict(action = 'store_true'),
    ]

    def begin(self, opts):
        opts.rgx = re.compile(opts.rgx)

    def process(self, opts, meta, val):
        m = opts.rgx.search(val)
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

    def begin(self, opts):
        if not opts.s:
            f = re.IGNORECASE if opts.i else 0
            opts.rgx = re.compile(opts.rgx, flags = f)

    def process(self, opts, meta, val):
        if opts.s:
            if opts.i:
                m = opts.rgx.lower() in val.lower()
            else:
                m = opts.rgx in val
        else:
            m = bool(opts.rgx.search(val))
        return None if m == opts.v else val

class FindAll(Step):

    OPTS_CONFIG = [
        'rgx',
        dict(),
    ]

    def begin(self, opts):
        opts.rgx = re.compile(opts.rgx)

    def process(self, opts, meta, val):
        return opts.rgx.findall(val)

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

    def begin(self, opts):
        # Reference: https://stackoverflow.com/questions/972.
        indent = ' ' * opts.i
        fmt = 'def _process(self, opts, meta, val):\n{}{}\n'
        code = fmt.format(indent, opts.code)
        d = {}
        exec(code, globals(), d)
        self.process = functools.partial(d['_process'], self)

####
# JSON handling.
####

class JsonD(Step):

    OPTS_CONFIG = [
        '-i',
        dict(type = int, default = 4),
    ]

    def process(self, opts, meta, val):
        d = json.loads(val)
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

    def begin(self, opts):
        opts.rgx1 = re.compile(opts.rgx1)
        opts.rgx2 = re.compile(opts.rgx2)
        opts.on = False

    def process(self, opts, meta, val):
        if opts.on:
            m = opts.rgx2.search(val)
            if m:
                opts.on = False
        else:
            m = opts.rgx1.search(val)
            if m:
                opts.on = True
        if opts.on:
            return val
        else:
            return None

class Para(Step):

    def begin(self, opts):
        self.para = []

    def process(self, opts, meta, val):
        if val.strip():
            self.para.append(val)
            return None
        else:
            return self.get_para()

    def finalize(self, opts, meta):
        return self.get_para()

    def get_para(self):
        if self.para:
            res = self.para
            self.para = []
            return res
        else:
            return None

class Uniq(Step):

    def begin(self, opts):
        self.reset()

    def process(self, opts, meta, val):
        if val not in self.uniq:
            self.uniq[val] = None

    def finalize(self, opts, meta):
        if meta.is_last_file and self.uniq:
            res = self.uniq
            self.reset()
            return ValIter(res)

    def reset(self):
        self.uniq = collections.OrderedDict()

