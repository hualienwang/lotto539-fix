# Lotto 539 Backtesting Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a testable Lotto 539 analysis foundation with date-indexed storage, reusable draw/statistics helpers, and baseline backtesting.

**Architecture:** Keep the crawler stable and add focused modules beside it. `lotto_analysis.py` owns normalized draw loading and pure statistics helpers; `backtest.py` owns strategy generation, metrics, ROI estimation, and CLI output. Tests use small temporary SQLite databases and pure functions so behavior is cheap to verify.

**Tech Stack:** Python 3, SQLite, argparse, dataclasses, pytest.

---

## File Structure

- Modify `fetch_lotto539_history.py`: create an index on `history."開獎日"` when saving history.
- Create `lotto_analysis.py`: define `Draw`, parsing helpers, SQLite loading, draw summaries, and frequency counts.
- Create `backtest.py`: define baseline strategies, backtest result aggregation, ROI estimation, and a CLI.
- Modify `test_fetch_lotto539_history.py`: assert `save_history()` creates the draw-date index.
- Create `test_lotto_analysis.py`: cover date parsing, number parsing, summaries, loading, and frequency tie-breaking.
- Create `test_backtest.py`: cover deterministic strategies, metrics, ROI, empty-window validation, and random seed behavior.

### Task 1: Database Draw-Date Index

**Files:**
- Modify: `fetch_lotto539_history.py`
- Modify: `test_fetch_lotto539_history.py`

- [ ] **Step 1: Write the failing test**

Add this test to `test_fetch_lotto539_history.py`:

```python
def test_save_history_creates_draw_date_index(tmp_path):
    db_path = tmp_path / "lotto-539.db"
    record = {
        "期別": "115000126",
        "開獎日": "115/05/23",
        "大小順序": "06 15 16 24 38",
        "頭獎中獎注數": 1,
    }

    save_history(db_path, [record])

    with sqlite3.connect(db_path) as conn:
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' ORDER BY name"
        ).fetchall()

    assert ("idx_history_draw_date",) in indexes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_fetch_lotto539_history.py::test_save_history_creates_draw_date_index -v`

Expected: FAIL because `idx_history_draw_date` is missing.

- [ ] **Step 3: Write minimal implementation**

In `save_history()` after `CREATE TABLE IF NOT EXISTS history (...)`, add:

```python
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_history_draw_date ON history ("開獎日")'
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_fetch_lotto539_history.py::test_save_history_creates_draw_date_index -v`

Expected: PASS.

### Task 2: Analysis Module Parsing and Features

**Files:**
- Create: `lotto_analysis.py`
- Create: `test_lotto_analysis.py`

- [ ] **Step 1: Write failing tests**

Create `test_lotto_analysis.py` with:

