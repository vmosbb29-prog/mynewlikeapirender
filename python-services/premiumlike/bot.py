"""
Telegram Bot with inline keyboard buttons.
Config is read from config.json — no environment variables needed.
"""
import os, json, time, logging, threading
import requests as req_lib

log = logging.getLogger(__name__)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

# ─── Config loader ────────────────────────────────────────────────────────────

def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception as e:
        log.error(f'Cannot load config.json: {e}')
        return {}

def get_bot_token():
    return load_config().get('bot_token', '')

def get_chat_id():
    return load_config().get('chat_id', '')

# ─── Telegram API helpers ─────────────────────────────────────────────────────

def tg(method, **params):
    token = get_bot_token()
    if not token or token == 'YOUR_BOT_TOKEN_HERE':
        return {}
    try:
        r = req_lib.post(
            f'https://api.telegram.org/bot{token}/{method}',
            json=params, timeout=15
        )
        return r.json()
    except Exception as e:
        log.warning(f'tg {method} error: {e}')
        return {}

def send_message(chat_id, text, reply_markup=None, parse_mode='Markdown'):
    params = dict(chat_id=chat_id, text=text, parse_mode=parse_mode)
    if reply_markup:
        params['reply_markup'] = reply_markup
    return tg('sendMessage', **params)

def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode='Markdown'):
    params = dict(chat_id=chat_id, message_id=message_id, text=text, parse_mode=parse_mode)
    if reply_markup:
        params['reply_markup'] = reply_markup
    return tg('editMessageText', **params)

def answer_callback(callback_query_id, text=''):
    tg('answerCallbackQuery', callback_query_id=callback_query_id, text=text)

# ─── Keyboards ────────────────────────────────────────────────────────────────

def main_keyboard():
    return {
        'inline_keyboard': [
            [
                {'text': '🔄 Refresh Tokens', 'callback_data': 'refresh'},
                {'text': '📊 Stats',           'callback_data': 'stats'},
            ],
            [
                {'text': '🏓 Ping',            'callback_data': 'ping'},
                {'text': '📋 Token Count',     'callback_data': 'token_count'},
            ],
            [
                {'text': '📜 Like History',    'callback_data': 'like_stats'},
                {'text': '⏰ Schedule Info',   'callback_data': 'schedule'},
            ],
            [
                {'text': '❓ Help',            'callback_data': 'help'},
            ],
        ]
    }

def back_keyboard():
    return {
        'inline_keyboard': [[
            {'text': '🏠 Main Menu', 'callback_data': 'menu'}
        ]]
    }

# ─── Handlers ─────────────────────────────────────────────────────────────────

def get_stats_text():
    try:
        import app as a, time as t_mod
        tokens = a.load_tokens()
        with a._stats_lock:
            s = dict(a.STATS)
        uptime_sec = int(t_mod.time() - a._start_epoch)
        h, rem = divmod(uptime_sec, 3600)
        m, sec = divmod(rem, 60)
        return (
            f'📊 *API Stats*\n\n'
            f'🔑 Tokens loaded: `{len(tokens)}`\n'
            f'🔄 Total refreshes: `{s.get("total_refresh", 0)}`\n'
            f'✅ Last ✅ success: `{s.get("last_success", 0)}`\n'
            f'❌ Last ❌ failed: `{s.get("last_failed", 0)}`\n'
            f'📦 All-time success: `{s.get("all_success", 0)}`\n'
            f'💀 All-time failed: `{s.get("all_failed", 0)}`\n'
            f'📤 Like requests: `{s.get("like_total", 0)}`\n'
            f'✅ Like OK: `{s.get("like_ok", 0)}`\n'
            f'❌ Like fail: `{s.get("like_fail", 0)}`\n'
            f'🕐 Last refresh: `{s.get("last_refresh", "Never")}`\n'
            f'⏱ Uptime: `{h}h {m}m {sec}s`'
        )
    except Exception as e:
        return f'❌ Error fetching stats: {e}'

