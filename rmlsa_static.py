"""
rmlsa_static.py
===============
Motor estático de Ruteo, Nivel de Modulación y Asignación de Espectro (RMLSA)
por fotografías anuales sobre Banda C (320 FSUs de 12.5 GHz).

Implementa paso a paso el algoritmo especificado en la Sección 7:
1. Generación y cuantización de la matriz de demanda anual D(k) = D(0) * (1 + r)^k.
2. Pre-cálculo de k-Shortest Paths (k-SP, por defecto k = 3) o Shortest Path (k = 1)
   con `networkx.shortest_simple_paths` y ordenamiento determinista descendente por
   (Bitrate * Distancia_Ruta_Más_Corta).
3. Evaluación física QoT en cada ruta candidata p_j mediante suma paralela inversa
   de GSNR y selección del formato de modulación m de mayor eficiencia espectral
   (de 64-QAM hacia BPSK), sumando G = 1 FSU de banda de guarda (S_req = n_FSU + G).
4. Asignación espectral First-Fit sujeta a las restricciones de Continuidad Espectral
   (mismos índices s en todos los enlaces de la ruta) y Contigüidad Espectral
   (bloque adyacente [s*, s* + S_req - 1] libre).
5. Contabilización de Conexiones Fuera (Rechazadas) distinguiendo exactamente entre:
   (a) Rechazo por Capa Física (QoT/GSNR insuficiente en todas las rutas), y
   (b) Rechazo por Saturación/Fragmentación de Espectro en Banda C.
6. Verificación automática de invariantes físicas y espectrales (Sección 12).

Curso: TEL-317 Redes Ópticas WDM - UTFSM
Hito: Taller 3
"""

from __future__ import annotations
import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import networkx as nx
import numpy as np

from config import (
    DEFAULT_ANNUAL_GROWTH_RATE,
    DEFAULT_K_PATHS,
    DELTA_SNR_HCF_DB,
    GSNR_1SPAN_SMF_DB,
    GUARD_BAND_SLOTS,
    MODULATION_BY_NAME,
    TOTAL_SLOTS,
)
from physics_qot import ModulationDecision, evaluate_path_qot
from topology import DemandRequest, NetworkTopology, OpticalLink

# Constantes de estado y causa de rechazo (Sección 7.5)
STATUS_ALLOCATED: str = "ATENDIDA"
STATUS_REJECTED: str = "CONEXION_FUERA"

REJECTION_NONE: str = "NONE"
REJECTION_QOT: str = "RECHAZO_CAPA_FISICA_GSNR"
REJECTION_SPECTRUM: str = "RECHAZO_SATURACION_ESPECTRO"


@dataclass
class ConnectionAllocationResult:
    """Registro detallado del resultado RMLSA para una conexión individual c in C(k)."""
    uid: int
    demand_id: str
    parent_demand_id: str
    source: int
    target: int
    bitrate_gbps: int
    year_k: int
    shortest_distance_km: float
    priority_weight: float
    status: str
    rejection_reason: str = REJECTION_NONE
    candidate_index_used: Optional[int] = None
    path_nodes: List[int] = field(default_factory=list)
    path_link_ids: List[str] = field(default_factory=list)
    route_distance_km: float = 0.0
    route_spans: int = 0
    gsnr_db: Optional[float] = None
    modulation: Optional[str] = None
    spectral_efficiency_bps_hz: int = 0
    payload_fsus: int = 0
    guard_band_fsus: int = 0
    total_fsus: int = 0
    start_slot: Optional[int] = None
    end_slot: Optional[int] = None  # Inclusivo: [start_slot, end_slot]

    @property
    def is_allocated(self) -> bool:
        return self.status == STATUS_ALLOCATED


