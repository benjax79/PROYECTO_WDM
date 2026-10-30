"""
topology.py
===========
Módulo de gestión de topología óptica de transporte (NSFNet 14 nodos / COST239),
cálculo de spans (80-100 km), estado físico de enlaces y spans (SMF / HCF / Híbrido),
invariante de 320 FSUs en Banda C, modelo de costos CAPEX y generación/escalamiento
anual de la matriz de demanda estática D(k) = D(0) * (1 + r)^k.

Curso: TEL-317 Redes Ópticas WDM - UTFSM
Hito: Taller 3
"""

from __future__ import annotations
import copy
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import networkx as nx
import numpy as np

from config import (
    BAND_NAME,
    COST239_BASE_DEMANDS_D0,
    COST239_LINKS,
    COST239_NODES,
    COST_AMP_PER_SPAN_UR,
    COST_HCF_PER_KM_UR,
    COST_INST_BYPASS_UR,
    COST_INST_DUCT_UR,
    DEFAULT_ANNUAL_GROWTH_RATE,
    DEFAULT_SPAN_LENGTH_KM,
    FIBER_HCF,
    FIBER_SMF,
    GUARD_BAND_SLOTS,
    NSFNET_BASE_DEMANDS_D0,
    NSFNET_LINKS,
    NSFNET_NODES,
    SLOT_WIDTH_GHZ,
    SUPPORTED_BITRATES_GBPS,
    TOTAL_SLOTS,
    VALID_FIBER_TYPES,
)


def calculate_num_spans(
    length_km: float,
    span_length_km: float = DEFAULT_SPAN_LENGTH_KM,
) -> int:
    """
    Calcula el número de tramos de amplificación (spans) de un enlace físico e:
        N_spans(e) = ceil(L(e) / L_span)
    donde L_span está típicamente entre 80 y 100 km (Sección 3).
    """
    if length_km <= 0:
        raise ValueError(f"La longitud del enlace debe ser positiva (recibido: {length_km} km).")
    if span_length_km <= 0:
        raise ValueError(f"La longitud de span debe ser positiva (recibido: {span_length_km} km).")
    return max(1, int(math.ceil(float(length_km) / float(span_length_km))))


