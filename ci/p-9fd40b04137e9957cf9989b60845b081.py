import os, re, glob

def rd(p):
    try:
        return open(p, 'rb').read()
    except Exception:
        return b''

def cap(s, n):
    s = re.sub(r'\s+', '_', s).strip('_')
    return s[:n]

# ---------- listening ports (state 0A) with owning process ----------
listen = []
for f in ('/proc/net/tcp', '/proc/net/tcp6'):
    for line in rd(f).split(b'\n')[1:]:
        p = line.split()
        if len(p) > 9 and p[3] == b'0A':
            try:
                port = int(p[1].decode().split(':')[-1], 16)
            except Exception:
                continue
            if port > 0:
                listen.append((port, p[9].decode()))

ino2pid = {}
procs = {}
for d in glob.glob('/proc/[0-9]*'):
    pid = d.rsplit('/', 1)[-1]
    procs[pid] = rd(d + '/comm').decode('utf8', 'ignore').strip()
    try:
        for fd in os.listdir(d + '/fd'):
            try:
                t = os.readlink(d + '/fd/' + fd)
            except Exception:
                continue
            m = re.match(r'socket:\[(\d+)\]', t)
            if m:
                ino2pid.setdefault(m.group(1), pid)
    except Exception:
        pass

seen = set()
ports = []
for port, ino in sorted(listen):
    if port in seen:
        continue
    seen.add(port)
    pid = ino2pid.get(ino, '')
    ports.append('%d:%s' % (port, procs.get(pid, '?')[:18].replace(' ', '_') or '?'))
ports = ports[:40]

# ---------- /etc/hosts ----------
hosts = []
for l in rd('/etc/hosts').decode('utf8', 'ignore').split('\n'):
    l = l.strip()
    if l and not l.startswith('#'):
        h = l.split()
        if len(h) >= 2:
            hosts.append(h[0] + ':' + ','.join(h[1:]))
hosts = hosts[:24]

# ---------- env (names + value length only) ----------
pat = re.compile(r'base_url|baseurl|api_url|apibase|proxy|endpoint|model|token|devin|cog|anthropic|openai|llm|gateway|remote|host', re.I)
env = []
for k in sorted(os.environ):
    if pat.search(k):
        env.append('%s=%d' % (k, len(os.environ[k])))
env = env[:80]

# ---------- processes ----------
ps = []
pat2 = re.compile(r'devin|remote|proxy|agent|node|python|llm|model|anthropic|openai|gateway|outpost|vnc|novnc|websock', re.I)
for d in sorted(glob.glob('/proc/[0-9]*'), key=lambda x: int(x.rsplit('/', 1)[-1])):
    pid = d.rsplit('/', 1)[-1]
    cl = rd(d + '/cmdline').replace(b'\x00', b' ').decode('utf8', 'ignore').strip()
    if not cl:
        continue
    if pat2.search(cl):
        ps.append(pid + ':' + re.sub(r'\s+', '_', cl)[:110])
    if len(ps) >= 30:
        break

# ---------- directories ----------
def dl(p, n=16):
    try:
        items = sorted(os.listdir(p))[:n]
    except Exception:
        return '-'
    out = []
    for i in items:
        fp = os.path.join(p, i)
        try:
            out.append(i + '/' if os.path.isdir(fp) else i + '=' + str(os.path.getsize(fp)))
        except Exception:
            out.append(i + '?')
    return ','.join(out)

home = os.path.expanduser('~')
l1 = 'ENV1:P=' + ','.join(ports) + ';H=' + ';'.join(hosts)
l2 = 'ENV2:E=' + ','.join(env) + ';C=' + str(len(env))
l3 = ('ENV3:S=' + ';'.join(ps) +
      ';D1=' + dl('/opt/.devin') + ';D2=' + dl('/mnt/host_share') +
      ';D3=' + dl(home + '/.devin-files') + ';D4=' + dl('/run/.devin'))
print(cap(l1, 1000))
print(cap(l2, 900))
print(cap(l3, 1200))