@dataclass
class StaticRMLSAResult:
    """Resumen completo de una fotografía anual ejecutada por el motor RMLSA."""
    network_name: str
    year_k: int
    growth_rate: float
    k_paths: int
    total_connections_requested: int
    allocated_connections: int
    rejected_connections: int                  # Métrica principal: Conexiones Fuera
    rejected_by_qot: int                       # Rechazo por GSNR insuficiente
    rejected_by_spectrum: int                  # Rechazo por saturación/fragmentación
    total_requested_gbps: float
    served_traffic_gbps: float
    unserved_traffic_gbps: float               # Tráfico No Atendido (Gbps)
    connection_rejection_ratio: float
    traffic_rejection_ratio: float
    total_fsus_occupied_across_links: int
    total_fsu_capacity_across_links: int
    global_spectrum_utilization_pct: float
    max_link_utilization_pct: float
    bottleneck_link_id: Optional[str]
    modulation_distribution: Dict[str, int]
    allocations: List[ConnectionAllocationResult]
    invariants_verified: bool = True

    def summary_dict(self) -> Dict[str, object]:
        return {
            "network_name": self.network_name,
            "year_k": self.year_k,
            "growth_rate": self.growth_rate,
            "k_paths": self.k_paths,
            "total_connections_requested": self.total_connections_requested,
            "allocated_connections": self.allocated_connections,
            "conexiones_fuera": self.rejected_connections,
            "rejected_by_qot": self.rejected_by_qot,
            "rejected_by_spectrum": self.rejected_by_spectrum,
            "total_requested_gbps": self.total_requested_gbps,
            "served_traffic_gbps": self.served_traffic_gbps,
            "served_traffic_tbps": round(self.served_traffic_gbps / 1000.0, 4),
            "unserved_traffic_gbps": self.unserved_traffic_gbps,
            "connection_rejection_pct": round(100.0 * self.connection_rejection_ratio, 3),
            "traffic_rejection_pct": round(100.0 * self.traffic_rejection_ratio, 3),
            "total_fsus_occupied": self.total_fsus_occupied_across_links,
            "total_fsu_capacity": self.total_fsu_capacity_across_links,
            "global_spectrum_utilization_pct": round(self.global_spectrum_utilization_pct, 2),
            "max_link_utilization_pct": round(self.max_link_utilization_pct, 2),
            "bottleneck_link_id": self.bottleneck_link_id,
            "modulation_distribution": dict(self.modulation_distribution),
            "invariants_verified": self.invariants_verified,
        }


# =============================================================================
# 1. FUNCIONES DE ENRUTAMIENTO (k-SHORTEST PATHS) Y ORDENAMIENTO DETERMINISTA
# =============================================================================

def compute_k_shortest_node_paths(
    graph: nx.Graph,
    source: int,
    target: int,
    k: int = DEFAULT_K_PATHS,
    weight: str = "length_km",
) -> List[List[int]]:
    """
    Calcula hasta k rutas simples más cortas {p_1, ..., p_k} entre (source, target)
    utilizando el algoritmo de Yen en `networkx.shortest_simple_paths` ponderado
    por longitud física en kilómetros.
    """
    if source == target:
        return [[source]]
    if not nx.has_path(graph, source, target):
        return []
    path_gen = nx.shortest_simple_paths(graph, source=source, target=target, weight=weight)
    return list(itertools.islice(path_gen, int(k)))


def precompute_all_k_shortest_paths(
    topology: NetworkTopology,
    k: int = DEFAULT_K_PATHS,
) -> Dict[Tuple[int, int], List[List[int]]]:
    """
    Pre-calcula (con caché por topología) las k rutas más cortas para todos los
    pares de nodos (u, v) de la topología.
    """
    k_int = int(k)
    if hasattr(topology, "_k_sp_cache") and k_int in topology._k_sp_cache:
        return topology._k_sp_cache[k_int]

    nodes = sorted(topology.graph.nodes())
    k_sp_table: Dict[Tuple[int, int], List[List[int]]] = {}
    for u in nodes:
        for v in nodes:
            if u != v:
                k_sp_table[(u, v)] = compute_k_shortest_node_paths(
                    topology.graph, u, v, k=k_int, weight="length_km"
                )
    if hasattr(topology, "_k_sp_cache"):
        topology._k_sp_cache[k_int] = k_sp_table
    return k_sp_table


def expand_node_path_to_link_sequences(
    topology: NetworkTopology,
    node_path: Sequence[int],
) -> List[List[OpticalLink]]:
    """
    Convierte una ruta de nodos [u_0, u_1, ..., u_m] en una o más secuencias de
    objetos OpticalLink.
    - En Camino 1 y Camino 3 (un enlace por par adyacente), retorna exactamente 1
      secuencia de enlaces.
    - En Camino 2 (cuando existen enlaces HCF paralelos junto a SMF activos),
      genera las combinaciones priorizando los enlaces HCF sobre SMF.
    """
    if len(node_path) < 2:
        return []
    hop_options: List[List[OpticalLink]] = [
        topology.get_links_between(int(node_path[i]), int(node_path[i + 1]))
        for i in range(len(node_path) - 1)
    ]
    sequences = [list(seq) for seq in itertools.product(*hop_options)]
    # Ordenar secuencias priorizando mayor cantidad total de spans HCF
    sequences.sort(key=lambda seq: sum(lk.num_hcf_spans for lk in seq), reverse=True)
    return sequences


