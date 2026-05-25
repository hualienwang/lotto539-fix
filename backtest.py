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
        draw
        for draw in ordered_draws
        if config.test_from is None or draw.draw_date >= config.test_from
    ]
    if not test_draws:
        raise ValueError("Backtest test window is empty")

    predictions = []
    rng = random.Random(config.seed)
    for draw in test_draws:
        prior_draws = [
            candidate for candidate in ordered_draws if candidate.draw_date < draw.draw_date
        ]
        if config.train_before is not None:
            training_draws = [
                candidate
                for candidate in prior_draws
                if candidate.draw_date < config.train_before
            ]
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
    estimated_payout = sum(
        config.payouts[prediction.hit_count] for prediction in predictions
    )
    return BacktestResult(
        predictions=predictions,
        hit_distribution=hit_distribution,
        average_hits=sum(prediction.hit_count for prediction in predictions)
        / len(predictions),
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
    parser.add_argument(
        "--strategy",
        choices=["random", "frequency", "recent-frequency"],
        default="frequency",
    )
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
