#! /usr/bin/python3

import os
import sys
from os.path import abspath
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import signal
import subprocess

from loguru import logger
import yaml
import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from common.models import Status, ClientMessage
from common.utils import FailedFiles

config = None

def count_files():
    command = f'find {config["EOS_DYBFS"]} -print'
    out = subprocess.check_output(command.split()).decode()
    out = out.split('\n')
    return len(out) - 1

app = FastAPI()
security = HTTPBasic()

runs = None 
copied_runs: Dict[str, Status] = dict()

runs_in_process = dict()

total_failed_files = FailedFiles()



class Auth:
    login  = None 
    passwd = None

    @staticmethod
    def get_credentials(credentials: HTTPBasicCredentials = Depends(security)):
        correct_username = secrets.compare_digest(credentials.username, Auth.login)
        correct_password = secrets.compare_digest(credentials.password, Auth.passwd)
        if not (correct_username and correct_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect login or password",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials

def task_overdue(submit_date):
    return (submit_date + timedelta(days=1.5)) < datetime.now()

def reschedule_hanged_tasks():
    should_remove = []
    for run, (submit_date, pathes) in runs_in_process.items():
        if task_overdue(submit_date):
            should_remove.append(run)

    total_hanged = len(should_remove)
    if total_hanged:
        logger.warning(f'{total_hanged} tasks are overdue by 2 days, taking them back to queue')

    for run in should_remove:
        _, pathes = runs_in_process.pop(run)
        runs[run] = pathes

@app.post("/runs/finalize")
async def add_run_to_completed(message: ClientMessage, credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    if message.status == Status.IntegrityFailed:
        failed_files_run = "failed_" + str(total_failed_files.integrity_failed_counter)
        total_failed_files.integrity_failed_counter += 1
        if message.failed_files:
            failed_in_run = message.failed_files
            total_failed_files.update(failed_in_run)
            good_failed = [_ for _ in failed_in_run 
                           if  _ not in total_failed_files.spurious_files] 
            n_failed = len(good_failed)
            if good_failed:
                runs[failed_files_run] = good_failed
                logger.warning(f'{message.run} reported {n_failed} new files with wrong checksums! Resubmitted new corrupted files')
            else:
                logger.critical(f'Some files with wrong checksums got reported '
                        'more then 4 times, stopping resubmitting it. It needs closer look.')
        else:
            logger.warning(f'{message.run} reported files with wrong checksums but provided empty list of corrupt files! Need closer look')

    try:
        runs_in_process.pop(message.run)
    except KeyError:
        logger.warning(f'{message.run} reported after it was rescheduled! Checking the waiting queue for it.')
        try:
            _ = runs.pop(message.run)
            logger.warning(f'{message.run} was removed from waiting queue.')
        except KeyError:
            logger.critical(f'{message.run} was not in waiting queue. Data corruption possible!')

    if not "failed" in message.run:
        copied_runs.update({message.run: Status.Done})
    logger.success(f'Finished copying {message.run}')
    reschedule_hanged_tasks()
    

@app.get("/files/completed")
async def completed_files(credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    return count_files()

@app.get("/files/corrupted")
async def files_corrupted(credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    return total_failed_files.spurious_files

@app.get("/runs/completed")
async def completed_runs(credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    return copied_runs

@app.get("/runs/remained/total")
async def total_runs(credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    return len(runs)

@app.get("/runs/copied/total")
async def total_copied_runs(credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    return len(copied_runs)

@app.get("/runs/next")
async def send_next_run(credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    try:
        entry = runs.popitem()
        run, pathes = entry
        start = datetime.now()
        runs_in_process[run] = (start, pathes)
        return {'run': run, 'files': pathes}
    except KeyError:
        raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="All runs are processed!"
                )


def get_configuration() -> Dict[str, Optional[str]]:
    try:
        with open(os.path.abspath('server_conf.yaml'), 'r') as f:
            config = yaml.load(f)
    except (FileNotFoundError, ValueError):
        logger.warning("No conf.yaml found in {}, rely on environmental vars to get credentials".format(os.getcwd()))
        return None
    return config


def parse_good_run_list(good_run_list, groupby_idx=5):
    good_runs: defaultdict[str: List[Tuple[str,str]]] = defaultdict(list)
    with open(good_run_list, 'r') as f:
        run_in_process = None
        for entry in f:
            path, cksum = entry.split(' ')
# trim '/dybfs/', necessary for rsync to read files to copy from list
            path = path.lstrip('/').split('/')
            path = '/'.join(path[1:])
            tokens = path.split('/')
            current_run = tokens[groupby_idx]
            good_runs[current_run].append((path, cksum.rstrip('\n')))
    return good_runs

@app.on_event('startup')
def init():
    '''Init configuration'''
    logger.add("warden_server.log")
    set_gracefull_shutdown()

    global config
    config = get_configuration()
    try:
        _ = (config['EOS'], config['EOS_DYBFS'])
    except KeyError:
        config['EOS'] = os.environ['EOS']
        config['EOS_DYBFS'] = os.environ['EOS_DYBFS']

    try:
        Auth.login =  config['credentials']['user']
        Auth.passwd = config['credentials']['passwd']
    except:
        Auth.login = os.environ.get('CLIENT_USER')
        Auth.passwd = os.environ.get('CLIENT_PASSWD')

    assert Auth.login and Auth.passwd,  "Must provide login and password for clients authentication"
    good_run_file_path = config['good_runs'] or os.environ.get('GOOD_RUNS')

    assert good_run_file_path, "Must provide a good run list for a server!"

    global runs
    if not config.get('good_runs_groupby_idx'):
        runs = parse_good_run_list(os.path.abspath(good_run_file_path))
    else:
        runs = parse_good_run_list(os.path.abspath(good_run_file_path), config.get('good_runs_groupby_idx'))
    logger.info('Initialized good run list')

    previously_copied = abspath('copied_runs.yaml')
    if os.path.exists(previously_copied) and config.get('check_previously_copied'):
        logger.info(f'Found previosly copied runs on {previously_copied}')
        with open(previously_copied) as f:
            previously_copied_runs = yaml.load(f)

        global copied_runs
        for run, status in previously_copied_runs.items():
            if status == Status.Done:
                del runs[run]
                logger.debug(f'Removing {run} from run list as it is copied')
            copied_runs[run] = status

def dump_copied_runs():
    '''Save info about runs that were copied'''
    if copied_runs:
        with open('copied_runs.yaml', 'w') as f:
            yaml.dump(copied_runs, f)

def dump_spurious_files():
    '''Save pathes of notorious files with likely wrong checksums'''
    path = abspath('wrong_checksums_files.txt')
    with open(path, 'w') as f:
        for path in total_failed_files.spurious_files:
            f.write(os.path.join('/dybfs', path)+"\n")
    
def gracefull_shutdown(signum=signal.SIGTERM, frame=None):
    '''Shutdown at SIGTERM but dump copied runs'''
    dump_copied_runs()
    dump_spurious_files()
    sys.exit(0)

def set_gracefull_shutdown():
    signal.signal(signal.SIGTERM, gracefull_shutdown)

exit_handler = app.on_event('shutdown')(gracefull_shutdown)
