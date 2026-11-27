"""
Tests for the "flows_indexing" option, which selects whether flows are written to the flow tables
at the resolution of their variables, once a year, or per time slice.
"""

import contextlib
import shutil
import sqlite3
from collections import defaultdict
from collections.abc import Generator
from importlib import resources
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from temoa._internal.table_writer import FLOW_TABLES, TableWriter
from temoa._internal.temoa_sequencer import TemoaSequencer
from temoa.core.config import TemoaConfig
from temoa.core.flows_indexing import ANNUAL_TIME_SLICE, FlowsIndexing
from temoa.types.model_types import FI, FlowType

SCHEMA = resources.files('temoa.db_schema') / 'temoa_schema_v4.sql'
A = ANNUAL_TIME_SLICE

VALUE_COLUMNS = {
    'output_flow_out': 'flow',
    'output_flow_in': 'flow',
    'output_curtailment': 'curtailment',
}


def _fi(season: str, tod: str, tech: str = 'T1') -> FI:
    return FI(
        cast('Any', 'R1'),
        cast('Any', 2030),
        cast('Any', season),
        cast('Any', tod),
        cast('Any', 'fuel'),
        cast('Any', tech),
        cast('Any', 2020),
        cast('Any', 'elc'),
    )


def _make_writer(db: Path) -> TableWriter:
    config = SimpleNamespace(
        output_database=db,
        scenario='test',
        flows_indexing=FlowsIndexing.DEFAULT,
        output_threshold_capacity=None,
        output_threshold_activity=None,
        output_threshold_emission=None,
        output_threshold_cost=None,
    )
    tw = TableWriter(cast('TemoaConfig', config))
    tw.tech_sectors = {'T1': 'electric', 'T2': 'electric'}
    tw.flow_register = {
        _fi('summer', 'day'): {FlowType.OUT: 10.0, FlowType.IN: 20.0, FlowType.CURTAIL: 1.0},
        _fi('summer', 'night'): {FlowType.OUT: 5.0, FlowType.IN: 10.0, FlowType.FLEX: 2.0},
        _fi(A, A, 'T2'): {FlowType.OUT: 4.0, FlowType.IN: 8.0, FlowType.LOST: 4.0},
        _fi('winter', 'day', 'T2'): {FlowType.OUT: 2e-4},
    }
    return tw


@pytest.fixture
def writer(tmp_path: Path) -> Generator[TableWriter, None, None]:
    db = tmp_path / 'flows.sqlite'
    with contextlib.closing(sqlite3.connect(db)) as con:
        con.executescript(SCHEMA.read_text(encoding='utf-8'))
    tw = _make_writer(db)
    yield tw
    tw.close()


def _rows(tw: TableWriter, table: str, scenario: str) -> list[tuple[Any, ...]]:
    return tw.connection.execute(
        f'SELECT season, tod, tech, {VALUE_COLUMNS[table]} FROM {table} WHERE scenario = ? '
        'ORDER BY tech, season, tod',
        (scenario,),
    ).fetchall()


def test_flow_register_is_written_as_indexed(writer: TableWriter) -> None:
    writer.write_flow_tables(iteration=1)
    assert _rows(writer, 'output_flow_out', 'test-1') == [
        ('summer', 'day', 'T1', pytest.approx(10.0)),
        ('summer', 'night', 'T1', pytest.approx(5.0)),
        (A, A, 'T2', pytest.approx(4.0)),
    ]
    assert len(_rows(writer, 'output_flow_in', 'test-1')) == 3
    assert _rows(writer, 'output_curtailment', 'test-1') == [
        ('summer', 'day', 'T1', pytest.approx(1.0)),
        ('summer', 'night', 'T1', pytest.approx(2.0)),
    ]


def test_annual_rows_are_cleared(writer: TableWriter) -> None:
    writer.write_flow_tables(iteration=1)
    writer.clear_scenario()
    for table in FLOW_TABLES:
        assert writer.connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0


def _foreign_key_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {fk[3] for fk in con.execute(f'PRAGMA foreign_key_list({table})')}


