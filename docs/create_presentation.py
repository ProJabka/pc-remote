from pathlib import Path
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Презентация_PC_Remote.pptx"
SCREEN_CONNECTION = ROOT / "docs" / "android-connection.png"
SCREEN_FILES = ROOT / "docs" / "android-files.png"
SCREEN_TRANSFER = ROOT / "docs" / "android-transfer.png"

# Published project repository.
GIT_URL = "https://github.com/ProJabka/pc-remote"

NAVY = RGBColor(25, 36, 59)
MUTED = RGBColor(105, 119, 145)
BLUE = RGBColor(70, 86, 217)
BLUE_LIGHT = RGBColor(233, 236, 255)
MINT = RGBColor(167, 243, 208)
GOLD = RGBColor(255, 243, 217)
WHITE = RGBColor(255, 255, 255)
BG = RGBColor(244, 246, 251)
GREEN = RGBColor(32, 134, 106)
RED = RGBColor(193, 64, 77)


def add_text(slide, text, x, y, w, h, size=20, color=NAVY, bold=False,
             align=PP_ALIGN.LEFT, font="Aptos", valign=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    frame.vertical_anchor = valign
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def add_rich_text(slide, lines, x, y, w, h, size=18, color=NAVY, spacing=8):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    for index, item in enumerate(lines):
        if isinstance(item, str):
            text, item_color, bold = item, color, False
        else:
            text, item_color, bold = item
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.space_after = Pt(spacing)
        run = p.add_run()
        run.text = text
        run.font.name = "Aptos"
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = item_color
    return box


def rounded(slide, x, y, w, h, fill=WHITE, line=None, radius=True):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line or fill
    shape.line.width = Pt(1)
    return shape


def circle(slide, x, y, d, fill):
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = fill
    return shape


def image(slide, path, x, y, w, h):
    return slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w), height=Inches(h))


def base(slide, number, title, subtitle=None, dark=False):
    background = slide.background
    background.fill.solid()
    background.fill.fore_color.rgb = NAVY if dark else BG
    add_text(slide, "PC REMOTE", 0.55, 0.32, 2.1, 0.25, 9, MINT if dark else BLUE, True)
    add_text(slide, f"{number:02d}", 12.25, 0.30, 0.65, 0.28, 10, MINT if dark else MUTED, True, PP_ALIGN.RIGHT)
    add_text(slide, title, 0.55, 0.82, 11.8, 0.65, 28, WHITE if dark else NAVY, True)
    if subtitle:
        add_text(slide, subtitle, 0.57, 1.53, 11.6, 0.38, 12, RGBColor(198, 208, 234) if dark else MUTED)


