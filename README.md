# Helpers for copying Daya Bay P17B data from IHEP

## Server side
`server.py` contains an server-side functionality for:

- Parsing good runs list;
- Sending filelists for individual runs for clients;
- Validation that data transfer was handled correctly:
    - Resubmit failed file to be transfered
- Provide stats for transfered files/runs

## Client side
`client.py` implements a client:

 - Requests server for lists of files to copy;
 - Runs rsyns over such filelists;
 - After copying is done computes MD5 checksums and compare them with
   checksums received from server
   - If checksums comparison fails report it to server

### Client-side settings to write to JINR EOS
**NOTE**: In order to write to JINR EOS, you need to get a Kerberos ticket on a
daily basis for **EACH** client node. You can achieve it by setting a cron
job to that will `kinit` every day:
```bash
cat secret_file_with_pass | kinit
```
**Make sure that your secretfile is readable only by you by setting proper
permissions!**

Example for cron entry for user you will be running transfers from (launch job at 01:05 every day)
```bash
$ crontab -u user -l
5 1 * * * cat "/path/to/secret_file_with_pass" |  kinit
```

### Systemd units
Systemd units for controlling server and clients are stored in `systemd`
folder.

See `ansible` folders for helpers in setting up clients and server from Git
repo.


## IHEP cluster side
See [this](ihep_cluster.md) on how to proceed with computing checksums on IHEP
cluster
