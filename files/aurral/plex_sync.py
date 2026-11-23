#!/usr/bin/env python3
"""Mirror Aurral flows/playlists into each owner's own Plex Home account.

Aurral 3.x publishes playlists only to the Plex server owner's account. This reads
the owner/member of every flow + static playlist from Aurral's API, then imports the
M3U Aurral writes (_playlists/*.m3u) into the matching Plex Home user's account.

Config: /etc/aurral-plex-sync.env  (PLEX_TOKEN, PLEX_URL, SECTION_ID, AURRAL_URL,
AURRAL_ADMIN_USER, AURRAL_ADMIN_PASS, M3U_DIR_LOCAL, M3U_DIR_PLEX, USER_MAP)
USER_MAP = "aurral_username=Plex Home title,..."   e.g. "christian=Christian,ally=Ally"
State: /var/lib/aurral-plex-sync/state.json (change detection + ownership of what we created).
"""
import json, os, re, sys, urllib.request, urllib.parse, urllib.error

def load_env(path):
    for line in open(path):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k, v.strip().strip('"\''))
load_env(os.environ.get('SYNC_ENV', '/etc/aurral-plex-sync.env'))
E = os.environ
DRY = '--dry-run' in sys.argv
FORCE = '--force' in sys.argv
STATE_PATH = E.get('STATE', '/var/lib/aurral-plex-sync/state.json')
CID = 'aurral-plex-sync'

