from collections import Counter
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class Draw:
    issue: str
    draw_date: date
    numbers: tuple[int, ...]
    jackpot_winners: int


def parse_roc_date(value: str) -> date:
    if not value:
        raise ValueError("Invalid ROC date: empty")

    parts = value.split("/")
    if len(parts) != 3:
        raise ValueError(f"Invalid ROC date: {value}")

    try:
        roc_year, month, day = (int(part) for part in parts)
        return date(roc_year + 1911, month, day)
    except ValueError as exc:
        raise ValueError(f"Invalid ROC date: {value}") from exc


def parse_numbers(value: str) -> tuple[int, ...]:
    try:
        numbers = tuple(int(part) for part in value.split())
    except ValueError as exc:
        raise ValueError(f"Invalid Lotto 539 numbers: {value}") from exc

    if (
        len(numbers) != 5
        or len(set(numbers)) != 5
        or any(number < 1 or number > 39 for number in numbers)
    ):
        raise ValueError(f"Invalid Lotto 539 numbers: {value}")

    return tuple(sorted(numbers))


def load_draws(db_path: Path) -> list[Draw]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            'SELECT "期別", "開獎日", "大小順序", "頭獎中獎注數" FROM history'
        ).fetchall()

    draws = [
        Draw(
            issue=issue,
            draw_date=parse_roc_date(draw_date),
            numbers=parse_numbers(numbers),
            jackpot_winners=int(jackpot_winners),
        )
        for issue, draw_date, numbers, jackpot_winners in rows
    ]
    return sorted(draws, key=lambda draw: (draw.draw_date, draw.issue))


def summarize_draw(draw: Draw) -> dict[str, object]:
    odd_count = sum(1 for number in draw.numbers if number % 2)
    return {
        "issue": draw.issue,
        "draw_date": draw.draw_date,
        "sum": sum(draw.numbers),
        "odd_count": odd_count,
        "even_count": 5 - odd_count,
        "tails": tuple(sorted(number % 10 for number in draw.numbers)),
    }


def calculate_ac_value(numbers) -> int:
    ordered = tuple(sorted(numbers))
    differences = {
        abs(first - second) for first, second in combinations(ordered, 2)
    }
    return len(differences) - (len(ordered) - 1)


def has_allowed_consecutive_pattern(numbers) -> bool:
    ordered = tuple(sorted(numbers))
    consecutive_pairs = 0
    current_run = 1

    for previous, current in zip(ordered, ordered[1:]):
        if current - previous == 1:
            consecutive_pairs += 1
            current_run += 1
            if current_run >= 3:
                return False
        else:
            current_run = 1

    return consecutive_pairs <= 1


def count_tail_pairs(numbers) -> int:
    tail_counts = Counter(number % 10 for number in numbers)
    return sum(count * (count - 1) // 2 for count in tail_counts.values())


def has_allowed_tail_pattern(numbers) -> bool:
    return count_tail_pairs(numbers) <= 1


def is_quality_combination(numbers, min_ac_value: int = 4) -> bool:
    return (
        calculate_ac_value(numbers) >= min_ac_value
        and has_allowed_consecutive_pattern(numbers)
        and has_allowed_tail_pattern(numbers)
    )


def count_number_frequency(draws) -> dict[int, int]:
    counter = Counter(number for draw in draws for number in draw.numbers)
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))
