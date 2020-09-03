#!/usr/bin/python3

import os
import sys
from os.path import join, abspath
import argparse

try:
    from tqdm import tqdm
except ImportError:
    print('No fancy progress bar support; install tqdm for it')
    tqdm = lambda x: x

try:
    import XRootD.client as xrdcl
    xrdcksum = xrdcl.flags.QueryCode.CHECKSUM
except ImportError:
    raise SystemError("XRootD python bindings not found")

class InputReader:
    def __init__(self, path):
        with open(abspath(path), "r") as f:
            self.entries = []
            for line in f:
                filename, cksum = line.rstrip("\n").split(" ")
                self.entries.append((filename, cksum))

    def __iter__(self):
        return iter(tqdm(self.entries))

                
def main(args):
    def _get_cksum(path):
        _, response = eos_fs.query(xrdcksum, join(root_folder, path))
        _, cksum = response.decode("utf-8").rstrip('\x00').split()
        return cksum

    expected: InputReader = args.input_file
    eos_fs = xrdcl.FileSystem(args.eos)
    root_folder = args.data_root 
    output_file = args.output

    wrong_cksum_files = []
    for fname, orig_cksum in expected:
        try:
            cksum_in_eos = _get_cksum(fname)
        except:
            # really naive handling, many things can cause problems: network,
            # authentication, storage inaccesibility...
            print(f'{fname} is not in storage! Adding it to wrong file list')
            wrong_cksum_files.append(fname)
            continue
        if cksum_in_eos != orig_cksum:
            print(f'Wrong cksum for {fname}: {cksum_in_eos} != {orig_cksum}')
            wrong_cksum_files.append(fname)

    if wrong_cksum_files:
        print(f'''{len(wrong_cksum_files)} files have wrong cksums, list of
        it is saved to {output_file}''')
        with open(output_file, 'w') as f:
            for fname in wrong_cksum_files:
                f.write(fname+'\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-file", required=True, type=InputReader, help="Help text")
    parser.add_argument("-e", "--eos", default="root://eos.jinr.ru", 
                        help='EOS storage address')
    parser.add_argument("-d", "--data-root", default="/eos/juno/dirac/juno/lustre-ro/dybfs",
                        help="Root directory for data in EOS")
    parser.add_argument("-o", "--output", type=abspath, help="Path where to store files with wrong checksums")

    args = parser.parse_args()

    main(args)