def sort_demands_deterministically(
    demands: Sequence[DemandRequest],
    topology: NetworkTopology,
    k_sp_cache: Optional[Dict[Tuple[int, int], List[List[int]]]] = None,
) -> List[DemandRequest]:
    """
    Ordena las conexiones solicitadas C(k) de forma determinista y descendente por
    el producto (Bitrate * Distancia_Ruta_Más_Corta) según la Sección 7.2.
    """
    ordered: List[DemandRequest] = []
    for req in demands:
        pair = (req.source, req.target)
        if k_sp_cache is not None and pair in k_sp_cache and k_sp_cache[pair]:
            sp_nodes = k_sp_cache[pair][0]
        else:
            paths = compute_k_shortest_node_paths(topology.graph, req.source, req.target, k=1)
            sp_nodes = paths[0] if paths else []

        if len(sp_nodes) >= 2:
            sp_dist = sum(
                topology.get_primary_link(sp_nodes[i], sp_nodes[i + 1]).length_km
                for i in range(len(sp_nodes) - 1)
            )
        else:
            sp_dist = 0.0

        req.shortest_distance_km = float(sp_dist)
        req.priority_weight = float(req.bitrate_gbps) * float(sp_dist)
        ordered.append(req)

    # Orden descendente por (Bitrate * Distancia_Ruta_Más_Corta), desempate determinista
    ordered.sort(
        key=lambda r: (-r.priority_weight, -r.bitrate_gbps, -r.shortest_distance_km, r.uid)
    )
    return ordered


# =============================================================================
# 2. CONTINUIDAD ESPECTRAL, CONTIGÜIDAD Y ASIGNACIÓN FIRST-FIT (320 FSUs)
# =============================================================================

def compute_path_availability_mask(links: Sequence[OpticalLink]) -> np.ndarray:
    """
    Calcula el vector booleano de disponibilidad de extremo a extremo (Continuidad
    Espectral) mediante la intersección lógica de los 320 slots de todos los
    enlaces e in p_j (Sección 7.4):
        available_mask[s] == True  <=>  el slot s está libre en TODOS los enlaces de p_j.
    """
    if not links:
        raise ValueError("La lista de enlaces de la ruta no puede estar vacía.")

    total_slots = links[0].total_slots
    combined_occupied = np.zeros(total_slots, dtype=bool)
    for lk in links:
        combined_occupied |= lk.spectrum_occupied
    return ~combined_occupied


def find_first_fit_contiguous_slots(
    availability_mask: np.ndarray,
    required_slots: int,
) -> Optional[int]:
    """
    Busca el menor índice inicial s* in {0, ..., 320 - S_req} (First-Fit) tal que
    el bloque contiguo [s*, s* + S_req - 1] esté completamente libre (True) en
    la máscara de disponibilidad intersección de la ruta (Contigüidad Espectral).

    Retorna `s*` si existe un bloque factible, o `None` si no hay espectro disponible.
    """
    total_slots = int(availability_mask.shape[0])
    s_req = int(required_slots)

    if s_req <= 0:
        raise ValueError(f"required_slots debe ser >= 1 (recibido: {s_req}).")
    if s_req > total_slots:
        return None

    # Búsqueda vectorial ultrarrápida en C sobre el arreglo booleano de 320 slots
    windows = np.lib.stride_tricks.sliding_window_view(availability_mask, s_req)
    valid_starts = np.flatnonzero( np.all(windows, axis=1) )
    if valid_starts.size > 0:
        return int(valid_starts[0])
    return None


def allocate_connection_first_fit(
    links: Sequence[OpticalLink],
    required_slots: int,
    connection_uid: int,
) -> Optional[Tuple[int, int]]:
    """
    Verifica Continuidad + Contigüidad Espectral sobre la secuencia de enlaces `links`
    y, si encuentra un bloque First-Fit de tamaño `required_slots`, lo ocupa en todos
    los enlaces de la ruta.

    Retorna `(start_slot, end_slot)` inclusivo si tuvo éxito, o `None` en caso contrario.
    """
    avail_mask = compute_path_availability_mask(links)
    s_star = find_first_fit_contiguous_slots(avail_mask, required_slots)
    if s_star is None:
        return None

    for lk in links:
        lk.occupy_slots(s_star, required_slots, connection_uid=connection_uid)

    return s_star, s_star + int(required_slots) - 1


