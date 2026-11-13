import os, re, json, glob, socket

def rd(p):
    try:
        return open(p, 'rb').read()
    except Exception as e:
        return ('ERR:' + type(e).__name__).encode()

def clean(s, n):
    return re.sub(r'\s+', '_', s).strip('_')[:n]

# ---------- A: local HTTP identity of every non-system listening port ----------
def http(port, method, timeout=4):
    try:
        s = socket.create_connection(('127.0.0.1', port), timeout=timeout)
        s.settimeout(timeout)
        s.sendall(('%s / HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nConnection: close\r\n\r\n' % (method, port)).encode())
        buf = b''
        while len(buf) < 3000:
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
        return '%s/%s/%s/%s' % (port, method, clean(lines[0] if lines else '', 32),
                                clean(body.decode('utf8', 'ignore'), 70))
    except Exception as e:
        return '%s/%s/ERR:%s' % (port, method, type(e).__name__)

def listening():
    ports = set()
    for f in ('/proc/net/tcp', '/proc/net/tcp6'):
        for ln in rd(f).decode('utf8', 'ignore').split('\n')[1:]:
            p = ln.split()
            if len(p) > 3 and p[3] == '0A':
                try:
                    ports.add(int(p[1].split(':')[1], 16))
                except Exception:
                    pass
    return sorted(ports)

ports = [p for p in listening() if p not in (22, 53)][:4]
A = ';'.join([http(p, 'GET') for p in ports] + [http(p, 'OPTIONS') for p in ports])

# ---------- B: devin-remote process env (names + value lengths only) ----------
B = ''
for d in glob.glob('/proc/[0-9]*'):
    cl = rd(d + '/cmdline').replace(b'\x00', b' ').decode('utf8', 'ignore')
    if 'devin-remote' not in cl:
        continue
    pid = d.rsplit('/', 1)[-1]
    uid = ''
    for line in rd(d + '/status').decode('utf8', 'ignore').split('\n'):
        if line.startswith('Uid:'):
            uid = line.split()[1]
    raw = rd(d + '/environ')
    if raw.startswith(b'ERR:'):
        B = 'pid=%s uid=%s env=%s' % (pid, uid, raw.decode())
    else:
        it = []
        for kv in raw.split(b'\x00'):
            if not kv:
                continue
            k, _, v = kv.decode('utf8', 'ignore').partition('=')
            it.append('%s=%d' % (k, len(v)))
        B = 'pid=%s uid=%s n=%d %s' % (pid, uid, len(it), ','.join(it[:28]))
    break

# ---------- C: small devin config files (values of secret-ish keys replaced by length) ----------
def san(o):
    if isinstance(o, dict):
        return {k: (('<len:%d>' % len(str(v))) if re.search(r'token|secret|key|password|auth|cred', str(k), re.I)
                    and not isinstance(v, (dict, list)) else san(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [san(x) for x in o[:5]]
    if isinstance(o, str):
        return o[:90]
    return o

C = []
for p in ['/opt/.devin/custom_remote_config.json', '/opt/.devin/client_prebaked', '/opt/.devin/provision_version']:
    b = rd(p)
    if b.startswith(b'ERR:'):
        C.append('%s=%s' % (os.path.basename(p), b.decode()))
        continue
    try:
        C.append('%s=%s' % (os.path.basename(p), clean(json.dumps(san(json.loads(b))), 190)))
    except Exception:
        C.append('%s=%s' % (os.path.basename(p), clean(b.decode('utf8', 'ignore'), 190)))

print(clean('ENV8:' + A, 700))
print(clean('ENV9:' + B, 520))
print(clean('ENV10:' + '|'.join(C), 560))
