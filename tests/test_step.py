from __future__ import absolute_import, unicode_literals, print_function

from nab import Step, getitem, iff
from nab.cli import main

def test_sum(tr, capsys):

    path = tr.get_file_path('data-ls-output.txt')
    base_args = '-s split -s index 4 -s int -s sum --'.split()
    exp_sum = 2916

    for n in range(1, 4):
        main(args = base_args + n * [path])
        captured = capsys.readouterr()
        assert captured.out == '{}\n'.format(n * exp_sum)
        assert captured.err == ''

def test_getitem(tr):

    xs = [0, 11, 22, 33, 44]
    kws = dict(a = 1, b = 2)

    tests = [
        (xs, 2, None, 22),
        (xs, 8, None, None),
        (kws, 'a', None, 1),
        (kws, 'Z', 'fubb', 'fubb'),
    ]

    for i, (obj, k, default, exp) in enumerate(tests):
        got = getitem(obj, k, default)
        assert (i, got) == (i, exp)

