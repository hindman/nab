#! /usr/bin/env python

import sys
import json
from collections import namedtuple

# USAGE: ./misc/phase-poc.sh

DEBUG = False

def main(args):
    paths = sys.argv[1:]
    try:
        ifiles = [InputFile(p) for p in paths]
        doit(ifiles)
    finally:
        for f in ifiles:
            f.fh.close()

def doit(ifiles):

    # The val processing steps.
    steps = (
        step_strip,    # 0
        step_int,      # 1
        step_decide1,  # 2
        step_double,   # 3
        step_decide2,  # 4
        step_decide3,  # 5
        step_print,    # 6
    )
    max_i = len(steps) - 1

    # We will use a stack with 4 types of data and will continue
    # until the stack is empty:
    #
    # - FilesCollection: An iterable of InputFile.
    # - InputFile: An iterable of input vals.
    # - ValIter: An iterable of values (returned by a step).
    # - Val: A val and the index of the step to which it should be passed.
    #
    # We bootstrap the stack with the FilesCollection.
    #
    # Every conditional branch is either terminal (meaning an iterator is
    # exhausted or no further processing is needed for a val) or we should add
    # one or multiple items to the stack -- multiple in cases where we get
    # a non-null value from a still-alive iterator (in that case, we add
    # both the iterator and a Val of the value).
    #
    stack = [FilesCollection(ifiles)]
    while stack:

        # Get the next item from the stack.
        item = stack.pop()
        debug('A', stack_len = len(stack), item_type = type(item).__name__)

        # Val: process it through its next step.
        if isinstance(item, Val):
            val = item
            debug('B0', val = val)
            i = val.step_index
            v = steps[i](val.val)
            if i >= max_i:
                # There are no downstream steps: we are done with this val.
                debug('B1', i = i, max_i = max_i)
            elif v is None:
                # Got a null value: no need to pass it to downstream steps.
                debug('B2', v = None)
            elif isinstance(v, ValIter):
                # Got a ValIter from the step: set its step_index.
                v.step_index = i + 1
                debug('B3', viter_xs = v.xs, step_index = v.step_index)
                stack.append(v)
            else:
                # Got some other value: prepare it for the next downstream step.
                val2 = Val(v, i + 1)
                debug('B4', val = val2)
                stack.append(val2)

        # ValIter: get the next value from it.
        elif isinstance(item, ValIter):
            viter = item
            v = getnext(viter)
            if v is None:
                debug('C1', v = None)
            else:
                val = Val(v, viter.step_index)
                debug('C2', v = v, step_index = viter.step_index)
                stack.extend((viter, val))

        # InputFile: get the next line from it.
        elif isinstance(item, InputFile):
            ifile = item
            line = getnext(ifile)
            if line is None:
                debug('D1', line = None)
                ifile.fh.close()
            else:
                val = Val(line, 0)
                debug('D2', val = val)
                stack.extend((ifile, val))

        # FilesCollection: get the next InputFile.
        elif isinstance(item, FilesCollection):
            fcoll = item
            ifile = getnext(fcoll)
            if ifile is None:
                debug('E1', ifile = None)
            else:
                debug('E2', path = ifile.path)
                stack.extend((fcoll, ifile))

        else:
            assert False, 'Should never happen'

def step_strip(val):
    return val.strip()

def step_int(val):
    return int(val)

def step_decide1(val):
    f = step_decide1
    if not hasattr(f, 'vals'):
        f.vals = []
    if f.vals and val == 88:
        ys = [v * 100 for v in f.vals + [val]]
        f.vals = []
        return ValIter(ys)
    elif f.vals:
        f.vals.append(val)
        return None
    elif val == 88:
        f.vals = [val]
        return None
    elif val == 999:
        return ValIter([900, 90, 9])
    else:
        return val

def step_double(val):
    return val * 2

def step_decide2(val):
    f = step_decide2
    if not hasattr(f, 'vals'):
        f.vals = []
    if f.vals and val == 18:
        ys = [v + 1 for v in f.vals + [val]]
        f.vals = []
        return ValIter(ys)
    elif f.vals:
        f.vals.append(val)
        return None
    elif val == 18:
        f.vals = [val]
        return None
    else:
        return val

def step_decide3(val):
    return ValIter([17000, 600]) if val == 17600 else val

def step_print(val):
    f = step_print
    if not hasattr(f, 'tot'):
        f.tot = 0
    f.tot += val
    msg = '{:<8} : {}'.format(val, f.tot)
    msg = val
    if DEBUG:
        debug('ZZZZ', val = val)
    else:
        print(msg)

def getnext(it, default = None):
    # A non-raising next().
    try:
        return next(it)
    except StopIteration:
        return default

Val = namedtuple('Val', 'val step_index')

class ValIter(object):

    def __init__(self, xs):
        self.xs = xs
        self.it = iter(xs)
        self.step_index = None

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.it)

class InputFile(object):

    def __init__(self, path):
        self.path = path
        self.fh = open(path)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.fh)

class FilesCollection(object):

    def __init__(self, ifiles):
        self.it = iter(ifiles)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.it)

def debug(name, **kws):
    if DEBUG:
        d = json.dumps(kws)
        msg = '{:>8} {}'.format(name + ':', d)
        print(msg)

if __name__ == '__main__':
    main(sys.argv[1:])