def _add_time_slices(con: sqlite3.Connection) -> None:
    con.executemany(
        'INSERT INTO time_season (sequence, season, segment_fraction) VALUES (?, ?, 0.5)',
        [(1, 'summer'), (2, 'winter')],
    )
    con.executemany(
        'INSERT INTO time_of_day (sequence, tod) VALUES (?, ?)', [(1, 'day'), (2, 'night')]
    )
    con.commit()


def _time_slice_violations(con: sqlite3.Connection) -> list[tuple[Any, ...]]:
    return [
        v for v in con.execute('PRAGMA foreign_key_check') if v[2] in ('time_season', 'time_of_day')
    ]


def test_time_sliced_rows_keep_time_slice_foreign_keys(writer: TableWriter) -> None:
    _add_time_slices(writer.connection)
    writer.flow_register = {fi: flows for fi, flows in writer.flow_register.items() if fi.s != A}
    writer.write_flow_tables(iteration=1)
    for table in FLOW_TABLES:
        assert _foreign_key_columns(writer.connection, table) >= {'season', 'tod'}, table
    assert _time_slice_violations(writer.connection) == []


def test_annual_rows_drop_time_slice_foreign_keys(writer: TableWriter) -> None:
    """
    The season and tod foreign keys of a flow table are removed the first time annual rows are
    written to it, keeping its rows and its other foreign keys
    """
    con = writer.connection
    _add_time_slices(con)
    con.execute(
        'INSERT INTO output_flow_out (scenario, region, period, season, tod, input_comm, '
        "tech, vintage, output_comm, flow) VALUES ('old', 'R1', 2030, 'summer', 'day', "
        "'fuel', 'T1', 2020, 'elc', 3.0)"
    )
    con.commit()
    writer.write_flow_tables(iteration=1)
    for table in ('output_flow_out', 'output_flow_in'):
        columns = _foreign_key_columns(con, table)
        assert 'tech' in columns, f'{table} should keep its other foreign keys'
        assert not columns & {'season', 'tod'}, table
    assert _foreign_key_columns(con, 'output_curtailment') >= {'season', 'tod'}
    assert _rows(writer, 'output_flow_out', 'old') == [('summer', 'day', 'T1', 3.0)]
    assert len(_rows(writer, 'output_flow_out', 'test-1')) == 3
    assert _time_slice_violations(con) == []


def test_legacy_summary_table_is_tolerated(writer: TableWriter) -> None:
    """
    Databases from earlier versions hold an output_flow_out_summary table.  It should be left
    in place and never written, but stale rows for the scenario should be cleared.
    """
    con = writer.connection
    assert (
        con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name = 'output_flow_out_summary'"
        ).fetchone()[0]
        == 0
    ), 'the summary table should no longer be part of the schema'

    con.execute(
        'CREATE TABLE output_flow_out_summary (scenario TEXT, region TEXT, sector TEXT, '
        'period INTEGER, input_comm TEXT, tech TEXT, vintage INTEGER, output_comm TEXT, '
        'flow REAL)'
    )
    con.executemany(
        'INSERT INTO output_flow_out_summary (scenario, flow) VALUES (?, ?)',
        [('test-1', 1.0), ('other-1', 1.0)],
    )
    con.commit()

    writer.clear_scenario()
    writer.write_flow_tables(iteration=1)

    remaining = con.execute('SELECT scenario FROM output_flow_out_summary').fetchall()
    assert remaining == [('other-1',)]
    assert len(_rows(writer, 'output_flow_out', 'test-1')) == 3


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        ('default', FlowsIndexing.DEFAULT),
        ('annual', FlowsIndexing.ANNUAL),
        ('ANNUAL', FlowsIndexing.ANNUAL),
        (' Time_Sliced ', FlowsIndexing.TIME_SLICED),
        (FlowsIndexing.TIME_SLICED, FlowsIndexing.TIME_SLICED),
    ],
)
def test_parse_flows_indexing(raw: object, expected: FlowsIndexing) -> None:
    assert FlowsIndexing.parse(raw) is expected


def test_parse_flows_indexing_rejects_bad_value() -> None:
    with pytest.raises(ValueError, match='flows_indexing'):
        FlowsIndexing.parse('hourly')


SOLVED_CASES = ['config_materials.toml', 'config_emissions.toml']
SCENARIOS = {indexing: f'flows_{indexing.value}' for indexing in FlowsIndexing}


