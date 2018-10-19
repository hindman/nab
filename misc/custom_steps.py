from __future__ import absolute_import, unicode_literals, print_function

from nab import Step, getitem

class Fubb(Step):

    def run(self, opts, ln):
        return getitem(ln.val, 9999999, 'FUBB: ') + ln.val

