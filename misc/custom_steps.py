from __future__ import absolute_import, unicode_literals, print_function

from nab import Step

class FlipFlop(Step):

    OPTS_CONFIG = [
        'rgx1',
        dict(),
        'rgx2',
        dict(),
    ]

    def begin(self, opts, ln):
        opts.rgx1 = re.compile(opts.rgx1)
        opts.rgx2 = re.compile(opts.rgx2)
        opts.on = False

    def run(self, opts, ln):
        # TODO:
        #
        # - Allow ON and then OFF checks to occur on same line.
        #
        # - Allow options to govern inclusiveness:
        #
        #              1st ON line  | 1st OFF line
        #    full    | yes          | yes            # Perl's default.
        #    partial | yes          | no
        #    none    | no           | no
        #
        # - Support line number mode for rgx1 and/or rgx2: in this case
        #   the ON/OFF logic is based on line numbers.
        #
        if opts.on:
            m = opts.rgx2.search(ln.val)
            if m:
                opts.on = False
        else:
            m = opts.rgx1.search(ln.val)
            if m:
                opts.on = True
        if opts.on:
            return ln.val
        else:
            return None

