"""
migration_policies.py
=====================
Implementación de las 3 Estrategias de Migración Progresiva SMF -> HCF propuestas
por el profesor (Sección 8) y la Heurística Secuencial Multi-Año Costo-Beneficio
con modelo CAPEX (Sección 9):

- Mode_1_Replace_Link (Camino 1): Reemplazo de enlaces completos SMF -> HCF
  manteniendo intactos los 320 FSUs de Banda C. Eleva el GSNR de las rutas que
  cruzan el enlace, permitiendo modulaciones de orden superior (menos FSUs/conexión).
- Mode_2_Parallel_HCF (Camino 2): Adición de enlace HCF en paralelo sin apagar
  la fibra SMF activa ("evitar dark fiber").
- Mode_3_Bypass_HCF (Camino 3): Creación de un enlace nuevo HCF directo de larga
  distancia (bypass extremo a extremo) entre nodos lejanos de alto tráfico.
- Baseline_Max_Utilization: Política de referencia que migra en cada decisión
  el enlace SMF con mayor cantidad de FSUs ocupados.

Curso: TEL-317 Redes Ópticas WDM - UTFSM
Hito: Taller 3
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import networkx as nx

from config import (
    DEFAULT_ANNUAL_GROWTH_RATE,
    DEFAULT_HORIZON_YEARS,
    DEFAULT_K_PATHS,
    DELTA_SNR_HCF_DB,
    FIBER_HCF,
    FIBER_SMF,
    GSNR_1SPAN_SMF_DB,
    GUARD_BAND_SLOTS,
)
from physics_qot import compute_hybrid_spans_gsnr_db, select_modulation
from rmlsa_static import StaticRMLSAResult, run_static_rmlsa
from topology import DemandRequest, NetworkTopology, OpticalLink, calculate_num_spans

# Identificadores oficiales de modos de migración (Sección 8 y 10)
MODE_NONE_SMF: str = "Baseline_100_SMF"
MODE_1_REPLACE_LINK: str = "Mode_1_Replace_Link"
MODE_2_PARALLEL_HCF: str = "Mode_2_Parallel_HCF"
MODE_3_BYPASS_HCF: str = "Mode_3_Bypass_HCF"

POLICY_GREEDY_COST_BENEFIT: str = "Greedy_Cost_Benefit"
POLICY_MAX_UTILIZATION: str = "Baseline_Max_Utilization"


@dataclass
class MigrationActionRecord:
    """Registro de una acción de migración ejecutada en el año k."""
    year_k: int
    step_in_year: int
    mode: str
    policy: str
    action_id: str
    source: int
    target: int
    length_km: float
    spans: int
    capex_cost_ur: float
    rejected_before: int
    rejected_after: int
    delta_rejected: int
    delta_served_gbps: float
    delta_fsus_saved: int
    efficiency_score: float


@dataclass
class AnnualMigrationSnapshot:
    """Fotografía anual completa del estado de la red y desempeño RMLSA en el año k."""
    year_k: int
    growth_rate: float
    mode: str
    policy: str
    rmlsa_before_migration: StaticRMLSAResult
    rmlsa_after_migration: StaticRMLSAResult
    actions_taken: List[MigrationActionRecord] = field(default_factory=list)
    incremental_capex_ur: float = 0.0
    cumulative_capex_ur: float = 0.0
    migrated_link_ids_cumulative: List[str] = field(default_factory=list)
    hcf_links_count: int = 0
    total_links_count: int = 0
    hcf_kilometers: float = 0.0

    def to_row_dict(self) -> Dict[str, object]:
        r = self.rmlsa_after_migration
        return {
            "year_k": self.year_k,
            "growth_rate": self.growth_rate,
            "mode": self.mode,
            "policy": self.policy,
            "total_connections_requested": r.total_connections_requested,
            "allocated_connections": r.allocated_connections,
            "conexiones_fuera_before": self.rmlsa_before_migration.rejected_connections,
            "conexiones_fuera": r.rejected_connections,
            "rejected_by_qot": r.rejected_by_qot,
            "rejected_by_spectrum": r.rejected_by_spectrum,
            "connection_rejection_pct": round(100.0 * r.connection_rejection_ratio, 3),
            "total_requested_gbps": r.total_requested_gbps,
            "served_traffic_gbps": r.served_traffic_gbps,
            "served_traffic_tbps": round(r.served_traffic_gbps / 1000.0, 4),
            "unserved_traffic_gbps": r.unserved_traffic_gbps,
            "total_fsus_occupied": r.total_fsus_occupied_across_links,
            "global_spectrum_utilization_pct": round(r.global_spectrum_utilization_pct, 2),
            "max_link_utilization_pct": round(r.max_link_utilization_pct, 2),
            "bottleneck_link_id": r.bottleneck_link_id,
            "actions_in_year": [a.action_id for a in self.actions_taken],
            "incremental_capex_ur": round(self.incremental_capex_ur, 2),
            "cumulative_capex_ur": round(self.cumulative_capex_ur, 2),
            "hcf_links_count": self.hcf_links_count,
            "total_links_count": self.total_links_count,
            "hcf_kilometers": round(self.hcf_kilometers, 1),
            "migrated_links_cumulative": list(self.migrated_link_ids_cumulative),
        }


@dataclass
class MultiYearSimulationResult:
    """Resultado completo de una simulación multi-año k = 0 ... K."""
    network_name: str
    mode: str
    policy: str
    growth_rate: float
    snapshots: List[AnnualMigrationSnapshot]
    all_actions: List[MigrationActionRecord]
    final_topology: NetworkTopology

    @property
    def total_capex_ur(self) -> float:
        return self.snapshots[-1].cumulative_capex_ur if self.snapshots else 0.0

    @property
    def cumulative_served_tbps(self) -> float:
        return sum(s.rmlsa_after_migration.served_traffic_gbps for s in self.snapshots) / 1000.0

    @property
    def cumulative_rejected_connections(self) -> int:
        return sum(s.rmlsa_after_migration.rejected_connections for s in self.snapshots)


# =============================================================================
# 1. GENERACIÓN DEL ESPACIO DE ACCIONES CANDIDATAS A SEGÚN EL CAMINO (1, 2 o 3)
# =============================================================================

@dataclass(frozen=True)
class CandidateAction:
    """Representa una intervención candidata e in A en un año k."""
    action_id: str
    mode: str
    source: int
    target: int
    length_km: float
    spans: int
    capex_cost_ur: float
    target_link_id: Optional[str] = None


def get_candidate_actions(
    topology: NetworkTopology,
    mode: str,
    max_bypass_candidates: int = 12,
) -> List[CandidateAction]:
    """
    Construye el conjunto de candidatos posibles A según la estrategia de migración:
      - Mode_1_Replace_Link: Todos los enlaces primarios que aún son SMF.
      - Mode_2_Parallel_HCF: Todos los pares adyacentes (u, v) que aún no tienen
        una fibra HCF paralela instalada.
      - Mode_3_Bypass_HCF: Pares de nodos lejanos no adyacentes (distancia >= 2 saltos)
        con mayor tráfico agregado en la matriz de demanda base, cuyo enlace directo
        HCF sea físicamente factible en Banda C.
    """
    candidates: List[CandidateAction] = []

    if mode == MODE_1_REPLACE_LINK:
        for lk in topology.links.values():
            if not lk.is_parallel and not lk.is_bypass and lk.fiber_type == FIBER_SMF:
                cost = topology.compute_capex_cost(lk, mode="replace")
                candidates.append(
                    CandidateAction(
                        action_id=lk.id,
                        mode=mode,
                        source=lk.source,
                        target=lk.target,
                        length_km=lk.length_km,
                        spans=lk.spans,
                        capex_cost_ur=cost,
                        target_link_id=lk.id,
                    )
                )
        return candidates

    if mode == MODE_2_PARALLEL_HCF:
        for u, v, edge_data in topology.graph.edges(data=True):
            primary: OpticalLink = edge_data["primary_link"]
            if primary.is_bypass:
                continue
            parallel_list: List[OpticalLink] = edge_data["parallel_links"]
            has_hcf_parallel = any(lk.is_parallel and lk.fiber_type == FIBER_HCF for lk in parallel_list)
            if not has_hcf_parallel:
                u_min, v_max = min(u, v), max(u, v)
                cost = topology.compute_capex_cost(primary, mode="parallel")
                candidates.append(
                    CandidateAction(
                        action_id=f"par_hcf_{primary.id}",
                        mode=mode,
                        source=u_min,
                        target=v_max,
                        length_km=primary.length_km,
                        spans=primary.spans,
                        capex_cost_ur=cost,
                        target_link_id=primary.id,
                    )
                )
        return candidates

    if mode == MODE_3_BYPASS_HCF:
        # Identificar pares de nodos no adyacentes con mayor presión de tráfico * distancia
        pair_scores: Dict[Tuple[int, int], float] = {}
        for d0 in topology.base_demands_d0:
            u, v = int(d0["source"]), int(d0["target"])
            u_min, v_max = min(u, v), max(u, v)
            if topology.graph.has_edge(u_min, v_max):
                continue
            sp_dist = float(
                nx.shortest_path_length(topology.graph, source=u_min, target=v_max, weight="length_km")
            )
            # Longitud directa estimada del enlace bypass (85% de la ruta en malla, múltiplo de span_length_km)
            direct_km = max(
                topology.span_length_km,
                round((0.85 * sp_dist) / topology.span_length_km) * topology.span_length_km,
            )
            n_spans = calculate_num_spans(direct_km, topology.span_length_km)
            # Verificar que el enlace bypass HCF sea físicamente factible (al menos QPSK/8-QAM)
            gsnr_hcf = compute_hybrid_spans_gsnr_db(0, n_spans)
            if not select_modulation(gsnr_hcf, bitrate_gbps=400).feasible:
                continue

            score = float(d0["base_bitrate_gbps"]) * sp_dist
            pair_scores[(u_min, v_max)] = pair_scores.get((u_min, v_max), 0.0) + score

        ranked_pairs = sorted(pair_scores.items(), key=lambda x: x[1], reverse=True)[
            :max_bypass_candidates
        ]
        for (u_min, v_max), _ in ranked_pairs:
            sp_dist = float(
                nx.shortest_path_length(topology.graph, source=u_min, target=v_max, weight="length_km")
            )
            direct_km = max(
                topology.span_length_km,
                round((0.85 * sp_dist) / topology.span_length_km) * topology.span_length_km,
            )
            n_spans = calculate_num_spans(direct_km, topology.span_length_km)
            cost = topology.compute_capex_cost(direct_km, mode="bypass")
            candidates.append(
                CandidateAction(
                    action_id=f"e{u_min}_{v_max}_bypass_hcf",
                    mode=mode,
                    source=u_min,
                    target=v_max,
                    length_km=direct_km,
                    spans=n_spans,
                    capex_cost_ur=cost,
                    target_link_id=None,
                )
            )
        return candidates

    raise ValueError(f"Modo de migración desconocido: {mode}")


def apply_candidate_action(
    topology: NetworkTopology,
    action: CandidateAction,
) -> OpticalLink:
    """Aplica sobre `topology` la acción de migración seleccionada (Camino 1, 2 o 3)."""
    if action.mode == MODE_1_REPLACE_LINK:
        assert action.target_link_id is not None
        return topology.set_link_fiber_type(action.target_link_id, FIBER_HCF)

    if action.mode == MODE_2_PARALLEL_HCF:
        return topology.add_parallel_hcf_link(action.source, action.target)

    if action.mode == MODE_3_BYPASS_HCF:
        return topology.add_bypass_hcf_link(
            action.source, action.target, length_km=action.length_km
        )

    raise ValueError(f"Modo de acción no soportado: {action.mode}")


# =============================================================================
# 2. SELECCIÓN VORAZ COSTO-BENEFICIO VS. BASELINE POR UTILIZACIÓN (Sección 9)
# =============================================================================

def select_best_migration_action(
    topology: NetworkTopology,
    current_rmlsa: StaticRMLSAResult,
    demands_k: Sequence[DemandRequest],
    mode: str,
    policy: str = POLICY_GREEDY_COST_BENEFIT,
    k_paths: int = DEFAULT_K_PATHS,
    remaining_budget_ur: Optional[float] = None,
) -> Optional[Tuple[CandidateAction, StaticRMLSAResult, float]]:
    """
    Evalúa los candidatos posibles e in A y selecciona la mejor acción según:
      - `POLICY_GREEDY_COST_BENEFIT` (Sección 9.3):
        Simula virtualmente cada candidato e y maximiza:
            e* = arg max_{e in A} [ Delta_N_fuera(e) / C(e) ]
        (con desempate por Delta_Gbps(e) / C(e) y ahorro de FSUs Delta_FSU(e) / C(e)).
      - `POLICY_MAX_UTILIZATION` (Sección 9.4 Baseline):
        Selecciona directamente el enlace SMF candidato con mayor número de FSUs
        ocupados en la corrida actual `current_rmlsa`.
    """
    candidates = get_candidate_actions(topology, mode=mode)
    if remaining_budget_ur is not None:
        candidates = [c for c in candidates if c.capex_cost_ur <= remaining_budget_ur + 1e-9]

    if not candidates:
        return None

    # Caso Baseline: Orden Fijo por Mayor Utilización de Slots en Banda C
    if policy == POLICY_MAX_UTILIZATION:
        def utilization_key(cand: CandidateAction) -> Tuple[int, float, float]:
            if cand.target_link_id and cand.target_link_id in topology.links:
                lk = topology.get_link_by_id(cand.target_link_id)
                return (lk.used_slots, lk.utilization, lk.length_km)
            return (0, 0.0, cand.length_km)

        best_cand = max(candidates, key=utilization_key)
        virt_topo = topology.copy()
        apply_candidate_action(virt_topo, best_cand)
        virt_res = run_static_rmlsa(
            virt_topo,
            year_k=current_rmlsa.year_k,
            growth_rate=current_rmlsa.growth_rate,
            k_paths=k_paths,
            custom_demands=demands_k,
            verify_invariants=False,
        )
        delta_rej = current_rmlsa.rejected_connections - virt_res.rejected_connections
        eff = float(delta_rej) / best_cand.capex_cost_ur
        return best_cand, virt_res, eff

    # Caso Propuesto: Selección Voraz Costo-Beneficio (Sección 9.3)
    best_tuple: Optional[Tuple[CandidateAction, StaticRMLSAResult, float]] = None
    best_key: Optional[Tuple[float, float, float, float]] = None

    for cand in candidates:
        virt_topo = topology.copy()
        apply_candidate_action(virt_topo, cand)
        virt_res = run_static_rmlsa(
            virt_topo,
            year_k=current_rmlsa.year_k,
            growth_rate=current_rmlsa.growth_rate,
            k_paths=k_paths,
            custom_demands=demands_k,
            verify_invariants=False,
        )

        delta_rejected = current_rmlsa.rejected_connections - virt_res.rejected_connections
        delta_served_gbps = virt_res.served_traffic_gbps - current_rmlsa.served_traffic_gbps
        delta_fsus_saved = (
            current_rmlsa.total_fsus_occupied_across_links
            - virt_res.total_fsus_occupied_across_links
        )

        # Solo considerar candidatos que aporten mejora física/espectral positiva
        if delta_rejected <= 0 and delta_served_gbps <= 0 and delta_fsus_saved <= 0:
            continue

        eff_rejected = float(delta_rejected) / cand.capex_cost_ur
        eff_gbps = float(delta_served_gbps) / cand.capex_cost_ur
        eff_fsus = float(delta_fsus_saved) / cand.capex_cost_ur

        candidate_key = (eff_rejected, float(delta_rejected), eff_gbps, eff_fsus)
        if best_key is None or candidate_key > best_key:
            best_key = candidate_key
            best_tuple = (cand, virt_res, eff_rejected)

    return best_tuple


# =============================================================================
# 3. SIMULADOR SECUENCIAL MULTI-AÑO CON HERENCIA PROGRESIVA (Sección 9.2 y 9.4)
# =============================================================================

def run_multi_year_simulation(
    base_topology: NetworkTopology,
    mode: str = MODE_1_REPLACE_LINK,
    policy: str = POLICY_GREEDY_COST_BENEFIT,
    years: Sequence[int] = tuple(range(DEFAULT_HORIZON_YEARS + 1)),
    growth_rate: float = DEFAULT_ANNUAL_GROWTH_RATE,
    k_paths: int = DEFAULT_K_PATHS,
    trigger_rejection_ratio: float = 0.01,
    trigger_min_rejected_connections: int = 1,
    max_migrations_per_year: int = 2,
    max_total_capex_ur: Optional[float] = None,
) -> MultiYearSimulationResult:
    """
    Ejecuta la planificación estática multi-año ("fotografías anuales" k = 0 ... K)
    con herencia progresiva de infraestructura HCF:
      1. En cada año k, evalúa primero el motor RMLSA sobre la red heredada de k - 1.
      2. Si `mode != MODE_NONE_SMF` y las Conexiones Fuera superan el umbral de disparo
         (ej. N_fuera > 0 y ratio >= trigger_rejection_ratio), activa el bucle de
         migración hasta recuperar el umbral, alcanzar `max_migrations_per_year`
         o agotar el presupuesto `max_total_capex_ur`.
      3. Conserva permanentemente los enlaces migrados para los años siguientes.
    """
    topo = base_topology.copy()
    snapshots: List[AnnualMigrationSnapshot] = []
    all_actions: List[MigrationActionRecord] = []
    migrated_ids_cumulative: List[str] = []
    cumulative_capex = 0.0

    for year_k in years:
        demands_k = topo.generate_annual_demands(year_k=year_k, growth_rate=growth_rate)

        # Evaluar red heredada del año k - 1
        rmlsa_initial = run_static_rmlsa(
            topo,
            year_k=year_k,
            growth_rate=growth_rate,
            k_paths=k_paths,
            custom_demands=demands_k,
            verify_invariants=True,
        )
        rmlsa_current = rmlsa_initial
        actions_this_year: List[MigrationActionRecord] = []
        inc_capex_year = 0.0

        # Verificar condición de disparo anual (Trigger - Sección 9.2)
        if mode != MODE_NONE_SMF and max_migrations_per_year > 0:
            step = 0
            while step < max_migrations_per_year:
                has_unmet = (
                    rmlsa_current.rejected_connections >= trigger_min_rejected_connections
                    and rmlsa_current.connection_rejection_ratio >= trigger_rejection_ratio
                )
                if not has_unmet:
                    break

                rem_budget: Optional[float] = None
                if max_total_capex_ur is not None:
                    rem_budget = max(0.0, float(max_total_capex_ur) - cumulative_capex)
                    if rem_budget <= 0.0:
                        break

                selection = select_best_migration_action(
                    topology=topo,
                    current_rmlsa=rmlsa_current,
                    demands_k=demands_k,
                    mode=mode,
                    policy=policy,
                    k_paths=k_paths,
                    remaining_budget_ur=rem_budget,
                )
                if selection is None:
                    break

                best_cand, _, eff_score = selection

                # Aplicar permanentemente la migración sobre la topología activa
                rej_before = rmlsa_current.rejected_connections
                gbps_before = rmlsa_current.served_traffic_gbps
                fsus_before = rmlsa_current.total_fsus_occupied_across_links

                applied_link = apply_candidate_action(topo, best_cand)
                rmlsa_current = run_static_rmlsa(
                    topo,
                    year_k=year_k,
                    growth_rate=growth_rate,
                    k_paths=k_paths,
                    custom_demands=demands_k,
                    verify_invariants=True,
                )

                step += 1
                inc_capex_year += best_cand.capex_cost_ur
                cumulative_capex += best_cand.capex_cost_ur
                migrated_ids_cumulative.append(applied_link.id)

                record = MigrationActionRecord(
                    year_k=year_k,
                    step_in_year=step,
                    mode=mode,
                    policy=policy,
                    action_id=applied_link.id,
                    source=best_cand.source,
                    target=best_cand.target,
                    length_km=best_cand.length_km,
                    spans=best_cand.spans,
                    capex_cost_ur=best_cand.capex_cost_ur,
                    rejected_before=rej_before,
                    rejected_after=rmlsa_current.rejected_connections,
                    delta_rejected=rej_before - rmlsa_current.rejected_connections,
                    delta_served_gbps=rmlsa_current.served_traffic_gbps - gbps_before,
                    delta_fsus_saved=fsus_before - rmlsa_current.total_fsus_occupied_across_links,
                    efficiency_score=eff_score,
                )
                actions_this_year.append(record)
                all_actions.append(record)

        topo_summary = topo.summary_dict()
        snapshot = AnnualMigrationSnapshot(
            year_k=year_k,
            growth_rate=growth_rate,
            mode=mode,
            policy=policy,
            rmlsa_before_migration=rmlsa_initial,
            rmlsa_after_migration=rmlsa_current,
            actions_taken=actions_this_year,
            incremental_capex_ur=inc_capex_year,
            cumulative_capex_ur=cumulative_capex,
            migrated_link_ids_cumulative=list(migrated_ids_cumulative),
            hcf_links_count=int(topo_summary["hcf_links"]),
            total_links_count=int(topo_summary["num_links"]),
            hcf_kilometers=float(topo_summary["hcf_length_km"]),
        )
        snapshots.append(snapshot)

    return MultiYearSimulationResult(
        network_name=topo.network_name,
        mode=mode,
        policy=policy,
        growth_rate=growth_rate,
        snapshots=snapshots,
        all_actions=all_actions,
        final_topology=topo,
    )
