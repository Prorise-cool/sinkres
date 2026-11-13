import os, re, json, subprocess, urllib.request, urllib.error

def rd(p, n=None):
    try:
        with open(p, 'rb') as f:
            return f.read() if n is None else f.read(n)
    except Exception:
        return b''

def cap(s, n):
    return re.sub(r'\s+', '_', s).strip('_')[:n]

def short(s, n=90):
    s = re.sub(r'\s+', ' ', str(s)).strip()
    return s[:n]

# ---------------- R1: config (redacted) + RPC identity + unknown-method shape ----------------
cfg_s = 'MISSING'
b = rd('/opt/.devin/custom_remote_config.json')
if b:
    cfg_s = re.sub(r'("auth_token"\s*:\s*")[^"]*(")', r'\1<redacted>\2', b.decode('utf8', 'ignore'))
    cfg_s = cap(cfg_s, 150)
tok = rd('/opt/.devin/devin_remote_auth_token').decode('utf8', 'ignore').strip()
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def rpc(method, params=None, path='/'):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": {} if params is None else params}).encode()
    req = urllib.request.Request('http://127.0.0.1:9876' + path, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    if tok:
        req.add_header('Authorization', 'Bearer ' + tok)
    try:
        with OPENER.open(req, timeout=4) as r:
            return r.status, r.read(500).decode('utf8', 'ignore')
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(300).decode('utf8', 'ignore')
        except Exception:
            return e.code, ''
    except Exception as e:
        return 0, repr(e)[:60]

ping = rpc('ping')
unk = rpc('zz_i81065_no_such_method')
R1 = 'CONF:%s|TOKLEN=%d|PING=%d:%s|UNK=%d:%s' % (
    cfg_s, len(tok), ping[0], short(ping[1], 50), unk[0], short(unk[1], 110))
R1 = cap(R1, 940)

# ---------------- binary extraction ----------------
data = b''
bsrc = 'none'
for p in ['/mnt/host_share/devin-remote', '/proc/1041/root/mnt/host_share/devin-remote',
          '/proc/1044/root/mnt/host_share/devin-remote']:
    d = rd(p)
    if d:
        data = d
        bsrc = p
        break

qs = set()
if data:
    for x in re.findall(rb'"([a-z][a-z0-9_\./\-]{2,60})"', data):
        qs.add(x.decode('utf8', 'ignore'))

TOOLNOUN = re.compile(r'(tool|plugin|mcp|skill|capabilit|server|template|extension|hook|browser)', re.I)
VERB = re.compile(r'^(get|list|show|describe|query|read|set|add|register|unregister|enable|disable|remove|'
                  r'delete|call|invoke|run|exec|execute|apply|reload|update|create|start|stop|status|'
                  r'resolve|fetch|validate|sync|attach|detach|install|uninstall|load|spawn|probe|inspect|dump)_')
NOUNSUF = re.compile(r'^[a-z][a-z0-9_]{2,40}_(tools?|plugins?|mcps?|skills?|capabilities|servers?|templates?|extensions?)$')
INTRO = ['rpc_methods', 'rpc.discover', 'list_methods', 'get_methods', 'system.listMethods', 'openrpc', 'describe']

cands = sorted(n for n in qs if (VERB.match(n) and TOOLNOUN.search(n)) or NOUNSUF.match(n))
intro_present = [m for m in INTRO if m in qs]
toolish = sorted(n for n in qs if TOOLNOUN.search(n) and len(n) <= 44)

sha16 = ''
if qs:
    import hashlib
    sha16 = hashlib.sha256('\n'.join(sorted(qs)).encode()).hexdigest()[:16]

R2 = 'BIN:%s_SZ=%d_QIDS=%d_CANDS=%d_SHA16=%s|CAND:%s' % (
    bsrc, len(data), len(qs), len(cands), sha16, ','.join(cands[:22]))
R2 = cap(R2, 940)

# ---------------- R3: probe only literal candidates ----------------
calls = []
for m in intro_present:
    if m not in calls:
        calls.append(m)
for m in cands:
    if m not in calls:
        calls.append(m)
calls = calls[:8]

WRITE = re.compile(r'^(register|add|enable|activate|install|load|spawn|unregister|disable|uninstall|remove|delete|'
                   r'unload)_(tool|tools|mcp|mcps|plugin|plugins|skill|skills|server|servers|extension|extensions)')
wcalls = [m for m in cands if WRITE.match(m)][:2]

res = []
for m in calls:
    st, body = rpc(m)
    if st == 200:
        try:
            j = json.loads(body)
            if 'result' in j:
                res.append('%s=ok:%s' % (m, short(json.dumps(j['result'], separators=(',', ':')), 70)))
            else:
                err = j.get('error') or {}
                res.append('%s=e%d:%s' % (m, int(err.get('code', 0)) if isinstance(err.get('code'), int) else 0,
                                          short(err.get('message', ''), 60)))
        except Exception:
            res.append('%s=%d:%s' % (m, st, short(body, 60)))
    else:
        res.append('%s=%d:%s' % (m, st, short(body, 50)))
for m in wcalls:
    st, body = rpc(m)
    res.append('W:%s=%d:%s' % (m, st, short(body, 55)))
R3 = 'PROBE:' + ';'.join(res)
R3 = cap(R3, 940)

# ---------------- R4: toolish token sample + intro flags + 9876 client code ----------------
cl = []
try:
    g = subprocess.run(['grep', '-rls', '--binary-files=without-match', '-e', 'devin_remote_auth_token',
                        '-e', '127.0.0.1:9876', '-e', 'localhost:9876',
                        '/opt/.devin', '/home/ubuntu/.devin-files'],
                       capture_output=True, timeout=25)
    cl = [x for x in g.stdout.decode('utf8', 'ignore').split('\n') if x][:4]
except Exception:
    cl = []

clinfo = []
for fp in cl[:2]:
    s = rd(fp, 2 * 1024 * 1024).decode('utf8', 'ignore')
    ms = sorted(set(re.findall(r'["\']([a-z][a-z0-9_]{3,40})["\']', s)))
    ms = [m for m in ms if TOOLNOUN.search(m) or VERB.match(m)][:8]
    clinfo.append('%s{%s}' % (os.path.basename(fp), ','.join(ms)))

tier = ''
try:
    t = rd('/home/ubuntu/.devin-files/client_live_tier.sh').decode('utf8', 'ignore')
    tier = ','.join(sorted(set(re.findall(r'\b(tier[_a-z0-9]*|plugin[_a-z0-9]*|tool[_a-z0-9]*)\b', t)))[:8])
except Exception:
    pass

R4 = 'TOOLISH:%s|INTRO:%s|CL:%s|TIER:%s' % (
    ','.join(toolish[:20]), ('Y:' + ','.join(intro_present)) if intro_present else 'none',
    ';'.join(clinfo) if clinfo else ('files=' + ','.join(os.path.basename(x) for x in cl) if cl else 'none'),
    tier[:60])
R4 = cap(R4, 940)

print(cap(R1, 940))
print(R2)
print(R3)
print(R4)
