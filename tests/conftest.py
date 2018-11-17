from __future__ import absolute_import, unicode_literals, print_function

import pytest
import json
import os

@pytest.fixture
def tr():
    return TestResource()

class TestResource(object):

    RESOURCES = dict(
        fubb = 123,
    )

    UTF8 = 'utf-8'

    def __init__(self):
        pass

    def __getitem__(self, k):
        if k in self.RESOURCES:
            return self.RESOURCES[k]
        else:
            return self.get_file(k)

    def dump(self, obj):
        print()
        print(obj)
        print()

    def dumpj(self, obj):
        self.dump(json.dumps(obj, indent = 4))

    def get_file_path(self, filename):
        tests_dir = os.path.dirname(__file__)
        return os.path.join(tests_dir, 'resources', filename)

    def get_file(self, filename):
        p = self.get_file_path(filename)
        with open(p) as fh:
            return fh.read()