# =============================================================================
# 3. VERIFICACIÓN AUTOMÁTICA DE INVARIANTES FÍSICAS Y ESPECTRALES (Sección 12)
# =============================================================================

def verify_rmlsa_invariants(
    topology: NetworkTopology,
    allocations: Sequence[ConnectionAllocationResult],
) -> bool:
    """
    Verifica matemáticamente todas las Invariantes Físicas y Espectrales (Sección 12):
    1. Todos los enlaces (SMF y HCF) tienen exactamente 320 FSUs en Banda C.
    2. 0 colisiones espectrales: ningún slot en ningún enlace es compartido por >1 conexión.
    3. Continuidad espectral: cada conexión atendida ocupa exactamente el mismo rango
       [start_slot, end_slot] en todos los enlaces de su ruta.
    4. Contigüidad espectral: el número de slots asignados es contiguo e igual a
       payload_fsus + guard_band_fsus.
    5. Factibilidad QoT: toda conexión atendida cumple GSNR_ruta^dB >= SNR_th^dB(m).
    """
    # Invariante 1: Límite estricto de 320 FSUs por enlace
    for lk in topology.links.values():
        if lk.total_slots != TOTAL_SLOTS or lk.spectrum_occupied.shape[0] != TOTAL_SLOTS:
            raise AssertionError(
                f"Violación de Invariante 1 en enlace {lk.id}: "
                f"total_slots={lk.total_slots} != {TOTAL_SLOTS}."
            )

    # Reconstruir mapa de ocupación desde cero a partir de las conexiones atendidas
    reconstructed_owner: Dict[str, np.ndarray] = {
        lid: np.full(TOTAL_SLOTS, -1, dtype=int) for lid in topology.links
    }

    for alloc in allocations:
        if not alloc.is_allocated:
            continue

        assert alloc.start_slot is not None and alloc.end_slot is not None
        assert alloc.modulation is not None and alloc.gsnr_db is not None

        # Invariante 4: Contigüidad espectral y banda de guarda
        expected_width = alloc.payload_fsus + alloc.guard_band_fsus
        actual_width = alloc.end_slot - alloc.start_slot + 1
        if actual_width != expected_width or actual_width != alloc.total_fsus:
            raise AssertionError(
                f"Violación de Contigüidad en conexión {alloc.demand_id}: "
                f"bloque [{alloc.start_slot}, {alloc.end_slot}] tiene ancho {actual_width} "
                f"!= S_req ({expected_width})."
            )
        if alloc.start_slot < 0 or alloc.end_slot >= TOTAL_SLOTS:
            raise AssertionError(
                f"Violación de Banda C en conexión {alloc.demand_id}: "
                f"slots [{alloc.start_slot}, {alloc.end_slot}] fuera de [0, {TOTAL_SLOTS - 1}]."
            )

        # Invariante 5: Umbral físico GSNR
        mod_spec = MODULATION_BY_NAME[alloc.modulation]
        if alloc.gsnr_db + 1e-9 < mod_spec.snr_threshold_db:
            raise AssertionError(
                f"Violación de Capa Física QoT en conexión {alloc.demand_id}: "
                f"GSNR={alloc.gsnr_db:.2f} dB < umbral {mod_spec.snr_threshold_db:.2f} dB "
                f"para {alloc.modulation}."
            )

        # Invariantes 2 y 3: Continuidad espectral y 0 colisiones en cada enlace de la ruta
        for lid in alloc.path_link_ids:
            lk = topology.get_link_by_id(lid)
            owner_slice = reconstructed_owner[lid][alloc.start_slot : alloc.end_slot + 1]
            if np.any(owner_slice != -1):
                raise AssertionError(
                    f"Colisión espectral detectada en enlace {lid} sobre slots "
                    f"[{alloc.start_slot}, {alloc.end_slot}] para conexión {alloc.demand_id}."
                )
            reconstructed_owner[lid][alloc.start_slot : alloc.end_slot + 1] = alloc.uid

            # Verificar coincidencia exacta con el estado interno del enlace
            if not np.all(lk.spectrum_owner[alloc.start_slot : alloc.end_slot + 1] == alloc.uid):
                raise AssertionError(
                    f"Desincronización de continuidad espectral en enlace {lid} "
                    f"para conexión {alloc.demand_id}."
                )

    for lid, lk in topology.links.items():
        if not np.array_equal(lk.spectrum_owner, reconstructed_owner[lid]):
            raise AssertionError(
                f"El mapa espectral del enlace {lid} no coincide exactamente con "
                f"las asignaciones registradas."
            )

    return True


