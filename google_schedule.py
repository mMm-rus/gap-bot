import csv
import io
import requests
from datetime import datetime, time, timedelta
from typing import List, Tuple
from zoneinfo import ZoneInfo


# ============================================================
# Публичные CSV Google Sheets
# ============================================================

SETTINGS_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRiIG1Vu4cScBRXZPDy_pDi_lzfBLcIbnGO21CTD2FLudflyq0CHJfefYkztX6ouf0-VkfVfXRpDv3v/"
    "pub?gid=530348637&single=true&output=csv"
)

SCHEDULE_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRiIG1Vu4cScBRXZPDy_pDi_lzfBLcIbnGO21CTD2FLudflyq0CHJfefYkztX6ouf0-VkfVfXRpDv3v/"
    "pub?gid=1110583233&single=true&output=csv"
)

EVENTS_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vRiIG1Vu4cScBRXZPDy_pDi_lzfBLcIbnGO21CTD2FLudflyq0CHJfefYkztX6ouf0-VkfVfXRpDv3v/"
    "pub?gid=282552184&single=true&output=csv"
)


# ============================================================
# Загрузка CSV
# ============================================================

def load_csv(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    text = response.content.decode("utf-8-sig")

    return list(csv.DictReader(io.StringIO(text)))


# ============================================================
# Вспомогательные функции
# ============================================================

def parse_date(value):
    return datetime.strptime(
        value.strip(),
        "%d.%m.%Y"
    ).date()


def parse_time(value):
    value = value.strip()

    if not value or value == "—":
        return None

    return datetime.strptime(
        value,
        "%H:%M"
    ).time()


# ============================================================
# Чтение настроек
# ============================================================

def get_settings():
    rows = load_csv(SETTINGS_URL)

    settings = {}

    for row in rows:
        parameter = row.get(
            "Параметр",
            ""
        ).strip()

        value = row.get(
            "Значение",
            ""
        ).strip()

        if parameter:
            settings[parameter] = value

    return settings


# ============================================================
# Поиск дня цикла
# ============================================================

def get_cycle_day(target_date, settings):
    cycle_start = parse_date(
        settings["Начало текущего цикла"]
    )

    configured_cycle_day = int(
        settings["День цикла"]
    )

    days_difference = (
        target_date - cycle_start
    ).days

    cycle_day = (
        (configured_cycle_day - 1 + days_difference) % 10
    ) + 1

    return cycle_day


# ============================================================
# Получение строки графика
# ============================================================

def get_schedule_row(cycle_day):
    rows = load_csv(SCHEDULE_URL)

    for row in rows:
        try:
            day = int(
                row.get(
                    "День цикла",
                    ""
                ).strip()
            )
        except ValueError:
            continue

        if day == cycle_day:
            return row

    return None


# ============================================================
# События
# ============================================================

def get_events(target_date):
    rows = load_csv(EVENTS_URL)

    events = []

    for row in rows:
        start_value = row.get(
            "Дата начала",
            ""
        ).strip()

        end_value = row.get(
            "Дата окончания",
            ""
        ).strip()

        if not start_value:
            continue

        start_date = parse_date(start_value)

        if end_value:
            end_date = parse_date(end_value)
        else:
            end_date = start_date

        if start_date <= target_date <= end_date:
            events.append(row)

    return events


# ============================================================
# Вычитание блокирующих интервалов
# ============================================================

def subtract_interval(
    base_start,
    base_end,
    block_start,
    block_end
):
    if block_end <= base_start:
        return [(base_start, base_end)]

    if block_start >= base_end:
        return [(base_start, base_end)]

    result = []

    if block_start > base_start:
        result.append(
            (
                base_start,
                min(block_start, base_end)
            )
        )

    if block_end < base_end:
        result.append(
            (
                max(block_end, base_start),
                base_end
            )
        )

    return result


# ============================================================
# Расчёт доступности
# ============================================================

def calculate_availability(target_date):
    settings = get_settings()

    cycle_day = get_cycle_day(
        target_date,
        settings
    )

    schedule = get_schedule_row(cycle_day)

    if not schedule:
        return {
            "date": target_date,
            "cycle_day": cycle_day,
            "schedule_type": None,
            "available": False,
            "available_start": None,
            "available_end": None,
            "events": [],
            "intervals": [],
            "text": "Не найден день цикла."
        }

    schedule_type = schedule.get(
        "Тип",
        ""
    ).strip()

    blocks_orders = schedule.get(
        "Блокирует заказы?",
        ""
    ).strip().upper()

    # --------------------------------------------------------
    # Рабочее окно
    # --------------------------------------------------------

    work_start = parse_time(
        settings.get(
            "начало рабочего окна",
            "09:00"
        )
    )

    work_end = parse_time(
        settings.get(
            "конец рабочего окна",
            "20:00"
        )
    )

    if work_start is None or work_end is None:
        return {
            "date": target_date,
            "cycle_day": cycle_day,
            "schedule_type": schedule_type,
            "available": False,
            "available_start": None,
            "available_end": None,
            "events": [],
            "intervals": [],
            "text": "Ошибка настроек рабочего окна."
        }

    # --------------------------------------------------------
    # Базовая доступность
    # --------------------------------------------------------

    if schedule_type == "СМЕНА":

        if blocks_orders == "ДА":
            # Дневная смена.
            # Заказы в этот день не принимаются.
            base_intervals = []

        else:
            # Ночная смена.
            # Заказы принимаются 09:00–18:00.
            # 18:00–20:00 — подготовка к смене.
            base_intervals = [
                (
                    work_start,
                    time(18, 0)
                )
            ]

    elif schedule_type == "ОТДЫХ_ПОСЛЕ_СМЕНЫ":

        # После ночной смены отдых до 15:00.
        base_intervals = [
            (
                time(15, 0),
                work_end
            )
        ]

    elif schedule_type == "ВЫХОДНОЙ":

        # Свободный день.
        base_intervals = [
            (
                work_start,
                work_end
            )
        ]

    else:

        # Неизвестный тип дня.
        base_intervals = []

    # --------------------------------------------------------
    # События
    # --------------------------------------------------------

    events = get_events(target_date)

    blocking_intervals: List[Tuple[time, time, str]] = []
    blocking_all_day = False

    for event in events:

        event_blocks = event.get(
            "Блокирует заказы?",
            ""
        ).strip().upper()

        if event_blocks != "ДА":
            continue

        event_start = parse_time(
            event.get(
                "Время начала",
                ""
            )
        )

        event_end = parse_time(
            event.get(
                "Время окончания",
                ""
            )
        )

        # Нет времени начала или окончания —
        # считаем событие блокирующим весь день.
        if event_start is None or event_end is None:
            blocking_all_day = True
            continue

        # Некорректный интервал.
        if event_end <= event_start:
            continue

        event_type = event.get(
            "Тип",
            ""
        ).strip()

        blocking_intervals.append(
            (
                event_start,
                event_end,
                event_type
            )
        )

    # --------------------------------------------------------
    # Событие на весь день
    # --------------------------------------------------------

    if blocking_all_day:
        final_intervals = []

    else:
        final_intervals = list(base_intervals)

        # Последовательно вычитаем каждое блокирующее событие.
        for block_start, block_end, _event_type in blocking_intervals:

            new_intervals = []

            for interval_start, interval_end in final_intervals:

                new_intervals.extend(
                    subtract_interval(
                        interval_start,
                        interval_end,
                        block_start,
                        block_end
                    )
                )

            final_intervals = new_intervals

    # --------------------------------------------------------
    # Итоговая доступность
    # --------------------------------------------------------

    available = len(final_intervals) > 0

    if not available:

        text = (
            f"{target_date.strftime('%d.%m.%Y')} — "
            f"приём заявок недоступен."
        )

    else:

        interval_text = ", ".join(
            (
                f"{start.strftime('%H:%M')}-"
                f"{end.strftime('%H:%M')}"
            )
            for start, end in final_intervals
        )

        text = (
            f"{target_date.strftime('%d.%m.%Y')} — "
            f"приём заявок: "
            f"{interval_text}."
        )

    # --------------------------------------------------------
    # Добавляем информацию о событиях
    # --------------------------------------------------------

    for start, end, event_type in blocking_intervals:

        text += (
            f" Событие {event_type}: "
            f"{start.strftime('%H:%M')}-"
            f"{end.strftime('%H:%M')}."
        )

    return {
        "date": target_date,
        "cycle_day": cycle_day,
        "schedule_type": schedule_type,
        "available": available,
        "available_start": (
            final_intervals[0][0]
            if available
            else None
        ),
        "available_end": (
            final_intervals[-1][1]
            if available
            else None
        ),
        "events": events,
        "intervals": final_intervals,
        "text": text
    }


# ============================================================
# Публичная функция для бота
# ============================================================

def get_availability(day="сегодня"):
    settings = get_settings()

    timezone_name = settings.get(
        "Часовой пояс",
        "Europe/Amsterdam"
    )

    tz = ZoneInfo(timezone_name)

    now = datetime.now(tz)

    if day == "сегодня":

        target_date = now.date()

    elif day == "завтра":

        target_date = (
            now.date() +
            timedelta(days=1)
        )

    else:

        try:
            target_date = parse_date(day)

        except ValueError:

            return (
                "Не понял дату. "
                "Используй «сегодня», «завтра» "
                "или дату в формате ДД.ММ.ГГГГ."
            )

    result = calculate_availability(
        target_date
    )

    return result["text"]

def get_shift_name(target_date):
    """
    Возвращает короткое название режима работы
    на указанную дату.
    """

    settings = get_settings()

    cycle_day = get_cycle_day(
        target_date,
        settings
    )

    schedule = get_schedule_row(cycle_day)

    if not schedule:
        return "❓ неизвестный режим"

    schedule_type = schedule.get(
        "Тип",
        ""
    ).strip()

    start_time = parse_time(
        schedule.get("Время начала", "")
    )

    end_time = parse_time(
        schedule.get("Время окончания", "")
    )

    if schedule_type == "ВЫХОДНОЙ":
        return "🏠 выходной"

    if schedule_type == "ОТДЫХ_ПОСЛЕ_СМЕНЫ":
        return "😴 отсыпной"

    if schedule_type == "СМЕНА":
        if start_time == time(8, 0) and end_time == time(20, 0):
            return "☀️ в день"

        if start_time == time(20, 0) and end_time == time(8, 0):
            return "🌙 в ночь"

    return "❓ неизвестный режим"

def get_shift_summary():
    """
    Возвращает режим работы на сегодня,
    завтра и послезавтра.
    """

    settings = get_settings()

    timezone_name = settings.get(
        "Часовой пояс",
        "Europe/Amsterdam"
    )

    tz = ZoneInfo(timezone_name)

    today = datetime.now(tz).date()

    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    return (
        f"Сегодня — {get_shift_name(today)}\n"
        f"Завтра — {get_shift_name(tomorrow)}\n"
        f"Послезавтра — {get_shift_name(day_after)}"
    )

def get_next_availability():
    """
    Возвращает ближайшее окно
    для приёма заявок.
    """

    settings = get_settings()

    timezone_name = settings.get(
        "Часовой пояс",
        "Europe/Amsterdam"
    )

    tz = ZoneInfo(timezone_name)

    today = datetime.now(tz).date()

    for offset in range(0, 31):

        target_date = (
            today +
            timedelta(days=offset)
        )

        result = calculate_availability(
            target_date
        )

        intervals = result.get(
            "intervals",
            []
        )

        if not intervals:
            continue

        date_text = target_date.strftime(
            "%d.%m.%Y"
        )

        first_start, first_end = intervals[0]

        if offset == 0:

            return (
                f"Сегодня — "
                f"{first_start.strftime('%H:%M')}-"
                f"{first_end.strftime('%H:%M')}"
            )

        if offset == 1:

            return (
                f"Завтра — "
                f"{first_start.strftime('%H:%M')}-"
                f"{first_end.strftime('%H:%M')}"
            )

        return (
            f"{date_text} — "
            f"{first_start.strftime('%H:%M')}-"
            f"{first_end.strftime('%H:%M')}"
        )

    return (
        "В ближайшие 30 дней нет "
        "времени для приёма заявок."
    )

def get_today_request_status():
    """
    Возвращает ответ для заказчика:
    можно ли принять заявку сегодня.
    """

    settings = get_settings()

    timezone_name = settings.get(
        "Часовой пояс",
        "Europe/Amsterdam"
    )

    tz = ZoneInfo(timezone_name)

    today = datetime.now(tz).date()

    result = calculate_availability(
        today
    )

    if not result["available"]:
        return (
            "Прости, мы сейчас не можем принять "
            "вашу заявку.\n"
            "Нажмите 2, чтобы узнать ближайшее "
            "время приёма заявок."
        )

    interval_text = ", ".join(
        (
            f"{start.strftime('%H:%M')}-"
            f"{end.strftime('%H:%M')}"
        )
        for start, end in result["intervals"]
    )

    return (
        f"Сегодня можем принять заявку: "
        f"{interval_text}."
    )