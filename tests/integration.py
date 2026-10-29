#!/usr/bin/env python3
"""Linux disposable instances only. Never writes to a production endpoint."""
import argparse
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import stt


def count(c):
    raw = stt.compose(c,'exec','-T','postgres','psql','-At','-U',c['POSTGRES_USER'],c['POSTGRES_DB'],
                      '-c','SELECT count(*) FROM xapi_statement',capture_output=True,text=True).stdout
    return int(raw.strip())


def run():
    if os.name != 'posix': raise ValueError('Run on disposable Linux Docker host')
    instances = []
    with tempfile.TemporaryDirectory(prefix='yet-integration-') as tmp:
        try:
            for i in range(2):
                args = argparse.Namespace(root=str(Path(tmp)/str(i)),project='yet-check-'+Path(tmp).name+'-'+str(i),
                    service='yet',environment='test',url='https://lrs-'+str(i)+'.invalid',port=28183+i,admin='test-admin')
                c = stt.profile(stt.initialize(args))
                instances.append(c)
                stt.check(c)
                stt.collision(c)
                stt.compose(c,'up','-d','--wait','--wait-timeout','300')
                stt.verify(c,write=True)
                stt.compose(c,'restart','--no-deps','lrsql')
                stt.compose(c,'up','-d','--no-deps','--wait','--wait-timeout','300','lrsql')
                stt.verify(c)
            a,b = instances
            import base64
            bad = base64.b64encode((a['LRSQL_API_KEY']+':'+a['LRSQL_API_SECRET']).encode()).decode()
            assert stt.request('http://127.0.0.1:'+b['LRSQL_HTTP_PORT']+'/xapi/statements',
                {'Authorization':'Basic '+bad,'X-Experience-API-Version':'1.0.3'})[0] == 401
            for key in ('LRSQL_HTTP_PORT','POSTGRES_DATA_PATH'):
                other = dict(b)
                other[key] = a[key]
                try: stt.collision(other)
                except ValueError: pass
                else: raise AssertionError('Collision accepted: '+key)
            before = count(a)
            assert before == 4 and count(b) == 4
            stt.backup(a)
            backup = next(p for p in Path(a['BACKUP_ROOT']).iterdir() if p.name[0].isdigit())
            args.root = str(Path(tmp)/'restore')
            args.project += '-restore'
            args.port = 28185
            restored_path = stt.initialize(args)
            target = stt.read_env(restored_path)
            with tarfile.open(backup/'private.tar.gz') as archive:
                secret = archive.extractfile('secrets.env').read()
            (Path(target['SECRET_ROOT'])/'secrets.env').write_bytes(secret)
            restored = stt.profile(restored_path)
            instances.append(restored)
            stt.restore(restored,str(backup))
            stt.verify(restored)
            assert count(restored) == before
            try: stt.restore(restored,str(backup))
            except ValueError: pass
            else: raise AssertionError('Nonempty restore accepted')
            print(json.dumps({'result':'PASS','instances':2,'versions':['1.0.3','2.0.0'],
                'statements_each':4,'persistence':True,'cross_credentials_rejected':True,
                'collisions_rejected':True,'backup_restore':True}))
        finally:
            for c in reversed(instances):
                if not c['COMPOSE_PROJECT_NAME'].startswith('yet-check-'):
                    raise ValueError('Unexpected cleanup target')
                stt.compose(c,'down','--volumes',stdout=sys.stderr)


if __name__ == '__main__': run()
