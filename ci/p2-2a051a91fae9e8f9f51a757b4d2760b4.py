import os, re, json, glob, socket, subprocess

def rd(p):
    try:
        return open(p, 'rb').read()
    except Exception as e:
        return ('ERR:' + type(e).__name__).encode()

def clean(s, n):
    return re.sub(r'\s+', '_', s).strip('_')[:n]

# ---------- L1: devin-remote process (cmdline + env names/lengths) ----------
pids = []
for d in glob.glob('/proc/[0-9]*'):
    cl = rd(d + '/cmdline').replace(b'\x00', b' ').decode('utf8', 'ignore')
    if 'devin-remote' in cl:
        pids.append((d.rsplit('/', 1)[-1], cl.strip()))
l1 = []
for pid, cl in pids[:2]:
    uid = ''
    for line in rd('/proc/%s/status' % pid).decode('utf8', 'ignore').split('\n'):
        if line.startswith('Uid:'):
            uid = line.split()[1]
    envraw = rd('/proc/%s/environ' % pid)
    items = []
    if envraw.startswith(b'ERR:'):
        items = [envraw.decode()]
    else:
        for kv in envraw.split(b'\x00'):
            if not kv:
                continue
            k, _, v = kv.decode('utf8', 'ignore').partition('=')
            items.append('%s=%d' % (k, len(v)))
    l1.append('pid=%s uid=%s cmd=%s env={%s}' % (pid, uid, clean(cl, 90), ','.join(items[:40])))
if not l1:
    l1 = ['no devin-remote proc']

# ---------- L2: small config files under /opt/.devin ----------
def sanitize(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if re.search(r'token|secret|key|password|auth|cred', str(k), re.I) and not isinstance(v, (dict, list)):
                out[k] = '<len:%d>' % len(str(v))
            else:
                out[k] = sanitize(v)
        return out
    if isinstance(obj, list):
        return [sanitize(x) for x in obj[:6]]
    if isinstance(obj, str):
        return obj[:160]
    return obj

cfg = []
for p in ['/opt/.devin/custom_remote_config.json', '/opt/.devin/client_prebaked', '/opt/.devin/provision_version']:
    b = rd(p)
    if b.startswith(b'ERR:'):
        cfg.append('%s=%s' % (os.path.basename(p), b.decode()))
        continue
    try:
        cfg.append('%s=%s' % (os.path.basename(p), clean(json.dumps(sanitize(json.loads(b))), 220)))
    except Exception:
        cfg.append('%s=%s' % (os.path.basename(p), clean(b.decode('utf8', 'ignore'), 220)))

# ---------- L3: dirs ----------
def dl(p, n=18):
    try:
        items = sorted(os.listdir(p))[:n]
    except Exception as e:
        return type(e).__name__
    out = []
    for i in items:
        fp = os.path.join(p, i)
        try:
            out.append(i + '/' if os.path.isdir(fp) else i + '=' + str(os.path.getsize(fp)))
        except Exception:
            out.append(i + '?')
    return ','.join(out)

home = os.path.expanduser('~')
l3 = 'D3=' + dl(home + '/.devin-files') + ';D4=' + dl('/run/.devin') + ';D5=' + dl('/mnt/host_share') + ';CWD=' + dl('/home/ubuntu')

# ---------- L4: local HTTP ports ----------
def http(port, method, timeout=4):
    try:
        s = socket.create_connection(('127.0.0.1', port), timeout=timeout)
        s.settimeout(timeout)
        req = ('%s / HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nConnection: close\r\n\r\n' % (method, port)).encode()
        s.sendall(req)
        buf = b''
        while len(buf) < 4000:
            try:
                c = s.recv(2048)
            except Exception:
                break
            if not c:
                break
            buf += c
        s.close()
        head, _, body = buf.partition(b'\r\n\r\n')
        lines = head.decode('utf8', 'ignore').split('\r\n')
        status = lines[0] if lines else ''
        server = ''
        for ln in lines:
            if ln.lower().startswith('server:'):
                server = ln.split(':', 1)[1].strip()
        return '%s/%s/%s/%s' % (port, method, clean(status, 40), clean(body.decode('utf8', 'ignore'), 100))
    except Exception as e:
        return '%s/%s/ERR:%s' % (port, method, type(e).__name__)

ports = [6080, 6789, 9876]
res = []
for p in ports:
    res.append(http(p, 'GET'))
for p in ports:
    res.append(http(p, 'OPTIONS'))
l4 = ';'.join(res)

print(clean('ENV4:' + '|'.join(l1), 1000))
print(clean('ENV5:' + '|'.join(cfg), 900))
print(clean('ENV6:' + l3, 900))
print(clean('ENV7:' + l4, 1200))