def bullet_card(slide, x, y, w, h, heading, body, accent=BLUE):
    rounded(slide, x, y, w, h, WHITE)
    circle(slide, x + 0.22, y + 0.24, 0.32, accent)
    add_text(slide, "✓", x + 0.22, y + 0.22, 0.32, 0.32, 12, WHITE, True, PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_text(slide, heading, x + 0.70, y + 0.22, w - 0.9, 0.32, 15, NAVY, True)
    add_text(slide, body, x + 0.70, y + 0.62, w - 0.92, h - 0.75, 12, MUTED)


def comparison_row(slide, y, label, ours, alternative):
    add_text(slide, label, 0.65, y, 2.3, 0.35, 13, NAVY, True)
    rounded(slide, 3.15, y - 0.08, 3.9, 0.55, BLUE_LIGHT)
    add_text(slide, ours, 3.38, y + 0.03, 3.45, 0.27, 12, BLUE, True)
    rounded(slide, 7.35, y - 0.08, 4.7, 0.55, WHITE)
    add_text(slide, alternative, 7.58, y + 0.03, 4.2, 0.27, 12, MUTED)


def create():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # 1 — title
    slide = prs.slides.add_slide(blank)
    base(slide, 1, "Файлы компьютера в телефоне", "PC Remote — защищённый доступ к выбранной папке ПК", dark=True)
    rounded(slide, 0.60, 3.25, 5.45, 2.55, RGBColor(35, 49, 81))
    add_text(slide, "Android-приложение + HTTPS-сервер для Windows", 0.92, 3.62, 4.75, 0.48, 19, WHITE, True)
    add_text(slide, "Автор: ProJabka", 0.92, 4.27, 4.7, 0.3, 13, RGBColor(198, 208, 234))
    # simplified device illustration
    rounded(slide, 8.15, 2.42, 3.35, 2.25, WHITE)
    rounded(slide, 8.46, 2.73, 2.73, 1.55, BLUE_LIGHT)
    rounded(slide, 9.25, 4.95, 1.15, 0.45, WHITE)
    rounded(slide, 8.72, 5.40, 2.20, 0.18, WHITE)
    add_text(slide, "↔", 9.14, 3.03, 1.2, 0.65, 42, BLUE, True, PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_text(slide, "ПК", 8.55, 4.32, 2.55, 0.25, 12, MUTED, True, PP_ALIGN.CENTER)
    rounded(slide, 10.95, 3.00, 1.28, 2.35, BLUE)
    rounded(slide, 11.14, 3.33, 0.90, 1.45, WHITE)
    add_text(slide, "PC", 11.26, 3.82, 0.65, 0.32, 17, BLUE, True, PP_ALIGN.CENTER)
    add_text(slide, "Без облака\nи посредников", 10.78, 5.65, 1.65, 0.48, 11, MINT, True, PP_ALIGN.CENTER)

    # 2 — problem
    slide = prs.slides.add_slide(blank)
    base(slide, 2, "Какую проблему решает проект", "Файлы часто остаются на ПК, когда они нужны вне рабочего места")
    bullet_card(slide, 0.62, 2.20, 3.85, 1.55, "Нет доступа вне дома", "Нужный документ или фотография находятся на компьютере, а телефон — под рукой.", BLUE)
    bullet_card(slide, 4.74, 2.20, 3.85, 1.55, "Облако не всегда подходит", "Нужно загружать файлы, есть ограничения по приватности, интернету и месту.", GREEN)
    bullet_card(slide, 8.86, 2.20, 3.85, 1.55, "Удалённый рабочий стол избыточен", "Для одного файла не нужен полный контроль экрана и клавиатуры ПК.", RGBColor(193, 139, 36))
    rounded(slide, 0.62, 4.35, 12.08, 1.55, NAVY)
    add_text(slide, "Цель", 0.95, 4.73, 1.1, 0.3, 14, MINT, True)
    add_text(slide, "Дать владельцу быстрый и безопасный доступ к файлам своего ПК с телефона — только к выбранной папке.", 2.0, 4.65, 9.95, 0.55, 22, WHITE, True)

    # 3 — product
    slide = prs.slides.add_slide(blank)
    base(slide, 3, "Что представляет собой PC Remote", "Два компонента работают вместе в одной локальной сети или через VPN")
    rounded(slide, 0.75, 2.10, 5.35, 3.65, WHITE)
    add_text(slide, "01", 1.08, 2.48, 0.55, 0.35, 16, BLUE, True)
    add_text(slide, "Android-приложение", 1.82, 2.46, 3.8, 0.35, 19, NAVY, True)
    add_rich_text(slide, [
        ("• список файлов и папок", NAVY, False),
        ("• поиск по текущей папке", NAVY, False),
        ("• скачивание на телефон", NAVY, False),
        ("• загрузка на ПК", NAVY, False),
        ("• создание папок", NAVY, False),
    ], 1.08, 3.15, 4.3, 1.75, 15, NAVY, 11)
    rounded(slide, 7.20, 2.10, 5.35, 3.65, WHITE)
    add_text(slide, "02", 7.53, 2.48, 0.55, 0.35, 16, GREEN, True)
    add_text(slide, "Сервер на ПК", 8.27, 2.46, 3.8, 0.35, 19, NAVY, True)
    add_rich_text(slide, [
        ("• HTTPS и проверка сертификата", NAVY, False),
        ("• секретный ключ доступа", NAVY, False),
        ("• доступ только к выбранной папке", NAVY, False),
        ("• режим только чтения", NAVY, False),
        ("• запрет удаления и перезаписи", NAVY, False),
    ], 7.53, 3.15, 4.35, 1.75, 15, NAVY, 11)
    add_text(slide, "Телефон  →  защищённый API  →  выбранная папка ПК", 1.0, 6.25, 11.3, 0.38, 16, BLUE, True, PP_ALIGN.CENTER)

    # 4 — workflow
    slide = prs.slides.add_slide(blank)
    base(slide, 4, "Как пользователь работает с приложением", "Три шага от запуска сервера до передачи файла")
    steps = [
        ("1", "Запуск", "На ПК запускается start-server.cmd.\nСервер показывает адрес, ключ и SHA-256 отпечаток.", BLUE),
        ("2", "Подключение", "В приложении вводятся данные из окна сервера.\nПроверяется точный TLS-сертификат.", GREEN),
        ("3", "Файлы", "Пользователь открывает папки, скачивает или загружает файлы.\nОригинал на ПК не удаляется.", RGBColor(193, 139, 36)),
    ]
    for i, (number, heading, body, accent) in enumerate(steps):
        x = 0.75 + i * 4.2
        circle(slide, x + 1.52, 2.1, 1.02, accent)
        add_text(slide, number, x + 1.52, 2.28, 1.02, 0.55, 25, WHITE, True, PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_text(slide, heading, x, 3.45, 4.05, 0.4, 20, NAVY, True, PP_ALIGN.CENTER)
        add_text(slide, body, x + 0.25, 4.05, 3.55, 1.0, 13, MUTED, False, PP_ALIGN.CENTER)
        if i < 2:
            add_text(slide, "→", x + 3.75, 2.42, 0.45, 0.42, 26, MUTED, True, PP_ALIGN.CENTER)
    rounded(slide, 1.75, 6.05, 9.85, 0.70, BLUE_LIGHT)
    add_text(slide, "Данные подключения шифруются ключом из Android Keystore", 2.0, 6.25, 9.35, 0.25, 14, BLUE, True, PP_ALIGN.CENTER)

    # 5 — alternatives
    slide = prs.slides.add_slide(blank)
    base(slide, 5, "Альтернативы и сравнение", "PC Remote не заменяет все решения — он оптимален для точечного доступа к своим файлам")
    add_text(slide, "Критерий", 0.65, 2.05, 2.25, 0.3, 12, MUTED, True)
    add_text(slide, "PC Remote", 3.15, 2.05, 3.9, 0.3, 12, BLUE, True)
    add_text(slide, "Альтернативные решения", 7.35, 2.05, 4.7, 0.3, 12, MUTED, True)
    comparison_row(slide, 2.60, "Приватность", "Файлы остаются на вашем ПК", "Облако хранит копии файлов")
    comparison_row(slide, 3.35, "Простота", "Одна папка и один APK", "SMB требует настройки сети")
    comparison_row(slide, 4.10, "Сценарий", "Передать / забрать файл", "AnyDesk даёт полный экран ПК")
    comparison_row(slide, 4.85, "Удалённый доступ", "Через личный VPN", "Облако доступно из интернета")
    comparison_row(slide, 5.60, "Стоимость", "Без подписки и облака", "Часть сервисов имеет платные лимиты")
    add_text(slide, "Альтернативы: Google Drive / OneDrive, Windows SMB, AnyDesk / TeamViewer.", 0.65, 6.55, 11.6, 0.25, 11, MUTED)

    # 6 — strengths/weaknesses
    slide = prs.slides.add_slide(blank)
    base(slide, 6, "Сильные стороны и ограничения", "В чём PC Remote превосходит альтернативы — и где уступает")
    rounded(slide, 0.72, 2.10, 5.78, 3.95, RGBColor(239, 252, 246))
    add_text(slide, "Преимущества PC Remote", 1.05, 2.45, 4.8, 0.38, 19, GREEN, True)
    add_rich_text(slide, [
        ("✓ данные не уходят в облако", GREEN, True),
        ("✓ доступ ограничен одной папкой", GREEN, True),
        ("✓ понятный сценарий без полного удалённого стола", GREEN, True),
        ("✓ сертификат и ключ проверяются приложением", GREEN, True),
        ("✓ APK работает без сторонних runtime-библиотек", GREEN, True),
    ], 1.05, 3.05, 4.95, 2.25, 14, GREEN, 13)
    rounded(slide, 6.82, 2.10, 5.78, 3.95, RGBColor(255, 247, 247))
    add_text(slide, "Ограничения проекта", 7.15, 2.45, 4.8, 0.38, 19, RED, True)
    add_rich_text(slide, [
        ("— ПК должен быть включён", RED, True),
        ("— нужен Wi-Fi или личный VPN", RED, True),
        ("— нет управления экраном ПК", RED, True),
        ("— нет докачки прерванной передачи", RED, True),
        ("— сейчас нет удаления файлов", RED, True),
    ], 7.15, 3.05, 4.95, 2.25, 14, RED, 13)

    # 7 — security
    slide = prs.slides.add_slide(blank)
    base(slide, 7, "Безопасность", "Проект сознательно ограничивает опасные операции")
    security = [
        ("TLS 1.2+", "Соединение шифруется; клиент проверяет точный SHA-256 сертификата.", BLUE),
        ("Bearer-ключ", "Каждый API-запрос требует секретный ключ. Есть ограничение неудачных попыток.", GREEN),
        ("Ограничение папкой", "Пути за пределами выбранной папки, ссылки, junction и ADS блокируются.", RGBColor(193, 139, 36)),
        ("Атомарная запись", "Совпадающие имена отклоняются; перезапись и удаление отключены.", RED),
    ]
    for i, (heading, body, accent) in enumerate(security):
        x = 0.75 + (i % 2) * 6.15
        y = 2.15 + (i // 2) * 1.85
        rounded(slide, x, y, 5.55, 1.45, WHITE)
        rounded(slide, x + 0.25, y + 0.30, 0.20, 0.82, accent, accent, False)
        add_text(slide, heading, x + 0.68, y + 0.25, 4.4, 0.32, 16, NAVY, True)
        add_text(slide, body, x + 0.68, y + 0.72, 4.45, 0.46, 12, MUTED)
    rounded(slide, 1.15, 6.10, 11.0, 0.65, NAVY)
    add_text(slide, "Для доступа через интернет используется личный VPN — порт не открывается всему интернету.", 1.38, 6.30, 10.55, 0.23, 13, WHITE, True, PP_ALIGN.CENTER)

    # 8 — screens
    slide = prs.slides.add_slide(blank)
    base(slide, 8, "Скриншоты приложения", "Интерфейс: подключение, список файлов, передача")
    image(slide, SCREEN_CONNECTION, 1.05, 2.0, 2.35, 5.22)
    image(slide, SCREEN_FILES, 5.49, 2.0, 2.35, 5.22)
    image(slide, SCREEN_TRANSFER, 9.93, 2.0, 2.35, 5.22)
    add_text(slide, "Экран подключения", 0.78, 7.28, 2.90, 0.20, 10, MUTED, True, PP_ALIGN.CENTER)
    add_text(slide, "Папки и файлы", 5.22, 7.28, 2.90, 0.20, 10, MUTED, True, PP_ALIGN.CENTER)
    add_text(slide, "Передача файла", 9.66, 7.28, 2.90, 0.20, 10, MUTED, True, PP_ALIGN.CENTER)

    # 9 — tech stack
    slide = prs.slides.add_slide(blank)
    base(slide, 9, "Технологии и результат", "Проект можно открыть и собрать в Android Studio")
    rounded(slide, 0.72, 2.05, 5.55, 3.85, WHITE)
    add_text(slide, "Стек", 1.05, 2.42, 4.7, 0.35, 19, NAVY, True)
    add_rich_text(slide, [
        ("Android: Java, SDK 35, minSdk 26", NAVY, True),
        ("Сборка: Gradle 8.11.1, AGP 8.9.1", NAVY, False),
        ("Сервер: Python 3.14 + HTTPS API", NAVY, False),
        ("Криптография: TLS, SHA-256, AES-GCM", NAVY, False),
        ("Проверка: Android Lint + 26 серверных тестов", NAVY, False),
    ], 1.05, 3.08, 4.65, 2.05, 14, NAVY, 13)
    rounded(slide, 6.72, 2.05, 5.85, 3.85, BLUE)
    add_text(slide, "Что готово", 7.08, 2.42, 4.9, 0.35, 19, WHITE, True)
    add_rich_text(slide, [
        ("✓ APK собран и проверен", WHITE, True),
        ("✓ исходный код Android и сервера", WHITE, False),
        ("✓ инструкция запуска на Windows", WHITE, False),
        ("✓ проверка в эмуляторе Android 15", WHITE, False),
        ("✓ скачивание и загрузка файлов", WHITE, False),
    ], 7.08, 3.08, 4.85, 2.05, 14, WHITE, 13)

    # 10 — git / hand-in
    slide = prs.slides.add_slide(blank)
    base(slide, 10, "Исходный код и APK", "Открытый репозиторий проекта PC Remote")
    rounded(slide, 0.75, 2.10, 7.35, 3.75, NAVY)
    add_text(slide, "Состав репозитория", 1.12, 2.48, 6.5, 0.4, 21, WHITE, True)
    add_rich_text(slide, [
        ("• android/ — проект Android Studio", WHITE, False),
        ("• server/ — HTTPS-сервер и тесты", WHITE, False),
        ("• release/PC-Remote.apk — APK", MINT, True),
        ("• docs/ — скриншоты и отчёт проверки", WHITE, False),
        ("• README.md — инструкция запуска", WHITE, False),
    ], 1.12, 3.15, 6.2, 1.95, 15, WHITE, 12)
    rounded(slide, 8.45, 2.10, 4.1, 3.75, WHITE)
    add_text(slide, "Ссылка на Git", 8.80, 2.48, 3.35, 0.35, 19, BLUE, True)
    link = add_text(slide, GIT_URL, 8.80, 3.20, 3.35, 0.95, 15, NAVY, True)
    if "<" not in GIT_URL:
        link.text_frame.paragraphs[0].runs[0].hyperlink.address = GIT_URL
    add_text(slide, "Исходный код, APK и документация доступны в репозитории.", 8.80, 4.35, 3.2, 0.78, 12, MUTED)
    rounded(slide, 1.55, 6.25, 10.2, 0.58, BLUE_LIGHT)
    add_text(slide, "PC Remote — ваши файлы на ПК, доступ к ним с телефона", 1.8, 6.43, 9.7, 0.22, 13, BLUE, True, PP_ALIGN.CENTER)

    prs.save(OUT)
    print(OUT)


if __name__ == "__main__":
    create()
