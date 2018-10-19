from __future__ import absolute_import, unicode_literals, print_function

def getitem(xs, i, default = None):
    # Get item that returns None (or some other default)
    # on bad index/key, rather than raising.
    try:
        return xs[i]
    except (IndexError, KeyError):
        return default

def iff(pred, t = True, f = False):
    return t if pred else f

