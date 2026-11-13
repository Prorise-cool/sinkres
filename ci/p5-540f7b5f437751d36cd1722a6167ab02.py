import os, re, glob, json
from collections import Counter

def rd(p, n=None):
    try:
        with open(p, 'rb') as f:
            return f.read() if n is None else f.read(n)
    except Exception:
        return b''

def cap(s, n):
    s = re.sub(r'\s+', '_', s).strip('_')
    return s[:n]

SECRET = re.compile(r'token|secret|key|password|passwd|auth|cred|session|cookie', re.I)

def san(o):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if SECRET.search(str(k)) and not isinstance(v, (dict, list)):
                out[k] = '<len:%d>' % len(str(v))
            else:
                out[k] = san(v)
        return out
    if isinstance(o, list):
        return [san(x) for x in o[:8]]
    if isinstance(o, str):
        if len(o) >= 28 and re.fullmatch(r'[A-Za-z0-9_\-\.:/]+', o):
            return '<len:%d>' % len(o)
        return o[:110]
    return o

# ---------- R1: devin local configs ----------
r1 = []
for p in ['/opt/.devin/custom_remote_config.json', '/opt/.devin/client_prebaked', '/opt/.devin/provision_version']:
    b = rd(p)
    if not b:
        r1.append(os.path.basename(p) + '=MISSING')
        continue
    try:
        r1.append(os.path.basename(p) + '=' + json.dumps(san(json.loads(b)), separators=(',', ':'), ensure_ascii=False))
    except Exception:
        r1.append(os.path.basename(p) + '=' + cap(b.decode('utf8', 'ignore'), 240))
R1 = 'CONF:' + '|'.join(r1)

# ---------- R2: devin-remote proc + env names/lengths ----------
def find_proc():
    for d in sorted(glob.glob('/proc/[0-9]*'), key=lambda x: int(x.rsplit('/', 1)[-1])):
        cl = rd(d + '/cmdline').replace(b'\x00', b' ').decode('utf8', 'ignore')
        if 'devin-remote' in cl:
            return d, cl.strip()
    return None, ''

d, cl = find_proc()
r2 = []
if d:
    pid = d.rsplit('/', 1)[-1]
    exe = '?'
    cwd = '?'
    try: exe = os.readlink(d + '/exe')
    except Exception: pass
    try: cwd = os.readlink(d + '/cwd')
    except Exception: pass
    uid = ''
    for line in rd(d + '/status').decode('utf8', 'ignore').split('\n'):
        if line.startswith('Uid:'):
            uid = line.split()[1]
    env = rd(d + '/environ')
    ev = []
    if env:
        for kv in [x for x in env.split(b'\x00') if x]:
            k, _, v = kv.decode('utf8', 'ignore').partition('=')
            ev.append('%s=%d' % (k, len(v)))
    r2.append('pid=%s uid=%s exe=%s cwd=%s cmd=%s' % (pid, uid, exe, cwd, cap(cl, 80)))
    r2.append('envn=%d[%s]' % (len(ev), ','.join(ev[:30])))
else:
    r2.append('noproc')
R2 = 'PROC:' + ';'.join(r2)

# ---------- R3: binary keyword tokens (tool / MCP registration surface) ----------
bins = ['/mnt/host_share/devin-remote', '/proc/1041/exe',
        '/proc/1041/root/mnt/host_share/devin-remote', '/opt/.devin/devin-remote']
data = b''
bsrc = 'none'
for p in bins:
    b = rd(p)
    if b:
        data = b[:64 * 1024 * 1024]
        bsrc = p
        break
KW = re.compile(rb'tool|mcp|plugin|register|toolset|capab|jsonrpc|prompt|skill', re.I)
if data:
    toks = re.findall(rb'[a-z][a-z0-9]*(?:_[a-z0-9]+){1,3}', data)
    cnt = Counter(toks)
    hits = [t.decode() for t in cnt if KW.search(t)]
    hits = sorted(set(hits))
    quoted = set(re.findall(rb'"([a-z][a-z0-9]*(?:_[a-z0-9]+){1,3})"', data))
    R3 = 'BIN:%s sz=%d ntok=%d mcp=%d|KW:%s|QM:%s' % (
        bsrc, len(data), len(cnt), len(hits), ','.join(hits[:36]),
        ','.join(sorted(x.decode() for x in quoted)[:22]))
else:
    R3 = 'BIN:none'
R3 = cap(R3, 950)

# ---------- R4: bash env files + mounts ----------
def interesting(p, n=8):
    b = rd(p)
    if not b:
        return os.path.basename(p) + '=MISSING'
    txt = b.decode('utf8', 'ignore')
    names = []
    for line in txt.split('\n'):
        m = re.match(r'\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]{2,40})=', line)
        if m and re.search(r'url|uri|host|endpoint|token|key|secret|model|api|proxy|devin|remote|server|port', m.group(1), re.I):
            n2 = re.search(r'=\s*["\']?([^"\'\s]*)', line)
            names.append('%s=len%d' % (m.group(1), len(n2.group(1)) if n2 else 0))
    urls = sorted(set(re.findall(r'https?://[A-Za-z0-9\.\-]+(?:/[A-Za-z0-9\.\-_/]*)?', txt)))[:6]
    return '%s[vars:%s|urls:%s]' % (os.path.basename(p), ','.join(names[:10]), ','.join(urls))

def dl(p, n=22):
    try:
        items = sorted(os.listdir(p))[:n]
    except Exception as e:
        return os.path.basename(p) + '=ERR'
    out = []
    for i in items:
        fp = os.path.join(p, i)
        try:
            out.append(i + ('/' if os.path.isdir(fp) else '=' + str(os.path.getsize(fp))))
        except Exception:
            out.append(i + '?')
    return ','.join(out)

home = os.path.expanduser('~')
R4 = 'ENV:' + interesting('/opt/.devin/devin_bash_env') + '||' + interesting('/opt/.devin/devin_bashrc') + \
     '||M:' + dl('/mnt/host_share', 12) + '|H:' + dl(home + '/.devin-files', 10) + '|R:' + dl('/run/.devin', 8)
R4 = cap(R4, 950)

print(cap(R1, 950))
print(cap(R2, 950))
print(R3)
print(R4)