# =============================================================================
# 4. PIPELINE COMPLETO DE EJECUCIÓN ESTÁTICA RMLSA POR FOTOGRAFÍA ANUAL
# =============================================================================

def run_static_rmlsa(
    topology: NetworkTopology,
    year_k: int = 0,
    growth_rate: float = DEFAULT_ANNUAL_GROWTH_RATE,
    k_paths: int = DEFAULT_K_PATHS,
    custom_demands: Optional[Sequence[DemandRequest]] = None,
    gsnr_1span_smf_db: float = GSNR_1SPAN_SMF_DB,
    delta_snr_hcf_db: float = DELTA_SNR_HCF_DB,
    guard_band_slots: int = GUARD_BAND_SLOTS,
    reset_spectrum_before_run: bool = True,
    verify_invariants: bool = True,
) -> StaticRMLSAResult:
    """
    Ejecuta el algoritmo RMLSA Estático completo para la fotografía del año `year_k`
    siguiendo los 5 pasos de la Sección 7:
      1. Generación de la matriz de demanda C(k) (o uso de `custom_demands`).
      2. Cálculo de k rutas más cortas (k-SP) y ordenamiento determinista por
         (Bitrate * Distancia_Ruta_Más_Corta).
      3. Evaluación de rutas candidatas y selección de modulación QoT (64-QAM -> BPSK).
      4. Asignación de espectro First-Fit con continuidad y contigüidad en Banda C.
      5. Clasificación de Conexiones Fuera (Rechazo por GSNR vs. Espectro).
    """
    if reset_spectrum_before_run:
        topology.reset_spectrum()

    # Paso 1: Obtener demandas solicitadas C(k)
    if custom_demands is not None:
        raw_demands = [
            DemandRequest(
                uid=d.uid,
                id=d.id,
                parent_demand_id=d.parent_demand_id,
                source=d.source,
                target=d.target,
                bitrate_gbps=d.bitrate_gbps,
                year_k=d.year_k,
            )
            for d in custom_demands
        ]
    else:
        raw_demands = topology.generate_annual_demands(
            year_k=year_k,
            growth_rate=growth_rate,
        )

    # Paso 2: Pre-cálculo de k-SP y ordenamiento determinista de conexiones
    k_sp_cache = precompute_all_k_shortest_paths(topology, k=k_paths)
    sorted_demands = sort_demands_deterministically(
        raw_demands, topology=topology, k_sp_cache=k_sp_cache
    )

    allocations: List[ConnectionAllocationResult] = []
    modulation_counts: Dict[str, int] = {m: 0 for m in MODULATION_BY_NAME}
    allocated_count = 0
    rejected_count = 0
    rejected_qot_count = 0
    rejected_spectrum_count = 0
    served_gbps = 0.0
    unserved_gbps = 0.0

    # Pasos 3, 4 y 5: Evaluar cada conexión ordenada c in C(k)
    for req in sorted_demands:
        candidate_node_paths = k_sp_cache.get((req.source, req.target), [])
        any_qot_feasible = False
        allocated_record: Optional[ConnectionAllocationResult] = None

        for cand_idx, node_path in enumerate(candidate_node_paths):
            link_sequences = expand_node_path_to_link_sequences(topology, node_path)

            for link_seq in link_sequences:
                qot: ModulationDecision = evaluate_path_qot(
                    path=link_seq,
                    bitrate_gbps=req.bitrate_gbps,
                    topology_or_graph=topology,
                    gsnr_1span_smf_db=gsnr_1span_smf_db,
                    delta_snr_hcf_db=delta_snr_hcf_db,
                    guard_band_slots=guard_band_slots,
                )

                if not qot.feasible or qot.modulation is None:
                    # Ni siquiera BPSK cumple el umbral físico de GSNR en esta ruta
                    continue

                any_qot_feasible = True

                # Paso 4: Intentar asignación First-Fit con continuidad y contigüidad
                slot_assignment = allocate_connection_first_fit(
                    links=link_seq,
                    required_slots=qot.total_fsus_required,
                    connection_uid=req.uid,
                )

                if slot_assignment is not None:
                    s_start, s_end = slot_assignment
                    route_km = sum(lk.length_km for lk in link_seq)
                    route_spans = sum(lk.spans for lk in link_seq)
                    allocated_record = ConnectionAllocationResult(
                        uid=req.uid,
                        demand_id=req.id,
                        parent_demand_id=req.parent_demand_id,
                        source=req.source,
                        target=req.target,
                        bitrate_gbps=req.bitrate_gbps,
                        year_k=req.year_k,
                        shortest_distance_km=req.shortest_distance_km,
                        priority_weight=req.priority_weight,
                        status=STATUS_ALLOCATED,
                        rejection_reason=REJECTION_NONE,
                        candidate_index_used=cand_idx,
                        path_nodes=list(node_path),
                        path_link_ids=[lk.id for lk in link_seq],
                        route_distance_km=route_km,
                        route_spans=route_spans,
                        gsnr_db=qot.gsnr_db,
                        modulation=qot.modulation,
                        spectral_efficiency_bps_hz=qot.spectral_efficiency_bps_hz,
                        payload_fsus=qot.payload_fsus,
                        guard_band_fsus=qot.guard_band_fsus,
                        total_fsus=qot.total_fsus_required,
                        start_slot=s_start,
                        end_slot=s_end,
                    )
                    break

            if allocated_record is not None:
                break

        if allocated_record is not None:
            allocations.append(allocated_record)
            allocated_count += 1
            served_gbps += float(req.bitrate_gbps)
            assert allocated_record.modulation is not None
            modulation_counts[allocated_record.modulation] += 1
        else:
            # Paso 5: Clasificación exacta de Conexión Fuera (Rechazada)
            if not any_qot_feasible:
                reason = REJECTION_QOT
                rejected_qot_count += 1
            else:
                reason = REJECTION_SPECTRUM
                rejected_spectrum_count += 1

            rejected_count += 1
            unserved_gbps += float(req.bitrate_gbps)
            allocations.append(
                ConnectionAllocationResult(
                    uid=req.uid,
                    demand_id=req.id,
                    parent_demand_id=req.parent_demand_id,
                    source=req.source,
                    target=req.target,
                    bitrate_gbps=req.bitrate_gbps,
                    year_k=req.year_k,
                    shortest_distance_km=req.shortest_distance_km,
                    priority_weight=req.priority_weight,
                    status=STATUS_REJECTED,
                    rejection_reason=reason,
                )
            )

    invariants_ok = True
    if verify_invariants:
        invariants_ok = verify_rmlsa_invariants(topology, allocations)

    total_reqs = len(sorted_demands)
    total_gbps = served_gbps + unserved_gbps
    total_used_fsus = sum(lk.used_slots for lk in topology.links.values())
    total_cap_fsus = len(topology.links) * topology.total_slots

    bottleneck_link: Optional[OpticalLink] = max(
        topology.links.values(),
        key=lambda lk: (lk.used_slots, lk.length_km),
        default=None,
    )

    return StaticRMLSAResult(
        network_name=topology.network_name,
        year_k=year_k,
        growth_rate=growth_rate,
        k_paths=k_paths,
        total_connections_requested=total_reqs,
        allocated_connections=allocated_count,
        rejected_connections=rejected_count,
        rejected_by_qot=rejected_qot_count,
        rejected_by_spectrum=rejected_spectrum_count,
        total_requested_gbps=total_gbps,
        served_traffic_gbps=served_gbps,
        unserved_traffic_gbps=unserved_gbps,
        connection_rejection_ratio=(rejected_count / total_reqs) if total_reqs else 0.0,
        traffic_rejection_ratio=(unserved_gbps / total_gbps) if total_gbps else 0.0,
        total_fsus_occupied_across_links=total_used_fsus,
        total_fsu_capacity_across_links=total_cap_fsus,
        global_spectrum_utilization_pct=(
            100.0 * total_used_fsus / total_cap_fsus if total_cap_fsus else 0.0
        ),
        max_link_utilization_pct=(
            100.0 * bottleneck_link.utilization if bottleneck_link is not None else 0.0
        ),
        bottleneck_link_id=bottleneck_link.id if bottleneck_link is not None else None,
        modulation_distribution=modulation_counts,
        allocations=allocations,
        invariants_verified=invariants_ok,
    )
