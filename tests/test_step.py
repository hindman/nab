from __future__ import absolute_import, unicode_literals, print_function

import subprocess

from nab import Step, getitem, iff
from nab.cli import main

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

def test_sum(tr):
    path = tr.get_file_path('data-ls-output.txt')
    fmt = 'nab -s split -s index 4 -s int -s sum -- {}'
    exp_sum = 2916
    for n in range(1, 4):
        paths = n * [path]
        cmd = fmt.format(' '.join(paths))
        out = subprocess.check_output(cmd, shell = True).decode(tr.UTF8)
        exp = '{}\n'.format(n * exp_sum)
        assert out == exp

def test_uniq(tr):
    path = tr.get_file_path('data-uniq.txt')
    fmt = 'nab -s strip -s uniq -s int -s pr -s sum -- {}'
    cmd = fmt.format(path)
    exp = '1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n55\n'
    out = subprocess.check_output(cmd, shell = True).decode(tr.UTF8)
    assert out == exp

def test_tail(tr):
    path = tr.get_file_path('data-ls-output.txt')
    fmt = 'nab -s split -s index 4 -s tail 3 -s int -s pr -s sum -- {}'
    cmd = fmt.format(path)
    exp = '238\n238\n144\n620\n'
    out = subprocess.check_output(cmd, shell = True).decode(tr.UTF8)
    assert out == exp