@pytest.fixture(scope='module', params=SOLVED_CASES)
def solved(request: Any, tmp_path_factory: Any) -> Generator[sqlite3.Connection, None, None]:
    """The same model solved once per flows_indexing choice, each as its own scenario"""
    tmp_path = tmp_path_factory.mktemp('flows_indexing')
    db: Path | None = None
    for indexing, scenario in SCENARIOS.items():
        config = TemoaConfig.build_config(
            config_file=Path(__file__).parent / 'testing_configs' / request.param,
            output_path=tmp_path,
            silent=True,
        )
        if db is None:
            db = tmp_path / Path(config.input_database).name
            shutil.copyfile(config.input_database, db)
        config.input_database = db
        config.output_database = db
        config.scenario = scenario
        config.flows_indexing = indexing
        TemoaSequencer(config=config).start()
    assert db is not None
    with contextlib.closing(sqlite3.connect(db)) as con:
        yield con


def _annual_techs(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute('SELECT tech FROM technology WHERE annual = 1')}


def _flow_rows(
    con: sqlite3.Connection, table: str, indexing: FlowsIndexing
) -> list[tuple[Any, ...]]:
    return con.execute(
        f'SELECT season, tod, input_comm, tech, output_comm, {VALUE_COLUMNS[table]} '
        f'FROM {table} WHERE scenario = ?',
        (SCENARIOS[indexing],),
    ).fetchall()


def _is_annual(season: str, tod: str) -> bool:
    if (season == A) != (tod == A):
        raise AssertionError(f'season {season} and tod {tod} should be annual together')
    return season == A


def test_default_indexing(solved: sqlite3.Connection) -> None:
    annual_techs = _annual_techs(solved)
    seen_annual = seen_sliced = False
    for table in FLOW_TABLES:
        for season, tod, i, t, o, _ in _flow_rows(solved, table, FlowsIndexing.DEFAULT):
            expected_annual = t in annual_techs or i is None or o is None
            assert _is_annual(season, tod) == expected_annual, (table, season, tod, i, t, o)
            seen_annual |= expected_annual
            seen_sliced |= not expected_annual
    assert seen_annual and seen_sliced


def test_annual_indexing(solved: sqlite3.Connection) -> None:
    for table in FLOW_TABLES:
        rows = _flow_rows(solved, table, FlowsIndexing.ANNUAL)
        assert all(_is_annual(season, tod) for season, tod, *_ in rows), table
    assert _flow_rows(solved, 'output_flow_out', FlowsIndexing.ANNUAL)


def test_time_sliced_indexing(solved: sqlite3.Connection) -> None:
    for table in FLOW_TABLES:
        rows = _flow_rows(solved, table, FlowsIndexing.TIME_SLICED)
        assert not any(_is_annual(season, tod) for season, tod, *_ in rows), table
    assert _flow_rows(solved, 'output_flow_out', FlowsIndexing.TIME_SLICED)


def test_yearly_totals_match(solved: sqlite3.Connection) -> None:
    """
    Each flow summed over its period is the same with any indexing, except for the time slices
    that per-slice results drop below the activity threshold
    """
    n_slices = solved.execute(
        'SELECT (SELECT COUNT(DISTINCT season) FROM time_season) * '
        '(SELECT COUNT(DISTINCT tod) FROM time_of_day)'
    ).fetchone()[0]
    for table in FLOW_TABLES:
        totals: dict[FlowsIndexing, dict[tuple[Any, ...], float]] = {}
        for indexing in FlowsIndexing:
            totals[indexing] = defaultdict(float)
            rows = solved.execute(
                f'SELECT region, period, input_comm, tech, vintage, output_comm, '
                f'{VALUE_COLUMNS[table]} FROM {table} WHERE scenario = ?',
                (SCENARIOS[indexing],),
            )
            for *key, val in rows:
                totals[indexing][tuple(key)] += val
        default = totals[FlowsIndexing.DEFAULT]
        for indexing in (FlowsIndexing.ANNUAL, FlowsIndexing.TIME_SLICED):
            other = totals[indexing]
            for key in default.keys() | other.keys():
                assert other.get(key, 0.0) == pytest.approx(
                    default.get(key, 0.0), rel=1e-6, abs=n_slices * 1e-3
                ), (table, indexing, key)
