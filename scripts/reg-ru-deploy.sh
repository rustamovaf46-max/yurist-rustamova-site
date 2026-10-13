#!/bin/sh
# Синхронизация опубликованных SEO-статей, sitemap и robots.txt из main.
# НЕ менять главную страницу, старые фотографии, видео, оформление и контакты.
set -eu
umask 077
DOMAIN='xn--80aafwvmkbibjcl2m.xn--p1ai'
ARCHIVE_URL='https://github.com/rustamovaf46-max/yurist-rustamova-site/archive/refs/heads/main.zip'
SITE_DIR=''
for candidate in "${HOME:-/var/www/u3681387/data}/www/$DOMAIN" "${HOME:-/var/www/u3681387}/data/www/$DOMAIN" "/var/www/u3681387/data/www/$DOMAIN"; do
  if [ -f "$candidate/index.html" ] && [ -d "$candidate/assets" ]; then
    if [ -n "$SITE_DIR" ] && [ "$SITE_DIR" != "$candidate" ]; then
      echo 'ОШИБКА: обнаружены две папки сайта; остановка.' >&2
      exit 1
    fi
    SITE_DIR=$candidate
  fi
done
if [ -z "$SITE_DIR" ] || [ ! -f "$SITE_DIR/index.html" ] || [ -L "$SITE_DIR" ] || [ -L "$SITE_DIR/assets" ]; then
  echo 'ОШИБКА: каталог сайта не найден или недопустим; ничего не изменено.' >&2
  exit 1
fi
LOCK_DIR="/tmp/zeus-reg-ru-u3681387-deploy.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo 'Предыдущая публикация выполняется; пропуск.'
  exit 0
fi
WORK_DIR=$(mktemp -d "/tmp/zeus-reg-ru-deploy.XXXXXXXX") || exit 1
cleanup() {
  rm -rf "$WORK_DIR"
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM
if command -v curl >/dev/null 2>&1; then
  curl -fLsS --retry 2 --connect-timeout 15 --max-time 120 "$ARCHIVE_URL" -o "$WORK_DIR/main.zip"
elif command -v wget >/dev/null 2>&1; then
  wget -q -T 120 -O "$WORK_DIR/main.zip" "$ARCHIVE_URL"
else
  echo 'ОШИБКА: curl и wget недоступны.' >&2
  exit 1
fi
BYTES=$(wc -c < "$WORK_DIR/main.zip")
if [ "$BYTES" -gt 52428800 ] || [ "$BYTES" -lt 1000 ]; then
  echo 'ОШИБКА: неверный размер архива.' >&2
  exit 1
fi
unzip -q "$WORK_DIR/main.zip" -d "$WORK_DIR"
SRC_DIR="$WORK_DIR/yurist-rustamova-site-main"
for mandatory in index.html robots.txt sitemap.xml assets/fatima-portrait.webp assets/fatima-promo.mp4; do
  if [ ! -s "$SRC_DIR/$mandatory" ] || [ -L "$SRC_DIR/$mandatory" ]; then
    echo "ОШИБКА: повреждён файл $mandatory" >&2
    exit 1
  fi
done
if ! grep -q 'xn--80aafwvmkbibjcl2m.xn--p1ai' "$SRC_DIR/sitemap.xml"; then
  echo 'ОШИБКА: неверный домен в sitemap.xml.' >&2
  exit 1
fi
if [ -n "$(find "$SRC_DIR/assets" -type l -print -quit)" ]; then
  echo 'ОШИБКА: символические ссылки в assets.' >&2
  exit 1
fi
COUNT=0
publish_file() {
  source_file=$1
  rel_file=$(printf '%s' "$source_file" | sed "s!^$SRC_DIR/!!")
  target_file="$SITE_DIR/$rel_file"
  target_dir=$(dirname "$target_file")
  if [ -L "$source_file" ] || [ ! -f "$source_file" ] || [ -L "$target_file" ] || [ -L "$target_dir" ]; then
    echo "ОШИБКА: недопустимый файл $rel_file" >&2
    exit 1
  fi
  if [ -f "$target_file" ] && cmp -s "$source_file" "$target_file"; then
    return
  fi
  mkdir -p "$target_dir"
  chmod 755 "$target_dir"
  temp_file=$(mktemp "$target_dir/.zeus.XXXXXXXX")
  if ! cp "$source_file" "$temp_file"; then
    rm -f "$temp_file"
    exit 1
  fi
  chmod 644 "$temp_file"
  mv -f "$temp_file" "$target_file"
  COUNT=$((COUNT + 1))
}
# Обновляем новый портрет до index.html, чтобы не было битой картинки.
if [ ! -s "$SRC_DIR/assets/fatima-white-suit-hero.avif" ]; then
  echo 'ОШИБКА: новый портрет отсутствует в архиве; публикация остановлена.' >&2
  exit 1
fi
publish_file "$SRC_DIR/assets/fatima-white-suit-hero.avif"
for f in "$SRC_DIR"/*.html; do
  [ -f "$f" ] || continue
  case "${f##*/}" in
    googled3be2855f213bfb7.html) continue ;;
  esac
  publish_file "$f"
done
for f in "$SRC_DIR/robots.txt" "$SRC_DIR/sitemap.xml"; do
  [ -f "$f" ] || continue
  publish_file "$f"
done
echo "Готово: обновлено публичных файлов — $COUNT; сайт — $DOMAIN"
