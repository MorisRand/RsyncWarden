#!/usr/bin/python3
from __future__ import print_function

import os
from os.path import abspath
import glob
import argparse


def merge_checksums(args):
    checksums = set()
    for  csum_file in glob.glob(args.checksums+'/checksums*'):
        with open(csum_file, 'r') as f:
            for line in f:
                cksum, _, path = line.split(' ')
                checksums.add(path)

    goodruns = set()
    with open(args.good_runs) as f:
        for line in f:
            goodruns.add(line)

    missing_pathes = goodruns.difference(checksums)
    print('Found {} missing files without checksums'.format(len(missing_pathes)))
    with open(args.missing_files, 'w') as f:
        for path in missing_pathes:
            f.write(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('checksums', type=abspath,
            help='Path to folder with checksums')
    parser.add_argument('--good-runs', type=abspath, required=True,
            help='Path to good run list')
    parser.add_argument('--missing-files', type=abspath, required=True,
            help='Path where missing files list will be created')
    
    args = parser.parse_args()
    merge_checksums(args)