@dataclass
class OpticalLink:
    """
    Representa una fibra/enlace físico bidireccional en Banda C con exactamente
    320 Frequency Slot Units (FSUs) de 12.5 GHz.

    Cumple estrictamente la Invariante Física #1 (Sección 12):
    Un enlace HCF tiene exactamente los mismos 320 FSUs en Banda C que un enlace SMF.
    """
    id: str
    source: int
    target: int
    length_km: float
    span_length_km: float = DEFAULT_SPAN_LENGTH_KM
    spans: int = field(init=False)
    fiber_type: str = FIBER_SMF
    span_types: List[str] = field(default_factory=list)
    is_parallel: bool = False
    is_bypass: bool = False
    total_slots: int = TOTAL_SLOTS

    # Estado espectral en Banda C:
    # - spectrum_occupied[s] == True  -> slot s ocupado
    # - spectrum_occupied[s] == False -> slot s libre
    # - spectrum_owner[s]    == -1    -> libre; >= 0 -> ID numérico de conexión alojada
    spectrum_occupied: np.ndarray = field(init=False, repr=False)
    spectrum_owner: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.total_slots != TOTAL_SLOTS:
            raise ValueError(
                f"Invariante Física violada en enlace {self.id}: "
                f"total_slots={self.total_slots} != {TOTAL_SLOTS} FSUs fijos de Banda C."
            )
        self.length_km = float(self.length_km)
        self.span_length_km = float(self.span_length_km)
        self.spans = calculate_num_spans(self.length_km, self.span_length_km)

        if not self.span_types:
            if self.fiber_type not in VALID_FIBER_TYPES:
                raise ValueError(f"Tipo de fibra inválido: {self.fiber_type}")
            self.span_types = [self.fiber_type] * self.spans
        else:
            if len(self.span_types) != self.spans:
                raise ValueError(
                    f"El enlace {self.id} tiene {self.spans} spans pero se entregaron "
                    f"{len(self.span_types)} tipos en span_types."
                )
            for st in self.span_types:
                if st not in VALID_FIBER_TYPES:
                    raise ValueError(f"Tipo de span inválido '{st}' en enlace {self.id}.")
            self._sync_fiber_label_from_spans()

        self.spectrum_occupied = np.zeros(self.total_slots, dtype=bool)
        self.spectrum_owner = np.full(self.total_slots, -1, dtype=int)

    def _sync_fiber_label_from_spans(self) -> None:
        unique_types = set(self.span_types)
        if unique_types == {FIBER_SMF}:
            self.fiber_type = FIBER_SMF
        elif unique_types == {FIBER_HCF}:
            self.fiber_type = FIBER_HCF
        else:
            self.fiber_type = "HYBRID"

    def set_fiber_type(self, fiber_type: str) -> None:
        """Actualiza todos los spans del enlace a SMF o HCF (sin alterar los 320 slots)."""
        if fiber_type not in VALID_FIBER_TYPES:
            raise ValueError(f"Tipo de fibra inválido: {fiber_type}. Use {VALID_FIBER_TYPES}.")
        self.fiber_type = fiber_type
        self.span_types = [fiber_type] * self.spans
        assert self.total_slots == TOTAL_SLOTS and len(self.spectrum_occupied) == TOTAL_SLOTS

    def set_span_types(self, span_types: Sequence[str]) -> None:
        """Actualiza la tecnología individual por span s = 1..N_spans(e) (SMF o HCF)."""
        if len(span_types) != self.spans:
            raise ValueError(
                f"Se requieren exactamente {self.spans} elementos para span_types "
                f"(recibido: {len(span_types)})."
            )
        for st in span_types:
            if st not in VALID_FIBER_TYPES:
                raise ValueError(f"Tipo de span inválido: {st}")
        self.span_types = list(span_types)
        self._sync_fiber_label_from_spans()

    def set_hcf_span_ratio(self, hcf_ratio: float) -> None:
        """Configura una fracción de spans como HCF y el resto como SMF (para rutas híbridas)."""
        if not (0.0 <= hcf_ratio <= 1.0):
            raise ValueError("hcf_ratio debe estar entre 0.0 y 1.0.")
        n_hcf = int(round(self.spans * hcf_ratio))
        n_smf = self.spans - n_hcf
        self.set_span_types([FIBER_HCF] * n_hcf + [FIBER_SMF] * n_smf)

    @property
    def num_smf_spans(self) -> int:
        return sum(1 for st in self.span_types if st == FIBER_SMF)

    @property
    def num_hcf_spans(self) -> int:
        return sum(1 for st in self.span_types if st == FIBER_HCF)

    def availability_mask(self) -> np.ndarray:
        """
        Retorna el vector booleano de disponibilidad de longitud 320:
            True  -> slot libre (disponible)
            False -> slot ocupado
        """
        return ~self.spectrum_occupied

    def is_slot_range_free(self, start_slot: int, num_slots: int) -> bool:
        """Verifica si el bloque contiguo [start_slot, start_slot + num_slots - 1] está libre."""
        if start_slot < 0 or num_slots <= 0 or (start_slot + num_slots) > self.total_slots:
            return False
        return not bool(np.any(self.spectrum_occupied[start_slot : start_slot + num_slots]))

    def occupy_slots(self, start_slot: int, num_slots: int, connection_uid: int) -> None:
        """Ocupa el bloque contiguo [start_slot, start_slot + num_slots - 1] verificando 0 colisiones."""
        if start_slot < 0 or num_slots <= 0 or (start_slot + num_slots) > self.total_slots:
            raise IndexError(
                f"Rango de slots [{start_slot}, {start_slot + num_slots - 1}] fuera de Banda C (0..{self.total_slots - 1})."
            )
        if np.any(self.spectrum_occupied[start_slot : start_slot + num_slots]):
            raise RuntimeError(
                f"Colisión espectral detectada en enlace {self.id} al intentar asignar "
                f"slots [{start_slot}, {start_slot + num_slots - 1}] a conexión {connection_uid}."
            )
        self.spectrum_occupied[start_slot : start_slot + num_slots] = True
        self.spectrum_owner[start_slot : start_slot + num_slots] = int(connection_uid)

    def reset_spectrum(self) -> None:
        """Limpia los 320 FSUs del enlace para una nueva fotografía anual."""
        self.spectrum_occupied.fill(False)
        self.spectrum_owner.fill(-1)

    @property
    def used_slots(self) -> int:
        """Cantidad total de FSUs actualmente ocupados en el enlace."""
        return int(np.count_nonzero(self.spectrum_occupied))

    @property
    def free_slots(self) -> int:
        """Cantidad total de FSUs actualmente libres en el enlace."""
        return int(self.total_slots - self.used_slots)

    @property
    def utilization(self) -> float:
        """Fracción de ocupación espectral en Banda C [0.0, 1.0]."""
        return float(self.used_slots) / float(self.total_slots)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "length_km": self.length_km,
            "spans": self.spans,
            "fiber_type": self.fiber_type,
            "span_types": list(self.span_types),
            "is_parallel": self.is_parallel,
            "is_bypass": self.is_bypass,
        }


