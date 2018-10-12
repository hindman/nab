from __future__ import absolute_import, unicode_literals, print_function

class Step(object):

    def begin(self, opts):
        # The Step can configure itself -- including the ability
        # to define its other hooks dynamically.
        pass

    def discover(self, opts):
        # A Step can return a new list of paths to be used. It can be either a
        # list of INPUT_PATH or a list of (INPUT_PATH, OUTPUT_PATH) pairs. In
        # the latter case, the output will go to separate files rather than to
        # a consolidated STDOUT. If the paths in a pari are equal, the original
        # file will be overwritten.
        pass

    def file_begin(self, opts):
        # Before a path is opened.
        pass

    def run(self, opts, ln):
        # Process one Line.
        pass

    def file_end(self, opts):
        # After a file is closed.
        pass

    def end():
        # Emit or persist overall results.
        pass

