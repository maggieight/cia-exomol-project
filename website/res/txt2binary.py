#!/usr/bin/env python
import os
import sys
import argparse
from array import array

parser = argparse.ArgumentParser(description='Convert a cross section in text'
    ' format to binary.')
parser.add_argument('in_names', help='Input filenames', nargs='+')
parser.add_argument('-t', '--two-column', dest='two_column', const=True,
                    default=False, action='store_const')
args = parser.parse_args()

def read_one_column(in_name):
    return [float(x) for x in open(in_name, 'r').readlines()]

def read_two_column(in_name):
    return [float(x.split()[1]) for x in open(in_name, 'r').readlines()]

read_txt_file = read_two_column if args.two_column else read_one_column

for in_name in args.in_names:
    sigma = read_txt_file(in_name)
    float_sigma = array('d', sigma)
    print('{}: {}'.format(in_name, len(sigma)))
    out_name = os.path.splitext(in_name)[0] + '.bsig'
    fo = open(out_name, 'wb')
    float_sigma.tofile(fo)
    fo.close()
