# Helpers for copying Daya Bay P17B data from IHEP

## Server side
`server.py` contains an server-side functionality for:

- Parsing good runs list;
- Sending filelists for individual runs for clients
- Validation that data transfer was handled correctly:
   - Comparing file lists in JINR EOS and good run list
   - Checking MD5 checksums for each file

## How to compute MD5 checksums on IHEP cluster:
The guide to computing in IHEP cluster guide is [available](http://afsapply.ihep.ac.cn/cchelp/en/).
Main gotchas:
- If you use **public key** authentication to enter **lxslc7.ihep.ac.cn**:
    - `kinit` -- authorize in IHEP Kerberos
    - `aklog -d` -- authorize in IHEP AFS using Kerberos ticket
- Your work area is in `/scratchfs/dyw/{user}`.
- P17B data is in `/dybfs/rec/P17B`
- Use `HepJob` to [submit tasks](http://afsapply.ihep.ac.cn/cchelp/en/local-cluster/jobs/HTCondor/)
- One can get a list of unique runs in good run list with:
```bash
awk -F / '{for (i=6; i <= 8; i++) printf $i""FS; print""}' /dybfs/rec/P17B/GoodRun_v3/paths.physics.good.p17b.v3.sync.txt | uniq > good_runs_individual.tx
```
- One needs to prepare a number of executable scripts to run via HepJob.
  Script `ihep_sub_for.py` will prepare a bunch of scripts for computing MD5
  checksums for each run using `md5sum` command. It will create a `jobs/`
  folder in `$PWD`.
```bash
python ihep_sub_for.py good_runs_individual.txt
```
- Submit tasks all at once with:
```bash
hep_sub jobs/job_%{ProcId}.sh -n N
```
> `N` should be equal to a number of tasks in `jobs`. Indexing **starts with
> zero**

- Find checksums missing after computing on IHEP cluster:
```bash
python3 merge_checksums.py path/to/folder/with/checksums --good-runs paths.physics.good.p17b.v3.sync.txt --missing-files missing.txt
```
