#!/usr/bin/env python3
"""Independent SQL LRS operations. Profiles are data, never shell code."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import uuid

ROOT = Path(__file__).resolve().parents[1]
PG_IMAGE = 'postgres:16.15-alpine3.24@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab'
LRS_IMAGE = 'yetanalytics/lrsql:v0.9.11@sha256:bf5661ab216d07175f6e429951bf53c79f6070d54812285ea4c208f991cf0a04'
SECRET_KEYS = ('POSTGRES_PASSWORD', 'LRSQL_ADMIN_PASSWORD', 'LRSQL_API_KEY', 'LRSQL_API_SECRET')


def read_env(path):
    result = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or key in result:
            raise ValueError('Invalid or duplicate profile key')
        if not value or any(x in value for x in ('$', '`', '\x00', '"', "'")):
            raise ValueError('Empty value, quotes or expansion in profile: '+key)
        if 'GENERATE_ME' in value or 'example.com' in value:
            raise ValueError('Example value in profile: '+key)
        result[key] = value
    return result


def private(path, directory=False):
    p = Path(path)
    if os.name != 'nt':
        mode = 0o700 if directory else 0o600
        if p.stat().st_mode & 0o777 != mode:
            raise ValueError('Private permissions required on '+p.name)


def absolute(value):
    p = Path(value)
    if not p.is_absolute() or p == Path(p.anchor) or '..' in p.parts:
        raise ValueError('Absolute non-root path required')
    return p.resolve()


def profile(path):
    p = absolute(path)
    private(p)
    c = read_env(p)
    files = [str(p)]
    if c.get('SECRET_ROOT'):
        private(c['SECRET_ROOT'], True)
        secret_file = absolute(c['SECRET_ROOT'])/'secrets.env'
        private(secret_file)
        s = read_env(secret_file)
        if set(s) & set(c) or set(s) != set(SECRET_KEYS):
            raise ValueError('Unexpected or duplicate private option')
        c.update(s)
        files.append(str(secret_file))
    required = ('POSTGRES_DB', 'POSTGRES_USER', 'LRSQL_ADMIN_USER', 'LRSQL_HTTP_PORT', 'LRSQL_PUBLIC_URL')+SECRET_KEYS
    if any(not c.get(k) for k in required):
        raise ValueError('Missing required profile option')
    c.setdefault('COMPOSE_PROJECT_NAME', 'yet-lrsql')
    c.setdefault('POSTGRES_IMAGE', PG_IMAGE)
    c.setdefault('LRSQL_IMAGE', LRS_IMAGE)
    for key, value in {'POSTGRES_CPUS':'1','POSTGRES_MEMORY':'512m','LRSQL_CPUS':'2',
                       'LRSQL_MEMORY':'1536m','LRSQL_LOG_LEVEL':'INFO',
                       'JAVA_TOOL_OPTIONS':'-XX:MaxRAMPercentage=60.0 -XX:InitialRAMPercentage=10.0'}.items():
        c.setdefault(key,value)
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]+', c['COMPOSE_PROJECT_NAME']):
        raise ValueError('Invalid Compose project')
    for k in ('POSTGRES_DB', 'POSTGRES_USER', 'LRSQL_ADMIN_USER'):
        if not re.fullmatch(r'[A-Za-z0-9_.@+-]+', c[k]):
            raise ValueError('Invalid identifier: '+k)
    u = urlsplit(c['LRSQL_PUBLIC_URL'])
    if u.scheme != 'https' or not u.hostname or u.path or u.query or u.fragment or u.username or u.port:
        raise ValueError('Public URL must be an HTTPS origin without path')
    if not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', u.hostname):
        raise ValueError('Invalid public DNS name')
    if not 1024 <= int(c['LRSQL_HTTP_PORT']) <= 65535:
        raise ValueError('Invalid loopback port')
    for k in SECRET_KEYS:
        if not re.fullmatch(r'[A-Za-z0-9_+=/@.%-]{32,}', c[k]):
            raise ValueError('At least 32 safe characters required: '+k)
    for k in ('POSTGRES_IMAGE', 'LRSQL_IMAGE'):
        if not re.fullmatch(r'[A-Za-z0-9./:_-]+@sha256:[a-f0-9]{64}', c[k]):
            raise ValueError('Image digest required: '+k)
    areas = []
    for k in ('POSTGRES_DATA_PATH', 'SECRET_ROOT', 'BACKUP_ROOT', 'OPS_ROOT'):
        if c.get(k):
            area = absolute(c[k])
            if not area.is_dir():
                raise ValueError('Installation directory does not exist: '+k)
            areas.append(area)
    if c.get('SECRET_ROOT'):
        areas.append(p.parent)
    for i, a in enumerate(areas):
        for b in areas[i+1:]:
            if a == b or a in b.parents or b in a.parents:
                raise ValueError('Installation directories must not overlap')
    if not 1 <= int(c.get('BACKUP_KEEP', '7')) <= 100:
        raise ValueError('Invalid backup retention')
    managed = set(c) | {'COMPOSE_FILE', 'COMPOSE_ENV_FILES', 'COMPOSE_PROFILES'}
    if managed & set(os.environ):
        raise ValueError('Managed options must not be exported in the shell')
    c['_files'] = files
    return c


def compose(c, *args, **kwargs):
    env = dict(os.environ)
    env.update({k:v for k,v in c.items() if not k.startswith('_')})
    cmd = ['docker', 'compose', '--project-directory', str(ROOT), '-f', str(ROOT/'compose.yaml')]
    for path in c['_files']:
        cmd += ['--env-file', path]
    # Pin interpolation as well as resource identity; no ambient .env is used.
    return subprocess.run(cmd+['-p', c['COMPOSE_PROJECT_NAME']]+list(args), env=env, check=True, **kwargs)


def initialize(a):
    root = absolute(a.root)
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]+', a.project):
        raise ValueError('Invalid project')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', a.service) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', a.environment):
        raise ValueError('Invalid service/environment')
    base = Path(a.service)/a.environment
    paths = {k:root/category/base for k,category in (
        ('SECRET_ROOT','secretos'), ('BACKUP_ROOT','respaldos'),
        ('OPS_ROOT','operaciones/registros'))}
    config = root/'configuraciones'/base/'prod.env'
    data = root/'datos'/base/'postgres'
    if config.exists() or (paths['SECRET_ROOT']/'secrets.env').exists() or data.exists():
        raise ValueError('Existing configuration or data; refusing initialization')
    u = urlsplit(a.url)
    if not re.fullmatch(r'https://[a-z0-9]+(?:[.-][a-z0-9]+)*', a.url) or not 1024 <= a.port <= 65535:
        raise ValueError('Invalid URL or port')
    if not re.fullmatch(r'[A-Za-z0-9_.@+-]+', a.admin):
        raise ValueError('Invalid admin username')
    # Detect a published port collision before generating private material.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', a.port))
    os.umask(0o077)
    for p in [*paths.values(), config.parent, data]:
        p.mkdir(parents=True, mode=0o700, exist_ok=True)
    c = dict(COMPOSE_PROJECT_NAME=a.project, POSTGRES_IMAGE=PG_IMAGE, LRSQL_IMAGE=LRS_IMAGE,
             POSTGRES_DB='lrsql', POSTGRES_USER='lrsql', POSTGRES_DATA_PATH=str(data),
             LRSQL_ADMIN_USER=a.admin, LRSQL_HTTP_PORT=str(a.port), LRSQL_PUBLIC_URL=a.url,
             LRSQL_LOG_LEVEL='INFO', LRSQL_CPUS='2', LRSQL_MEMORY='1536m',
             POSTGRES_CPUS='1', POSTGRES_MEMORY='512m', BACKUP_KEEP='7')
    c.update({k:str(v) for k,v in paths.items()})
    secret_file = paths['SECRET_ROOT']/'secrets.env'
    with secret_file.open('x', encoding='utf-8', newline='\n') as f:
        f.write(''.join(k+'='+secrets.token_hex(32)+'\n' for k in SECRET_KEYS))
    with config.open('x', encoding='utf-8', newline='\n') as f:
        f.write(''.join(k+'='+v+'\n' for k,v in c.items()))
    profile(config)
    print('Initialized profile: '+str(config)+'; secrets not displayed')
    return config


def check(c):
    model = json.loads(compose(c, 'config', '--format', 'json', capture_output=True).stdout)
    app = model['services']['lrsql']
    ports = app['ports']
    if len(ports) != 1 or ports[0]['host_ip'] != '127.0.0.1' or model['services']['postgres'].get('ports'):
        raise ValueError('Invalid network exposure')
    if any(s.get('container_name') for s in model['services'].values()):
        raise ValueError('Explicit container name is not allowed')
    expected = c['COMPOSE_PROJECT_NAME']
    volumes = model.get('volumes', {})
    if model['networks']['yet-internal']['name'] != expected+'-internal' or (volumes and volumes['postgres_data']['name'] != expected+'-postgres-data'):
        raise ValueError('Resource identity mismatch')
    print('Profile, image digests, independent resources and loopback valid')
    return model


def collision(c):
    # Existing own containers may be updated; no other project can claim port/data.
    ids = subprocess.check_output(['docker','ps','-aq'], text=True).split()
    if ids:
        containers = json.loads(subprocess.check_output(['docker','inspect',*ids]))
        for obj in containers:
            own = (obj['Config'].get('Labels') or {}).get('com.docker.compose.project') == c['COMPOSE_PROJECT_NAME']
            for binding in (obj['HostConfig'].get('PortBindings') or {}).values():
                if not own and any(x['HostPort'] == c['LRSQL_HTTP_PORT'] for x in binding or []):
                    raise ValueError('Port already assigned to another project')
            if not own and c.get('POSTGRES_DATA_PATH'):
                data = Path(c['POSTGRES_DATA_PATH']).resolve()
                for mount in obj.get('Mounts', []):
                    source = Path(mount.get('Source','/')).resolve()
                    if source == data or source in data.parents or data in source.parents:
                        raise ValueError('Data directory already assigned to another project')
    own_ids = compose(c, 'ps', '-q', 'lrsql', capture_output=True, text=True).stdout.strip()
    if not own_ids:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', int(c['LRSQL_HTTP_PORT'])))


def request(url, headers=None, payload=None, method=None):
    data = None if payload is None else json.dumps(payload).encode()
    h = dict(headers or {})
    if data is not None:
        h['Content-Type'] = 'application/json'
    req = Request(url, headers=h, data=data, method=method)
    try:
        with urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, json.loads(raw) if 'json' in r.headers.get('Content-Type','') and raw else None
    except HTTPError as e:
        return e.code, None


def verify(c, public=False, write=False):
    base = c['LRSQL_PUBLIC_URL'] if public else 'http://127.0.0.1:'+c['LRSQL_HTTP_PORT']
    def expect(path, expected, headers=None, payload=None, method=None):
        status, body = request(base+path, headers, payload, method)
        if status != expected:
            raise ValueError('HTTP verification failed: '+path.split('?')[0]+' status '+str(status))
        return body
    expect('/admin', 200)
    expect('/admin/account/login', 401, payload={'username':c['LRSQL_ADMIN_USER'], 'password':'invalid-password'})
    login = expect('/admin/account/login', 200, payload={'username':c['LRSQL_ADMIN_USER'], 'password':c['LRSQL_ADMIN_PASSWORD']})
    bearer = {'Authorization':'Bearer '+login['json-web-token']}
    expect('/admin/verify', 204, bearer)
    expect('/admin/account', 401)
    auth = base64.b64encode((c['LRSQL_API_KEY']+':'+c['LRSQL_API_SECRET']).encode()).decode()
    for version in ('1.0.3','2.0.0'):
        h = {'Authorization':'Basic '+auth, 'X-Experience-API-Version':version}
        expect('/xapi/about', 200, h)
        expect('/xapi/statements?limit=1', 401, {'X-Experience-API-Version':version})
        expect('/xapi/statements?limit=1', 401, {**h,'Authorization':'Basic '+base64.b64encode(b'invalid:invalid').decode()})
        if write:
            for _ in range(2):
                sid = str(uuid.uuid4())
                stmt = {'id':sid,'actor':{'objectType':'Agent','account':{'homePage':'https://example.invalid','name':'isolated-verification'}},
                        'verb':{'id':'http://adlnet.gov/expapi/verbs/experienced'},
                        'object':{'id':'urn:yet:isolated-verification:'+sid}}
                expect('/xapi/statements?statementId='+sid, 204, h, stmt, 'PUT')
                if expect('/xapi/statements?statementId='+sid, 200, h)['id'] != sid:
                    raise ValueError('Statement readback mismatch')
        statements = expect('/xapi/statements?limit=1', 200, h)
        more = statements.get('more')
        if write and not more:
            raise ValueError('Expected a pagination link after isolated writes')
        if more:
            u = urlsplit(more)
            if u.netloc and (u.netloc != urlsplit(base).netloc or u.scheme != urlsplit(base).scheme):
                raise ValueError('Pagination points outside configured origin')
            expect(u.path+('?' + u.query if u.query else ''), 200, h)
        print('xAPI '+version+': authentication, read'+(', write, pagination' if write else '')+' verified')
    expect('/admin/account/logout', 200, bearer, {}, 'POST')
    print('Administration, invalid credentials and '+('HTTPS' if public else 'loopback')+' verified')


def nginx(c, tls):
    host = urlsplit(c['LRSQL_PUBLIC_URL']).hostname
    print('server { listen 80; listen [::]:80; server_name '+host+'; location ^~ /.well-known/acme-challenge/ { root /var/www/letsencrypt; } location / { return '+('301 https://'+host+'$request_uri' if tls else '503')+'; } }')
    if tls:
        print('server { listen 443 ssl; listen [::]:443 ssl; http2 on; server_name '+host+'; ssl_certificate /etc/letsencrypt/live/'+host+'/fullchain.pem; ssl_certificate_key /etc/letsencrypt/live/'+host+'/privkey.pem; ssl_protocols TLSv1.2 TLSv1.3; ssl_session_tickets off; server_tokens off; client_max_body_size 20m; add_header X-Content-Type-Options nosniff always; location / { proxy_pass http://127.0.0.1:'+c['LRSQL_HTTP_PORT']+'; proxy_http_version 1.1; proxy_set_header Connection ""; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $remote_addr; proxy_set_header X-Forwarded-Proto https; proxy_set_header X-Forwarded-Host $host; proxy_set_header X-Forwarded-Port 443; proxy_set_header Forwarded ""; proxy_read_timeout 60s; } }')


def backup(c):
    import fcntl
    os.umask(0o077)
    destination = absolute(c['BACKUP_ROOT'])
    private(destination, True)
    with (destination/'.backup.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        raw = compose(c,'ps','--format','json',capture_output=True,text=True).stdout
        states = [json.loads(x) for x in raw.splitlines() if x.strip()]
        if len(states) != 2 or any(s.get('State') != 'running' or s.get('Health') != 'healthy' for s in states):
            raise ValueError('Both services must be healthy before backup')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        pending = destination/(stamp+'.partial')
        pending.mkdir(mode=0o700)
        try:
            compose(c,'stop','--timeout','30','lrsql',stdout=subprocess.DEVNULL)
            with (pending/'database.dump').open('wb') as f:
                compose(c,'exec','-T','postgres','pg_dump','-Fc','-U',c['POSTGRES_USER'],c['POSTGRES_DB'],stdout=f)
            with tarfile.open(pending/'private.tar.gz','w:gz') as archive:
                for i, path in enumerate(c['_files']):
                    archive.add(path, arcname=('profile.env' if i == 0 else 'secrets.env'))
            (pending/'images.json').write_text(json.dumps({k:c[k] for k in ('LRSQL_IMAGE','POSTGRES_IMAGE')}))
            (pending/'revision.txt').write_bytes(subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD']))
            subprocess.run(['git','-C',str(ROOT),'bundle','create',str(pending/'source.bundle'),'HEAD'],check=True)
        finally:
            compose(c,'start','--wait','--wait-timeout','300','lrsql',stdout=subprocess.DEVNULL)
        checks = [hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name for f in sorted(pending.iterdir())]
        (pending/'SHA256SUMS').write_text('\n'.join(checks)+'\n')
        validate_backup(pending)
        pending.rename(destination/stamp)
        complete = sorted(p for p in destination.iterdir() if re.fullmatch(r'\d{8}_\d{6}',p.name) and p.is_dir() and not p.is_symlink() and (p/'SHA256SUMS').is_file())
        for old in complete[:-int(c.get('BACKUP_KEEP','7'))]:
            if old.resolve().parent != destination:
                raise ValueError('Invalid retention target')
            validate_backup(old)
            shutil.rmtree(old)
        print('Complete backup verified: '+stamp)


def validate_backup(path):
    required = {'database.dump','private.tar.gz','images.json','revision.txt','source.bundle'}
    entries = {}
    for line in (path/'SHA256SUMS').read_text().splitlines():
        digest, sep, name = line.partition('  ')
        if not sep or name not in required or name in entries or not re.fullmatch('[a-f0-9]{64}',digest):
            raise ValueError('Invalid backup manifest')
        f = path/name
        if f.is_symlink() or not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != digest:
            raise ValueError('Backup checksum mismatch')
        entries[name] = digest
    if set(entries) != required:
        raise ValueError('Incomplete backup')


def restore(c, source):
    path = absolute(source)
    validate_backup(path)
    images = json.loads((path/'images.json').read_text())
    if any(images[k] != c[k] for k in ('LRSQL_IMAGE','POSTGRES_IMAGE')):
        raise ValueError('Restore requires matching pinned images')
    data = absolute(c['POSTGRES_DATA_PATH'])
    if any(data.iterdir()) or compose(c,'ps','-aq',capture_output=True,text=True).stdout.strip():
        raise ValueError('Restore requires empty data and a new project')
    collision(c)
    compose(c,'up','-d','--wait','postgres')
    with (path/'database.dump').open('rb') as f:
        compose(c,'exec','-T','postgres','pg_restore','--exit-on-error','--no-owner','-U',c['POSTGRES_USER'],'-d',c['POSTGRES_DB'],stdin=f)
    compose(c,'up','-d','--wait','--wait-timeout','300')
    print('Restored into new independent project; original unchanged')


def timer(c, calendar):
    if os.name != 'posix' or os.geteuid() != 0:
        raise ValueError('Timer installation requires Linux root')
    if not re.fullmatch(r'\*-\*-\* \d{2}:\d{2}:\d{2} America/Santiago', calendar):
        raise ValueError('Explicit daily America/Santiago calendar required')
    name = c['COMPOSE_PROJECT_NAME']+'-backup'
    command = ' '.join(json.dumps(x) for x in ['/usr/bin/python3',str(ROOT/'scripts/stt.py'),'--env-file',c['_files'][0],'backup'])
    content = {
        'service':'[Unit]\nDescription=Consistent SQL LRS backup\nRequires=docker.service\nAfter=docker.service\n[Service]\nType=oneshot\nUMask=0077\nExecStart='+command+'\n',
        'timer':'[Unit]\nDescription=Daily SQL LRS backup\n[Timer]\nOnCalendar='+calendar+'\nPersistent=true\n[Install]\nWantedBy=timers.target\n'}
    for suffix, text in content.items():
        p = Path('/etc/systemd/system')/(name+'.'+suffix)
        if p.exists() and p.read_text() != text:
            raise ValueError('Refusing to replace a different systemd unit')
    for suffix, text in content.items():
        p = Path('/etc/systemd/system')/(name+'.'+suffix)
        p.write_text(text)
        p.chmod(0o644)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now',name+'.timer'],check=True)
    print('Installed timer '+name)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--env-file', default=str(ROOT/'.env.prod'))
    p.add_argument('action', choices=['init','check','up','restart','verify','nginx','backup','restore','timer'])
    p.add_argument('--root')
    p.add_argument('--project')
    p.add_argument('--service',default='yet')
    p.add_argument('--environment',default='prod')
    p.add_argument('--url')
    p.add_argument('--admin',default='stt-admin')
    p.add_argument('--port',type=int,default=18083)
    p.add_argument('--tls',action='store_true')
    p.add_argument('--public',action='store_true')
    p.add_argument('--write',action='store_true',help='Only for disposable instances; persists statements')
    p.add_argument('--source')
    p.add_argument('--calendar',default='*-*-* 04:50:00 America/Santiago')
    a = p.parse_args()
    if a.action == 'init':
        if not all((a.root,a.project,a.url)):
            raise ValueError('init requires --root --project --url')
        initialize(a)
        return
    c = profile(a.env_file)
    if a.action == 'check': check(c); collision(c)
    elif a.action == 'verify': verify(c,a.public,a.write)
    elif a.action == 'nginx': nginx(c,a.tls)
    elif a.action == 'backup': backup(c)
    elif a.action == 'restore': restore(c,a.source)
    elif a.action == 'timer': timer(c,a.calendar)
    elif a.action == 'up':
        check(c); collision(c)
        compose(c,'pull')
        compose(c,'up','-d','--wait','--wait-timeout','300')
        verify(c)
    elif a.action == 'restart':
        compose(c,'restart','--wait','--wait-timeout','300')
        verify(c)


if __name__ == '__main__':
    try:
        main()
    except (ValueError,OSError,subprocess.CalledProcessError) as e:
        # Do not print subprocess commands, bodies, resolved env or response data.
        message = 'External operation failed; inspect private service logs' if isinstance(e,subprocess.CalledProcessError) else str(e)
        print('ERROR: '+message, file=sys.stderr)
        sys.exit(1)
