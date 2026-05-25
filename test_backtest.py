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
        Draw("4", date(2025, 1, 2), (5, 7, 8, 9, 10), 0),
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
