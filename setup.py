#! /usr/bin/env python

from os.path import dirname, realpath, join
from setuptools import setup, find_packages
import sys


####
# Basic metadata.
####

project_name = 'nab'
package_name = project_name.replace('-', '_')
repo_name    = project_name
src_subdir   = 'src'
description  = 'Python text munging in the spirit of awk, sed, and Perl'
url          = 'https://github.com/hindman/' + repo_name
author       = 'Monty Hindman'
author_email = 'mhindman@gmail.com'


####
# Requirements.
####

reqs = [
    'six',
]

extras = {
    'test' : [
        'coverage',
        'pytest',
        'pytest-cache',
        'pytest-cov',
        'tox',
    ],
    'dev' : [
        'ipython',
        'pycodestyle',
        'twine',
        'virtualenv',
        'virtualenvwrapper',
    ],
}


####
# Packages and scripts.
####

packages = find_packages(where = src_subdir)

package_data = {
    package_name: [],
}

entry_points = {
    'console_scripts': [
        'nab = nab.cli:main',
    ],
}


####
# Import __version__.
####

project_dir = dirname(realpath(__file__))
version_file = join(project_dir, src_subdir, package_name, 'version.py')
exec(open(version_file).read())


####
# Install.
####

setup(
    name             = project_name,
    version          = __version__,
    author           = author,
    author_email     = author_email,
    url              = url,
    description      = description,
    zip_safe         = False,
    packages         = packages,
    package_dir      = {'': src_subdir},
    package_data     = package_data,
    install_requires = reqs,
    tests_require    = extras['test'],
    extras_require   = extras,
    entry_points     = entry_points,
)

