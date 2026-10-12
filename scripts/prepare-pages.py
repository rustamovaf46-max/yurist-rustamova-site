"""Собрать опубликованные страницы и медиа без редакционных черновиков."""

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "_site"
REQUIRED = (
    "index.html",
    "sitemap.xml",
    "robots.txt",
    "googled3be2855f213bfb7.html",
    "assets/fatima-promo.mp4",
)

for name in REQUIRED:
    source = ROOT / name
    if not source.is_file() or source.stat().st_size == 0:
        raise SystemExit(f"Не найден обязательный файл: {name}")

if OUTPUT.exists():
    shutil.rmtree(OUTPUT)
OUTPUT.mkdir()

public_files = sorted(ROOT.glob("*.html"))
public_files += [ROOT / "sitemap.xml", ROOT / "robots.txt"]
public_files += sorted(ROOT.glob("*.css")) + sorted(ROOT.glob("*.js"))
public_files += sorted((ROOT / "assets").rglob("*"))

copied = []
for source in public_files:
    if source.is_symlink():
        raise SystemExit(f"Символическая ссылка в публичных файлах: {source}")
    if not source.is_file():
        continue
    relative = source.relative_to(ROOT)
    if any(part.startswith(".") for part in relative.parts):
        continue
    destination = OUTPUT / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    copied.append(relative.as_posix())

print(f"Подготовлено публичных файлов: {len(copied)}")
for name in copied:
    print(name)