def handle_callback(cq):
    data       = cq.get('data', '')
    cq_id      = cq['id']
    chat_id    = cq['message']['chat']['id']
    message_id = cq['message']['message_id']

    if data == 'menu':
        answer_callback(cq_id)
        edit_message(chat_id, message_id,
                     '🔥 *Free Fire Like API Bot*\nMenu:', main_keyboard())

    elif data == 'refresh':
        answer_callback(cq_id, '⏳ Refreshing...')
        edit_message(chat_id, message_id, '⏳ Token refresh চলছে... অপেক্ষা করুন।')
        try:
            import app as a
            ok, fail = a.do_refresh_tokens(notify_telegram=False)
            status = '✅' if fail == 0 else ('⚠️' if ok > 0 else '❌')
            text = (
                f'{status} *Refresh Complete!*\n\n'
                f'✅ Success: `{ok}`\n'
                f'❌ Failed: `{fail}`\n'
                f'📦 Total tokens: `{ok}`'
            )
        except Exception as e:
            text = f'❌ Refresh failed: {e}'
        edit_message(chat_id, message_id, text, back_keyboard())

    elif data == 'stats':
        answer_callback(cq_id)
        edit_message(chat_id, message_id, get_stats_text(), back_keyboard())

    elif data == 'ping':
        answer_callback(cq_id, '✅ Alive!')
        edit_message(chat_id, message_id,
                     '🏓 *Pong!*\n\n✅ API is alive and running!',
                     back_keyboard())

    elif data == 'token_count':
        answer_callback(cq_id)
        try:
            import app as a
            tokens = a.load_tokens()
            text = (
                f'🔑 *Token Status*\n\n'
                f'📦 Loaded: `{len(tokens)}`\n'
                f'✅ Ready to send likes!'
            )
        except Exception as e:
            text = f'❌ Error: {e}'
        edit_message(chat_id, message_id, text, back_keyboard())

    elif data == 'like_stats':
        answer_callback(cq_id)
        try:
            import app as a
            with a._stats_lock:
                s = dict(a.STATS)
            total = s.get('like_total', 0)
            ok    = s.get('like_ok', 0)
            fail  = s.get('like_fail', 0)
            rate  = f'{(ok/total*100):.1f}%' if total > 0 else 'N/A'
            text = (
                f'📜 *Like Stats*\n\n'
                f'📤 Total requests: `{total}`\n'
                f'✅ Successful: `{ok}`\n'
                f'❌ Failed: `{fail}`\n'
                f'📈 Success rate: `{rate}`'
            )
        except Exception as e:
            text = f'❌ Error: {e}'
        edit_message(chat_id, message_id, text, back_keyboard())

    elif data == 'schedule':
        answer_callback(cq_id)
        edit_message(chat_id, message_id,
                     '⏰ *Auto Refresh Schedule*\n\n'
                     '🔁 প্রতি ৭ ঘন্টায় auto refresh\n'
                     '🕛 রাত ৩:৩০ AM (UTC) daily refresh\n'
                     '🚀 Server start হলে refresh\n\n'
                     '📲 প্রতিটা refresh এর পরে এখানে notification আসবে।',
                     back_keyboard())

    elif data == 'help':
        answer_callback(cq_id)
        edit_message(chat_id, message_id,
                     '❓ *Help*\n\n'
                     '🔄 *Refresh Tokens* — নতুন JWT token generate করুন\n'
                     '📊 *Stats* — API এর সব stats দেখুন\n'
                     '🏓 *Ping* — API alive কিনা চেক করুন\n'
                     '📋 *Token Count* — কতটা token আছে\n'
                     '📜 *Like History* — like request এর stats\n'
                     '⏰ *Schedule Info* — auto refresh schedule\n\n'
                     '📌 Bot text commands:\n'
                     '`/start` `/refresh` `/stats` `/ping`',
                     back_keyboard())

def handle_message(msg):
    chat_id = msg['chat']['id']
    text    = msg.get('text', '')
    cmd     = text.split()[0].split('@')[0] if text.startswith('/') else ''

    if cmd == '/start':
        send_message(chat_id,
                     '🔥 *Free Fire Like API Bot*\n\n'
                     'নিচের buttons থেকে যা করতে চান select করুন:',
                     main_keyboard())

    elif cmd == '/refresh':
        send_message(chat_id, '⏳ Token refresh চলছে...')
        try:
            import app as a
            ok, fail = a.do_refresh_tokens(notify_telegram=False)
            send_message(chat_id,
                         f'✅ *Done!* Success: `{ok}` | Failed: `{fail}`',
                         main_keyboard())
        except Exception as e:
            send_message(chat_id, f'❌ Error: {e}', main_keyboard())

    elif cmd == '/stats':
        send_message(chat_id, get_stats_text(), main_keyboard())

    elif cmd == '/ping':
        send_message(chat_id, '🏓 *Pong!* API is alive ✅', main_keyboard())

    elif cmd == '/menu' or cmd == '/help':
        send_message(chat_id,
                     '🔥 *Free Fire Like API Bot*\n\nMenu:',
                     main_keyboard())

# ─── Notification helper (called from app.py / scheduler) ────────────────────

def notify(text, parse_mode='Markdown'):
    chat_id = get_chat_id()
    if not chat_id or chat_id == 'YOUR_CHAT_ID_HERE':
        return
    send_message(chat_id, text, parse_mode=parse_mode)

# ─── Polling loop ─────────────────────────────────────────────────────────────

def poll_loop():
    token = get_bot_token()
    if not token or token == 'YOUR_BOT_TOKEN_HERE':
        log.info('config.json bot_token not set — Telegram bot disabled.')
        return

    log.info('Telegram bot polling started.')
    offset = 0
    while True:
        try:
            data = tg('getUpdates', offset=offset, timeout=30)
            for u in (data.get('result') or []):
                offset = u['update_id'] + 1
                try:
                    if 'callback_query' in u:
                        handle_callback(u['callback_query'])
                    elif 'message' in u:
                        handle_message(u['message'])
                except Exception as e:
                    log.error(f'update handler error: {e}')
        except Exception as e:
            log.error(f'poll_loop error: {e}')
            time.sleep(5)

def start_bot():
    t = threading.Thread(target=poll_loop, daemon=True, name='tg-bot')
    t.start()
    return t
