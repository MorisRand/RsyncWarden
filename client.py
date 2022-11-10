#!/usr/bin/python3

import os
import sys
from os.path import abspath
import subprocess
import time
from tempfile import NamedTemporaryFile
import argparse

import yaml
import requests
from retrying import retry
from loguru import logger

from common.models import ClientMessage, Status

RSYNC_VERBOSE_COMMAND = '''rsync -h --progress -avzp --ignore-existing --files-from={filelist}  rsync://{ihep_host}:/dybfs {eos_home}'''
RSYNC_SILENT_COMMAND = '''rsync -avzp --ignore-existing --files-from={filelist}  rsync://{ihep_host}:/dybfs {eos_home}'''
RSYNC_REWRITE_COMMAND = '''rsync -h --progress -avzp --files-from={filelist}  rsync://{ihep_host}:/dybfs {eos_home}'''

def get_config():
    try:
        with open(abspath("client_conf.yaml"), 'r') as f:
            config = yaml.load(f)
    except FileNotFoundError:
        logger.info('Failed to find config, trying environmetal vars')
        config = dict()
        config['login'] = os.environ['CLIENT_LOGIN']
        config['passwd'] = os.environ['CLIENT_PASSWD']
        config['server_address'] = os.environ['SERVER_ADDRESS']
        config['eos_home'] = os.environ['EOS_HOME']
        config['ihep_host'] = os.environ['IHEP_HOST']
    return config

def compute_adler(path):
    s = subprocess.check_output(f"xrdadler32 {path}".split()).decode()
    # subporcess returns "cksum path", need to extract cksum
    return s.split()[0]

def eos_is_up(eos_prefix):
    try: 
        gen = os.walk(eos_prefix)
        # get /eos node
        next(gen)
        # will raise StopIteration if FUSE client is detached from eos_prefix
        next(gen)
        return True
    except StopIteration as e:
        logger.critical(f'EOS FUSE mount is not avaliable at {eos_prefix}!')
        os.exit(1)

@logger.catch
def get_new_run(server, credentials):
    @retry(wait_fixed=2000, stop_max_attempt_number=5)
    def _new():
        response = requests.get('http://'+server+"/runs/next", auth=credentials)
        response.raise_for_status()
        return response

    try:
       response = _new()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == requests.codes.GONE:
            logger.success(f'No more runs to copy, we are done!')
            sys.exit(0)
        else:
            logger.critical(f'Unexpected HTTP error {e}')
        raise 
    except requests.exceptions.RequestException as e:
        logger.critical('''Failed to get response from server,
                          shutdown the process {}'''.format(os.getpid()))
        raise
    json = response.json()
    run, pathes_n_cksums = json['run'], json['files']
    pathes = [path for path, _ in pathes_n_cksums]
    cksums = [cksum for _, cksum in pathes_n_cksums]
    return run, pathes, cksums

@retry(wait_fixed=2000, stop_max_attempt_number=5)
def finalize_run(server, credentials, message):
    response = requests.post('http://'+server+"/runs/finalize", auth=credentials, data=message.json())
    response.raise_for_status()
    return response

def event_loop(config):
    credentials = (config['login'], config['passwd'])
    server = config['server_address']
    ihep_host = config['ihep_host']
    eos_home = config['eos_home']


    # path like /eos
    eos_prefix = '/' + eos_home.split('/')[1]

    temp, rsync_process = None, None
    
    while True:
        eos_is_up(eos_prefix)
        run, pathes, cksums = get_new_run(server, credentials)
        temp =  NamedTemporaryFile(mode='w+t')
        logger.debug(f'Created temporaty file {temp.name} to fill with pathes to transfer in {run}')
        
        # prepare the file list for rsync process
        for path in pathes:
            temp.write(path+'\n')
        # force writing to the disk
        temp.seek(0)

        filelist = temp.name
        if "failed" in run:
            rsync_command = RSYNC_REWRITE_COMMAND.format(**locals())
        else:
            rsync_command = RSYNC_VERBOSE_COMMAND.format(**locals())


        logger.info(f'Starting new copy process for {run}')
        logger.debug(f'Executing {rsync_command}')
        rsync_process = subprocess.Popen(rsync_command.split())

        # WILL BLOCK EXECUTION UNTIL RSYNC ENDS 
        logger.debug(f'Blocking till rsync finishes')
        waiter = rsync_process.wait()
        logger.debug(f'Rsync is done!')
        # when rsync terminate, close temporary file
        temp.close()
        # compute and compare checksums:
        logger.debug(f'Computing checksums')
        wrong_checksums_files = []
        for path, cksum in zip(pathes, cksums):
            path_in_eos = os.path.join(eos_home, path)
            if compute_adler(path_in_eos) != cksum:
                wrong_checksums_files.append((path, cksum))

        n_wrong_files = len(wrong_checksums_files)
        if n_wrong_files:
            logger.warning(f'{n_wrong_files} files with wrong checksums, sending to server for resubmit')
            msg = ClientMessage(run=run,
                                status=Status.IntegrityFailed,
                                failed_files=wrong_checksums_files)
        else:
            logger.info(f'Zero files failed checksums')
            msg = ClientMessage(run=run, status=Status.Done)

        finalize_run(server=server, credentials=credentials, message=msg)





if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', type=int, nargs=1, help='Index of process, for systemd')
    args = parser.parse_args()
    i = args.i

    if i:
        logpath = os.path.join(os.getcwd(), 'warden_client_{}.log'.format(i))
    else:
        logpath = os.path.join(os.getcwd(), 'warden_client_{}.log'.format(os.getpid()))

    logger.add(logpath, backtrace=True, diagnose=True, rotation='500 MB')

    config = get_config()
    event_loop(config)
    
