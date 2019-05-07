from __future__ import absolute_import, unicode_literals, print_function

import sys

class Step(object):

    NAME = None
    GROUPS = []
    DESC = None
    USAGE = None
    OPTS_CONFIG = None

    def __init__(self, sid, name, opts, meta):
        self.sid = sid
        self.name = name
        self.opts = opts
        self.meta = meta

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return '{}({}, {}, {})'.format(
            self.__class__.__name__,
            self.name,
            self.sid,
            self.opts,
        )

    def out(self, *xs, **kws):
        kws.setdefault('file', getattr(self.meta.out, 'handle', None) or sys.stdout)
        print(*xs, **kws)

    def err(self, *xs, **kws):
        kws.setdefault('file', getattr(self.meta.err, 'handle', None) or sys.stderr)
        print(*xs, **kws)

    def begin(self, opts):
        # The Step can configure itself -- including the ability
        # to define its other hooks dynamically.
        pass

    def discover(self, opts, fsets):
        # Takes a list-of-dict-of-dict:
        #
        # - Each outer dict represents a FileSet (keys: inp, out, err).
        #
        # - Each inner-dict represents a FileHandle (keys: path, handle, and
        #   any arguments taken by the built-in open() function).
        #
        # The function can return a new list to replace the prior list.
        #
        # The most common approach is to return FileHandle dicts with a path
        # and, occasionally, kwargs for open(). In that case, nab will open and
        # close files on behalf of the user. For more specialize needs, the
        # FileHandle dict can include an already opened file handle. In this
        # case, nab will not open/close the file; nonetheless, the path
        # argument is still required (for debugging purposes).
        return fsets

    def initialize(self, opts, meta):
        # Before a path is opened.
        pass

    def process(self, opts, meta, val):
        # Process one Line.
        return val

    def finalize(self, opts, meta):
        # After a file is closed.
        pass

    def end(self, opts, meta):
        # Emit or persist overall results.
        pass

