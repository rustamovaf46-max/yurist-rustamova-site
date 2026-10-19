"""Установить общие настройки аналитики на публичные HTML-страницы без изменения вёрстки."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
# На REG.RU синхронизируются HTML-файлы. Встраивание исключает зависимость
# от версии серверного deploy-скрипта и отдельной доставки JS/CSS.
ASSETS = ('<!-- Analytics consent start -->\n<style id="analytics-consent-style">\n' +
          (ROOT / 'analytics-consent.css').read_text(encoding='utf-8') +
          '</style>\n<script id="analytics-consent-script" data-metrika-id="113668938">\n' +
          (ROOT / 'analytics-consent.js').read_text(encoding='utf-8') +
          '</script>\n<!-- Analytics consent end -->\n')
PREFERENCES = ('<div class="analytics-preferences"><a href="/analytics-consent.html#settings" '
               'data-analytics-settings>Настройки аналитики и cookie</a></div>')
check = '--check' in sys.argv
missing = []
for page in sorted(ROOT.glob('*.html')):
    if page.name.startswith(('yandex_', 'google')):
        continue
    old = page.read_text(encoding='utf-8')
    new = old
    if '<!-- Analytics consent start -->' in new:
        new = re.sub(r'<!-- Analytics consent start -->.*?<!-- Analytics consent end -->\n?',
                     lambda _: ASSETS,new,count=1,flags=re.S)
    elif 'src="/analytics-consent.js?' in new:
        new = re.sub(r'<link rel="stylesheet" href="/analytics-consent\.css\?[^\"]*">\s*'
                     r'<script defer src="/analytics-consent\.js\?[^\"]*" data-metrika-id="113668938"></script>\s*',
                     lambda _: ASSETS,new,count=1)
    else:
        new, count = re.subn(r'</head\s*>', lambda _: ASSETS + '</head>', new, count=1, flags=re.I)
        if count != 1:
            raise SystemExit('Не найден </head>: ' + page.name)
    if 'data-analytics-settings' not in new:
        new, count = re.subn(r'</footer\s*>', PREFERENCES + '</footer>', new, count=1, flags=re.I)
        if count != 1:
            raise SystemExit('Не найден </footer>: ' + page.name)
    if new != old:
        missing.append(page.name)
        if not check:
            page.write_text(new,encoding='utf-8')
if check and missing:
    raise SystemExit('Отсутствует аналитика с согласием: ' + ', '.join(missing))
print(('Требуют обновления: ' if check else 'Обновлены: ') + str(len(missing)))
