import os, json, time, threading, binascii, base64, asyncio, logging
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template
import requests as req_lib
import aiohttp
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
from google.protobuf.message import DecodeError
import like_pb2, like_count_pb2, uid_generator_pb2

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
TOKENS_FILE = os.path.join(BASE_DIR, 'tokens.json')
UIDPASS_FILE = os.path.join(BASE_DIR, 'uidpass.json')
STATS_FILE  = os.path.join(BASE_DIR, 'stats.json')

JWT_API   = 'https://xtytdtyj-jwt.up.railway.app/token'
AES_KEY   = b'Yg&tc%DEuh6%Zc^8'
AES_IV    = b'6oyZDr22E3ychjM%'

_stats_lock = threading.Lock()

def _default_stats():
    return {
        'total_refresh': 0,
        'last_refresh': None,
        'last_success': 0,
        'last_failed': 0,
        'all_success': 0,
        'all_failed': 0,
        'like_total': 0,
        'like_ok': 0,
        'like_fail': 0,
        'start_time': datetime.now(timezone.utc).isoformat(),
    }

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return _default_stats()

def save_stats(s):
    with open(STATS_FILE, 'w') as f:
        json.dump(s, f, indent=2)

STATS = load_stats()

def update_stats(**kw):
    with _stats_lock:
        for k, v in kw.items():
            if k in STATS and isinstance(v, (int, float)):
                STATS[k] += v
            else:
                STATS[k] = v
        save_stats(STATS)

# ─── Token helpers ────────────────────────────────────────────────────────────

def load_tokens():
    try:
        with open(TOKENS_FILE) as f:
            return json.load(f)
    except Exception as e:
        log.error(f'load_tokens error: {e}')
        return []

def save_tokens(lst):
    with open(TOKENS_FILE, 'w') as f:
        json.dump(lst, f, indent=2)

def fetch_one_token(uid, password):
    try:
        r = req_lib.get(f'{JWT_API}?uid={uid}&password={password}', timeout=15)
        r.raise_for_status()
        t = r.json().get('token')
        if t:
            return t, True
    except Exception as e:
        log.warning(f'fetch_one_token UID {uid} failed: {e}')
    return None, False

def do_refresh_tokens(notify_telegram=True):
    try:
        with open(UIDPASS_FILE) as f:
            uidpass_list = json.load(f)
    except Exception as e:
        msg = f'❌ Cannot read uidpass.json: {e}'
        log.error(msg)
        if notify_telegram:
            try:
                from bot import notify
                notify(msg)
            except Exception:
                pass
        return 0, 0

    success, failed = 0, 0
    new_tokens = []
    for item in uidpass_list:
        token, ok = fetch_one_token(item['uid'], item['password'])
        if ok:
            new_tokens.append({'token': token})
            success += 1
        else:
            failed += 1

    if new_tokens:
        save_tokens(new_tokens)

    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    update_stats(
        total_refresh=1,
        last_refresh=now_str,
        last_success=0, last_failed=0,
        all_success=success,
        all_failed=failed,
    )
    with _stats_lock:
        STATS['last_success'] = success
        STATS['last_failed']  = failed
        save_stats(STATS)

    if notify_telegram:
        try:
            from bot import notify
            status = '✅' if failed == 0 else ('⚠️' if success > 0 else '❌')
            notify(
                f'{status} *Token Refresh Done*\n'
                f'🕐 Time: `{now_str}`\n'
                f'✅ Success: `{success}`\n'
                f'❌ Failed: `{failed}`\n'
                f'📦 Total tokens: `{len(new_tokens)}`'
            )
        except Exception as e:
            log.warning(f'telegram notify error: {e}')

    log.info(f'Token refresh: success={success} failed={failed}')
    return success, failed

# ─── AES / Protobuf helpers ───────────────────────────────────────────────────

def encrypt_message(plaintext):
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return binascii.hexlify(cipher.encrypt(pad(plaintext, AES.block_size))).decode()

def create_like_proto(uid, region):
    m = like_pb2.like()
    m.uid = int(uid)
    m.region = region
    return m.SerializeToString()

def create_uid_proto(uid):
    m = uid_generator_pb2.uid_generator()
    m.saturn_ = int(uid)
    m.garena = 1
    return m.SerializeToString()

def region_url(server_name, endpoint):
    s = server_name.upper()
    if s == 'IND':
        base = 'https://client.ind.freefiremobile.com'
    elif s in {'BR', 'US', 'SAC', 'NA'}:
        base = 'https://client.us.freefiremobile.com'
    else:
        base = 'https://clientbp.ggpolarbear.com'
    return base + endpoint

