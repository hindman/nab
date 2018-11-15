from __future__ import absolute_import, unicode_literals, print_function

def getitem(xs, i, default = None):
    # A non-raising __getitem__().
    try:
        return xs[i]
    except (IndexError, KeyError):
        return default

def getnext(it, default = None):
    # A non-raising next().
    try:
        return next(it)
    except StopIteration:
        return default

def iff(pred, t = True, f = False):
    return t if pred else f

