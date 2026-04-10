import json
from pathlib import Path

import pytest

from hiking_planner import solve

# A small, simple trail
SIMPLE_HUTS = {
    "Start": 0,
    "Hut A": 20,
    "Hut B": 45,
    "Hut C": 70,
    "Finish": 100,
}

# (n_days, target_km) combinations exercised by the parametrized tests.
DAY_TARGET_CASES = [
    (3, 20),
    (4, 25),
    (5, 20),
    (6, 15),
]

_HUTS_FILE = Path(__file__).parent / "huts.json"


@pytest.fixture(scope="session")
def huts() -> dict[str, int]:
    return json.loads(_HUTS_FILE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_returns_correct_number_of_days(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=1)
    assert len(plans) == 1
    assert len(plans[0]) == n_days


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_day_numbers_are_sequential(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=1)
    assert [d.day for d in plans[0]] == list(range(1, n_days + 1))


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_starts_at_trailhead(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=1)
    assert plans[0][0].from_hut == list(huts.keys())[0]


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_ends_at_last_hut(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=1)
    assert plans[0][-1].to_hut == list(huts.keys())[-1]


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_total_distance_equals_trail_length(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=1)
    assert sum(d.distance for d in plans[0]) == list(huts.values())[-1]


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_each_day_moves_forward(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=1)
    assert all(d.distance > 0 for d in plans[0])


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_deviations_are_non_negative(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=1)
    assert all(d.deviation >= 0 for d in plans[0])


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_deviation_matches_distance(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=1)
    for d in plans[0]:
        assert d.deviation == abs(d.distance - target_km)


# --- solve() with a small custom trail ---


def test_solve_simple_trail_two_days():
    plans = solve(SIMPLE_HUTS, n_days=2, target_km=50, number_of_plans=1)
    assert len(plans) == 1
    plan = plans[0]
    assert len(plan) == 2
    assert plan[0].from_hut == "Start"
    assert plan[-1].to_hut == "Finish"
    assert sum(d.distance for d in plan) == 100


# --- multi-plan tests (number_of_plans > 1) ---


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_returns_at_most_requested_plans(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=3)
    assert len(plans) <= 3


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_plans_are_ordered_by_deviation(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=5)
    costs = [sum(d.deviation for d in plan) for plan in plans]
    assert costs == sorted(costs)


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_plans_are_distinct(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=5)
    stop_sequences = [tuple(d.to_hut for d in plan) for plan in plans]
    assert len(stop_sequences) == len(set(stop_sequences))


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_all_plans_cover_full_trail(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=3)
    total_km = list(huts.values())[-1]
    for plan in plans:
        assert sum(d.distance for d in plan) == total_km


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_best_plan_is_stable_across_counts(huts, n_days, target_km):
    plans_1 = solve(huts, n_days, target_km, number_of_plans=1)
    plans_3 = solve(huts, n_days, target_km, number_of_plans=3)
    # Both calls must agree on the minimum cost, even if they pick a different
    # plan when there are ties.
    best_cost_1 = sum(d.deviation for d in plans_1[0])
    best_cost_3 = sum(d.deviation for d in plans_3[0])
    assert best_cost_1 == best_cost_3


@pytest.mark.parametrize("n_days,target_km", DAY_TARGET_CASES)
def test_solve_each_plan_has_correct_day_count(huts, n_days, target_km):
    plans = solve(huts, n_days, target_km, number_of_plans=3)
    for plan in plans:
        assert len(plan) == n_days


def test_solve_returns_none_when_impossible():
    # More days than non-start huts is caught by the sanity check.
    tiny = {"Start": 0, "Only Hut": 30, "Finish": 60}
    with pytest.raises(ValueError):
        solve(tiny, n_days=5, target_km=10, number_of_plans=1)
