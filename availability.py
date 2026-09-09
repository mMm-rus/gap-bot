from datetime import datetime
from typing import List, Tuple


def subtract_interval(
    base_start,
    base_end,
    block_start,
    block_end
) -> List[Tuple]:
    """
    Вычитает блокирующий интервал из базового интервала.
    Возвращает список оставшихся доступных интервалов.
    """

    if block_end <= base_start or block_start >= base_end:
        return [(base_start, base_end)]

    result = []

    if block_start > base_start:
        result.append((
            base_start,
            min(block_start, base_end)
        ))

    if block_end < base_end:
        result.append((
            max(block_end, base_start),
            base_end
        ))

    return [
        (start, end)
        for start, end in result
        if start < end
    ]


def calculate_availability(
    target_date,
    settings,
    schedule,
    events,
    cycle_day=None
):
    """
    Рассчитывает доступность исполнителя на конкретную дату.

    Этот модуль содержит бизнес-логику доступности.
    Он не зависит от MAX.
    """

    schedule_type = schedule.get("Тип", "").strip()
    blocks_orders = schedule.get(
        "Блокирует заказы?",
        ""
    ).strip().upper()

    work_start = datetime.strptime(
        settings.get("начало рабочего окна", "09:00"),
        "%H:%M"
    ).time()

    work_end = datetime.strptime(
        settings.get("конец рабочего окна", "20:00"),
        "%H:%M"
    ).time()

    # Базовая доступность по типу смены
    if schedule_type == "СМЕНА":
        if blocks_orders == "ДА":
            base_intervals = []
        else:
            base_intervals = [
                (
                    datetime.strptime("09:00", "%H:%M").time(),
                    datetime.strptime("18:00", "%H:%M").time()
                )
            ]

    elif schedule_type == "ОТДЫХ_ПОСЛЕ_СМЕНЫ":
        base_intervals = [
            (
                datetime.strptime("15:00", "%H:%M").time(),
                work_end
            )
        ]

    elif schedule_type == "ВЫХОДНОЙ":
        base_intervals = [
            (work_start, work_end)
        ]

    else:
        base_intervals = []

    intervals = base_intervals[:]

    # Применяем блокирующие события
    for event in events:
        if event.get(
            "Блокирует заказы?",
            ""
        ).strip().upper() != "ДА":
            continue

        event_start = event.get(
            "Время начала",
            ""
        ).strip()

        event_end = event.get(
            "Время окончания",
            ""
        ).strip()

        # Событие без времени блокирует весь день
        if not event_start or not event_end:
            intervals = []
            break

        try:
            block_start = datetime.strptime(
                event_start,
                "%H:%M"
            ).time()

            block_end = datetime.strptime(
                event_end,
                "%H:%M"
            ).time()
        except ValueError:
            continue

        if block_end <= block_start:
            continue

        new_intervals = []

        for interval_start, interval_end in intervals:
            new_intervals.extend(
                subtract_interval(
                    interval_start,
                    interval_end,
                    block_start,
                    block_end
                )
            )

        intervals = new_intervals

    available = bool(intervals)

    # Формируем текст здесь только как совместимость
    # со старым интерфейсом google_schedule.py.
    if available:
        interval_text = ", ".join(
            f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
            for start, end in intervals
        )
        text = (
            f"{target_date.strftime('%d.%m.%Y')}: "
            f"доступен. Окна: {interval_text}"
        )
    else:
        text = (
            f"{target_date.strftime('%d.%m.%Y')}: "
            f"недоступен."
        )

    return {
        "date": target_date,
        "cycle_day": cycle_day,
        "schedule_type": schedule_type,
        "available": available,
        "first_available_start": (
            intervals[0][0] if intervals else None
        ),
        "last_available_end": (
            intervals[-1][1] if intervals else None
        ),
        "events": events,
        "intervals": intervals,
        "text": text,
    }