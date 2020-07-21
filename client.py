#!/usr/bin/python3

import os
from os.path import abspath
import subprocess
import time
from tempfile import NamedTemporaryFile

import yaml
import requests
from retrying import retry
from loguru import logger

from common.models import ClientMessage, Status

RSYNC_VERBOSE_COMMAND = '''rsync -h --progress -avzp --ignore-existing
                           --files-from={filelist}  rsync://{ihep_host}:/dybfs {eos_home}'''
RSYNC_REWRITE_COMMAND = '''rsync -h --progress -avzp 
                            --files-from={filelist}  rsync://{ihep_host}:/dybfs {eos_home}'''
RSYNC_SILENT_COMMAND = '''rsync -avzp 
                            --files-from={filelist}  rsync://{ihep_host}:/dybfs {eos_home}'''

def get_config():
    try:
        with open(abspath("client_config.yaml"), 'r') as f:
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


@logger.catch()
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

def event_loop(config):
    credentials = (config['login'], config['passwd'])
    server = config['server_address']
    ihep_host = config['ihep_host']
    eos_home = config['eos_home']

    copying_in_progress, checking_cksums = False
    while True:
        if not copying_in_progress:
            run, pathes, cksums = get_new_run(server, credentials)

        logger.info(f'Starting new copy process for {run}')
        with NamedTemporaryFile(mode='w+t') as temp:
            # prepare the file list for rsync process
            for path in pathes:
                temp.write(path+'\n')
            # force writing to the disk
            temp.seek(0)

            filelist = temp.name

            time.sleep(5)







if __name__ == "__main__":
    logger.add('client_{}.log'.format(os.getpid()), backtrace=True,
            diagnose=True, rotation='500 MB')
    config = get_config()
    event_loop(config)
    