```python
from datetime import date
import sqlite3

import pytest

from lotto_analysis import (
    Draw,
    count_number_frequency,
    load_draws,
    parse_numbers,
    parse_roc_date,
    summarize_draw,
)


def test_parse_roc_date_converts_taiwan_year_to_gregorian_date():
    assert parse_roc_date("115/05/23") == date(2026, 5, 23)


@pytest.mark.parametrize("value", ["", "2026-05-23", "115/13/01", "abc/05/23"])
def test_parse_roc_date_rejects_invalid_values(value):
    with pytest.raises(ValueError, match=value or "empty"):
        parse_roc_date(value)


def test_parse_numbers_returns_sorted_tuple_of_five_unique_numbers():
    assert parse_numbers("06 15 16 24 38") == (6, 15, 16, 24, 38)


@pytest.mark.parametrize("value", ["01 02 03 04", "01 02 03 04 04", "00 02 03 04 05", "01 02 03 04 40"])
def test_parse_numbers_rejects_invalid_values(value):
    with pytest.raises(ValueError, match=value):
        parse_numbers(value)


def test_summarize_draw_returns_basic_features():
    draw = Draw(issue="115000126", draw_date=date(2026, 5, 23), numbers=(6, 15, 16, 24, 38), jackpot_winners=1)

    assert summarize_draw(draw) == {
        "issue": "115000126",
        "draw_date": date(2026, 5, 23),
        "sum": 99,
        "odd_count": 1,
        "even_count": 4,
        "tails": (4, 5, 6, 6, 8),
    }


def test_count_number_frequency_counts_numbers_and_breaks_ties_by_number():
    draws = [
        Draw("1", date(2026, 1, 1), (1, 2, 3, 4, 5), 0),
        Draw("2", date(2026, 1, 2), (1, 2, 6, 7, 8), 0),
    ]

    assert list(count_number_frequency(draws).items()) == [
        (1, 2),
        (2, 2),
        (3, 1),
        (4, 1),
        (5, 1),
        (6, 1),
        (7, 1),
        (8, 1),
    ]


def test_load_draws_reads_sqlite_history_in_chronological_order(tmp_path):
    db_path = tmp_path / "lotto-539.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            '''
            CREATE TABLE history (
                "期別" TEXT PRIMARY KEY,
                "開獎日" TEXT NOT NULL,
                "大小順序" TEXT NOT NULL,
                "頭獎中獎注數" INTEGER NOT NULL
            )
            '''
        )
        conn.executemany(
            'INSERT INTO history ("期別", "開獎日", "大小順序", "頭獎中獎注數") VALUES (?, ?, ?, ?)',
            [
                ("115000002", "115/01/02", "06 07 08 09 10", 1),
                ("115000001", "115/01/01", "01 02 03 04 05", 0),
            ],
        )

    assert load_draws(db_path) == [
        Draw("115000001", date(2026, 1, 1), (1, 2, 3, 4, 5), 0),
        Draw("115000002", date(2026, 1, 2), (6, 7, 8, 9, 10), 1),
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest test_lotto_analysis.py -v`

Expected: FAIL because `lotto_analysis` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `lotto_analysis.py`:

```python
from collections import Counter
from dataclasses import dataclass
from datetime import date
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
    if len(numbers) != 5 or len(set(numbers)) != 5 or any(number < 1 or number > 39 for number in numbers):
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


def count_number_frequency(draws) -> dict[int, int]:
    counter = Counter(number for draw in draws for number in draw.numbers)
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest test_lotto_analysis.py -v`

Expected: PASS.

### Task 3: Backtest Strategies and Metrics

**Files:**
- Create: `backtest.py`
- Create: `test_backtest.py`

- [ ] **Step 1: Write failing tests**

Create `test_backtest.py` with:

```python
from datetime import date

import pytest

from backtest import (
    DEFAULT_PAYOUTS,
    BacktestConfig,
    choose_frequency_numbers,
    choose_random_numbers,
    run_backtest,
)
from lotto_analysis import Draw


def test_choose_frequency_numbers_uses_highest_counts_with_number_tie_breaker():
    training_draws = [
        Draw("1", date(2026, 1, 1), (1, 2, 3, 4, 5), 0),
        Draw("2", date(2026, 1, 2), (1, 2, 6, 7, 8), 0),
        Draw("3", date(2026, 1, 3), (1, 9, 10, 11, 12), 0),
    ]

    assert choose_frequency_numbers(training_draws) == (1, 2, 3, 4, 5)


def test_choose_random_numbers_is_reproducible_with_seed():
    first = choose_random_numbers(seed=539)
    second = choose_random_numbers(seed=539)

    assert first == second
    assert len(first) == 5
    assert len(set(first)) == 5
    assert all(1 <= number <= 39 for number in first)


def test_run_backtest_reports_hit_distribution_and_estimated_roi():
    draws = [
        Draw("1", date(2024, 12, 30), (1, 2, 3, 4, 5), 0),
        Draw("2", date(2024, 12, 31), (1, 2, 6, 7, 8), 0),
        Draw("3", date(2025, 1, 1), (1, 2, 3, 9, 10), 0),
        Draw("4", date(2025, 1, 2), (6, 7, 8, 9, 10), 0),
    ]
    config = BacktestConfig(
        strategy="frequency",
        train_before=date(2025, 1, 1),
        test_from=date(2025, 1, 1),
        ticket_cost=50,
        payouts={0: 0, 1: 0, 2: 50, 3: 300, 4: 20000, 5: 8000000},
    )

    result = run_backtest(draws, config)

    assert result.total_draws == 2
    assert result.hit_distribution == {0: 0, 1: 1, 2: 0, 3: 1, 4: 0, 5: 0}
    assert result.average_hits == 2.0
    assert result.total_cost == 100
    assert result.estimated_payout == 300
    assert result.estimated_roi == 2.0
    assert result.predictions[0].predicted_numbers == (1, 2, 3, 4, 5)


def test_recent_frequency_uses_only_draws_before_target_date():
    draws = [
        Draw("1", date(2025, 1, 1), (1, 2, 3, 4, 5), 0),
        Draw("2", date(2025, 1, 2), (1, 2, 3, 6, 7), 0),
        Draw("3", date(2025, 1, 3), (30, 31, 32, 33, 34), 0),
    ]
    config = BacktestConfig(
        strategy="recent-frequency",
        test_from=date(2025, 1, 2),
        recent_window=1,
        payouts=DEFAULT_PAYOUTS,
    )

    result = run_backtest(draws, config)

    assert result.predictions[0].predicted_numbers == (1, 2, 3, 4, 5)
    assert result.predictions[1].predicted_numbers == (1, 2, 3, 6, 7)


def test_run_backtest_rejects_empty_test_window():
    config = BacktestConfig(strategy="frequency", test_from=date(2025, 1, 1))

    with pytest.raises(ValueError, match="test window is empty"):
        run_backtest([], config)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest test_backtest.py -v`

Expected: FAIL because `backtest` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `backtest.py`:

