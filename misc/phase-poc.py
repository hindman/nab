import sys
from collections import deque
import pdb

####
#
# USAGE:
#
#   python misc/phase-poc.py misc/phase-poc.inp >| tmp/phase-poc.got
#   cmp tmp/phase-poc.got misc/phase-poc.exp
#
# TODO:
#
# - Switch to a stack with single vals, and use the type of the item
#   popped off the stack to drive the conditional logic.
#
# - Convert the algorithm to stop when the stack is empty.
#
####

def main(args):
    paths = sys.argv[1:]
    try:
        handles = [open(p) for p in paths]
        doit(zip(paths, handles))
    finally:
        for h in handles:
            h.close()

def doit(pairs):

    # The val processing steps.
    steps = (
        step_strip,
        step_int,
        step_decide,
        step_double,
        step_print,
    )
    max_i = len(steps) - 1

    # Variables used to manage the processing of vals through steps:
    # - fiter : Iterator of files to be processed.
    # - fh    : Currently active file handle.
    # - val   : A (NEXT_STEP_INDEX, VALUE) tuple.
    # - viter : An interator of such val tuples.
    # - stack : A stack of (VAL, VITER) tuples.
    fiter = iter(pairs)
    fh = None
    stack = []

    # Process the data until the stack is empty.
    while True:

        try:
            val, viter = stack.pop()
        except IndexError:
            val = None
            viter = None

        # If we already have a val, process it through its next step.
        if val:
            i, v = val
            v = steps[i](v)
            if i >= max_i:
                # There are no downstream steps: we are done with this val.
                stack.append((None, viter))
            elif v is None:
                # Got a null value: no need to pass it to downstream steps.
                stack.append((None, viter))
            elif isinstance(v, list):
                # We got a sequences of values. Prepare the val-iterator.
                tups = [(i + 1, x) for x in v]
                viter = iter(tups)
                stack.append((None, viter))
            else:
                # We got a value. Prepare it for the next downstream step.
                val = (i + 1, v)
                stack.append((val, viter))

        # If we have an iterable of vals, get the next val.
        elif viter:
            val = getnext(viter)
            if val is not None:
                stack.append((val, viter))

        # If we have a file handle, try to get the next value from it.
        elif fh:
            line = getnext(fh, None)
            if line is None:
                fh.close()
                fh = None
            else:
                val = (0, line)
                stack.append((val, None))

        # Otherwise, advance to the next input file.
        # Stop when we run out of files.
        else:
            path, fh = getnext(pairs, (None, None))
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

def step_decide(val):
    f = step_decide
    if not hasattr(f, 'vals'):
        f.vals = []
    if f.vals and val == 88:
        ys = [v * 100 for v in f.vals + [val]]
        f.vals = []
        return ys
    elif f.vals:
        f.vals.append(val)
        return None
    elif val == 88:
        f.vals = [val]
        return None
    elif val == 999:
        return [900, 90, 9]
    else:
        return val

def step_double(val):
    return val * 2

def step_print(val):
    f = step_print
    if not hasattr(f, 'tot'):
        f.tot = 0
    f.tot += val
    print(val)

if __name__ == '__main__':
    main(sys.argv[1:])

