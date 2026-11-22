#!/bin/sh
# Синхронизация опубликованных SEO-статей, sitemap и robots.txt из main.
# Сохранять дизайн и контакты; одобренные портреты разворачивать до обновления HTML.
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
for mandatory in index.html robots.txt sitemap.xml assets/fatima-portrait.webp assets/fatima-promo.mp4 assets/fatima-hero-sharp.webp assets/fatima-portrait-natural.webp; do
  if [ ! -s "$SRC_DIR/$mandatory" ] || [ -L "$SRC_DIR/$mandatory" ]; then
    echo "ОШИБКА: повреждён файл $mandatory" >&2
    exit 1
  fi
done
if ! grep -q 'xn--80aafwvmkbibjcl2m.xn--p1ai' "$SRC_DIR/sitemap.xml"; then
  echo 'ОШИБКА: неверный домен в sitemap.xml.' >&2
  exit 1
fi
INDEXNOW_KEY='91f7e03d63fefe7098456dca52d83d4a'
if [ ! -s "$SRC_DIR/$INDEXNOW_KEY.txt" ] || [ -L "$SRC_DIR/$INDEXNOW_KEY.txt" ] || [ "$(cat "$SRC_DIR/$INDEXNOW_KEY.txt")" != "$INDEXNOW_KEY" ]; then
  echo 'ОШИБКА: нет действительного публичного файла подтверждения IndexNow.' >&2
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
# Сначала публикуем ресурсы, затем HTML: новые файлы картинок и видео
# не должны приводить к 404 после публикации страниц. Старые файлы не удаляем.
for f in "$SRC_DIR"/assets/*; do
  [ -f "$f" ] || continue
  publish_file "$f"
done
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
# Файл проверки IndexNow нужен на боевом REG.RU; ранее сюда не копировался.
publish_file "$SRC_DIR/$INDEXNOW_KEY.txt"
# Сохраняем любые существующие пользовательские правила и добавляем
# собственную секцию canonical в начало .htaccess. При 500/цикле — откат.
install_canonical_redirects() {
  redirect_source="$SRC_DIR/.htaccess"
  redirect_target="$SITE_DIR/.htaccess"
  [ -s "$redirect_source" ] && [ ! -L "$redirect_source" ] || {
    echo 'WARNING: исходная секция canonical не найдена; пропуск' >&2
    return 0
  }
  if [ -L "$redirect_target" ]; then
    echo 'WARNING: .htaccess является ссылкой — не изменён' >&2
    return 0
  fi
  if [ -e "$redirect_target" ] && [ ! -f "$redirect_target" ]; then
    echo 'WARNING: .htaccess не обычный файл — не изменён' >&2
    return 0
  fi
  if [ -f "$redirect_target" ] && grep -q 'BEGIN ZEUS CANONICAL' "$redirect_target"; then
    echo 'CANONICAL: управляемый блок уже существует; не дублируем'
    return 0
  fi
  if ! command -v curl >/dev/null 2>&1; then
    echo 'WARNING: без curl нельзя безопасно проверить редирект; пропуск' >&2
    return 0
  fi
  had_old=no
  if [ -f "$redirect_target" ]; then
    had_old=yes
    cp -p "$redirect_target" "$WORK_DIR/previous-htaccess"
  fi
  temporary=$(mktemp "$SITE_DIR/.zeus-htaccess.XXXXXXXX") || exit 1
  cat "$redirect_source" > "$temporary"
  if [ "$had_old" = yes ]; then
    printf '\n' >> "$temporary"
    cat "$WORK_DIR/previous-htaccess" >> "$temporary"
  fi
  chmod 644 "$temporary"
  mv -f "$temporary" "$redirect_target"
  # Cache-busting path checks cover both the HTTP 301 and HTTPS 200.
  nonce="zeus-redirect-$(date +%s)"
  redirect_result=$(curl -sS --connect-timeout 7 --max-time 20 -o /dev/null \
      -w '%{http_code} %{redirect_url}' "http://$DOMAIN/robots.txt?$nonce") || redirect_result=''
  secure_status=$(curl -sS --connect-timeout 7 --max-time 20 -o /dev/null \
      -w '%{http_code}' "https://$DOMAIN/robots.txt?$nonce") || secure_status=''
  case "$redirect_result" in
    "301 https://$DOMAIN/robots.txt?$nonce")
      if [ "$secure_status" = 200 ]; then
        echo 'CANONICAL PASS: HTTP 301 to HTTPS; HTTPS 200'
        return 0
      fi ;;
  esac
  echo "WARNING: canonical smoke check failed (HTTP=$redirect_result; HTTPS=$secure_status); restoring previous .htaccess" >&2
  if [ "$had_old" = yes ]; then
    cp -p "$WORK_DIR/previous-htaccess" "$redirect_target"
  else
    rm -f "$redirect_target"
  fi
  return 0
}
install_canonical_redirects

# Install and update ONLY ZEUS's managed security block while preserving the
# host owner's other .htaccess rules. The previous deploy script deliberately
# skipped .htaccess whenever ZEUS CANONICAL was already present: that would
# prevent newly added security headers from ever reaching production.
SECURITY_APPLIED=no
install_security_rules() {
  source_file="$SRC_DIR/.htaccess"
  target_file="$SITE_DIR/.htaccess"
  [ -f "$target_file" ] && [ ! -L "$target_file" ] || {
    echo 'WARNING: .htaccess unavailable; security rules not installed' >&2
    return 0
  }
  if ! command -v curl >/dev/null 2>&1; then
    echo 'WARNING: cannot verify security headers without curl; no security change made' >&2
    return 0
  fi
  source_begin=$(grep -c '^# BEGIN ZEUS SECURITY$' "$source_file" || true)
  source_end=$(grep -c '^# END ZEUS SECURITY$' "$source_file" || true)
  target_begin=$(grep -c '^# BEGIN ZEUS SECURITY$' "$target_file" || true)
  target_end=$(grep -c '^# END ZEUS SECURITY$' "$target_file" || true)
  if [ "$source_begin" -ne 1 ] || [ "$source_end" -ne 1 ] || \
     [ "$target_begin" -ne "$target_end" ] || [ "$target_begin" -gt 1 ]; then
    echo 'WARNING: security markers are malformed; no security change made' >&2
    return 0
  fi

  backup="$WORK_DIR/security-htaccess-previous"
  cp -p "$target_file" "$backup"
  staged=$(mktemp "$SITE_DIR/.zeus-security.XXXXXXXX") || exit 1
  # Delete only the prior ZEUS-managed segment, leave any user rules intact.
  sed '/^# BEGIN ZEUS SECURITY$/,/^# END ZEUS SECURITY$/d' "$target_file" > "$staged"
  printf '\n' >> "$staged"
  sed -n '/^# BEGIN ZEUS SECURITY$/,/^# END ZEUS SECURITY$/p' "$source_file" >> "$staged"
  chmod 644 "$staged"
  changed=no
  if cmp -s "$staged" "$target_file"; then
    rm -f "$staged"
  else
    mv -f "$staged" "$target_file"
    changed=yes
  fi

  # On every run verify actual HTTP response headers after a fresh request.
  # No green "security applied" state is allowed on absent/ignored headers.
  nonce="zeus-security-$(date +%s)"
  header_result=$(curl -fsS --connect-timeout 7 --max-time 20 \
      -H 'Cache-Control: no-cache' -D - -o /dev/null \
      "https://$DOMAIN/robots.txt?$nonce") || header_result=''
  lower_headers=$(printf '%s' "$header_result" | tr '[:upper:]' '[:lower:]')
  if printf '%s\n' "$lower_headers" | grep -q '^x-content-type-options: nosniff' && \
     printf '%s\n' "$lower_headers" | grep -q '^x-frame-options: deny' && \
     printf '%s\n' "$lower_headers" | grep -q '^content-security-policy: '; then
    SECURITY_APPLIED=yes
    echo 'SECURITY LIVE PASS: X-Content-Type-Options, X-Frame-Options, CSP confirmed'
    return 0
  fi

  if [ "$changed" = yes ]; then
    cp -p "$backup" "$target_file"
    echo 'WARNING: security block rolled back because live HTTP headers did not pass' >&2
  else
    echo 'WARNING: existing security block did not pass HTTP verification' >&2
  fi
  return 0
}
install_security_rules

# Статус физической выкладки REG.RU — записывать ПОСЛЕ копирования sitemap.
# Публичный маркер не содержит учётных данных и позволяет отличать завершённый
# cron от зелёного теста GitHub, который лишь увидел старую версию.
STAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
SITEMAP_COUNT=$(grep -c '<loc>' "$SITE_DIR/sitemap.xml" || true)
SITEMAP_SUM=$(cksum "$SITE_DIR/sitemap.xml" | awk '{print $1 "-" $2}')
HEALTH_TMP=$(mktemp "$SITE_DIR/.zeus-health.XXXXXXXX")
{
  echo "published_at_utc=$STAMP"
  echo "sitemap_url_count=$SITEMAP_COUNT"
  echo "sitemap_checksum=$SITEMAP_SUM"
  echo "updated_files=$COUNT"
} > "$HEALTH_TMP"
chmod 644 "$HEALTH_TMP"
mv -f "$HEALTH_TMP" "$SITE_DIR/zeus-sync-status.txt"
echo "ZEUS REG.RU SYNC: time=$STAMP urls=$SITEMAP_COUNT checksum=$SITEMAP_SUM updated=$COUNT"
echo "Готово: обновлено публичных файлов — $COUNT; сайт — $DOMAIN"
