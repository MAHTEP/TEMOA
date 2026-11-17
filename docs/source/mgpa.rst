.. _mgpa:

Modeling to Generate near-Pareto-optimal Alternatives (MGPA)
============================================================

The MGPA extension combines Multi-Objective Optimization (:ref:`MOO <moo>`) with
Modeling to Generate Alternatives (:ref:`MGA <mga>`). It first computes the
Pareto front between two objective functions, and then explores alternative
solutions that are close to selected Pareto optimal solutions, i.e. solutions
in which both objective functions are only slightly worse (or better) than on
the Pareto front, while the energy system is as different as possible.

Method
------

#. The Pareto front between the objective functions :math:`f_1` and :math:`f_2`
   is computed exactly as in a MOO run, with ``ncaps`` caps on :math:`f_2`.
#. The Pareto optimal solutions to explore are selected: all of them, a subset,
   the elbow of the front, or the solutions at given values of :math:`f_2`.
#. Around each selected solution, with objective values :math:`f_1^*` and
   :math:`f_2^*`, alternatives are generated exactly as in an MGA run, with the
   cost relaxation of MGA replaced by a band on both objective functions:

   .. math::

      f_1^* - s_1 R_1 \le f_1 \le f_1^* + s_1 R_1
      \qquad
      f_2^* - s_2 R_2 \le f_2 \le f_2^* + s_2 R_2

   where :math:`s_1` and :math:`s_2` are the slacks (``slack1``, ``slack2``)
   and :math:`R_1` and :math:`R_2` are the ranges of the two objective functions
   over the Pareto front.

The slacks are fractions of the range of each objective function over the
Pareto front, and not of its value. In this way they have the same meaning at
every point of the front, also where an objective function is zero or negative.
If the front consists of a single solution (non-conflicting objective
functions), the slacks are fractions of the objective function values.

The lower bounds keep the alternatives close to the selected Pareto optimal
solution: without them, alternatives could slide along the front towards the
neighbouring solutions.

Configuration
-------------

To perform an MGPA run, set the ``scenario_mode`` to ``"MGPA"`` in your
configuration TOML file and provide an ``[MGPA]`` section:

.. code-block:: toml

   scenario_mode = "MGPA"

   [MGPA]
   f1 = "cost"
   f2 = "emission"
   ncaps = 11
   emission_commodities = ["co2"]
   points = "elbow"
   slack1 = 0.05
   slack2 = 0.05
   axis = "tech_category_capacity"
   iteration_limit = 20

MGPA requires the input and output databases to be the same.

Pareto front options
^^^^^^^^^^^^^^^^^^^^

``f1``, ``f2``, ``ncaps``, ``c``, ``emission_commodities`` and
``construction_input_commodities`` have the same meaning as in the ``[MOO]``
section (see :ref:`moo`). The built-in objective functions (``cost``,
``emission``, ``construction_input``) and the custom objective functions
defined in the MOO weight tables are all available.

Selection of the Pareto optimal solutions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **points**: The Pareto optimal solutions around which alternatives are
  generated:

  * ``"all"``: every solution of the front (default);
  * ``"elbow"``: the elbow of the front, detected automatically;
  * a list of solution indices, e.g. ``[0, 5, 10]``, where ``0`` is the
    solution with the highest cap on ``f2``, i.e. the lowest ``f1``.

* **f2_values**: A list of values of ``f2``, e.g. ``[150.0]``. For each of them
  the Pareto optimal solution with ``f2`` capped at that value is computed, in
  addition to the ``ncaps`` solutions of the front, and alternatives are
  generated around it. The values must lie within the range of ``f2`` on the
  front. When ``f2_values`` is specified and ``points`` is not, only these
  solutions are explored.

The elbow is the solution farthest from the straight line joining the two ends
of the front, after scaling both objective functions by their range. It is the
solution beyond which improving one objective function becomes markedly more
expensive in terms of the other.

Alternative generation options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **slack1**, **slack2**: The half-widths of the bands on ``f1`` and ``f2``, as
  fractions of their ranges over the Pareto front. Default: ``0.01``.
* **axis**: The quantity explored by the alternatives, by technology category:
  ``tech_category_activity`` (default), ``tech_category_capacity`` or
  ``tech_category_emission`` (see :ref:`mga`). Only the technologies with a
  category in the ``technology`` table are part of the exploration.
* **axis_emission_commodities**: The emission commodities of the
  ``tech_category_emission`` axis, e.g. ``["co2"]``. It is distinct from
  ``emission_commodities``, which defines the ``emission`` objective function.
* **weighting**: ``hull_expansion`` (default), as in MGA.
* **hull_max_dimension**: The largest number of categories in one convex hull,
  as in MGA. Default: ``8``.
* **iteration_limit**: The number of alternatives generated around each
  selected Pareto optimal solution. Default: ``10``.
* **time_limit_hrs**: The time limit for the generation of the alternatives
  around each selected solution. Default: ``12``.

The ``[MOO]`` and ``[MGA]`` sections are not read in an MGPA run: all the
options are taken from the ``[MGPA]`` section.

The flows of both the Pareto optimal solutions and the alternatives follow the
top-level ``flows_indexing`` option (see :ref:`flows-indexing`).

Parallel execution and solver options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Both the Pareto optimal solutions and the alternatives are solved in parallel
by worker processes:

* **MOO_num_workers**, **MOO_solver_options**: The workers solving the Pareto
  optimal solutions, as ``num_workers`` and ``solver_options`` in the ``[MOO]``
  section. Their fallback values are in ``MOO_solver_options.toml``.
* **MGA_num_workers**, **MGA_solver_options**: The workers solving the
  alternatives, as ``num_workers`` and ``solver_options`` in the ``[MGA]``
  section. Their fallback values are in ``MGA_solver_options.toml``.

The solver options are merged as in MOO and MGA runs: the ``options`` of the
``solver`` entry of the configuration file take precedence over the fallback
files, and the options above take precedence over both.

.. note::
   The alternatives are only bound by the bands on ``f1`` and ``f2``. When
   ``cost`` is neither of them, nothing limits the cost of the alternatives:
   they can be arbitrarily expensive, and some of the solves can be unbounded
   (e.g. when the capacity of a category is maximized). Unbounded solves are
   discarded and replaced, but they slow down the run. Including ``cost`` as
   one of the two objective functions avoids this.

Outputs
-------

* Each Pareto optimal solution is saved under the scenario name
  ``<scenario>-<n>``, as in a MOO run. The solutions computed at the
  ``f2_values`` are numbered after those of the front, starting from ``ncaps``.
* Each alternative is saved under the scenario name ``<scenario>-<n>-<k>``,
  where ``n`` is the Pareto optimal solution it belongs to and ``k`` ranges from
  ``1`` to ``iteration_limit``.

For every solution and alternative, the ``output_objective`` table reports the
values of the three built-in objective functions and of the custom objective
functions selected as ``f1`` or ``f2``. Capacities, flows, costs and emissions
are saved in the standard output tables. With ``save_storage_levels = true``,
the storage levels of every solution and alternative are saved too. With
``save_duals = true``, the duals of the Pareto optimal solutions are saved, as
in a MOO run; the alternatives have none, as in an MGA run.

The plot of the hull volume of each exploration is saved in the folder
``mgpa_solution_<n>`` of the output path.
