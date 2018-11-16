#! /usr/bin/env python

import sys
import json

####
#
# USAGE:
#
#   ./misc/phase-poc.sh
#
# TODO:
#
# - Switch to a stack with single vals, and use the type of the item
#   popped off the stack to drive the conditional logic.
#
# - Convert the algorithm to stop when the stack is empty.
#
####

DEBUG = False

def main(args):
    paths = sys.argv[1:]
    try:
        handles = [open(p) for p in paths]
        doit(list(zip(paths, handles)))
    finally:
        for h in handles:
            h.close()

def debug(name, **kws):
    if DEBUG:
        d = json.dumps(kws)
        msg = '{:>8} {}'.format(name + ':', d)
        print(msg)

def doit(pairs):

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

    # Variables used to manage the processing of vals through steps:
    # - fcoll : Collection of files to be processed.
    # - fh    : Currently active file handle.
    # - val   : A (NEXT_STEP_INDEX, VALUE) tuple.
    # - viter : An interator of such val tuples.
    # - stack : A stack of (VAL, VITER) tuples.
    fcoll = FilesCollection(pairs)
    fh = None
    stack = []

    # Process the data until the stack is empty.
    while True:

        try:
            val, viter = stack.pop()
            debug('0', val = val, viter = id(viter) if viter else None, stack_len = len(stack))
        except IndexError:
            val = None
            viter = None

        # If we already have a val, process it through its next step.
        if val:
            debug('A', val = val)
            i, v = val
            v = steps[i](v)
            if i >= max_i:
                # There are no downstream steps: we are done with this val.
                debug('A1')
                stack.append((None, viter))
            elif v is None:
                # Got a null value: no need to pass it to downstream steps.
                debug('A2')
                stack.append((None, viter))
            elif isinstance(v, ValIter):
                # We got a sequences of values. Prepare the val-iterator.
                # And don't forget to put the current viter, if any, back on the stack.
                tups = [(i + 1, x) for x in v]
                debug('A3', tups = tups)
                stack.append((None, viter))
                stack.append((None, ValIter(tups)))
            else:
                # We got a value. Prepare it for the next downstream step.
                val = (i + 1, v)
                debug('A4', val = val)
                stack.append((val, viter))

        # If we have an iterable of vals, get the next val.
        elif viter:
            val = getnext(viter)
            debug('B', val = val)
            if val is not None:
                stack.append((val, viter))

        # If we have a file handle, try to get the next value from it.
        elif fh:
            line = getnext(fh, None)
            debug('C', line = line)
            if line is None:
                fh.close()
                fh = None
            else:
                val = (0, line)
                stack.append((val, None))

        # Otherwise, advance to the next input file.
        # Stop when we run out of files.
        else:
            path, fh = getnext(fcoll, (None, None))
            debug('D', path = path)
            if fh is None:
                break

def getnext(it, default = None):
    # A non-raising next().
    try:
        return next(it)
    except StopIteration:
        return default

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
    print(msg)

class ValIter(object):

    def __init__(self, xs):
        self.it = iter(xs)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.it)

class FilesCollection(object):

    def __init__(self, pairs):
        self.it = iter(pairs)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.it)

if __name__ == '__main__':
    main(sys.argv[1:])

