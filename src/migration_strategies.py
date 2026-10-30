"""
src/migration_strategies.py
===========================
Módulo puente compatible con la Sección 10 de la especificación técnica.
Re-exporta las 3 estrategias de migración HCF y la heurística voraz costo-beneficio
implementadas en `migration_policies.py`.
"""

from migration_policies import (
    AnnualMigrationSnapshot,
    CandidateAction,
    MODE_1_REPLACE_LINK,
    MODE_2_PARALLEL_HCF,
    MODE_3_BYPASS_HCF,
    MODE_NONE_SMF,
    MigrationActionRecord,
    MultiYearSimulationResult,
    POLICY_GREEDY_COST_BENEFIT,
    POLICY_MAX_UTILIZATION,
    apply_candidate_action,
    get_candidate_actions,
    run_multi_year_simulation,
    select_best_migration_action,
)

__all__ = [
    "AnnualMigrationSnapshot",
    "CandidateAction",
    "MODE_1_REPLACE_LINK",
    "MODE_2_PARALLEL_HCF",
    "MODE_3_BYPASS_HCF",
    "MODE_NONE_SMF",
    "MigrationActionRecord",
    "MultiYearSimulationResult",
    "POLICY_GREEDY_COST_BENEFIT",
    "POLICY_MAX_UTILIZATION",
    "apply_candidate_action",
    "get_candidate_actions",
    "run_multi_year_simulation",
    "select_best_migration_action",
]
