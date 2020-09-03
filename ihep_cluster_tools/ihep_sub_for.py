from __future__ import print_function
import os
import argparse

DYB_LUSTRE_P17B = "/dybfs/rec/P17B/rec/"
#  condor_jobs = []
#  condor_payload = htcondor.Submit({
        #  'executable': '/usr/bin/md5sum',
        #  'arguments': arguments,
        #  'output': output,
        #  'error': error
        #  })
#  condor_jobs.append(condor_payload)
#  schedd = htcondor.Schedd()
#  with schedd.transaction() as txn:
    #  for job in condor_jobs:
        #  cluster_id = job.queue(txn)
    #  print(cluster_id)


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
        for i, runs in enumerate(f):
            runs = runs[:-1]
            arguments = DYB_LUSTRE_P17B + runs + '*.root'
            thousands, hundreds, dozens, _ = [_.lstrip("runs_") for _  in runs.split('/')]
            output = output_path + "/checksums_{}_{}_{}.out".format(thousands, hundreds, dozens)
            job = job_path +"/job_{}.sh".format(i)
            script_body = '#!/bin/bash\n md5sum {} > {}'.format(arguments, output)

            with open(job, 'w') as j:
                j.write(script_body)
            os.chmod(job, 0755)

    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', type=os.path.abspath,
        help='Path to file with run unique run number ids')

    args = parser.parse_args()
    submit_htcondor_jobs(args.input_file)
