from __future__ import absolute_import, unicode_literals, print_function

import sys

class Step(object):

    NAME = None
    DESC = None
    OPTS_CONFIG = None

    def __init__(self, sid, name, opts, ln):
        self.sid = sid
        self.name = name
        self.opts = opts
        self.ln = ln

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
        kws.setdefault('file', getattr(self.ln.out, 'handle', None) or sys.stdout)
        print(*xs, **kws)

    def err(self, *xs, **kws):
        kws.setdefault('file', getattr(self.ln.err, 'handle', None) or sys.stderr)
        print(*xs, **kws)

    def begin(self, opts, ln):
        # The Step can configure itself -- including the ability
        # to define its other hooks dynamically.
        pass

    def discover(self, opts, ln):
        # A Step can return a new list of paths to be used. It can be either a
        # list of INPUT_PATH or a list of (INPUT_PATH, OUTPUT_PATH) pairs. In
        # the latter case, the output will go to separate files rather than to
        # a consolidated STDOUT. If the paths in a pari are equal, the original
        # file will be overwritten.
        pass

    def file_begin(self, opts, ln):
        # Before a path is opened.
        pass

    def run(self, opts, ln):
        # Process one Line.
        pass

    def file_end(self, opts, ln):
        # After a file is closed.
        pass

    def end(self, opts, ln):
        # Emit or persist overall results.
        pass

