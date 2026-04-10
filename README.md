# hiking-planner

Plan the optimal overnight stops on a long-distance hike using an [SMT](https://en.wikipedia.org/wiki/Satisfiability_modulo_theories) solver ([Z3](https://github.com/Z3Prover/z3)).

Given a trail defined as an ordered list of huts with their distances from the trailhead, the planner finds the stop sequence that minimises the total deviation from a chosen daily-distance target. It can return multiple ranked alternatives and optionally target a shorter last day (e.g. half-distance finish).

## Features

- **Optimal planning** — uses Z3's `Optimize` to minimise total deviation from the daily target
- **Multiple alternatives** — enumerate the N best distinct stop sequences
- **Half-day finish** — optionally halve the target for the last day
- **Rich terminal output** — colour-coded tables via [Rich](https://github.com/Textualize/rich)
- **Externally configured trail** — hut data lives in a JSON file, no code changes needed to try a new trail

## Requirements

- Python 3.12+
- [Poetry](https://python-poetry.org/) (dependency management)

## Installation

```bash
git clone https://github.com/bewagner/hiking-planner.git
cd hiking-planner
poetry install
```

## Trail data

The trail is described in a JSON file mapping hut names to their cumulative distance from the trailhead (in km).  The first entry must be `0`.  Edit or replace `huts.json` to model your own trail:

```json
{
    "Trailhead": 0,
    "First Hut": 18,
    "Second Hut": 35,
    "Summit Lodge": 52
}
```

Point `HUTS_FILE` in `hiking_planner.py` at your file.

## Usage

Adjust the constants at the top of `hiking_planner.py`:

| Constant | Default | Description |
|---|---|---|
| `HUTS_FILE` | `"huts.json"` | Path to the trail JSON (relative to the script) |
| `NUMBER_OF_DAYS` | `5` | Number of hiking days |
| `DAILY_TARGET_KM` | `25` | Target distance per day (km) |
| `NUMBER_OF_PLANS_TO_SHOW` | `3` | How many ranked alternatives to display |
| `HALF_DAY_FINISH` | `True` | If `True`, the last day targets half the daily distance |

Then run:

```bash
poetry run python hiking_planner.py
```

The solver prints a ranked table for each plan, showing per-day distance, target, and deviation from the target.

### Using the API directly

```python
from hiking_planner import solve

huts = {
    "Trailhead": 0,
    "Hut A": 18,
    "Hut B": 35,
    "Summit Lodge": 52,
}

plans = solve(huts, n_days=3, target_km=18, number_of_plans=3, half_day_finish=True)
for plan in plans:
    for day in plan:
        print(day)
```

`solve()` returns a `list[list[DayPlan]]` ordered by total deviation (best first).  Each `DayPlan` has `day`, `from_hut`, `to_hut`, `distance`, and `deviation` fields.

## Development

```bash
# Run the test suite
poetry run pytest

# Run linting and formatting checks
poetry run pre-commit run --all-files
```

Pre-commit hooks (ruff lint + ruff-format) run automatically on every commit once installed:

```bash
poetry run pre-commit install
```