```python
import argparse
from dataclasses import dataclass, field
from datetime import date
import random
from pathlib import Path

from lotto_analysis import Draw, count_number_frequency, load_draws


DEFAULT_PAYOUTS = {0: 0, 1: 0, 2: 50, 3: 300, 4: 20000, 5: 8000000}


@dataclass(frozen=True)
class BacktestConfig:
    strategy: str
    train_before: date | None = None
    test_from: date | None = None
    recent_window: int = 20
    seed: int | None = None
    ticket_cost: int = 50
    payouts: dict[int, int] = field(default_factory=lambda: dict(DEFAULT_PAYOUTS))


@dataclass(frozen=True)
class PredictionResult:
    draw: Draw
    predicted_numbers: tuple[int, ...]
    hit_count: int


@dataclass(frozen=True)
class BacktestResult:
    predictions: list[PredictionResult]
    hit_distribution: dict[int, int]
    average_hits: float
    total_cost: int
    estimated_payout: int
    estimated_roi: float

    @property
    def total_draws(self) -> int:
        return len(self.predictions)


def choose_random_numbers(seed: int | None = None) -> tuple[int, ...]:
    rng = random.Random(seed)
    return tuple(sorted(rng.sample(range(1, 40), 5)))


def choose_frequency_numbers(draws: list[Draw]) -> tuple[int, ...]:
    frequency = count_number_frequency(draws)
    chosen = list(frequency.keys())[:5]
    if len(chosen) < 5:
        for number in range(1, 40):
            if number not in chosen:
                chosen.append(number)
            if len(chosen) == 5:
                break
    return tuple(sorted(chosen))


def run_backtest(draws: list[Draw], config: BacktestConfig) -> BacktestResult:
    ordered_draws = sorted(draws, key=lambda draw: (draw.draw_date, draw.issue))
    test_draws = [
        draw for draw in ordered_draws if config.test_from is None or draw.draw_date >= config.test_from
    ]
    if not test_draws:
        raise ValueError("Backtest test window is empty")

    predictions = []
    rng = random.Random(config.seed)
    for draw in test_draws:
        prior_draws = [candidate for candidate in ordered_draws if candidate.draw_date < draw.draw_date]
        if config.train_before is not None:
            training_draws = [candidate for candidate in prior_draws if candidate.draw_date < config.train_before]
        else:
            training_draws = prior_draws

        if config.strategy == "random":
            predicted = tuple(sorted(rng.sample(range(1, 40), 5)))
        elif config.strategy == "frequency":
            predicted = choose_frequency_numbers(training_draws)
        elif config.strategy == "recent-frequency":
            predicted = choose_frequency_numbers(prior_draws[-config.recent_window :])
        else:
            raise ValueError(f"Unknown strategy: {config.strategy}")

        hit_count = len(set(predicted) & set(draw.numbers))
        predictions.append(PredictionResult(draw, predicted, hit_count))

    hit_distribution = {hits: 0 for hits in range(6)}
    for prediction in predictions:
        hit_distribution[prediction.hit_count] += 1

    total_cost = len(predictions) * config.ticket_cost
    estimated_payout = sum(config.payouts[prediction.hit_count] for prediction in predictions)
    return BacktestResult(
        predictions=predictions,
        hit_distribution=hit_distribution,
        average_hits=sum(prediction.hit_count for prediction in predictions) / len(predictions),
        total_cost=total_cost,
        estimated_payout=estimated_payout,
        estimated_roi=(estimated_payout - total_cost) / total_cost,
    )


def parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def format_result(result: BacktestResult) -> str:
    lines = [
        f"Test draws: {result.total_draws}",
        f"Average hits: {result.average_hits:.3f}",
        "Hit distribution:",
    ]
    lines.extend(f"  {hits}: {count}" for hits, count in result.hit_distribution.items())
    lines.extend(
        [
            f"Total cost: {result.total_cost}",
            f"Estimated payout: {result.estimated_payout}",
            f"Estimated ROI: {result.estimated_roi:.3f}",
            "ROI is estimated with the configured payout table, not official draw payouts.",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Backtest Lotto 539 baseline strategies.")
    parser.add_argument("--db", default="lotto-539.db", help="SQLite database path")
    parser.add_argument("--strategy", choices=["random", "frequency", "recent-frequency"], default="frequency")
    parser.add_argument("--train-before", help="Training cutoff date in YYYY-MM-DD")
    parser.add_argument("--test-from", help="First test date in YYYY-MM-DD")
    parser.add_argument("--recent-window", type=int, default=20)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--ticket-cost", type=int, default=50)
    args = parser.parse_args()

    config = BacktestConfig(
        strategy=args.strategy,
        train_before=parse_iso_date(args.train_before),
        test_from=parse_iso_date(args.test_from),
        recent_window=args.recent_window,
        seed=args.seed,
        ticket_cost=args.ticket_cost,
    )
    result = run_backtest(load_draws(Path(args.db)), config)
    print(format_result(result))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest test_backtest.py -v`

Expected: PASS.

### Task 4: Full Verification and CLI Smoke Test

**Files:**
- Verify: all Python files

- [ ] **Step 1: Run the complete test suite**

Run: `pytest -v`

Expected: all tests pass.

- [ ] **Step 2: Run the CLI against the repository database**

Run: `python backtest.py --db lotto-539.db --strategy frequency --test-from 2026-05-01`

Expected: command exits 0 and prints `Test draws:`, `Average hits:`, `Hit distribution:`, and `Estimated ROI:`.

- [ ] **Step 3: Review git diff**

Run: `git diff -- fetch_lotto539_history.py lotto_analysis.py backtest.py test_fetch_lotto539_history.py test_lotto_analysis.py test_backtest.py`

Expected: diff only contains the planned implementation and tests.

- [ ] **Step 4: Commit implementation**

Run:

```bash
git add fetch_lotto539_history.py lotto_analysis.py backtest.py test_fetch_lotto539_history.py test_lotto_analysis.py test_backtest.py
git commit -m "feat: add lotto 539 backtesting foundation"
```
