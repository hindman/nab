from __future__ import absolute_import, unicode_literals, print_function

import collections
import json
import random
import re

####
# Steps.
####

# Step: pr and wr.

def pr_run(ln, opts):
    if ln.val is not None:
        print(ln.val)
    return ln.val

def wr_run(ln, opts):
    if ln.val is not None:
        print(ln.val, end = '')
    return ln.val

# Step: strip.

strip_opts = [
    's',
    dict(nargs = '?'),
]

def strip_run(ln, opts):
    ln.val = ln.val.strip(opts.s)
    return ln.val

# Step: lstrip.

lstrip_opts = strip_opts

def lstrip_run(ln, opts):
    ln.val = ln.val.lstrip(opts.s)
    return ln.val

# Step: lstrip.

rstrip_opts = strip_opts

def rstrip_run(ln, opts):
    ln.val = ln.val.rstrip(opts.s)
    return ln.val

# Step: chomp.

def chomp_run(ln, opts):
    ln.val = ln.val.rstrip('\n')
    return ln.val

# Step: split.

split_opts = [
    'rgx',
    dict(),
]

def split_begin(opts):
    opts.rgx = re.compile(opts.rgx)

def split_run(ln, opts):
    return opts.rgx.split(ln.val)

# Step: index.

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

# Step: rindex.

rindex_opts = index_opts

def rindex_begin(opts):
    opts.i = - opts.i

rindex_run = index_run

# Step: nl and anl.

def anl_begin(ln, opts):
    pass

def nl_run(ln, opts):
    v = ln.val
    return v if v.endswith('\n') else v + '\n'

# Step: cat.

def cat_run(ln, opts):
    return ln.val

# Step: head.

head_opts = [
    'n',
    dict(type = int),
]

def head_run(ln, opts):
    if ln.line_num <= opts.n:
        return ln.val

# Step: prefix.

prefix_opts = [
    'pre',
    dict(),
]

def prefix_run(ln, opts):
    return opts.pre + ln.val

# Step: suffix.

suffix_opts = [
    'suff',
    dict(),
]

def suffix_run(ln, opts):
    return ln.val + opts.suff

# Step: freq.

def freq_run(ln, opts):
    opts.freq[ln.val] += 1

def freq_begin(opts):
    opts.freq = collections.Counter()

def freq_end(opts):
    for k in sorted(opts.freq):
        msg = '{}: {}'.format(k, opts.freq[k])
        print(msg)

# Step: sum.

def sum_run(ln, opts):
    opts.sum += ln.val

def sum_begin(opts):
    opts.sum = 0

def sum_end(opts):
    print(opts.sum)

# Step: int.

def int_run(ln, opts):
    return int(float(ln.val))

# Step: float.

def float_run(ln, opts):
    return float(ln.val)

# Step: sub.

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

# Step: join.

join_opts = [
    'j',
    dict(),
]

def join_run(ln, opts):
    return opts.j.join(ln.val)

# Step: range.

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

# Step: str.

def str_run(ln, opts):
    return str(ln.val)

# Step: skip.

skip_opts = [
    'n',
    dict(type = int),
]

def skip_run(ln, opts):
    if ln.line_num > opts.n:
        return ln.val

# Step: findall.

findall_opts = [
    'rgx',
    dict(),
]

def findall_begin(opts):
    opts.rgx = re.compile(opts.rgx)

def findall_run(ln, opts):
    return opts.rgx.findall(ln.val)

# Step: run.

run_opts = [
    'code',
    dict(),
]

def run_begin(opts):
    fmt = 'def run_run(ln, opts):\n   {}\n'
    code = fmt.format(opts.code)
    exec(code, globals())
    return dict(run = run_run)

# Step: jsond.

jsond_opts = [
    '-i',
    dict(type = int, default = 4),
]

def jsond_run(ln, opts):
    d = json.loads(ln.val)
    return json.dumps(d, indent = opts.i)

