from __future__ import print_function
import os
import argparse

try:
    import htcondor
except ImportError:
    print("No condor")

DYB_LUSTRE_P17B = "/dybfs/rec/P17B/rec/"

class CondorSubmitter:
    def __init__(self, chunks, output_base):
        self.chunks = chunks
        self.output_base = output_base

    def submit_htcondor_jobs(run_file):
        output_path = os.getcwd()+"/condor"
        if not os.path.exists(output_path):
            os.mkdir(output_path)
            print("Creating output folder {}".format(output_path))

        job_path = os.getcwd()+"/jobs"
        if not os.path.exists(job_path):
            os.mkdir(job_path)
            print("Creating job folder {}".format(output_path))

        with open(run_file, 'r') as f:
            print("Reading input files")
            files = list(f.readlines())
            it = iter(files)
            chunks = []
            while True:
                chunks.append([])
                print("Creating next chunk: {}".format(len(chunks)))
                try:
                    for _ in range(self.chunks):
                        chunks[-1].append(it.next())
                except StopIteration:
                    print("Prepared chunks")
                    break
                
            for i, pathes in enumerate(chunks):
                print("processing {} job".format(i))
                #arguments = DYB_LUSTRE_P17B + runs
                # arguments = DYB_LUSTRE_P17B + runs + '*.root'
                #thousands, hundreds, dozens, _ = [_.lstrip("runs_") for _  in runs.split('/')]
                output = output_path + "/"+self.output_base.format(i)
                job = job_path +"/job_{}.sh".format(i)
                script_begin = '#!/bin/bash\n'
                script_body="xrdadler32 {} >> {}\n"
                with open(job, 'w') as j:
                    j.write(script_begin)
                    for path in pathes:
                        path = path.rstrip('\n')
                        j.write(script_body.format(path, output))
                os.chmod(job, 0755)

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', type=os.path.abspath,
        help='Path to file with run unique run number ids')
    parser.add_argument("-cs", "--chunk-size", default=50, help="Number of files per job")
    parser.add_argument("-o", "--output-base", required=True, help="Basename for naming output files")
    args = parser.parse_args()

    submitter = CondorSubmitter(chunks=args.chunk_size,
                                output_base=args.output_base
                                )
    submitter.submit_htcondor_jobs(args.input_file)
