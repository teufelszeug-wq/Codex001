"""Fail-closed real-race audit: never count CI or post-off predictions as pre-off."""
import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

REQUIRED = ('race_id','version','saved_at','off_at','source_refs','records')
def git_pre_off_evidence(file, off, repo, saved=None):
    repo = Path(repo).resolve()
    file = Path(file).resolve()
    relative = file.relative_to(repo).as_posix()
    log = subprocess.run(['git', '-C', str(repo), 'log', '--format=%H', '--', relative],
                         capture_output=True, text=True, check=True)
    for sha in log.stdout.splitlines():
        blob = subprocess.run(['git', '-C', str(repo), 'show', f'{sha}:{relative}'],
                              capture_output=True, check=True).stdout
        if blob != file.read_bytes():
            continue
        stamp = subprocess.run(['git', '-C', str(repo), 'show', '-s', '--format=%cI', sha],
                               capture_output=True, text=True, check=True).stdout.strip()
        if datetime.fromisoformat(stamp) < off and (saved is None or datetime.fromisoformat(stamp) >= saved):
            return {'commit_sha': sha, 'committed_at': stamp}
    return None

def audit(targets, forecast_files, git_repo=None):
    by_id = {r['race_id']:r for r in targets['targets']}
    if len(by_id)!=len(targets['targets']):
        raise ValueError('duplicate target race IDs')
    rows={rid:{'race_id':rid,'pre_off_verified':False,'reason':'NO_VERIFIED_PRE_OFF_FORECAST'} for rid in by_id}
    rejected=[]
    candidates=[]
    for file in forecast_files:
        try:
            doc=json.loads(Path(file).read_text(encoding='utf-8'))
            if any(k not in doc for k in REQUIRED):raise ValueError('required forecast fields missing')
            rid=doc['race_id']
            if rid not in by_id:continue
            saved=datetime.fromisoformat(doc['saved_at'])
            off=datetime.fromisoformat(doc['off_at'])
            expected=datetime.fromisoformat(by_id[rid]['off_at'])
            if (not saved.tzinfo or saved.utcoffset() is None or
                not off.tzinfo or off.utcoffset() is None or
                not expected.tzinfo or expected.utcoffset() is None or
                saved >= off or off != expected):
                raise ValueError('not a verified pre-off timestamp')
            if type(doc['version']) is not int or doc['version']<1 or not doc['source_refs'] or not doc['records']:
                raise ValueError('missing version, source, or predictions')
            if not isinstance(doc['records'],list) or not all(isinstance(r,dict) for r in doc['records']):
                raise ValueError('records must be a nonempty list of objects')
            if not all(isinstance(r.get('forecaster_id'),str) and r['forecaster_id'].strip() for r in doc['records']):
                raise ValueError('each record requires a nonblank forecaster_id')
            forecaster_ids = [r['forecaster_id'].strip() for r in doc['records']]
            if len(forecaster_ids) != len(set(forecaster_ids)):
                raise ValueError('duplicate forecaster_id within forecast version')
            if not isinstance(rid,str) or not rid.strip():
                raise ValueError('race_id must be a nonblank string')
            if not isinstance(doc['source_refs'],list) or not all(isinstance(s,str) and s.strip() for s in doc['source_refs']):
                raise ValueError('source_refs must be a nonempty list of nonblank strings')
            # A self-reported timestamp is a candidate, not independent proof.
            # Ordinary Git history or contemporaneous storage logs are sufficient;
            # third-party TSA/Object Lock is NOT required.
            evidence = None
            if git_repo is not None:
                try:
                    evidence = git_pre_off_evidence(file, off, git_repo, saved)
                except (OSError, ValueError, subprocess.CalledProcessError) as exc:
                    rejected.append({'file':str(file),'error_type':type(exc).__name__,
                                     'reason':'Git evidence check failed: '+str(exc)})
            if evidence:
                rows[rid].update(pre_off_verified=True, reason='GIT_COMMIT_PRE_OFF_VERIFIED',
                                 evidence=evidence)
            elif not rows[rid]['pre_off_verified']:
                # An unverified duplicate must not erase earlier verified evidence.
                rows[rid]['reason']='PRE_OFF_CANDIDATE_AWAITING_GIT_OR_STORAGE_HISTORY'
            candidates.append({'race_id':rid,'file':str(file),'saved_at':doc['saved_at'],
                               'off_at':doc['off_at'],'version':doc['version'],
                               'source_refs':doc['source_refs']})
        except (OSError,ValueError,TypeError,KeyError) as exc:
            # Keep a machine-readable failure trail instead of silently dropping
            # malformed or temporally invalid evidence.
            rejected.append({'file':str(file),'error_type':type(exc).__name__,'reason':str(exc)})
    return {'schema':'prism.real_race_audit/v1','target_count':len(by_id),
            'verified_pre_off_count':sum(r['pre_off_verified'] for r in rows.values()),
            'status':'CRITICAL' if not any(r['pre_off_verified'] for r in rows.values()) else 'INCOMPLETE',
            'races':list(rows.values()),'pre_off_candidates':candidates,
            'pre_off_candidate_count':len(candidates),
            'rejected_files':rejected,'rejected_count':len(rejected)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--targets',type=Path,required=True)
    p.add_argument('--forecast',type=Path,action='append',default=[])
    p.add_argument('--git-repo',type=Path)
    a=p.parse_args()
    print(json.dumps(audit(json.loads(a.targets.read_text(encoding='utf-8')),a.forecast,a.git_repo),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