@dataclass
class DemandRequest:
    """
    Representa una solicitud de conexión individual cuantizada dentro de la
    fotografía anual C(k) (Sección 7.1 y 7.2).
    """
    uid: int
    id: str
    parent_demand_id: str
    source: int
    target: int
    bitrate_gbps: int
    year_k: int = 0
    shortest_distance_km: float = 0.0
    priority_weight: float = 0.0


def decompose_bitrate_to_transponders(
    total_bitrate_gbps: float,
    allowed_bitrates: Sequence[int] = SUPPORTED_BITRATES_GBPS,
    quantization_step_gbps: float = 10.0,
    max_transponder_gbps: int = 400,
) -> List[int]:
    """
    Descompone un tráfico agregado D_{u,v}(k) en demandas individuales discretas
    d_i in {1000, 400, 100, 40, 10} Gbps mediante partición voraz (Sección 7.1).

    Parámetros:
    -----------
    total_bitrate_gbps : float
        Tráfico total requerido entre (u, v) en el año k.
    allowed_bitrates : Sequence[int]
        Tasas de línea estándar soportadas por los transpondedores EON.
    quantization_step_gbps : float
        Paso mínimo de cuantización (10 Gbps).
    max_transponder_gbps : int
        Tasa máxima por conexión individual (por defecto 400G o 1000G).
    """
    if total_bitrate_gbps <= 0:
        return []

    # Redondeo al múltiplo de 10 Gbps más cercano (mínimo 10 Gbps)
    quantized = max(
        int(quantization_step_gbps),
        int(round(total_bitrate_gbps / quantization_step_gbps) * quantization_step_gbps),
    )

    rates_desc = sorted(
        [r for r in allowed_bitrates if r <= max_transponder_gbps],
        reverse=True,
    )
    if not rates_desc:
        rates_desc = sorted(allowed_bitrates, reverse=True)

    result: List[int] = []
    remaining = quantized
    for rate in rates_desc:
        while remaining >= rate:
            result.append(rate)
            remaining -= rate

    if remaining > 0:
        smallest_rate = rates_desc[-1]
        result.append(smallest_rate)

    return result


