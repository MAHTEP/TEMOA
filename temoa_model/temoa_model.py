#!/usr/bin/env python

"""
Tools for Energy Model Optimization and Analysis (Temoa): 
An open source framework for energy systems optimization modeling

Copyright (C) 2015,  NC State University

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

A complete copy of the GNU General Public License v2 (GPLv2) is available 
in LICENSE.txt.  Users uncompressing this from an archive may not have 
received this license file.  If not, see <http://www.gnu.org/licenses/>.
"""

from temoa_rules import *
from temoa_initialize import *
from temoa_run import *

import IPython


def temoa_create_model(name="Temoa"):
    """\
    Returns an abstract instance of Temoa -- Abstract because it needs
    to be populated with a "dot dat" file in order to create a specific model
    instantiation.
  """
    M = TemoaModel(name)

    # ---------------------------------------------------------------
    # Define sets. 
    # Sets are collections of items used to index parameters and variables
    # ---------------------------------------------------------------

    # Define time periods
    M.time_exist = Set(ordered=True) 
    M.time_future = Set(ordered=True)
    M.time_optimize = Set(ordered=True, initialize=init_set_time_optimize)
    # Define time period vintages to track capacity installation
    M.vintage_exist = Set(ordered=True, initialize=init_set_vintage_exist)
    M.vintage_optimize = Set(ordered=True, initialize=init_set_vintage_optimize)
    M.vintage_all = M.time_exist | M.time_optimize
    # Perform some basic validation on the specified time periods.
    M.validate_time = BuildAction(rule=validate_time)

    # Define the model time slices
    M.time_season = Set(ordered=True)
    M.time_of_day = Set(ordered=True)

    # Define regions
    M.regions = Set()
    # RegionalIndices is the set of all the possible combinations of interregional 
    # exhanges plus original region indices. If tech_exchange is empty, RegionalIndices =regions.
    M.RegionalIndices = Set(initialize=CreateRegionalIndices)

    # Define technology-related sets
    M.tech_resource = Set()
    M.tech_production = Set()
    M.tech_all = M.tech_resource | M.tech_production
    M.tech_imports = Set(within=M.tech_all)
    M.tech_exports = Set(within=M.tech_all)
    M.tech_domestic = Set(within=M.tech_all)
    M.tech_baseload = Set(within=M.tech_all)
    M.tech_storage = Set(within=M.tech_all)
    M.tech_reserve = Set(within=M.tech_all)
    M.tech_ramping = Set(within=M.tech_all)
    M.tech_capacity_min = Set(within=M.tech_all)
    M.tech_capacity_max = Set(within=M.tech_all)
    M.tech_curtailment = Set(within=M.tech_all)
    M.tech_flex = Set(within=M.tech_all)
    M.tech_exchange = Set(within=M.tech_all)
    M.groups = Set(dimen=1) # Define groups for technologies
    M.tech_groups = Set(within=M.tech_all) # Define techs used in groups
    M.tech_annual = Set(within=M.tech_all) # Define techs with constant output
    M.tech_variable = Set(within=M.tech_all) # Define techs for use with TechInputSplitAverage constraint, where techs have variable annual output but the user wishes to constrain them annually

    # Define commodity-related sets
    M.commodity_demand = Set()
    M.commodity_emissions = Set()
    M.commodities_e_moo = Set(within=M.commodity_emissions) # Used to define the emission commodities contributing to the emissions objective function
    M.commodity_physical = Set()
    M.commodity_material = Set()
    M.commodity_carrier = M.commodity_physical | M.commodity_demand | M.commodity_material
    M.commodity_all = M.commodity_carrier | M.commodity_emissions

    # Define sets for MGA weighting
    M.tech_mga = Set(within=M.tech_all)
    M.tech_ELC = Set(within=M.tech_all)
    M.tech_STG = Set(within=M.tech_all)
    M.tech_CCUS = Set(within=M.tech_all)
    M.tech_UPS = Set(within=M.tech_all)

    # ---------------------------------------------------------------
    # Define parameters.
    # In order to increase model efficiency, we use sparse
    # indexing of parameters, variables, and equations to prevent the
    # creation of indices for which no data exists. While basic model sets
    # are defined above, sparse index sets are defined below adjacent to the
    # appropriate parameter, variable, or constraint and all are initialized
    # in temoa_initialize.py.
    # Because the function calls that define the sparse index sets obscure the
    # sets utilized, we use a suffix that includes a one character name for each
    # set. Example: "_tv" indicates a set defined over "technology" and "vintage".
    # The complete index set is: psditvo, where p=period, s=season, d=day,
    # i=input commodity, t=technology, v=vintage, o=output commodity.
    # ---------------------------------------------------------------

    M.GlobalDiscountRate = Param()

    # Define time-related parameters
    M.PeriodLength = Param(M.time_optimize, initialize=ParamPeriodLength)
    M.SegFrac = Param(M.time_season, M.time_of_day)
    M.validate_SegFrac = BuildAction(rule=validate_SegFrac)

    # Define demand- and resource-related parameters
    M.DemandDefaultDistribution = Param(M.time_season, M.time_of_day, mutable=True)
    M.DemandSpecificDistribution = Param(
        M.regions, M.time_season, M.time_of_day, M.commodity_demand, mutable=True
    )

    M.Demand = Param(M.regions, M.time_optimize, M.commodity_demand)
    M.initialize_Demands = BuildAction(rule=CreateDemands)
    
    M.ResourceBound = Param(M.regions, M.time_optimize, M.commodity_physical)

    # Define technology performance parameters
    M.CapacityToActivity = Param(M.RegionalIndices, M.tech_all, default=1)
    
    M.ExistingCapacity = Param(M.RegionalIndices, M.tech_all, M.vintage_exist)

    M.Efficiency = Param(
        M.RegionalIndices, M.commodity_physical, M.tech_all, M.vintage_all, M.commodity_carrier
    )
    M.validate_UsedEfficiencyIndices = BuildAction(rule=CheckEfficiencyIndices)

    M.CapacityFactor_rtv = Set(dimen=3, initialize=CapacityFactorIndices)
    M.CapacityFactor = Param(M.CapacityFactor_rtv, default=1)

    M.CapacityFactor_rsdtv = Set(dimen=5, initialize=CapacityFactorProcessIndices)
    M.CapacityFactorProcess = Param(M.CapacityFactor_rsdtv, mutable=True)

    M.CapacityFactor_rsdt = Set(dimen=4, initialize=CapacityFactorTechIndices)
    M.CapacityFactorTech = Param(M.CapacityFactor_rsdt, default=1)

    M.initialize_CapacityFactors = BuildAction(rule=CreateCapacityFactors)

    M.LifetimeTech = Param(M.RegionalIndices, M.tech_all, default=40)
    M.LifetimeLoanTech = Param(M.RegionalIndices, M.tech_all, default=10)

    M.LifetimeProcess_rtv = Set(dimen=3, initialize=LifetimeProcessIndices)
    M.LifetimeProcess = Param(M.LifetimeProcess_rtv, mutable=True)

    M.LifetimeLoanProcess_rtv = Set(dimen=3, initialize=LifetimeLoanProcessIndices)
    M.LifetimeLoanProcess = Param(M.LifetimeLoanProcess_rtv, mutable=True)
    M.initialize_Lifetimes = BuildAction(rule=CreateLifetimes)

    M.TechInputSplit = Param(M.RegionalIndices, M.time_optimize, M.commodity_physical, M.tech_all)
    M.TechInputSplitAverage = Param(M.RegionalIndices, M.time_optimize, M.commodity_physical, M.tech_variable)
    M.TechOutputSplit = Param(M.RegionalIndices, M.time_optimize, M.tech_all, M.commodity_carrier)

    # The method below creates a series of helper functions that are used to
    # perform the sparse matrix of indexing for the parameters, variables, and
    # equations below.
    M.Create_SparseDicts = BuildAction(rule=CreateSparseDicts)

    # Define technology cost parameters
    M.CostFixed_rptv = Set(dimen=4, initialize=CostFixedIndices)
    M.CostFixed = Param(M.CostFixed_rptv, mutable=True)

    M.CostFixedVintageDefault_rtv = Set(
        dimen=3, initialize=lambda M: set((r, t, v) for r, p, t, v in M.CostFixed_rptv)
    )
    M.CostFixedVintageDefault = Param(M.CostFixedVintageDefault_rtv)

    M.CostInvest_rtv = Set(dimen=3, initialize=CostInvestIndices)
    M.CostInvest = Param(M.CostInvest_rtv)

    M.CostVariable_rptv = Set(dimen=4, initialize=CostVariableIndices)
    M.CostVariable = Param(M.CostVariable_rptv, mutable=True)

    M.CostVariableVintageDefault_rtv = Set(
        dimen=3, initialize=lambda M: set((r, t, v) for r, p, t, v in M.CostVariable_rptv)
    )
    M.CostVariableVintageDefault = Param(M.CostVariableVintageDefault_rtv)

    M.initialize_Costs = BuildAction(rule=CreateCosts)

    M.DiscountRate_rtv = Set(dimen=3, initialize=lambda M: M.CostInvest.keys())
    M.DiscountRate = Param(M.DiscountRate_rtv, default=0.05)

    M.Loan_rtv = Set(dimen=3, initialize=lambda M: M.CostInvest.keys())
    M.LoanAnnualize = Param(M.Loan_rtv, initialize=ParamLoanAnnualize_rule)

    
    M.ModelProcessLife_rptv = Set(dimen=4, initialize=ModelProcessLifeIndices)
    M.ModelProcessLife = Param(
        M.ModelProcessLife_rptv, initialize=ParamModelProcessLife_rule
    )
    
    M.ProcessLifeFrac_rptv = Set(dimen=4, initialize=ModelProcessLifeIndices)
    M.ProcessLifeFrac = Param(
        M.ProcessLifeFrac_rptv, initialize=ParamProcessLifeFraction_rule
    )

    # Define parameters associated with user-defined constraints
    M.MinCapacity = Param(M.RegionalIndices, M.time_optimize, M.tech_all)
    M.MaxCapacity = Param(M.RegionalIndices, M.time_optimize, M.tech_all)
    M.DiscreteCapacity = Param(M.tech_all)
    M.MaxResource = Param(M.RegionalIndices, M.tech_all)
    M.MaxActivity = Param(M.RegionalIndices, M.time_optimize, M.tech_all)
    M.MinActivity = Param(M.RegionalIndices, M.time_optimize, M.tech_all)
    M.GrowthRateMax = Param(M.RegionalIndices, M.tech_all)
    M.GrowthRateSeed = Param(M.RegionalIndices, M.tech_all)
    M.EmissionLimit = Param(M.RegionalIndices, M.time_optimize, M.commodity_emissions)
    M.EmissionActivity_reitvo = Set(dimen=6, initialize=EmissionActivityIndices)
    M.EmissionActivity = Param(M.EmissionActivity_reitvo, default=0)
    M.TechGroupWeight = Param(M.tech_groups, M.groups, default=0)
    M.MinActivityGroup = Param(M.RegionalIndices, M.time_optimize, M.groups)
    M.MaxActivityGroup = Param(M.RegionalIndices, M.time_optimize, M.groups)
    M.MinCapacityGroup = Param(M.RegionalIndices, M.time_optimize, M.groups)
    M.MaxCapacityGroup = Param(M.RegionalIndices, M.time_optimize, M.groups)
    M.MinInputGroup = Param(M.RegionalIndices, M.time_optimize, M.commodity_physical, M.groups)
    M.MaxInputGroup = Param(M.RegionalIndices, M.time_optimize, M.commodity_physical, M.groups)
    M.MinOutputGroup = Param(M.RegionalIndices, M.time_optimize, M.commodity_physical, M.groups)
    M.MaxOutputGroup = Param(M.RegionalIndices, M.time_optimize, M.commodity_physical, M.groups)
    M.LinkedTechs = Param(M.RegionalIndices, M.tech_all, M.commodity_emissions)

    # Define parameters associated with electric sector operation
    M.RampUp = Param(M.regions, M.tech_ramping)
    M.RampDown = Param(M.regions, M.tech_ramping)
    M.CapacityCredit = Param(M.RegionalIndices, M.time_optimize, M.tech_all, M.vintage_all, default=1)
    M.PlanningReserveMargin = Param(M.regions, default=0.2)
    # Storage duration is expressed in hours
    M.StorageDuration = Param(M.regions, M.tech_storage, default=4)
    # Initial storage charge level, expressed as fraction of full energy capacity.
    # If the parameter is not defined, the model optimizes the initial storage charge level.
    M.StorageInit_rtv = Set(dimen=3, initialize=StorageInitIndices)
    M.StorageInitFrac = Param(M.StorageInit_rtv)

    M.MyopicBaseyear = Param(default=0, mutable=True)

    M.MultiObjectiveSlacked = Param(['cost', 'emissions'], within=Reals, default=0)

    # Define parameters associated with energy and material supply risk assessment
    M.EnergyCommodityConcentrationIndex = Param(M.RegionalIndices, M.commodity_physical, M.time_optimize, default=0)
    M.TechnologyMaterialSupplyRisk = Param(M.RegionalIndices, M.tech_all, M.vintage_optimize, default=0)
    M.MaterialIntensity = Param(M.RegionalIndices, M.commodity_material, M.tech_all, M.vintage_optimize, default=0)
    M.MaxMaterialReserve = Param(M.RegionalIndices, M.tech_all)

    # ---------------------------------------------------------------
    # Define Decision Variables.
    # Decision variables are optimized in order to minimize cost.
    # Base decision variables represent the lowest-level variables
    # in the model. Derived decision variables are calculated for
    # convenience, where 1 or more indices in the base variables are
    # summed over.
    # ---------------------------------------------------------------
    # Define base decision variables
    M.FlowVar_rpsditvo = Set(dimen=8, initialize=FlowVariableIndices)
    M.V_FlowOut = Var(M.FlowVar_rpsditvo, domain=NonNegativeReals)
    M.FlowVarAnnual_rpitvo = Set(dimen=6, initialize=FlowVariableAnnualIndices)
    M.V_FlowOutAnnual = Var(M.FlowVarAnnual_rpitvo, domain=NonNegativeReals)

    M.FlexVar_rpsditvo = Set(dimen=8, initialize=FlexVariablelIndices)
    M.V_Flex = Var(M.FlexVar_rpsditvo, domain=NonNegativeReals)
    M.FlexVarAnnual_rpitvo = Set(dimen=6, initialize=FlexVariableAnnualIndices)
    M.V_FlexAnnual = Var(M.FlexVarAnnual_rpitvo, domain=NonNegativeReals)

    M.CurtailmentVar_rpsditvo = Set(dimen=8, initialize=CurtailmentVariableIndices)
    M.V_Curtailment = Var(M.CurtailmentVar_rpsditvo, domain=NonNegativeReals)

    M.FlowInStorage_rpsditvo = Set(dimen=8, initialize=FlowInStorageVariableIndices)
    M.V_FlowIn = Var(M.FlowInStorage_rpsditvo, domain=NonNegativeReals)
    M.StorageLevel_rpsdtv = Set(dimen=6, initialize=StorageVariableIndices)
    M.V_StorageLevel = Var(M.StorageLevel_rpsdtv, domain=NonNegativeReals)
    M.V_StorageInit = Var(M.StorageInit_rtv, domain=NonNegativeReals)

    # Derived decision variables

    M.CapacityVar_rtv = Set(dimen=3, initialize=CapacityVariableIndices)
    M.V_Capacity = Var(M.CapacityVar_rtv, domain=NonNegativeReals)
    M.V_DiscreteCapacity = Var(M.CapacityVar_rtv, domain=Integers)

    M.CapacityAvailableVar_rpt = Set(
        dimen=3, initialize=CapacityAvailableVariableIndices
    )
    M.V_CapacityAvailableByPeriodAndTech = Var(
        M.CapacityAvailableVar_rpt, domain=NonNegativeReals
    )

    # Define variable for multi-objective optimization
    M.V_Costs_rp = Var(M.RegionalIndices, M.time_optimize, domain=NonNegativeReals, initialize=0)
    M.V_Emissions_rp = Var(M.RegionalIndices, M.time_optimize, domain=NonNegativeReals, initialize=0)
    M.V_ImportShare = Var(M.RegionalIndices, M.time_optimize, M.commodity_physical, domain=NonNegativeReals, initialize=0)
    M.V_EnergySupplyRisk = Var(M.RegionalIndices, M.time_optimize, domain=NonNegativeReals, initialize=0)
    M.V_MaterialSupplyRisk = Var(M.RegionalIndices, M.time_optimize, domain=NonNegativeReals, initialize=0)
    M.V_MatCons = Var(M.RegionalIndices, M.commodity_material, M.tech_all, M.vintage_optimize, domain=NonNegativeReals, initialize=0)

    # ---------------------------------------------------------------
    # Declare the Objective Function.
    # ---------------------------------------------------------------
    M.TotalCost = Objective(rule=TotalCost_rule, sense=minimize)

    # ---------------------------------------------------------------
    # Declare the Constraints.
    # Constraints are specified to ensure proper system behavior,
    # and also to calculate some derived quantities. Note that descriptions
    # of these constraints are provided in the associated comment blocks
    # in temoa_rules.py, where the constraints are defined.
    # ---------------------------------------------------------------

    # Declare constraints to calculate derived decision variables

    M.CapacityConstraint_rpsdtv = Set(dimen=6, initialize=CapacityConstraintIndices)
    M.CapacityConstraint = Constraint(
        M.CapacityConstraint_rpsdtv, rule=Capacity_Constraint)

    M.CapacityAnnualConstraint_rptv = Set(dimen=4, initialize=CapacityAnnualConstraintIndices)
    M.CapacityAnnualConstraint = Constraint(
        M.CapacityAnnualConstraint_rptv, rule=CapacityAnnual_Constraint)

    M.CapacityAvailableByPeriodAndTechConstraint = Constraint(
        M.CapacityAvailableVar_rpt, rule=CapacityAvailableByPeriodAndTech_Constraint
    )

    M.ExistingCapacityConstraint_rtv = Set(
        dimen=3, initialize=lambda M: M.ExistingCapacity.sparse_iterkeys()
    )
    M.ExistingCapacityConstraint = Constraint(
        M.ExistingCapacityConstraint_rtv, rule=ExistingCapacity_Constraint
    )

    # Declare core model constraints that ensure proper system functioning
    # In driving order, starting with the need to meet end-use demands

    M.DemandConstraint_rpsdc = Set(dimen=5, initialize=DemandConstraintIndices)
    M.DemandConstraint = Constraint(M.DemandConstraint_rpsdc, rule=Demand_Constraint)

    M.DemandActivityConstraint_rpsdtv_dem_s0d0 = Set(
        dimen=9, initialize=DemandActivityConstraintIndices
    )
    M.DemandActivityConstraint = Constraint(
        M.DemandActivityConstraint_rpsdtv_dem_s0d0, rule=DemandActivity_Constraint
    )

    M.CommodityBalanceConstraint_rpsdc = Set(
        dimen=5, initialize=CommodityBalanceConstraintIndices
    )
    M.CommodityBalanceConstraint = Constraint(
        M.CommodityBalanceConstraint_rpsdc, rule=CommodityBalance_Constraint
    )

    M.CommodityBalanceAnnualConstraint_rpc = Set(
        dimen=3, initialize=CommodityBalanceAnnualConstraintIndices
    )
    M.CommodityBalanceAnnualConstraint = Constraint(
        M.CommodityBalanceAnnualConstraint_rpc, rule=CommodityBalanceAnnual_Constraint
    )

    M.TotalCostConstraint = Constraint(M.regions, M.time_optimize, rule=TotalCost_Constraint)
    M.CostSlackedConstraint = Constraint(rule=CostSlacked_Constraint)

    M.TotalEmissionsConstraint = Constraint(M.regions, M.time_optimize, rule=TotalEmissions_Constraint)
    M.EmissionsSlackedConstraint = Constraint(rule=EmissionsSlacked_Constraint)

    M.ImportShareConstraint_rpc = Set(
        dimen=3, initialize=ImportShareConstraintIndices
    )
    M.ImportShareConstraint = Constraint(
        M.ImportShareConstraint_rpc, rule=ImportShare_Constraint
    )
    M.EnergySupplyRiskConstraint = Constraint(
        M.regions, M.time_optimize, rule=EnergySupplyRisk_Constraint
    )

    M.MaterialSupplyRiskConstraint = Constraint(
        M.regions, M.time_optimize, rule=MaterialSupplyRisk_Constraint
    )
    M.MaterialConsumptionConstraint = Constraint(
        M.regions, M.commodity_material, M.tech_all, M.vintage_optimize, rule=MaterialConsumption_Constraint
    )
    M.MaterialBalanceConstraint = Constraint(
        M.regions, M.time_optimize, M.commodity_material, rule=MaterialBalance_Constraint
    )
    # M.MaxMaterialReserveConstraint = Constraint(
    #     M.regions, M.tech_all, rule=MaxMaterialReserve_Constraint
    # )
    M.MaxMaterialReserveConstraint_rt = Set(
        dimen=2, initialize=lambda M: M.MaxMaterialReserve.sparse_iterkeys()
    )
    M.MaxMaterialReserveConstraint = Constraint(
        M.MaxMaterialReserveConstraint_rt, rule=MaxMaterialReserve_Constraint
    )

    M.ResourceConstraint_rpr = Set(
        dimen=3, initialize=lambda M: M.ResourceBound.sparse_iterkeys()
    )
    M.ResourceExtractionConstraint = Constraint(
        M.ResourceConstraint_rpr, rule=ResourceExtraction_Constraint
    )

    M.BaseloadDiurnalConstraint_rpsdtv = Set(
        dimen=6, initialize=BaseloadDiurnalConstraintIndices
    )
    M.BaseloadDiurnalConstraint = Constraint(
        M.BaseloadDiurnalConstraint_rpsdtv, rule=BaseloadDiurnal_Constraint
    )

    M.RegionalExchangeCapacityConstraint_rrtv = Set(
        dimen=4, initialize=RegionalExchangeCapacityConstraintIndices
    )
    M.RegionalExchangeCapacityConstraint = Constraint(
        M.RegionalExchangeCapacityConstraint_rrtv, rule=RegionalExchangeCapacity_Constraint)

    # This set works for all the storage-related constraints
    M.StorageConstraints_rpsdtv = Set(dimen=6, initialize=StorageVariableIndices)
    M.StorageEnergyConstraint = Constraint(
        M.StorageConstraints_rpsdtv, rule=StorageEnergy_Constraint
    )

    M.StorageEnergyUpperBoundConstraint = Constraint(
        M.StorageConstraints_rpsdtv, rule=StorageEnergyUpperBound_Constraint
    )

    M.StorageChargeRateConstraint = Constraint(
        M.StorageConstraints_rpsdtv, rule=StorageChargeRate_Constraint
    )

    M.StorageDischargeRateConstraint = Constraint(
        M.StorageConstraints_rpsdtv, rule=StorageDischargeRate_Constraint
    )

    M.StorageThroughputConstraint = Constraint(
        M.StorageConstraints_rpsdtv, rule=StorageThroughput_Constraint
    )

    M.StorageInitConstraint_rtv = Set(dimen=2,initialize=StorageInitConstraintIndices)
    M.StorageInitConstraint = Constraint(
        M.StorageInitConstraint_rtv, rule=StorageInit_Constraint
    )

    M.RampConstraintDay_rpsdtv = Set(dimen=6, initialize=RampConstraintDayIndices)
    M.RampUpConstraintDay = Constraint(
        M.RampConstraintDay_rpsdtv, rule=RampUpDay_Constraint
    )
    M.RampDownConstraintDay = Constraint(
        M.RampConstraintDay_rpsdtv, rule=RampDownDay_Constraint
    )

    M.RampConstraintSeason_rpstv = Set(dimen=5, initialize=RampConstraintSeasonIndices)
    M.RampUpConstraintSeason = Constraint(
        M.RampConstraintSeason_rpstv, rule=RampUpSeason_Constraint
    )
    M.RampDownConstraintSeason = Constraint(
        M.RampConstraintSeason_rpstv, rule=RampDownSeason_Constraint
    )

    M.RampConstraintPeriod_rptv = Set(dimen=4, initialize=RampConstraintPeriodIndices)
    M.RampUpConstraintPeriod = Constraint(
        M.RampConstraintPeriod_rptv, rule=RampUpPeriod_Constraint
    )
    M.RampDownConstraintPeriod = Constraint(
        M.RampConstraintPeriod_rptv, rule=RampDownPeriod_Constraint
    )

    M.ReserveMargin_rpsd = Set(dimen=4, initialize=ReserveMarginIndices)
    M.ReserveMarginConstraint = Constraint(
        M.ReserveMargin_rpsd, rule=ReserveMargin_Constraint
    )

    M.EmissionLimitConstraint_rpe = Set(
        dimen=3, initialize=lambda M: M.EmissionLimit.sparse_iterkeys()
    )
    M.EmissionLimitConstraint = Constraint(
        M.EmissionLimitConstraint_rpe, rule=EmissionLimit_Constraint
    )

    from itertools import product

    M.GrowthRateMaxConstraint_rtv = Set(
        dimen=3,
        initialize=lambda M: set(
            product(M.time_optimize, M.GrowthRateMax.sparse_iterkeys())
        ),
    )
    M.GrowthRateConstraint = Constraint(
        M.GrowthRateMaxConstraint_rtv, rule=GrowthRateConstraint_rule
    )

    M.MaxActivityConstraint_rpt = Set(
        dimen=3, initialize=lambda M: M.MaxActivity.sparse_iterkeys()
    )
    M.MaxActivityConstraint = Constraint(
        M.MaxActivityConstraint_rpt, rule=MaxActivity_Constraint
    )

    M.MinActivityConstraint_rpt = Set(
        dimen=3, initialize=lambda M: M.MinActivity.sparse_iterkeys()
    )
    M.MinActivityConstraint = Constraint(
        M.MinActivityConstraint_rpt, rule=MinActivity_Constraint
    )

    M.MinActivityGroup_rpg = Set(
        dimen=3, initialize=lambda M: M.MinActivityGroup.sparse_iterkeys()
    )
    M.MinActivityGroupConstraint = Constraint(
        M.MinActivityGroup_rpg, rule=MinActivityGroup_Constraint
    )

    M.MaxActivityGroup_rpg = Set(
        dimen=3, initialize=lambda M: M.MaxActivityGroup.sparse_iterkeys()
    )
    M.MaxActivityGroupConstraint = Constraint(
        M.MaxActivityGroup_rpg, rule=MaxActivityGroup_Constraint
    )

    M.MinCapacityGroupConstraint_rpg = Set(
        dimen=3, initialize=lambda M: M.MinCapacityGroup.sparse_iterkeys()
    )
    M.MinCapacityGroupConstraint = Constraint(
        M.MinCapacityGroupConstraint_rpg, rule=MinCapacityGroup_Constraint
    )

    M.MaxCapacityGroupConstraint_rpg = Set(
        dimen=3, initialize=lambda M: M.MaxCapacityGroup.sparse_iterkeys()
    )
    M.MaxCapacityGroupConstraint = Constraint(
        M.MaxCapacityGroupConstraint_rpg, rule=MaxCapacityGroup_Constraint
    )

    M.MinInputGroup_Constraint_rpig = Set(
        dimen=4, initialize=lambda M: M.MinInputGroup.sparse_iterkeys()
    )
    M.MinInputGroupConstraint = Constraint(
        M.MinInputGroup_Constraint_rpig, rule=MinInputGroup_Constraint
    )

    M.MaxInputGroup_Constraint_rpig = Set(
        dimen=4, initialize=lambda M: M.MaxInputGroup.sparse_iterkeys()
    )
    M.MaxInputGroupConstraint = Constraint(
        M.MaxInputGroup_Constraint_rpig, rule=MaxInputGroup_Constraint
    )

    M.MinOutputGroup_Constraint_rpig = Set(
        dimen=4, initialize=lambda M: M.MinOutputGroup.sparse_iterkeys()
    )
    M.MinOutputGroupConstraint = Constraint(
        M.MinOutputGroup_Constraint_rpig, rule=MinOutputGroup_Constraint
    )

    M.MaxOutputGroup_Constraint_rpig = Set(
        dimen=4, initialize=lambda M: M.MaxOutputGroup.sparse_iterkeys()
    )
    M.MaxOutputGroupConstraint = Constraint(
        M.MaxOutputGroup_Constraint_rpig, rule=MaxOutputGroup_Constraint
    )

    M.MaxCapacityConstraint_rpt = Set(
        dimen=3, initialize=lambda M: M.MaxCapacity.sparse_iterkeys()
    )
    M.MaxCapacityConstraint = Constraint(
        M.MaxCapacityConstraint_rpt, rule=MaxCapacity_Constraint
    )

    M.DiscreteConstraint = Constraint(
        M.CapacityVar_rtv, rule=DiscreteCapacity_Constraint
    )

    M.MaxResourceConstraint_rt = Set(
        dimen=2, initialize=lambda M: M.MaxResource.sparse_iterkeys()
    )
    M.MaxResourceConstraint = Constraint(
        M.MaxResourceConstraint_rt, rule=MaxResource_Constraint
    )

    M.MinCapacityConstraint_rpt = Set(
        dimen=3, initialize=lambda M: M.MinCapacity.sparse_iterkeys()
    )
    M.MinCapacityConstraint = Constraint(
        M.MinCapacityConstraint_rpt, rule=MinCapacity_Constraint
    )

    M.TechInputSplitConstraint_rpsditv = Set(
        dimen=7, initialize=TechInputSplitConstraintIndices
    )
    M.TechInputSplitConstraint = Constraint(
        M.TechInputSplitConstraint_rpsditv, rule=TechInputSplit_Constraint
    )

    M.TechInputSplitAnnualConstraint_rpitv = Set(
        dimen=5, initialize=TechInputSplitAnnualConstraintIndices
    )
    M.TechInputSplitAnnualConstraint = Constraint(
        M.TechInputSplitAnnualConstraint_rpitv, rule=TechInputSplitAnnual_Constraint
    )
    
    M.TechInputSplitAverageConstraint_rpitv = Set(
        dimen=5, initialize=TechInputSplitAverageConstraintIndices
    )
    M.TechInputSplitAverageConstraint = Constraint(
        M.TechInputSplitAverageConstraint_rpitv, rule=TechInputSplitAverage_Constraint
    )
    
    M.TechOutputSplitConstraint_rpsdtvo = Set(
        dimen=7, initialize=TechOutputSplitConstraintIndices
    )
    M.TechOutputSplitConstraint = Constraint(
        M.TechOutputSplitConstraint_rpsdtvo, rule=TechOutputSplit_Constraint
    )

    M.TechOutputSplitAnnualConstraint_rptvo = Set(
        dimen=5, initialize=TechOutputSplitAnnualConstraintIndices
    )
    M.TechOutputSplitAnnualConstraint = Constraint(
        M.TechOutputSplitAnnualConstraint_rptvo, rule=TechOutputSplitAnnual_Constraint
    )
    M.LinkedEmissionsTechConstraint_rpsdtve = Set(dimen=7, initialize=LinkedTechConstraintIndices)
    M.LinkedEmissionsTechConstraint = Constraint(
        M.LinkedEmissionsTechConstraint_rpsdtve, rule=LinkedEmissionsTech_Constraint)
    return M


model = temoa_create_model()


def runModelUI(config_filename):
    """This function launches the model run from the Temoa GUI"""

    solver = TemoaSolver(model, config_filename)
    for k in solver.createAndSolve():
        yield k
        # yield " " * 1024


def runModel():
    """This function launches the model run, and is invoked when called from
    __main__.py"""

    dummy = ""  # If calling from command line, send empty string
    solver = TemoaSolver(model, dummy)
    for k in solver.createAndSolve():
        pass


if "__main__" == __name__:
    """This code only invoked when called this file is invoked directly from the
    command line as follows: $ python temoa_model/temoa_model.py path/to/dat/file"""

    dummy = ""  # If calling from command line, send empty string
    model = runModel()