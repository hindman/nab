#! /usr/bin/env bash

inp='misc/phase-poc.inp'
exp='misc/phase-poc.exp'
got='tmp/phase-poc.got'

rm -f $got
python misc/phase-poc.py $inp > $got
cmp $got $exp && echo 'OK'