def http(method, url, headers=None, body=None):
    req = urllib.request.Request(url, body, headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def plex_h(tok):
    return {'X-Plex-Token': tok, 'X-Plex-Client-Identifier': CID, 'X-Plex-Product': 'Aurral Plex Sync', 'Accept': 'application/json'}

def plex(method, _path, tok, **q):
    url = E["PLEX_URL"] + _path + ('?' + urllib.parse.urlencode(q) if q else '')
    st, b = http(method, url, plex_h(tok), b'' if method != 'GET' else None)
    return st, (json.loads(b) if b[:1] in (b'{', b'[') else b)

def safe(name):  # Aurral's M3U filename rule
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()

# --- Aurral
base = E['AURRAL_URL'].rstrip('/') + '/api'
st, b = http('POST', base + '/auth/login', {'Content-Type': 'application/json'},
             json.dumps({'username': E['AURRAL_ADMIN_USER'], 'password': E['AURRAL_ADMIN_PASS']}).encode())
if st != 200: sys.exit(f'aurral login failed {st}')
ah = {'Authorization': 'Bearer ' + json.loads(b)['token']}
raw = json.loads(http('GET', base + '/users', ah)[1])
raw = raw.get('users', raw) if isinstance(raw, dict) else raw
users = {u['id']: u['username'].lower() for u in raw}
status = json.loads(http('GET', base + '/playlists/status', ah)[1])
items = [dict(i, kind='flow') for i in status.get('flows', [])] + \
        [dict(i, kind='static') for i in status.get('staticPlaylists', [])]

# --- Plex Home users -> tokens
umap = {k.strip().lower(): v.strip() for k, v in (p.split('=', 1) for p in E['USER_MAP'].split(',') if '=' in p)}
st, b = http('GET', 'https://plex.tv/api/home/users', plex_h(E['PLEX_TOKEN']) | {'Accept': 'application/xml'})
import xml.etree.ElementTree as ET
home = {u.get('title'): u.get('id') for u in ET.fromstring(b).iter('User')}
def user_token(title):
    uid = home[title]
    st, b = http('POST', f'https://plex.tv/api/home/users/{uid}/switch', plex_h(E['PLEX_TOKEN']) | {'Accept': 'application/xml'}, b'')
    m = re.search(rb'authenticationToken="([^"]+)"', b)
    if st not in (200, 201) or not m: raise RuntimeError(f'token for {title}: {st}')
    utok = m.group(1).decode()
    st, rb = http('GET', 'https://plex.tv/api/v2/resources?includeHttps=1&includeRelay=0', plex_h(utok))
    for r in json.loads(rb):
        if r.get('clientIdentifier') == E.get('PLEX_MACHINE_ID', r.get('clientIdentifier')) and 'server' in (r.get('provides') or '') and r.get('accessToken'):
            return r['accessToken']
    raise RuntimeError(f'{title} has no access to the Plex server')

state = json.load(open(STATE_PATH)) if os.path.exists(STATE_PATH) else {}
# want[plex_title] = {playlist name: m3u local path}
want = {}
for it in items:
    if it.get('enabled') is False: continue
    ids = [it.get('ownerUserId')] + list(it.get('memberUserIds') or [])
    f = os.path.join(E['M3U_DIR_LOCAL'], safe(it['name']) + '.m3u')
    for uid in ids:
        pt = umap.get(users.get(uid, ''))
        if pt and os.path.exists(f):
            want.setdefault(pt, {})[it['name']] = f
        elif pt:
            print(f'skip {it["name"]}: no m3u yet')

# Plex doesn't auto-scan new Aurral downloads reliably: nudge a scan of the Aurral folder when any
# playlist is new/changed/incomplete, so tracks resolve on this or the next run.
if not DRY and any(ust_.get(n, {}).get('mtime') != os.path.getmtime(f)
                   for pt_, d_ in want.items() for n, f in d_.items() for ust_ in [state.get(pt_, {})]):
    plex('GET', f'/library/sections/{E["SECTION_ID"]}/refresh', E['PLEX_TOKEN'],
         path=E['M3U_DIR_PLEX'].rsplit('/_playlists', 1)[0])
    import time; time.sleep(int(E.get('SCAN_WAIT', '45')))

changed = 0
for pt in sorted(set(want) | set(state)):
    tok = user_token(pt)
    ust = state.setdefault(pt, {})
    _, pl = plex('GET', '/playlists', tok, playlistType='audio')
    existing = {p['title']: p['ratingKey'] for p in pl['MediaContainer'].get('Metadata', [])}
    for name, f in want.get(pt, {}).items():
        mt = os.path.getmtime(f)
        if not FORCE and ust.get(name, {}).get('mtime') == mt and name in existing: continue
        print(f'[{pt}] sync "{name}"' + (' (dry)' if DRY else ''))
        changed += 1
        if DRY: continue
        stem = safe(name)
        if name in existing and (name in ust or True):   # replace previous copy in this user's account
            plex('DELETE', f'/playlists/{existing[name]}', tok)
        # Plex only lets the server owner import an M3U: import as owner into a temp playlist,
        # read its track ratingKeys, then rebuild it in the user's own account.
        atok = E['PLEX_TOKEN']
        _, ex = plex('GET', '/playlists', atok, playlistType='audio')
        for p_ in ex['MediaContainer'].get('Metadata', []):
            if p_['title'] == stem and stem != name: plex('DELETE', f'/playlists/{p_["ratingKey"]}', atok)
        st, _ = plex('POST', '/playlists/upload', atok, sectionID=E['SECTION_ID'], force=1,
                     path=E['M3U_DIR_PLEX'].rstrip('/') + '/' + stem + '.m3u')
        _, pl2 = plex('GET', '/playlists', atok, playlistType='audio')
        tmp = next((p_ for p_ in pl2['MediaContainer'].get('Metadata', []) if p_['title'] == stem), None)
        if not tmp:
            print(f'  !! import failed ({st})'); continue
        _, items_ = plex('GET', f'/playlists/{tmp["ratingKey"]}/items', atok)
        keys = [m['ratingKey'] for m in items_['MediaContainer'].get('Metadata', [])]
        if stem != name:   # same title as the owner's own copy: leave that one alone
            plex('DELETE', f'/playlists/{tmp["ratingKey"]}', atok)
        if not keys: print('  !! no tracks resolved'); continue
        uri = lambda ks: f'server://{E["PLEX_MACHINE_ID"]}/com.plexapp.plugins.library/library/metadata/' + ','.join(ks)
        st, r = plex('POST', '/playlists', tok, type='audio', title=name, smart=0, uri=uri(keys[:100]))
        if st != 200: print(f'  !! create failed ({st})'); continue
        new = r['MediaContainer']['Metadata'][0]
        for i in range(100, len(keys), 100):
            plex('PUT', f'/playlists/{new["ratingKey"]}/items', tok, uri=uri(keys[i:i+100]))
        print(f'  {len(keys)} tracks')
        total = sum(1 for l in open(f, errors='replace') if l.strip() and not l.startswith('#'))
        # if Plex hasn't indexed every track yet, leave mtime unset so the next run retries
        ust[name] = {'mtime': mt if len(keys) >= total else None, 'ratingKey': new['ratingKey']}
        if len(keys) < total: print(f'  ({total - len(keys)} not in Plex yet; will retry)')
    for name in [n for n in ust if n not in want.get(pt, {})]:   # no longer wanted -> remove ours
        print(f'[{pt}] remove "{name}"' + (' (dry)' if DRY else ''))
        changed += 1
        if not DRY:
            if name in existing: plex('DELETE', f'/playlists/{existing[name]}', tok)
            del ust[name]
if not DRY:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    json.dump(state, open(STATE_PATH, 'w'), indent=1)
print(f'done, {changed} change(s)')
