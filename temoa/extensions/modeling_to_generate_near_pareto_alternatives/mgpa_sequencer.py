"""
Performs top-level control over a Modeling to Generate near-Pareto-optimal Alternatives (MGPA) run

The Pareto front between two objective functions is computed as in a MOO run.  Then, around the
selected Pareto optimal solutions, alternatives are generated as in an MGA run, while both
objective functions are kept within a band around their Pareto optimal values.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from logging import getLogger
from typing import TYPE_CHECKING, Any

import pyomo.environ as pyo

from temoa.extensions.modeling_to_generate_alternatives.manager_factory import get_manager
from temoa.extensions.modeling_to_generate_alternatives.mga_constants import MgaAxis, MgaWeighting
from temoa.extensions.modeling_to_generate_alternatives.mga_sequencer import (
    MgaResult,
    MgaResultExtractor,
    MgaSequencer,
)
from temoa.extensions.modeling_to_generate_near_pareto_alternatives.pareto_points import (
    ALL_POINTS,
    parse_f2_values,
    parse_points,
    select_points,
)
from temoa.extensions.multi_objective_optimization.moo_sequencer import MooSequencer

if TYPE_CHECKING:
    from temoa.core.config import TemoaConfig
    from temoa.core.model import TemoaModel
    from temoa.extensions.modeling_to_generate_alternatives.vector_manager import VectorManager

logger = getLogger(__name__)

MGA_OPTIONS = (
    'axis',
    'axis_emission_commodities',
    'weighting',
    'hull_max_dimension',
    'iteration_limit',
    'time_limit_hrs',
)
WORKER_OPTIONS = {
    'MOO_num_workers': ('moo', 'num_workers'),
    'MOO_solver_options': ('moo', 'solver_options'),
    'MGA_num_workers': ('mga', 'num_workers'),
    'MGA_solver_options': ('mga', 'solver_options'),
}
RENAMED_OPTIONS = {
    'num_workers': 'MOO_num_workers',
    'solver_options': 'MOO_solver_options',
    'alternatives_num_workers': 'MGA_num_workers',
    'alternatives_solver_options': 'MGA_solver_options',
}


@dataclass(frozen=True)
class MgpaResult(MgaResult):
    values: list[tuple[str, float]] = field(default_factory=list)


@dataclass(frozen=True)
class MgpaResultExtractor(MgaResultExtractor):
    """Takes the objective values out of a solved alternative too"""

    labels: tuple[str, ...] = ()

    def __call__(self, model: TemoaModel) -> MgpaResult:
        result = super().__call__(model)
        moo_values: Any = model.moo_values
        return MgpaResult(
            name=result.name,
            hull_point=result.hull_point,
            results=result.results,
            values=[(label, float(pyo.value(moo_values[label]))) for label in self.labels],
        )


class MgpaAlternativesSequencer(MgaSequencer):
    """MGA exploration around one Pareto optimal solution"""

    objective_labels: list[str]

    def result_extractor(self, vector_manager: VectorManager) -> MgpaResultExtractor:
        extractor = super().result_extractor(vector_manager)
        return MgpaResultExtractor(
            extractor.poller, extractor.hull_terms, tuple(self.objective_labels)
        )

    def process_solve_results(self, result: MgaResult) -> None:
        super().process_solve_results(result)
        values = result.values if isinstance(result, MgpaResult) else []
        self.writer._insert_objective_results(values, iteration=int(result.name.split('-')[-1]))


class MgpaSequencer(MooSequencer):
    def __init__(self, config: TemoaConfig):
        inputs: dict[str, Any] = dict(config.mgpa_inputs or {})
        renamed = sorted(key for key in RENAMED_OPTIONS if key in inputs)
        if renamed:
            raise ValueError(
                f'MGPA options {renamed} are named '
                f'{[RENAMED_OPTIONS[key] for key in renamed]} in the [MGPA] section'
            )
        worker_inputs: dict[str, dict[str, Any]] = {'moo': {}, 'mga': {}}
        for key, (phase, option) in WORKER_OPTIONS.items():
            if key in inputs:
                worker_inputs[phase][option] = inputs[key]
        super().__init__(config, inputs={**inputs, **worker_inputs['moo']})

        self.slack1 = float(inputs.get('slack1', 0.01))
        self.slack2 = float(inputs.get('slack2', 0.01))
        if self.slack1 < 0 or self.slack2 < 0:
            raise ValueError('MGPA options slack1 and slack2 must be non-negative')
        self.f2_values = parse_f2_values(inputs.get('f2_values'))
        self.points = parse_points(inputs.get('points', [] if self.f2_values else ALL_POINTS))
        self.mga_inputs = {key: inputs[key] for key in MGA_OPTIONS if key in inputs}
        self.mga_inputs.setdefault('axis', MgaAxis.TECH_CATEGORY_ACTIVITY.name)
        self.mga_inputs.setdefault('weighting', MgaWeighting.HULL_EXPANSION.name)
        self.mga_inputs.setdefault('iteration_limit', 10)
        self.mga_inputs.update(worker_inputs['mga'])
        if (
            str(self.mga_inputs['axis']).upper() == MgaAxis.TECH_CATEGORY_EMISSION.name
            and 'axis_emission_commodities' not in inputs
        ):
            raise ValueError(
                'MGPA axis TECH_CATEGORY_EMISSION requires the "axis_emission_commodities" option '
                'in the [MGPA] section of the config file, ex:  axis_emission_commodities = ["co2"]'
            )
        logger.info(
            'Initialized MGPA sequencer with slack1: %s, slack2: %s, points: %s, f2 values: %s',
            self.slack1,
            self.slack2,
            self.points,
            self.f2_values,
        )

    def start(self) -> None:
        """Run the sequencer"""
        # ==== basic sequence ====
        # 1. Compute the Pareto front, as in a MOO run
        # 2. Compute the Pareto optimal solutions at the requested values of f2
        # 3. Select the Pareto optimal solutions to explore
        # 4. Generate alternatives around each of them, as in an MGA run
        instance = self.build_model()
        caps = self.find_caps(instance)
        outside = [v for v in self.f2_values if not caps[0] <= v <= caps[-1]]
        if outside:
            raise ValueError(
                f'MGPA f2_values {outside} are outside the range of {self.f2} on the Pareto front: '
                f'{caps[0]:0.6g} to {caps[-1]:0.6g}'
            )

        front = self.solve_points(instance, dict(enumerate(reversed(caps))))
        if not front:
            raise RuntimeError('No Pareto optimal solution was found.  Terminating MGPA run.')
        requested = self.solve_points(instance, dict(enumerate(self.f2_values, start=self.ncaps)))

        selected = {n: front[n] for n in select_points(self.points, front)} | requested
        f1_values = [f1 for f1, _f2 in front.values()]
        f1_range = max(f1_values) - min(f1_values)
        logger.info('MGPA explores the Pareto optimal solutions: %s', sorted(selected))
        for n, (f1_value, f2_value) in sorted(selected.items()):
            self._report(f'Generating alternatives around Pareto optimal solution {n}.')
            self.explore_point(
                instance,
                n,
                (f1_value, self.slack1 * (f1_range or abs(f1_value))),
                (f2_value, self.slack2 * (self.f2_range or abs(f2_value))),
            )

    def explore_point(
        self,
        instance: TemoaModel,
        n: int,
        f1_band: tuple[float, float],
        f2_band: tuple[float, float],
    ) -> None:
        model: Any = instance
        model.mgpa_f1_band = pyo.Constraint(
            expr=pyo.inequality(
                f1_band[0] - f1_band[1], model.moo_values[self.f1], f1_band[0] + f1_band[1]
            )
        )
        model.mgpa_f2_band = pyo.Constraint(
            expr=pyo.inequality(
                f2_band[0] - f2_band[1], model.moo_values[self.f2], f2_band[0] + f2_band[1]
            )
        )
        logger.info(
            'MGPA solution %d:  %s within %0.6g of %0.6g, %s within %0.6g of %0.6g',
            n,
            self.f1,
            f1_band[1],
            f1_band[0],
            self.f2,
            f2_band[1],
            f2_band[0],
        )

        point_config = copy.copy(self.config)
        point_config.scenario = f'{self.config.scenario}-{n}'
        point_config.mga_inputs = self.mga_inputs
        point_config.output_path = self.config.output_path / f'mgpa_solution_{n}'
        point_config.output_path.mkdir(exist_ok=True)
        instance.name = self.config.scenario
        sequencer = MgpaAlternativesSequencer(point_config, clear_scenario=False)
        sequencer.objective_labels = self.labels
        try:
            vector_manager = get_manager(
                axis=sequencer.mga_axis,
                model=instance,
                weighting=sequencer.mga_weighting,
                con=sequencer.con,
                optimal_cost=f1_band[0],
                cost_relaxation=self.slack1,
                config=point_config,
            )
            sequencer.explore(vector_manager)
        finally:
            sequencer.writer.close()
            sequencer.con.close()
            instance.del_component(model.mgpa_f1_band)
            instance.del_component(model.mgpa_f2_band)
