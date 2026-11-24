"""
The solver options and workers of Monte Carlo and Method of Morris read from the config file,
which takes precedence over the extension options files.
"""

import shutil
from pathlib import Path
from typing import Any

from temoa.core.config import TemoaConfig
from temoa.core.modes import TemoaMode
from temoa.extensions.method_of_morris.morris_sequencer import MorrisSequencer
from temoa.extensions.monte_carlo.mc_sequencer import MCSequencer

UTOPIA_DB = Path(__file__).parent / 'testing_outputs' / 'utopia.sqlite'


def _config(tmp_path: Path, mode: TemoaMode, **sections: Any) -> TemoaConfig:
    db = tmp_path / 'utopia.sqlite'
    shutil.copy(UTOPIA_DB, db)
    return TemoaConfig(
        scenario='options',
        scenario_mode=mode,
        input_database=db,
        output_database=db,
        output_path=tmp_path,
        solver={'name': 'appsi_highs', 'options': {'threads': 8, 'time_limit': 100}},
        time_sequencing='seasonal_timeslices',
        silent=True,
        **sections,
    )


def test_monte_carlo_options_from_config(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        TemoaMode.MONTE_CARLO,
        monte_carlo={'num_workers': 3, 'solver_options': {'threads': 2}},
    )
    sequencer = MCSequencer(config)
    assert sequencer.num_workers == 3
    assert sequencer.worker_solver_options['threads'] == 2
    assert sequencer.worker_solver_options['time_limit'] == 100


def test_monte_carlo_options_file(tmp_path: Path) -> None:
    options_file = tmp_path / 'mc_options.toml'
    options_file.write_text('num_workers = 5\n\n[appsi_highs]\nthreads = 1\nmip_rel_gap = 0.5\n')
    config = _config(
        tmp_path, TemoaMode.MONTE_CARLO, monte_carlo={'solver_options': 'mc_options.toml'}
    )
    config.config_file = tmp_path / 'config.toml'
    sequencer = MCSequencer(config)
    assert sequencer.num_workers == 5
    assert sequencer.worker_solver_options['threads'] == 8
    assert sequencer.worker_solver_options['mip_rel_gap'] == 0.5


def test_morris_options_from_config(tmp_path: Path) -> None:
    config = _config(
        tmp_path, TemoaMode.METHOD_OF_MORRIS, morris={'solver_options': {'threads': 1}}
    )
    sequencer = MorrisSequencer(config)
    try:
        assert sequencer.solver_options['threads'] == 1
        assert sequencer.solver_options['time_limit'] == 100
    finally:
        sequencer.con.close()
