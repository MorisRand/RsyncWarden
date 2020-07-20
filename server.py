#! /usr/bin/python3

import os
from typing import List, Dict, Optional
from collections import defaultdict
import tempfile

from loguru import logger
import yaml
import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from common.models import CopyStatus

app = FastAPI()
security = HTTPBasic()

runs = None 
copied_runs = dict()
runs_in_process = dict()


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



@app.get("/" )
async def root(credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    return {"message": credentials.username }

@app.put("/dummy/runs/finilize")
async def add_run_to_completed(payload: Payload, credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    copied_runs.update({payload.run: payload.status})

@app.put("/runs/finilize")
async def add_run_to_completed(run: str, credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    copied_runs.update({run: Status.ShouldCheckIntegrity})

@app.get("/runs/completed")
async def completed_runs(credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    return copied_runs

@app.get("/runs/total")
async def total_runs(credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    return len(runs)

@app.get("/runs/copied/total")
async def total_runs(credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    return len(copied_runs)

@app.get("/runs/next")
async def send_next_run(credentials: HTTPBasicCredentials = Depends(Auth.get_credentials)):
    pass

def get_configuration() -> Dict[str, Optional[str]]:
    try:
        with open(os.path.abspath('server_conf.yaml'), 'r') as f:
            config = yaml.load(f)
    except (FileNotFoundError, ValueError):
        logger.warning("No conf.yaml found in {}, rely on environmental vars to get credentials".format(os.getcwd()))
        return None
    return config


def parse_good_run_list(good_run_list, groupby_idx=7):
    good_runs = defaultdict(list)
    with open(good_run_list, 'r') as f:
        run_in_process = None
        for path in f:
            tokens = path.split('/')
            current_run = tokens[groupby_idx]
            good_runs[current_run].append(path)

    return good_runs

@app.on_event('startup')
def init():
    logger.add("{}.log".format(os.getpid()))
    config = get_configuration()
    try:
        Auth.login =  config['credentials']['user']
        Auth.passwd = config['credentials']['passwd']
    except:
        Auth.login = os.environ.get('CLIENT_USER')
        Auth.passwd = os.environ.get('CLIENT_PASSWD')

    assert Auth.login
    assert Auth.passwd
    good_run_file_path = config['good_runs'] or os.environ.get('GOOD_RUNS')

    assert good_run_file_path, "Must provide a good run list for a server!"

    global runs
    if not config.get('good_runs_groupby_idx'):
        runs = parse_good_run_list(os.path.abspath(good_run_file_path))
    else:
        runs = parse_good_run_list(os.path.abspath(good_run_file_path), config.get('good_runs_groupby_idx'))
    logger.info('Initialized good run list')

@app.on_event('shutdown')
def dump_copied_runs():
    with open('copied_runs.lst', 'w') as f:
        yaml.dump(copied_runs, f)
        