class NetworkTopology:
    """
    Clase principal de topología óptica EON sobre Banda C (320 FSUs).
    Encapsula el grafo NetworkX, el registro de enlaces físicos (SMF, HCF,
    paralelos y bypass), el modelo CAPEX y la matriz de demanda base D(0).
    """

    def __init__(
        self,
        network_name: str = "NSFNet_14_Transport",
        nodes: Optional[Sequence[Dict[str, object]]] = None,
        links: Optional[Sequence[Dict[str, object]]] = None,
        base_demands_d0: Optional[Sequence[Dict[str, object]]] = None,
        span_length_km: float = DEFAULT_SPAN_LENGTH_KM,
        total_slots: int = TOTAL_SLOTS,
        slot_width_ghz: float = SLOT_WIDTH_GHZ,
        guard_band_slots: int = GUARD_BAND_SLOTS,
    ) -> None:
        if total_slots != TOTAL_SLOTS:
            raise ValueError(
                f"Invariante Física: Banda C tiene exactamente {TOTAL_SLOTS} FSUs "
                f"(recibido: {total_slots})."
            )
        self.network_name: str = network_name
        self.band: str = BAND_NAME
        self.total_slots: int = total_slots
        self.slot_width_ghz: float = float(slot_width_ghz)
        self.guard_band_slots: int = int(guard_band_slots)
        self.span_length_km: float = float(span_length_km)

        self.graph: nx.Graph = nx.Graph(
            network_name=self.network_name,
            band=self.band,
            total_slots=self.total_slots,
            slot_width_ghz=self.slot_width_ghz,
            guard_band_slots=self.guard_band_slots,
            span_length_km=self.span_length_km,
        )
        self.links: Dict[str, OpticalLink] = {}
        self._k_sp_cache: Dict[int, Dict[Tuple[int, int], List[List[int]]]] = {}
        self.base_demands_d0: List[Dict[str, object]] = copy.deepcopy(
            list(base_demands_d0) if base_demands_d0 is not None else NSFNET_BASE_DEMANDS_D0
        )

        node_list = list(nodes) if nodes is not None else NSFNET_NODES
        for n in node_list:
            nid = int(n["id"])
            self.graph.add_node(
                nid,
                id=nid,
                name=str(n.get("name", f"N{nid}")),
                city=str(n.get("city", f"Node_{nid}")),
                pos=tuple(n.get("pos", (0.0, 0.0))),
            )

        link_list = list(links) if links is not None else NSFNET_LINKS
        for ld in link_list:
            self.add_link(
                link_id=str(ld["id"]),
                source=int(ld["source"]),
                target=int(ld["target"]),
                length_km=float(ld["length_km"]),
                fiber_type=str(ld.get("fiber_type", FIBER_SMF)),
                span_types=ld.get("span_types", None),
                is_parallel=bool(ld.get("is_parallel", False)),
                is_bypass=bool(ld.get("is_bypass", False)),
            )

    def add_link(
        self,
        link_id: str,
        source: int,
        target: int,
        length_km: float,
        fiber_type: str = FIBER_SMF,
        span_types: Optional[Sequence[str]] = None,
        is_parallel: bool = False,
        is_bypass: bool = False,
    ) -> OpticalLink:
        """Agrega un enlace físico (primario, paralelo HCF o bypass HCF) a la topología."""
        if link_id in self.links:
            raise ValueError(f"El enlace con id '{link_id}' ya existe en la topología.")

        # Ignorar marcadores '...' provenientes de ejemplos abreviados en documentación
        cleaned_span_types: Optional[List[str]] = None
        if span_types is not None:
            valid_only = [s for s in span_types if s in VALID_FIBER_TYPES]
            expected_spans = calculate_num_spans(length_km, self.span_length_km)
            if len(valid_only) == expected_spans:
                cleaned_span_types = valid_only

        opt_link = OpticalLink(
            id=link_id,
            source=source,
            target=target,
            length_km=length_km,
            span_length_km=self.span_length_km,
            fiber_type=fiber_type,
            span_types=cleaned_span_types if cleaned_span_types else [],
            is_parallel=is_parallel,
            is_bypass=is_bypass,
            total_slots=self.total_slots,
        )
        self.links[link_id] = opt_link

        if self.graph.has_edge(source, target):
            # Ya existe un enlace entre (source, target): registrar como fibra paralela
            edge_data = self.graph[source][target]
            edge_data["parallel_links"].append(opt_link)
        else:
            self._k_sp_cache.clear()
            self.graph.add_edge(
                source,
                target,
                id=opt_link.id,
                length_km=opt_link.length_km,
                spans=opt_link.spans,
                fiber_type=opt_link.fiber_type,
                span_types=opt_link.span_types,
                is_parallel=opt_link.is_parallel,
                is_bypass=opt_link.is_bypass,
                primary_link=opt_link,
                parallel_links=[opt_link],
            )
        self._sync_edge_attributes(source, target)
        return opt_link

    def _sync_edge_attributes(self, u: int, v: int) -> None:
        """Sincroniza los atributos del borde (u, v) en self.graph con su OpticalLink primario."""
        if not self.graph.has_edge(u, v):
            return
        edge_data = self.graph[u][v]
        primary: OpticalLink = edge_data["primary_link"]
        edge_data["id"] = primary.id
        edge_data["length_km"] = primary.length_km
        edge_data["spans"] = primary.spans
        edge_data["fiber_type"] = primary.fiber_type
        edge_data["span_types"] = primary.span_types
        edge_data["is_parallel"] = primary.is_parallel
        edge_data["is_bypass"] = primary.is_bypass

    def get_link_by_id(self, link_id: str) -> OpticalLink:
        """Obtiene el objeto OpticalLink por su identificador único (ej. 'e0_1')."""
        if link_id not in self.links:
            raise KeyError(f"No existe el enlace '{link_id}' en la topología.")
        return self.links[link_id]

    def get_primary_link(self, u: int, v: int) -> OpticalLink:
        """Obtiene el enlace primario entre los nodos adyacentes (u, v)."""
        if not self.graph.has_edge(u, v):
            raise KeyError(f"No existe enlace entre los nodos ({u}, {v}).")
        return self.graph[u][v]["primary_link"]

    def get_links_between(self, u: int, v: int) -> List[OpticalLink]:
        """
        Retorna todos los enlaces activos entre (u, v) (incluyendo enlaces HCF
        paralelos instalados bajo Camino 2). Se ordenan priorizando enlaces HCF
        sobre SMF para favorecer mejor GSNR y menor consumo de FSUs.
        """
        if not self.graph.has_edge(u, v):
            raise KeyError(f"No existe enlace entre los nodos ({u}, {v}).")
        links_uv: List[OpticalLink] = list(self.graph[u][v]["parallel_links"])
        # Ordenar poniendo primero el enlace con mayor número de spans HCF
        links_uv.sort(key=lambda lk: lk.num_hcf_spans, reverse=True)
        return links_uv

    def set_link_fiber_type(
        self,
        link_or_nodes: Union[str, Tuple[int, int]],
        fiber_type: str = FIBER_HCF,
    ) -> OpticalLink:
        """
        Camino 1: Reemplaza la tecnología de fibra de un enlace completo (SMF -> HCF)
        manteniendo intactos los 320 FSUs de Banda C.
        """
        if isinstance(link_or_nodes, str):
            lk = self.get_link_by_id(link_or_nodes)
        else:
            u, v = link_or_nodes
            lk = self.get_primary_link(u, v)
        lk.set_fiber_type(fiber_type)
        self._sync_edge_attributes(lk.source, lk.target)
        return lk

    def set_link_span_types(
        self,
        link_or_nodes: Union[str, Tuple[int, int]],
        span_types: Sequence[str],
    ) -> OpticalLink:
        """Configura los tipos de fibra span por span (SMF / HCF) en un enlace."""
        if isinstance(link_or_nodes, str):
            lk = self.get_link_by_id(link_or_nodes)
        else:
            u, v = link_or_nodes
            lk = self.get_primary_link(u, v)
        lk.set_span_types(span_types)
        self._sync_edge_attributes(lk.source, lk.target)
        return lk

    def add_parallel_hcf_link(self, u: int, v: int) -> OpticalLink:
        """
        Camino 2: Conserva el enlace SMF original activo (evitando dark fiber)
        e instala en paralelo un nuevo enlace HCF e_HCF entre los mismos nodos (u, v)
        con sus propios 320 FSUs en Banda C.
        """
        primary = self.get_primary_link(u, v)
        u_min, v_max = min(u, v), max(u, v)
        existing_parallels = len(self.graph[u][v]["parallel_links"])
        new_id = f"e{u_min}_{v_max}_hcf_p{existing_parallels}"
        return self.add_link(
            link_id=new_id,
            source=u_min,
            target=v_max,
            length_km=primary.length_km,
            fiber_type=FIBER_HCF,
            is_parallel=True,
            is_bypass=False,
        )

    def add_bypass_hcf_link(
        self,
        u: int,
        v: int,
        length_km: Optional[float] = None,
    ) -> OpticalLink:
        """
        Camino 3: Crea un enlace directo nuevo HCF de larga distancia (bypass)
        entre dos nodos lejanos (u, v). Si no se especifica length_km, se estima
        como el 85% de la distancia de ruta más corta en la malla original (línea
        directa geográfica).
        """
        if u == v:
            raise ValueError("No se puede crear un bypass de un nodo hacia sí mismo.")
        u_min, v_max = min(u, v), max(u, v)
        if length_km is None:
            sp_dist = nx.shortest_path_length(self.graph, source=u_min, target=v_max, weight="length_km")
            # Distancia directa redondeada a múltiplos de span_length_km
            raw_direct = max(self.span_length_km, 0.85 * float(sp_dist))
            length_km = math.ceil(raw_direct / self.span_length_km) * self.span_length_km

        new_id = f"e{u_min}_{v_max}_bypass_hcf"
        suffix = 1
        while new_id in self.links:
            suffix += 1
            new_id = f"e{u_min}_{v_max}_bypass_hcf_{suffix}"

        return self.add_link(
            link_id=new_id,
            source=u_min,
            target=v_max,
            length_km=float(length_km),
            fiber_type=FIBER_HCF,
            is_parallel=self.graph.has_edge(u_min, v_max),
            is_bypass=True,
        )

    def compute_capex_cost(
        self,
        link_or_length_km: Union[str, OpticalLink, float],
        mode: str = "replace",
    ) -> float:
        """
        Calcula el costo incremental CAPEX en Unidades Relativas (UR) según Sección 9.1:
            C(e) = c_km * L(e) + C_amp * N_spans(e) + C_inst(modo)
        Donde:
            - c_km   = 1.0 UR/km
            - C_amp  = 15.0 UR/span
            - C_inst = 50.0 UR para ducto existente (mode in {'replace', 'parallel', 'mode_1', 'mode_2'})
                       150.0 UR para obra civil / ruta nueva bypass (mode in {'bypass', 'mode_3'})
        """
        if isinstance(link_or_length_km, str):
            lk = self.get_link_by_id(link_or_length_km)
            length_km = lk.length_km
            n_spans = lk.spans
        elif isinstance(link_or_length_km, OpticalLink):
            length_km = link_or_length_km.length_km
            n_spans = link_or_length_km.spans
        else:
            length_km = float(link_or_length_km)
            n_spans = calculate_num_spans(length_km, self.span_length_km)

        mode_norm = mode.strip().lower()
        if mode_norm in ("bypass", "mode_3", "mode_3_bypass_hcf", "camino_3"):
            c_inst = COST_INST_BYPASS_UR
        else:
            c_inst = COST_INST_DUCT_UR

        return float(
            COST_HCF_PER_KM_UR * length_km
            + COST_AMP_PER_SPAN_UR * n_spans
            + c_inst
        )

    def reset_spectrum(self) -> None:
        """Limpia la ocupación de los 320 FSUs en todos los enlaces de la red."""
        for lk in self.links.values():
            lk.reset_spectrum()

    def generate_annual_demands(
        self,
        year_k: int = 0,
        growth_rate: float = DEFAULT_ANNUAL_GROWTH_RATE,
        max_transponder_gbps: int = 400,
    ) -> List[DemandRequest]:
        """
        Genera la lista de conexiones solicitadas C(k) para la fotografía del año k:
            D_{u,v}(k) = D_{u,v}(0) * (1 + r)^k
        descomponiendo de forma acumulativa año a año (m = 0 .. k) en transpondedores
        discretos de {1000, 400, 100, 40, 10} Gbps (Sección 7.1). Esto garantiza que
        tanto el tráfico total como el número de conexiones solicitadas crezcan de
        forma estrictamente monótona con el año k y con la tasa r.
        """
        if year_k < 0:
            raise ValueError(f"El año k debe ser >= 0 (recibido: {year_k}).")

        requests: List[DemandRequest] = []
        uid_counter = 0
        r = float(growth_rate)

        for d0 in self.base_demands_d0:
            parent_id = str(d0["id"])
            u = int(d0["source"])
            v = int(d0["target"])
            base_gbps = float(d0["base_bitrate_gbps"])

            prev_quantized_gbps = 0
            conn_idx = 0
            for m in range(int(year_k) + 1):
                target_gbps = base_gbps * ((1.0 + r) ** m)
                quantized_gbps = max(10, int(round(target_gbps / 10.0) * 10))
                delta_gbps = quantized_gbps - prev_quantized_gbps
                prev_quantized_gbps = quantized_gbps

                if delta_gbps <= 0:
                    continue

                transponders = decompose_bitrate_to_transponders(
                    total_bitrate_gbps=float(delta_gbps),
                    allowed_bitrates=SUPPORTED_BITRATES_GBPS,
                    max_transponder_gbps=max_transponder_gbps,
                )
                for rate_gbps in transponders:
                    req_id = f"{parent_id}_k{year_k}_c{conn_idx}"
                    requests.append(
                        DemandRequest(
                            uid=uid_counter,
                            id=req_id,
                            parent_demand_id=parent_id,
                            source=u,
                            target=v,
                            bitrate_gbps=int(rate_gbps),
                            year_k=int(year_k),
                        )
                    )
                    uid_counter += 1
                    conn_idx += 1

        return requests

    def copy(self) -> "NetworkTopology":
        """Crea una copia profunda e independiente de la topología (compartiendo caché de rutas inmutable)."""
        cached_ksp = self._k_sp_cache
        self._k_sp_cache = {}
        try:
            cloned = copy.deepcopy(self)
        finally:
            self._k_sp_cache = cached_ksp
        cloned._k_sp_cache = dict(cached_ksp)
        return cloned

    def summary_dict(self) -> Dict[str, object]:
        """Retorna métricas agregadas del estado físico y espectral actual de la topología."""
        total_links = len(self.links)
        smf_links = sum(1 for lk in self.links.values() if lk.fiber_type == FIBER_SMF)
        hcf_links = sum(1 for lk in self.links.values() if lk.fiber_type == FIBER_HCF)
        hybrid_links = sum(1 for lk in self.links.values() if lk.fiber_type == "HYBRID")
        total_km = sum(lk.length_km for lk in self.links.values())
        hcf_km = sum(
            lk.length_km * (lk.num_hcf_spans / lk.spans) for lk in self.links.values()
        )
        total_used_fsus = sum(lk.used_slots for lk in self.links.values())
        total_capacity_fsus = total_links * self.total_slots

        return {
            "network_name": self.network_name,
            "num_nodes": self.graph.number_of_nodes(),
            "num_links": total_links,
            "smf_links": smf_links,
            "hcf_links": hcf_links,
            "hybrid_links": hybrid_links,
            "total_length_km": total_km,
            "hcf_length_km": hcf_km,
            "hcf_link_percentage": (100.0 * hcf_links / total_links) if total_links else 0.0,
            "total_used_fsus": total_used_fsus,
            "total_capacity_fsus": total_capacity_fsus,
            "global_spectrum_utilization_pct": (
                100.0 * total_used_fsus / total_capacity_fsus if total_capacity_fsus else 0.0
            ),
            "max_link_utilization_pct": (
                100.0 * max((lk.utilization for lk in self.links.values()), default=0.0)
            ),
        }

    def to_dict(self) -> Dict[str, object]:
        """Exporta la topología al esquema JSON exacto de la Sección 6."""
        nodes_out = [
            {
                "id": int(nid),
                "name": str(data.get("name", f"N{nid}")),
                "city": str(data.get("city", f"Node_{nid}")),
                "pos": list(data.get("pos", (0.0, 0.0))),
            }
            for nid, data in sorted(self.graph.nodes(data=True), key=lambda x: x[0])
        ]
        links_out = [lk.to_dict() for lk in self.links.values()]
        return {
            "network_name": self.network_name,
            "band": self.band,
            "total_slots": self.total_slots,
            "slot_width_ghz": self.slot_width_ghz,
            "guard_band_slots": self.guard_band_slots,
            "span_length_km": self.span_length_km,
            "nodes": nodes_out,
            "links": links_out,
            "base_demands_D0": copy.deepcopy(self.base_demands_d0),
        }


