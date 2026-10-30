"""
physics_qot.py
==============
Motor físico de Calidad de Transmisión (QoT) para Redes Ópticas Elásticas (EON).
Implementa:
1. Cálculo exacto de degradación acumulada de GSNR mediante la suma paralela
   inversa de ruido ASE + NLI por span (Pedro et al. [1], [3], Sección 3):
       GSNR_ruta(p)^(-1) = sum_{e in p} sum_{s=1}^{N_spans(e)} GSNR_span(tau(e, s))^(-1)
                         = sum_{e in p} [ N_spans(e) / GSNR_span(tau(e)) ]
2. Selección determinista del formato de modulación factible de mayor eficiencia
   espectral (64-QAM -> 32-QAM -> 16-QAM -> 8-QAM -> QPSK -> BPSK) que cumpla:
       GSNR_ruta^dB(p) >= SNR_th^dB(m)
3. Determinación de Frequency Slot Units (FSUs) requeridos según la Tabla Oficial
   del Taller 1 (Sección 4) más banda de guarda G = 1 slot (S_req = n_FSU + G).

Curso: TEL-317 Redes Ópticas WDM - UTFSM
Hito: Taller 3
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

import networkx as nx

from config import (
    DELTA_SNR_HCF_DB,
    FIBER_HCF,
    FIBER_SMF,
    GSNR_1SPAN_SMF_DB,
    GUARD_BAND_SLOTS,
    MODULATION_BY_NAME,
    MODULATION_FORMATS,
    ModulationFormatSpec,
    SLOT_WIDTH_GHZ,
    VALID_FIBER_TYPES,
)
from topology import NetworkTopology, OpticalLink


@dataclass(frozen=True)
class ModulationDecision:
    """
    Resultado de la evaluación física QoT y selección de formato de modulación
    para una ruta candidata p y una tasa de transmisión en Gbps.
    """
    feasible: bool
    modulation: Optional[str]
    spectral_efficiency_bps_hz: int
    snr_threshold_db: Optional[float]
    gsnr_db: float
    gsnr_margin_db: Optional[float]
    bitrate_gbps: int
    payload_fsus: int
    guard_band_fsus: int
    total_fsus_required: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "feasible": self.feasible,
            "modulation": self.modulation,
            "spectral_efficiency_bps_hz": self.spectral_efficiency_bps_hz,
            "snr_threshold_db": self.snr_threshold_db,
            "gsnr_db": round(self.gsnr_db, 4),
            "gsnr_margin_db": round(self.gsnr_margin_db, 4) if self.gsnr_margin_db is not None else None,
            "bitrate_gbps": self.bitrate_gbps,
            "payload_fsus": self.payload_fsus,
            "guard_band_fsus": self.guard_band_fsus,
            "total_fsus_required": self.total_fsus_required,
        }


# =============================================================================
# 1. FUNCIONES DE GSNR POR SPAN Y ACUMULACIÓN PARALELA INVERSA EN RUTA
# =============================================================================

def db_to_linear(val_db: float) -> float:
    """Convierte una relación señal a ruido de decibeles (dB) a escala lineal."""
    return 10.0 ** (float(val_db) / 10.0)


def linear_to_db(val_linear: float) -> float:
    """Convierte una relación señal a ruido de escala lineal a decibeles (dB)."""
    if val_linear <= 0.0:
        raise ValueError(f"El valor lineal de SNR debe ser > 0 (recibido: {val_linear}).")
    return 10.0 * math.log10(float(val_linear))


def get_span_gsnr_db(
    fiber_type: str,
    gsnr_1span_smf_db: float = GSNR_1SPAN_SMF_DB,
    delta_snr_hcf_db: float = DELTA_SNR_HCF_DB,
) -> float:
    """
    Retorna el GSNR en dB de un único span de amplificación según su tecnología:
        - SMF: GSNR_1,SMF^dB = 26.44 dB
        - HCF: GSNR_1,HCF^dB = GSNR_1,SMF^dB + Delta_SNR_HCF^dB
    """
    ft = fiber_type.strip().upper()
    if ft == FIBER_SMF:
        return float(gsnr_1span_smf_db)
    if ft == FIBER_HCF:
        return float(gsnr_1span_smf_db) + float(delta_snr_hcf_db)
    raise ValueError(
        f"Tecnología de span desconocida '{fiber_type}'. Valores permitidos: {VALID_FIBER_TYPES}."
    )


def get_span_gsnr_linear(
    fiber_type: str,
    gsnr_1span_smf_db: float = GSNR_1SPAN_SMF_DB,
    delta_snr_hcf_db: float = DELTA_SNR_HCF_DB,
) -> float:
    """
    Retorna el GSNR lineal de un único span:
        GSNR_span(tau) = P_tx / (P_ASE(tau) + P_NLI(tau)) = 10^(GSNR_span^dB(tau) / 10)
    """
    return db_to_linear(get_span_gsnr_db(fiber_type, gsnr_1span_smf_db, delta_snr_hcf_db))


def compute_spans_gsnr_db(
    span_types: Sequence[str],
    gsnr_1span_smf_db: float = GSNR_1SPAN_SMF_DB,
    delta_snr_hcf_db: float = DELTA_SNR_HCF_DB,
) -> float:
    """
    Calcula el GSNR acumulado en el receptor [dB] para una secuencia arbitraria
    de spans híbridos tau(s) in {'SMF', 'HCF'} mediante la suma paralela inversa:
        GSNR_ruta(p)^(-1) = sum_{s=1}^{N_spans} GSNR_span(tau(s))^(-1)
        GSNR_ruta^dB(p)   = 10 * log10(GSNR_ruta(p))
    """
    if not span_types:
        raise ValueError("La secuencia de spans no puede estar vacía.")

    inv_gsnr_sum = 0.0
    for st in span_types:
        gsnr_span_lin = get_span_gsnr_linear(st, gsnr_1span_smf_db, delta_snr_hcf_db)
        inv_gsnr_sum += 1.0 / gsnr_span_lin

    gsnr_route_linear = 1.0 / inv_gsnr_sum
    return linear_to_db(gsnr_route_linear)


def compute_hybrid_spans_gsnr_db(
    num_spans_smf: int,
    num_spans_hcf: int,
    gsnr_1span_smf_db: float = GSNR_1SPAN_SMF_DB,
    delta_snr_hcf_db: float = DELTA_SNR_HCF_DB,
) -> float:
    """
    Fórmula cerrada equivalente de suma paralela inversa para N_SMF spans de fibra
    monomodo estándar y N_HCF spans de fibra de núcleo hueco:
        GSNR_ruta(p)^(-1) = (N_SMF / GSNR_span(SMF)) + (N_HCF / GSNR_span(HCF))
    """
    if num_spans_smf < 0 or num_spans_hcf < 0 or (num_spans_smf + num_spans_hcf) == 0:
        raise ValueError(
            f"Número de spans inválido: num_spans_smf={num_spans_smf}, num_spans_hcf={num_spans_hcf}."
        )
    gsnr_smf_lin = get_span_gsnr_linear(FIBER_SMF, gsnr_1span_smf_db, delta_snr_hcf_db)
    gsnr_hcf_lin = get_span_gsnr_linear(FIBER_HCF, gsnr_1span_smf_db, delta_snr_hcf_db)

    inv_gsnr_sum = (float(num_spans_smf) / gsnr_smf_lin) + (float(num_spans_hcf) / gsnr_hcf_lin)
    return linear_to_db(1.0 / inv_gsnr_sum)


def extract_route_links(
    path: Sequence[Union[int, str, OpticalLink]],
    topology_or_graph: Optional[Union[NetworkTopology, nx.Graph]] = None,
) -> List[OpticalLink]:
    """
    Convierte una ruta expresada como:
      (a) lista de objetos OpticalLink,
      (b) lista de IDs de enlaces ['e0_1', 'e1_3', ...], o
      (c) lista de nodos [0, 1, 3, ...]
    en la lista ordenada de objetos OpticalLink que componen el camino.
    """
    if not path:
        raise ValueError("La ruta entregada está vacía.")

    first = path[0]
    if isinstance(first, OpticalLink):
        return list(path)  # type: ignore[arg-type]

    if isinstance(first, str):
        if not isinstance(topology_or_graph, NetworkTopology):
            raise ValueError("Se requiere una instancia de NetworkTopology para resolver IDs de enlaces.")
        return [topology_or_graph.get_link_by_id(str(lid)) for lid in path]

    # Caso (c): Secuencia de IDs de nodos [u_0, u_1, ..., u_m]
    if len(path) < 2:
        raise ValueError(f"Una ruta de nodos debe tener al menos 2 nodos (recibido: {path}).")

    if isinstance(topology_or_graph, NetworkTopology):
        links_out: List[OpticalLink] = []
        for i in range(len(path) - 1):
            u, v = int(path[i]), int(path[i + 1])
            # get_links_between retorna primero el enlace con mejor tecnología (HCF > SMF)
            links_out.append(topology_or_graph.get_links_between(u, v)[0])
        return links_out

    if isinstance(topology_or_graph, nx.Graph):
        links_out = []
        for i in range(len(path) - 1):
            u, v = int(path[i]), int(path[i + 1])
            if not topology_or_graph.has_edge(u, v):
                raise KeyError(f"No existe el enlace ({u}, {v}) en el grafo.")
            edge_data = topology_or_graph[u][v]
            if "primary_link" in edge_data:
                links_out.append(edge_data["primary_link"])
            else:
                # Construir OpticalLink temporal desde atributos del grafo
                lk = OpticalLink(
                    id=str(edge_data.get("id", f"e{min(u,v)}_{max(u,v)}")),
                    source=u,
                    target=v,
                    length_km=float(edge_data["length_km"]),
                    fiber_type=str(edge_data.get("fiber_type", FIBER_SMF)),
                    span_types=list(edge_data.get("span_types", [])),
                )
                links_out.append(lk)
        return links_out

    raise TypeError(
        "Se requiere `topology_or_graph` (NetworkTopology o nx.Graph) cuando `path` es una lista de nodos."
    )


def compute_path_gsnr_db(
    path: Sequence[Union[int, str, OpticalLink]],
    topology_or_graph: Optional[Union[NetworkTopology, nx.Graph]] = None,
    gsnr_1span_smf_db: float = GSNR_1SPAN_SMF_DB,
    delta_snr_hcf_db: float = DELTA_SNR_HCF_DB,
) -> float:
    """
    Calcula el GSNR acumulado en decibeles [dB] a lo largo de una ruta candidata p
    aplicando la ecuación de suma paralela inversa de Pedro et al. [1], [3] (Sección 3):
        GSNR_ruta(p)^(-1) = sum_{e in p} sum_{s=1}^{N_spans(e)} GSNR_span(tau(e, s))^(-1)
                          = sum_{e in p} [ N_spans(e) / GSNR_span(tau(e)) ]
    """
    links = extract_route_links(path, topology_or_graph)
    inv_gsnr_total = 0.0

    for lk in links:
        if lk.fiber_type in (FIBER_SMF, FIBER_HCF):
            # Todos los spans del enlace tienen la misma tecnología tau(e)
            gsnr_span_lin = get_span_gsnr_linear(lk.fiber_type, gsnr_1span_smf_db, delta_snr_hcf_db)
            inv_gsnr_total += float(lk.spans) / gsnr_span_lin
        else:
            # Enlace híbrido a nivel de spans individuales tau(e, s)
            for st in lk.span_types:
                gsnr_span_lin = get_span_gsnr_linear(st, gsnr_1span_smf_db, delta_snr_hcf_db)
                inv_gsnr_total += 1.0 / gsnr_span_lin

    gsnr_route_linear = 1.0 / inv_gsnr_total
    return linear_to_db(gsnr_route_linear)


# =============================================================================
# 2. DECISIÓN DE FORMATO DE MODULACIÓN Y CÁLCULO DE SLOTS (FSUs) (Sección 4)
# =============================================================================

def get_required_fsus(
    modulation_name: str,
    bitrate_gbps: int,
    include_guard_band: bool = False,
    guard_band_slots: int = GUARD_BAND_SLOTS,
) -> int:
    """
    Retorna el número de Frequency Slot Units (n_FSU) requerido para un formato
    de modulación m y una tasa de transmisión en Gbps según la Tabla Oficial de
    la Sección 4 (Datos Taller 1).

    Si la tasa solicitada no está directamente en las columnas discretas
    {10, 40, 100, 400, 1000} Gbps, aplica la fórmula física exacta de grilla
    de 12.5 GHz:
        n_FSU = ceil(bitrate_gbps / (eta_m * 12.5))
    """
    if modulation_name not in MODULATION_BY_NAME:
        raise KeyError(
            f"Formato de modulación '{modulation_name}' desconocido. "
            f"Opciones válidas: {list(MODULATION_BY_NAME.keys())}."
        )
    spec: ModulationFormatSpec = MODULATION_BY_NAME[modulation_name]
    bitrate_int = int(bitrate_gbps)

    if bitrate_int in spec.fsu_by_bitrate_gbps:
        n_fsu = spec.fsu_by_bitrate_gbps[bitrate_int]
    else:
        if bitrate_gbps <= 0:
            raise ValueError(f"bitrate_gbps debe ser > 0 (recibido: {bitrate_gbps}).")
        n_fsu = max(
            1,
            int(math.ceil(float(bitrate_gbps) / (spec.spectral_efficiency_bps_hz * SLOT_WIDTH_GHZ))),
        )

    if include_guard_band:
        return int(n_fsu + int(guard_band_slots))
    return int(n_fsu)


def select_modulation(
    gsnr_db: float,
    bitrate_gbps: int,
    guard_band_slots: int = GUARD_BAND_SLOTS,
) -> ModulationDecision:
    """
    Selecciona el formato de modulación m de MAYOR eficiencia espectral
    (evaluando en orden: 64-QAM -> 32-QAM -> 16-QAM -> 8-QAM -> QPSK -> BPSK)
    que cumpla la condición de factibilidad física de capa óptica (Sección 3 y 7.3):
        GSNR_ruta^dB(p) >= SNR_th^dB(m)

    Si ni siquiera BPSK (SNR_th = 5.3 dB) cumple el umbral, retorna
    `ModulationDecision(feasible=False, modulation=None, ...)`.
    """
    gsnr_val = float(gsnr_db)
    bitrate_int = int(bitrate_gbps)
    g_slots = int(guard_band_slots)

    for spec in MODULATION_FORMATS:
        # Tolerancia numérica IEEE 754 de 1e-9 dB para bordes exactos (ej. 130 spans = 5.30057 dB)
        if gsnr_val + 1e-9 >= spec.snr_threshold_db:
            n_fsu = get_required_fsus(
                spec.name,
                bitrate_int,
                include_guard_band=False,
                guard_band_slots=g_slots,
            )
            return ModulationDecision(
                feasible=True,
                modulation=spec.name,
                spectral_efficiency_bps_hz=spec.spectral_efficiency_bps_hz,
                snr_threshold_db=spec.snr_threshold_db,
                gsnr_db=gsnr_val,
                gsnr_margin_db=gsnr_val - spec.snr_threshold_db,
                bitrate_gbps=bitrate_int,
                payload_fsus=n_fsu,
                guard_band_fsus=g_slots,
                total_fsus_required=n_fsu + g_slots,
            )

    # Ningún formato cumple el umbral mínimo de BPSK (5.3 dB)
    return ModulationDecision(
        feasible=False,
        modulation=None,
        spectral_efficiency_bps_hz=0,
        snr_threshold_db=None,
        gsnr_db=gsnr_val,
        gsnr_margin_db=None,
        bitrate_gbps=bitrate_int,
        payload_fsus=0,
        guard_band_fsus=g_slots,
        total_fsus_required=0,
    )


def evaluate_path_qot(
    path: Sequence[Union[int, str, OpticalLink]],
    bitrate_gbps: int,
    topology_or_graph: Optional[Union[NetworkTopology, nx.Graph]] = None,
    gsnr_1span_smf_db: float = GSNR_1SPAN_SMF_DB,
    delta_snr_hcf_db: float = DELTA_SNR_HCF_DB,
    guard_band_slots: int = GUARD_BAND_SLOTS,
) -> ModulationDecision:
    """
    Evalúa de extremo a extremo una ruta candidata p: calcula su GSNR acumulado
    y retorna la decisión de formato de modulación y FSUs requeridos.
    """
    gsnr_db = compute_path_gsnr_db(
        path=path,
        topology_or_graph=topology_or_graph,
        gsnr_1span_smf_db=gsnr_1span_smf_db,
        delta_snr_hcf_db=delta_snr_hcf_db,
    )
    return select_modulation(
        gsnr_db=gsnr_db,
        bitrate_gbps=bitrate_gbps,
        guard_band_slots=guard_band_slots,
    )
