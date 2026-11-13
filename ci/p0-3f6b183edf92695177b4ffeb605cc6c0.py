
import os, re, socket, subprocess

SAFE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:,/=|@+~-")
def san(s, n=680):
    s = ''.join(c if c in SAFE else '_' for c in str(s))
    s = re.sub(r'_+', '_', s).strip('_')
    return s[:n]

def rd(p, lim=4000000):
    try:
        with open(p, 'rb') as f:
            return f.read(lim)
    except Exception:
        return None

def run(cmd, t=20):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=t)
        return ((r.stdout or b'') + (r.stderr or b'')).decode('utf-8', 'replace')
    except Exception as e:
        return 'EXC_' + type(e).__name__

def sec1():
    data = rd('/proc/self/mountinfo', 4000000)
    if data is None:
        return 'no-mountinfo'
    segs = []
    for ln in data.decode('utf-8', 'replace').splitlines():
        low = ln.lower()
        if any(k in low for k in ('host_share', 'virtiofs', '9p', 'fuse', 'vsock')):
            f = ln.split(' ')
            mp = f[4] if len(f) > 4 else '?'
            mo = f[5] if len(f) > 5 else '?'
            tail = ln.split(' - ', 1)[1] if ' - ' in ln else ''
            g = tail.split(' ')
            fst = g[0] if g else '?'
            src = g[1] if len(g) > 1 else '?'
            so = g[2] if len(g) > 2 else '?'
            segs.append('MP=' + mp + '|FS=' + fst + '|SRC=' + src + '|O=' + mo + '|SO=' + so)
    return san(' ;; '.join(segs)) or 'no-match'

def sec2():
    p = []
    p.append('findmnt=' + san(run("findmnt -T /mnt/host_share -o TARGET,SOURCE,FSTYPE,OPTIONS -n 2>&1"), 300))
    p.append('statfs=' + san(run("stat -f -c %T,%b,%f,%S /mnt/host_share 2>&1"), 120))
    mm = [l for l in (rd('/proc/mounts') or b'').decode('utf-8', 'replace').splitlines() if 'host' in l.lower()]
    p.append('mnts=' + san(' ;; '.join(mm), 260))
    return san(' | '.join(p))

def sec3():
    d = []
    d.append('devsock=' + ('Y' if os.path.exists('/dev/vsock') else 'N') + ',devvhost=' + ('Y' if os.path.exists('/dev/vhost-vsock') else 'N'))
    v = rd('/sys/devices/virtual/misc/vsock/dev', 100)
    d.append('devnum=' + (san(v.decode('utf-8', 'replace').strip(), 20) if v else 'ERR'))
    try:
        e = sorted(os.listdir('/sys/class/vsock'))
        d.append('classvsock=' + ','.join(e[:8]) + '(n=' + str(len(e)) + ')')
    except Exception as ex:
        d.append('classvsock=ERR_' + type(ex).__name__)
    try:
        e = sorted(os.listdir('/sys/class/vsock/vsock0'))
        d.append('vsock0=' + ','.join(e[:14]))
    except Exception as ex:
        d.append('vsock0=ERR_' + type(ex).__name__)
    try:
        vd = sorted(os.listdir('/sys/bus/virtio/devices'))
        d.append('virtio=n' + str(len(vd)) + ':' + ','.join(vd[:8]))
    except Exception as ex:
        d.append('virtio=ERR_' + type(ex).__name__)
    mods = [l.split()[0] for l in (rd('/proc/modules') or b'').decode('utf-8', 'replace').splitlines() if 'vsock' in l or 'virtio' in l]
    d.append('mods=' + ','.join(mods[:8]))
    pv = rd('/proc/net/vsock', 200000)
    if pv is None:
        d.append('netvsock=ERR_missing')
    else:
        ls = pv.decode('utf-8', 'replace').splitlines()
        d.append('netvsock=n' + str(len(ls)) + ':' + san(' '.join(ls[:3]), 160))
    try:
        misc = [l for l in (rd('/proc/misc') or b'').decode('utf-8', 'replace').splitlines() if 'vsock' in l]
        d.append('misc=' + san(' '.join(misc), 60))
    except Exception:
        d.append('misc=ERR')
    return san(' | '.join(d))

def sec4():
    r = []
    r.append('AF_VSOCK=' + str(hasattr(socket, 'AF_VSOCK')) +
             ',ANY=' + str(getattr(socket, 'VMADDR_CID_ANY', 'NA')) +
             ',HOST=' + str(getattr(socket, 'VMADDR_CID_HOST', 'NA')) +
             ',LOCAL=' + str(getattr(socket, 'VMADDR_CID_LOCAL', 'NA')))
    try:
        s = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
        try:
            s.bind((socket.VMADDR_CID_ANY, 0))
        except Exception as be:
            r.append('bindERR=' + type(be).__name__ + '_' + san(str(be), 60))
        try:
            r.append('sockname=' + san(str(s.getsockname()), 60))
        except Exception as ge:
            r.append('socknameERR=' + type(ge).__name__)
        s.close()
    except Exception as ex:
        r.append('sockERR=' + type(ex).__name__ + '_' + san(str(ex), 80))
    try:
        f = open('/dev/vsock', 'rb')
        r.append('devopen=Y')
        f.close()
    except Exception as ex:
        r.append('devopen=' + type(ex).__name__ + '_' + san(str(ex), 60))
    try:
        f = open('/dev/vhost-vsock', 'rb')
        r.append('vhostopen=Y')
        f.close()
    except Exception as ex:
        r.append('vhostopen=' + type(ex).__name__)
    return san(' | '.join(r))

def lst(p, n=16):
    try:
        out = []
        for name in sorted(os.listdir(p))[:n]:
            fp = os.path.join(p, name)
            try:
                st = os.lstat(fp)
                out.append(name + ':' + str(st.st_size) + ':' + str(int(st.st_mtime)))
            except Exception:
                out.append(name + ':?')
        return ' '.join(out)
    except Exception as ex:
        return 'ERR_' + type(ex).__name__

def sec5():
    h = []
    h.append('hs=' + san(lst('/mnt/host_share', 16), 340))
    h.append('pkg=' + san(lst('/mnt/host_share/package', 8), 180))
    try:
        st = os.stat('/mnt/host_share')
        h.append('hsmt=' + str(int(st.st_mtime)) + ',ino=' + str(st.st_ino) + ',mode=' + oct(st.st_mode & 0o7777))
    except Exception:
        h.append('hsmt=?')
    p = '/mnt/host_share/vsock-authorized-keys'
    try:
        data = rd(p, 4000000) or b''
        lines = [l for l in data.decode('utf-8', 'replace').splitlines() if l.strip()]
        types = {}
        for l in lines:
            t = l.split(' ')[0][:20]
            types[t] = types.get(t, 0) + 1
        h.append('vsockauth=' + str(len(data)) + 'B,lines=' + str(len(lines)) + ',' + san(','.join(k + 'x' + str(v) for k, v in list(types.items())[:4]), 60))
    except Exception as ex:
        h.append('vsockauth=ERR_' + type(ex).__name__)
    return san(' | '.join(h))

lines = []
for fn in (sec1, sec2, sec3, sec4, sec5):
    try:
        lines.append(fn())
    except Exception as ex:
        lines.append('SECERR_' + fn.__name__ + '_' + type(ex).__name__)
print('\n'.join(lines[:5]))