# =============================================================================
# FUNCIONES DE FÁBRICA Y PERSISTENCIA JSON (Sección 6 y 10)
# =============================================================================

def build_nsfnet_topology(span_length_km: float = DEFAULT_SPAN_LENGTH_KM) -> NetworkTopology:
    """Construye la topología NSFNet de 14 nodos y 21 enlaces bidireccionales en Banda C."""
    return NetworkTopology(
        network_name="NSFNet_14_Transport",
        nodes=NSFNET_NODES,
        links=NSFNET_LINKS,
        base_demands_d0=NSFNET_BASE_DEMANDS_D0,
        span_length_km=span_length_km,
    )


def build_cost239_topology(span_length_km: float = DEFAULT_SPAN_LENGTH_KM) -> NetworkTopology:
    """Construye la topología europea COST239 de 11 nodos y 26 enlaces bidireccionales."""
    return NetworkTopology(
        network_name="COST239_11_PanEuropean",
        nodes=COST239_NODES,
        links=COST239_LINKS,
        base_demands_d0=COST239_BASE_DEMANDS_D0,
        span_length_km=span_length_km,
    )


def build_ring5_test_topology(span_length_km: float = DEFAULT_SPAN_LENGTH_KM) -> NetworkTopology:
    """
    Construye un anillo de 5 nodos para verificación unitaria de continuidad
    y contigüidad espectral exigida en TEST-01 (Sección 11).
    """
    nodes = [{"id": i, "name": f"N{i}", "city": f"RingNode_{i}"} for i in range(5)]
    links = [
        {"id": "e0_1", "source": 0, "target": 1, "length_km": 300.0},
        {"id": "e1_2", "source": 1, "target": 2, "length_km": 300.0},
        {"id": "e2_3", "source": 2, "target": 3, "length_km": 300.0},
        {"id": "e3_4", "source": 3, "target": 4, "length_km": 300.0},
        {"id": "e0_4", "source": 0, "target": 4, "length_km": 300.0},
    ]
    demands = [
        {"id": "d_0_2", "source": 0, "target": 2, "base_bitrate_gbps": 400},
        {"id": "d_1_3", "source": 1, "target": 3, "base_bitrate_gbps": 400},
        {"id": "d_2_4", "source": 2, "target": 4, "base_bitrate_gbps": 100},
        {"id": "d_0_3", "source": 0, "target": 3, "base_bitrate_gbps": 100},
    ]
    return NetworkTopology(
        network_name="Ring_5_Unit_Test",
        nodes=nodes,
        links=links,
        base_demands_d0=demands,
        span_length_km=span_length_km,
    )


