import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from temoa._internal.temoa_sequencer import TemoaSequencer
from temoa.core.config import TemoaConfig
from temoa.core.modes import TemoaMode
from temoa.extensions.modeling_to_generate_near_pareto_alternatives.pareto_points import (
    elbow_point,
    parse_f2_values,
    parse_points,
    select_points,
)

TESTING_OUTPUTS = Path(__file__).parent / 'testing_outputs'
OUTPUT_TABLES = (
    'output_cost',
    'output_emission',
    'output_flow_out',
    'output_net_capacity',
    'output_objective',
)


def run_mgpa(tmp_path: Path, mgpa_inputs: dict[str, Any]) -> dict[str, dict[str, float]]:
    db = tmp_path / 'utopia.sqlite'
    shutil.copy(TESTING_OUTPUTS / 'utopia.sqlite', db)
    config = TemoaConfig(
        scenario='mgpa',
        scenario_mode=TemoaMode.MGPA,
        input_database=db,
        output_database=db,
        output_path=tmp_path,
        solver='appsi_highs',
        time_sequencing='seasonal_timeslices',
        source_trace=True,
        silent=True,
        MGPA={'f1': 'cost', 'f2': 'emission', 'emission_commodities': ['co2'], **mgpa_inputs},
    )
    TemoaSequencer(config=config).start()
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            'SELECT scenario, objective_name, total_system_cost FROM output_objective '
            "WHERE scenario LIKE 'mgpa-%'"
        ).fetchall()
        for table in OUTPUT_TABLES:
            written = {
                row[0]
                for row in con.execute(
                    f"SELECT DISTINCT scenario FROM {table} WHERE scenario LIKE 'mgpa-%'"
                )
            }
            assert written == {row[0] for row in rows}, table
    finally:
        con.close()
    res: dict[str, dict[str, float]] = {}
    for scenario, name, val in rows:
        res.setdefault(scenario, {})[name] = val
    return res


def test_elbow_point() -> None:
    front = {0: (100.0, 0.0), 1: (40.0, 2.5), 2: (20.0, 5.0), 3: (10.0, 7.5), 4: (0.0, 10.0)}
    assert elbow_point(front) == 1
    assert elbow_point({0: (5.0, 1.0), 1: (5.0, 1.0)}) == 0


def test_point_options() -> None:
    front = {0: (3.0, 0.0), 1: (1.0, 1.0), 2: (0.0, 2.0)}
    assert select_points(parse_points('All'), front) == [0, 1, 2]
    assert select_points(parse_points('elbow'), front) == [1]
    assert select_points(parse_points([2, 0, 2]), front) == [0, 2]
    assert parse_points(1) == [1]
    assert parse_f2_values(None) == []
    assert parse_f2_values(1) == [1.0]
    assert parse_f2_values([0.5, 2]) == [0.5, 2.0]
    for bad in ('knee', 1.5, ['elbow'], True):
        with pytest.raises(ValueError, match='points'):
            parse_points(bad)
    with pytest.raises(ValueError, match='f2_values'):
        parse_f2_values(['a'])
    with pytest.raises(ValueError, match='not solutions of the Pareto front'):
        select_points([5], front)


def test_alternatives_around_the_elbow(tmp_path: Path) -> None:
    inputs = {
        'ncaps': 4,
        'points': 'elbow',
        'slack1': 0.05,
        'slack2': 0.1,
        'iteration_limit': 3,
        'MOO_num_workers': 2,
        'MGA_num_workers': 2,
        'MGA_solver_options': {'threads': 1},
    }
    res = run_mgpa(tmp_path, inputs)
    front = {n: (res[f'mgpa-{n}']['cost'], res[f'mgpa-{n}']['emission']) for n in range(4)}
    elbow = elbow_point(front)
    assert set(res) == {f'mgpa-{n}' for n in range(4)} | {f'mgpa-{elbow}-{k}' for k in (1, 2, 3)}
    f1_slack = 0.05 * (front[3][0] - front[0][0])
    f2_slack = 0.1 * (front[0][1] - front[3][1])
    for k in (1, 2, 3):
        point = res[f'mgpa-{elbow}-{k}']
        assert point['cost'] == pytest.approx(front[elbow][0], abs=f1_slack * (1 + 1e-6))
        assert point['emission'] == pytest.approx(front[elbow][1], abs=f2_slack * (1 + 1e-6))


def test_alternatives_at_a_value_of_f2(tmp_path: Path) -> None:
    inputs = {
        'ncaps': 3,
        'f2_values': [150.0],
        'slack1': 0.02,
        'slack2': 0.02,
        'iteration_limit': 2,
        'axis': 'tech_category_emission',
        'axis_emission_commodities': ['co2'],
    }
    res = run_mgpa(tmp_path, inputs)
    assert set(res) == {f'mgpa-{n}' for n in range(4)} | {'mgpa-3-1', 'mgpa-3-2'}
    assert res['mgpa-3']['emission'] == pytest.approx(150.0)
    f2_slack = 0.02 * (res['mgpa-0']['emission'] - res['mgpa-2']['emission'])
    for k in (1, 2):
        assert res[f'mgpa-3-{k}']['emission'] == pytest.approx(150.0, abs=f2_slack * (1 + 1e-6))


@pytest.mark.parametrize(
    ('mgpa_inputs', 'message'),
    [
        ({'slack1': -0.1}, 'slack1 and slack2 must be non-negative'),
        ({'points': 'knee'}, 'Invalid MGPA option points'),
        ({'ncaps': 3, 'points': [7]}, 'not solutions of the Pareto front'),
        ({'ncaps': 3, 'f2_values': [1e9]}, 'outside the range'),
        ({'axis': 'tech_category_emission'}, 'requires the "axis_emission_commodities" option'),
        ({'num_workers': 2}, r"\['MOO_num_workers'\]"),
    ],
)
def test_invalid_options(tmp_path: Path, mgpa_inputs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        run_mgpa(tmp_path, mgpa_inputs)
