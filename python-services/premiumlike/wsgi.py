import logging
from app import app
from bot import start_bot, notify
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

log.info('Starting token refresh on boot...')
try:
    from app import do_refresh_tokens
    do_refresh_tokens(notify_telegram=True)
except Exception as e:
    log.warning(f'Boot token refresh failed: {e}')

log.info('Starting scheduler...')
start_scheduler()

log.info('Starting Telegram bot...')
start_bot()

notify(
    '🚀 *FF Like API চালু হয়েছে!*\n\n'
    '✅ Server is online\n'
    '🔑 Tokens loaded\n'
    '⏰ Auto-refresh scheduled\n\n'
    'নিচের /start দিয়ে menu খুলুন।'
)

log.info('WSGI app ready.')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