def ensure_default_topologies_json(
    json_path: Union[str, Path] = "data/topologies.json",
    span_length_km: float = DEFAULT_SPAN_LENGTH_KM,
) -> Path:
    """
    Genera (si no existe) el archivo JSON estándar `data/topologies.json`
    con NSFNet (14 nodos, 21 enlaces) y COST239 (11 nodos, 26 enlaces)
    siguiendo el formato de las Secciones 6 y 10.
    """
    path = Path(json_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    nsfnet = build_nsfnet_topology(span_length_km=span_length_km).to_dict()
    cost239 = build_cost239_topology(span_length_km=span_length_km).to_dict()

    payload = {
        "NSFNet_14_Transport": nsfnet,
        "COST239_11_PanEuropean": cost239,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_topology_from_json(
    json_path: Union[str, Path] = "data/topologies.json",
    network_name: str = "NSFNet_14_Transport",
    span_length_km: Optional[float] = None,
) -> NetworkTopology:
    """
    Carga una topología desde un archivo JSON (compatible tanto con un JSON de
    red única como el de la Sección 6, como con un catálogo multi-red en data/topologies.json).
    """
    path = Path(json_path)
    if not path.exists():
        ensure_default_topologies_json(path)

    raw = json.loads(path.read_text(encoding="utf-8"))
    if "network_name" in raw and "nodes" in raw and "links" in raw:
        net_data = raw
    elif network_name in raw:
        net_data = raw[network_name]
    else:
        raise KeyError(
            f"No se encontró la red '{network_name}' en {path}. "
            f"Redes disponibles: {list(raw.keys())}"
        )

    eff_span_km = (
        float(span_length_km)
        if span_length_km is not None
        else float(net_data.get("span_length_km", DEFAULT_SPAN_LENGTH_KM))
    )

    return NetworkTopology(
        network_name=str(net_data["network_name"]),
        nodes=net_data["nodes"],
        links=net_data["links"],
        base_demands_d0=net_data.get("base_demands_D0", NSFNET_BASE_DEMANDS_D0),
        span_length_km=eff_span_km,
        total_slots=int(net_data.get("total_slots", TOTAL_SLOTS)),
        slot_width_ghz=float(net_data.get("slot_width_ghz", SLOT_WIDTH_GHZ)),
        guard_band_slots=int(net_data.get("guard_band_slots", GUARD_BAND_SLOTS)),
    )
