#!/usr/bin/python3
from __future__ import print_function

import os
from os.path import abspath
import glob
import argparse


def merge_checksums(args):
    checksums_pathes = set()
    checksums_full = set()
    old, new = args.substitute_path
    for  csum_file in glob.glob(args.checksums+'/checksums*'):
        with open(csum_file, 'r') as f:
            for line in f:
                cksum, path = line.split(' ')
                checksums_pathes.add(path)
                checksums_full.add((path, cksum))

    goodruns = set()
    with open(args.good_runs, 'r') as f:
        for line in f:
            goodruns.add(line)

    missing_pathes = goodruns.difference(checksums_pathes)
    print('Found {} missing files without checksums'.format(len(missing_pathes)))
    with open(args.missing_files, 'w') as f:
        for path in missing_pathes:
            f.write(path)

    if args.goodrun_checksums:
        with open(args.goodrun_checksums, 'w') as f:
            for path, cksum in sorted(checksums_full):
                if path in goodruns:
                    cksum = cksum.rstrip('\n')
                    path = path.rstrip('\n')
                    # P19A files in EOS are in dybfs2 folder but in IHEP they
                    # are in dybfs lustre partion so we swap it for correct
                    # mapping to our setup
                    path = path.replace(old, new) 
                    f.write(f'{path} {cksum}\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('checksums', type=abspath,
            help='Path to folder with checksums')
    parser.add_argument('--good-runs', type=abspath, required=True,
            help='Path to good run list')
    parser.add_argument('--missing-files', type=abspath, required=True,
            help='Path where missing files list will be created')
    parser.add_argument('--goodrun-checksums', type=abspath,
            help='Path to file where checksums and pathes for goodrun list will be stored')
    parser.add_argument('--substitute-path', nargs=2, type=abspath, metavar="(OLD_VAL NEW_VAL)",
            help='Subsititute part of file path with new value')
    
    args = parser.parse_args()
    merge_checksums(args)