HEADERS_BASE = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
    'Connection': 'Keep-Alive',
    'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Expect': '100-continue',
    'X-Unity-Version': '2018.4.11f1',
    'X-GA': 'v1 1',
    'ReleaseVersion': 'OB53',
}

def make_request(enc_hex, server_name, token, endpoint):
    url = region_url(server_name, endpoint)
    headers = {**HEADERS_BASE, 'Authorization': f'Bearer {token}'}
    resp = req_lib.post(url, data=bytes.fromhex(enc_hex), headers=headers, verify=False)
    binary = resp.content
    items = like_count_pb2.Info()
    try:
        items.ParseFromString(binary)
    except DecodeError as e:
        log.error(f'protobuf decode error: {e}')
        return None
    return items

async def send_likes_async(enc_hex, token_list, url):
    edata = bytes.fromhex(enc_hex)
    async with aiohttp.ClientSession() as session:
        tasks = [
            session.post(url, data=edata,
                         headers={**HEADERS_BASE, 'Authorization': f'Bearer {t["token"]}'})
            for t in token_list
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

# ─── Flask routes ─────────────────────────────────────────────────────────────

@app.route('/ping')
def ping():
    return jsonify({'status': 'ok', 'time': datetime.now(timezone.utc).isoformat()}), 200

@app.route('/')
def dashboard():
    tokens = load_tokens()
    with _stats_lock:
        s = dict(STATS)
    s['token_count'] = len(tokens)
    uptime_sec = int(time.time() - _start_epoch)
    h, rem = divmod(uptime_sec, 3600)
    m, sec = divmod(rem, 60)
    s['uptime'] = f'{h}h {m}m {sec}s'
    return render_template('dashboard.html', stats=s)

@app.route('/api/stats')
def api_stats():
    tokens = load_tokens()
    with _stats_lock:
        s = dict(STATS)
    s['token_count'] = len(tokens)
    uptime_sec = int(time.time() - _start_epoch)
    h, rem = divmod(uptime_sec, 3600)
    m, sec2 = divmod(rem, 60)
    s['uptime'] = f'{h}h {m}m {sec2}s'
    return jsonify(s)

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    ok, fail = do_refresh_tokens(notify_telegram=True)
    return jsonify({'success': ok, 'failed': fail, 'total': ok + fail})

@app.route('/like')
def handle_like():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({'error': 'uid required'}), 400

    tokens = load_tokens()
    if not tokens:
        return jsonify({'error': 'No tokens loaded. Call /api/refresh first.'}), 503

    token = tokens[0]['token']
    server_name = request.args.get('server_name', '').upper()
    if not server_name:
        try:
            payload = token.split('.')[1]
            payload += '=' * (-len(payload) % 4)
            d = json.loads(base64.urlsafe_b64decode(payload))
            server_name = d.get('lock_region', '').upper()
        except Exception:
            pass
    if not server_name:
        return jsonify({'error': 'server_name required'}), 400

    try:
        enc_uid = encrypt_message(create_uid_proto(uid))
        before = make_request(enc_uid, server_name, token, '/GetPlayerPersonalShow')
        if before is None:
            update_stats(like_total=1, like_fail=1)
            return jsonify({'error': 'Failed to get player info. Update tokens.'}), 500

        before_data = json.loads(MessageToJson(before))
        before_like = int(before_data.get('AccountInfo', {}).get('Likes', 0) or 0)

        like_enc = encrypt_message(create_like_proto(uid, server_name))
        url = region_url(server_name, '/LikeProfile')
        asyncio.run(send_likes_async(like_enc, tokens, url))

        after = make_request(enc_uid, server_name, token, '/GetPlayerPersonalShow')
        if after is None:
            update_stats(like_total=1, like_fail=1)
            return jsonify({'error': 'Failed to get player info after likes.'}), 500

        after_data = json.loads(MessageToJson(after))
        acc = after_data.get('AccountInfo', {})
        after_like = int(acc.get('Likes', 0) or 0)
        given = after_like - before_like

        update_stats(like_total=1, like_ok=(1 if given > 0 else 0), like_fail=(0 if given > 0 else 1))

        return jsonify({
            'LikesGivenByAPI': given,
            'LikesafterCommand': after_like,
            'LikesbeforeCommand': before_like,
            'PlayerNickname': acc.get('PlayerNickname', ''),
            'Region': server_name,
            'UID': int(acc.get('UID', 0) or 0),
            'status': 1 if given > 0 else 2,
        })
    except Exception as e:
        log.exception('like error')
        update_stats(like_total=1, like_fail=1)
        return jsonify({'error': str(e)}), 500

# ─── Startup ──────────────────────────────────────────────────────────────────

_start_epoch = time.time()
