import json
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table
from z3 import (
    ArithRef,
    If,
    Int,
    IntVal,
    ModelRef,
    Optimize,
    Or,
    Solver,
    Sum,
    sat,
)


HUTS_FILE = "huts.json"
NUMBER_OF_DAYS: int = 5  # days
DAILY_TARGET_KM: int = 25  # km per day
NUMBER_OF_PLANS_TO_SHOW: int = 3  # number of top plans to show when running the script
HALF_DAY_FINISH: bool = True  # if True, the last day targets half the daily distance


@dataclass
class DayPlan:
    day: int
    from_hut: str
    to_hut: str
    distance: int
    deviation: int


def _check_huts(huts: dict[str, int]) -> None:
    if len(huts) < 2:
        raise ValueError("Need at least a start and a finish hut.")
    km = list(huts.values())
    if km[0] != 0:
        raise ValueError("The first hut must be at km 0 (the trailhead).")
    if any(km[i] >= km[i + 1] for i in range(len(km) - 1)):
        raise ValueError("Hut distances must be strictly increasing.")


def _check_n_days(n_days: int, huts: dict[str, int]) -> None:
    if n_days < 1:
        raise ValueError("n_days must be at least 1.")
    if n_days > len(huts) - 1:
        raise ValueError(
            f"n_days ({n_days}) exceeds the number of possible stops ({len(huts) - 1})."
        )
    total_km = list(huts.values())[-1]
    if total_km / n_days < 1:
        raise ValueError(
            f"The trail is only {total_km} km over {n_days} days — "
            "that's less than 1 km/day. Reduce the number of days or use a longer trail."
        )


def _check_target_km(target_km: int) -> None:
    if target_km <= 0:
        raise ValueError("target_km must be a positive number.")


def _hut_pos(hut_km: list[int], idx: ArithRef) -> ArithRef:
    """Z3 expression for the km position of hut idx."""
    expr: ArithRef = IntVal(hut_km[-1])
    for i in range(len(hut_km) - 2, -1, -1):
        expr = If(idx == i, hut_km[i], expr)
    return expr


def _add_constraints(
    context: Optimize | Solver,
    stops: list[ArithRef],
    hut_km: list[int],
    n_days: int,
    target_km: int,
    half_day_finish: bool = False,
) -> list[ArithRef]:
    """Add all routing and deviation constraints to context. Returns the deviation variables."""
    for d in range(n_days):
        context.add(stops[d] >= 0, stops[d] < len(hut_km))
    context.add(stops[0] >= 1)
    context.add(stops[-1] == len(hut_km) - 1)
    for d in range(1, n_days):
        context.add(stops[d] > stops[d - 1])
    deviations: list[ArithRef] = []
    for d in range(n_days):
        day_dist = (
            _hut_pos(hut_km, stops[0]) - hut_km[0]
            if d == 0
            else _hut_pos(hut_km, stops[d]) - _hut_pos(hut_km, stops[d - 1])
        )
        effective_target = (
            target_km // 2 if half_day_finish and d == n_days - 1 else target_km
        )
        dev = Int(f"dev_{d}")
        context.add(dev >= day_dist - effective_target)
        context.add(dev >= effective_target - day_dist)
        deviations.append(dev)
    return deviations


def _extract_plan(
    model: ModelRef,
    stops: list[ArithRef],
    deviations: list[ArithRef],
    hut_names: list[str],
    hut_km: list[int],
) -> list[DayPlan]:
    """Build a DayPlan list from a Z3 model."""
    plan: list[DayPlan] = []
    prev_km = hut_km[0]
    prev_name = hut_names[0]
    for d, stop in enumerate(stops):
        idx = model[stop].as_long()
        curr_km = hut_km[idx]
        curr_name = hut_names[idx]
        plan.append(
            DayPlan(
                day=d + 1,
                from_hut=prev_name,
                to_hut=curr_name,
                distance=curr_km - prev_km,
                deviation=model[deviations[d]].as_long(),
            )
        )
        prev_km = curr_km
        prev_name = curr_name
    return plan


def solve(
    huts: dict[str, int],
    n_days: int,
    target_km: int,
    number_of_plans: int,
    half_day_finish: bool = False,
) -> list[list[DayPlan]]:
    """Return the top n_plans plans ordered by total deviation (best first).

    Plans are not required to share the same cost; each successive plan
    is the next best distinct stop assignment.
    If half_day_finish is True, the last day targets half the daily distance.
    """
    if number_of_plans < 1:
        raise ValueError("n_plans must be at least 1.")
    _check_huts(huts)
    _check_n_days(n_days, huts)
    _check_target_km(target_km)

    hut_names: list[str] = list(huts.keys())
    hut_km: list[int] = list(huts.values())

    stops: list[ArithRef] = [Int(f"stop_{d}") for d in range(n_days)]
    opt = Optimize()
    deviations = _add_constraints(
        opt, stops, hut_km, n_days, target_km, half_day_finish
    )
    opt.minimize(Sum(deviations))

    results: list[list[DayPlan]] = []
    while len(results) < number_of_plans and opt.check() == sat:
        model = opt.model()
        stop_vals: list[int] = [model[s].as_long() for s in stops]
        results.append(_extract_plan(model, stops, deviations, hut_names, hut_km))
        # Block this combination; the optimizer will find the next best on the next call.
        opt.add(Or([stops[d] != stop_vals[d] for d in range(n_days)]))

    return results


def print_plan(
    plan: list[DayPlan],
    total_km: int,
    target_km: int,
    rank: int = 1,
    half_day_finish: bool = False,
) -> None:
    n_days = len(plan)
    half_day_note = f", last day targets {target_km // 2} km" if half_day_finish else ""
    title = (
        f"Optimal {n_days}-day hiking plan (target: {target_km} km/day{half_day_note})"
        if rank == 1
        else f"Option {rank}"
    )
    table = Table(title=title)
    table.add_column("Day")
    table.add_column("From")
    table.add_column("To")
    table.add_column("Distance")
    table.add_column("Target")
    table.add_column("Deviation")

    for day in plan:
        is_last = day.day == n_days
        day_target = target_km // 2 if half_day_finish and is_last else target_km
        table.add_row(
            str(day.day),
            day.from_hut,
            day.to_hut,
            f"{day.distance} km",
            f"{day_target} km",
            f"{day.deviation} km",
        )

    total_dev = sum(day.deviation for day in plan)
    table.add_section()
    table.add_row(
        "Total", "", "", f"{total_km} km", "", f"{total_dev} km", style="bold"
    )
    Console().print(table)


if __name__ == "__main__":
    # Huts on the trail with their distance from the start in km.
    huts_file = Path(__file__).parent / HUTS_FILE
    huts: dict[str, int] = json.loads(huts_file.read_text(encoding="utf-8"))

    plans = solve(
        huts,
        NUMBER_OF_DAYS,
        DAILY_TARGET_KM,
        number_of_plans=NUMBER_OF_PLANS_TO_SHOW,
        half_day_finish=HALF_DAY_FINISH,
    )
    if not plans:
        print("No solution found. Check your hut layout and constraints.")
    else:
        total_km = list(huts.values())[-1]
        for i, plan in enumerate(plans, start=1):
            print_plan(
                plan,
                total_km=total_km,
                target_km=DAILY_TARGET_KM,
                rank=i,
                half_day_finish=HALF_DAY_FINISH,
            )
