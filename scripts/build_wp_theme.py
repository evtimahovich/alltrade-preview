#!/usr/bin/env python3
"""Сборка WordPress-темы из index.html.

Берёт корневой index.html + assets/ и собирает установочный архив темы:
  dist/alltrade-ltd-theme/   — папка темы
  dist/alltrade-ltd.zip      — архив для установки через WP-админку

Запуск:  python3 scripts/build_wp_theme.py
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
THEME = DIST / "alltrade-ltd-theme"
THEME_SLUG = "alltrade-ltd"

STYLE_CSS = """/*
Theme Name: ALLTRADE-LTD
Description: Одностраничный сайт ALLTRADE-LTD — СИЗ под ключ для промышленности Казахстана. Вся вёрстка и стили в index.php, этот файл нужен WordPress только для регистрации темы.
Version: 1.0
Author: ALLTRADE-LTD
Text Domain: alltrade-ltd
*/
"""

FUNCTIONS_PHP = """<?php
// Тема-лендинг: страница полностью самодостаточна (инлайн-стили в index.php).
// Убираем стили ядра WP, чтобы они не вмешивались в вёрстку.
add_action('wp_enqueue_scripts', function () {
    wp_dequeue_style('wp-block-library');
    wp_dequeue_style('classic-theme-styles');
    wp_dequeue_style('global-styles');
}, 20);

// Свой <title> уже есть в разметке — title-tag не подключаем.
// Убираем emoji-скрипты WP (не используются, лишние запросы).
remove_action('wp_head', 'print_emoji_detection_script', 7);
remove_action('wp_print_styles', 'print_emoji_styles');
"""


def build() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    # Относительные пути assets/ -> URL темы (иначе WP отдаёт страницу не из корня
    # и картинки ломаются). Абсолютные https://.../assets/ (og:image) не трогаем.
    html, n = re.subn(r'"assets/', '"<?php echo $A; ?>/assets/', html)
    leftovers = re.findall(r'[^/"]assets/', html)
    print(f"путей переписано: {n}, осталось без замены: {len(leftovers)}")
    if leftovers:
        sys.exit(f"ОШИБКА: непереписанные пути: {leftovers[:5]}")

    if "<?php echo $A; ?>" not in html.split("</head>")[0]:
        sys.exit("ОШИБКА: в <head> не оказалось ни одного пути темы — что-то не так")

    # wp_head/wp_footer — чтобы работали плагины (аналитика, пиксели и т.п.)
    html = html.replace("</head>", "<?php wp_head(); ?>\n</head>", 1)
    html = html.replace("</body>", "<?php wp_footer(); ?>\n</body>", 1)

    index_php = "<?php $A = get_template_directory_uri(); ?>\n" + html

    if THEME.exists():
        shutil.rmtree(THEME)
    THEME.mkdir(parents=True)
    (THEME / "index.php").write_text(index_php, encoding="utf-8")
    (THEME / "style.css").write_text(STYLE_CSS, encoding="utf-8")
    (THEME / "functions.php").write_text(FUNCTIONS_PHP, encoding="utf-8")
    shutil.copytree(ROOT / "assets", THEME / "assets")

    # Скриншот темы для админки — из og-cover (macOS sips; если нет — пропускаем)
    try:
        subprocess.run(
            ["sips", "-s", "format", "png", str(ROOT / "assets" / "og-cover.jpg"),
             "--out", str(THEME / "screenshot.png")],
            check=True, capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        # нет sips (Linux/CI) — просто кладём jpg, WP понимает screenshot.jpg
        shutil.copy(ROOT / "assets" / "og-cover.jpg", THEME / "screenshot.jpg")

    zip_path = DIST / f"{THEME_SLUG}.zip"
    zip_path.unlink(missing_ok=True)
    # Внутри архива папка темы должна называться slug'ом
    staging = DIST / "_zip"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    shutil.copytree(THEME, staging / THEME_SLUG)
    subprocess.run(["zip", "-qr", str(zip_path), THEME_SLUG], cwd=staging, check=True)
    shutil.rmtree(staging)

    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"готово: {zip_path} ({size_mb:.1f} МБ)")


if __name__ == "__main__":
    build()
