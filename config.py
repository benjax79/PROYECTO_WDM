"""
config.py
=========
Configuración global, constantes físicas de Banda C, tabla oficial de formatos
de modulación (Taller 1 / Sección 4), parámetros de costos CAPEX y definición
base de la topología NSFNet (14 nodos, 21 enlaces bidireccionales) para el
Simulador Estático de Migración SMF -> HCF en Redes Ópticas Elásticas (EON).

Curso: TEL-317 Redes Ópticas WDM - UTFSM
Hito: Taller 3
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple

# =============================================================================
# 1. PARÁMETROS ESPECTRALES DE BANDA C (EON - GRILLA FLEXIBLE ITU-T G.694.1)
# =============================================================================
BAND_NAME: str = "C"
BAND_MIN_FREQ_THZ: float = 191.3
BAND_TOTAL_WIDTH_GHZ: float = 4000.0  # 4.0 a 4.4 THz de ancho espectral (4 THz)
SLOT_WIDTH_GHZ: float = 12.5          # Ancho de cada Frequency Slot Unit (FSU)
TOTAL_SLOTS: int = 320                # Invariante física: 320 FSUs fijos para SMF y HCF
GUARD_BAND_SLOTS: int = 1             # G = 1 FSU de banda de guarda por conexión

# =============================================================================
# 2. PARÁMETROS FÍSICOS DE TRANSMISIÓN Y SPANS (SMF vs. HCF)
# =============================================================================
DEFAULT_SPAN_LENGTH_KM: float = 100.0  # Longitud estándar de span (soporta 80 - 100 km)
MIN_SPAN_LENGTH_KM: float = 80.0
MAX_SPAN_LENGTH_KM: float = 100.0

# Calibración exacta Sección 5 (consistente con Tabla de Banda C del curso):
# - 1 span de 100 km de fibra SMF de referencia tiene GSNR_1,SMF = 26.44 dB.
#   * 130 spans SMF -> 26.44 - 10*log10(130) = 5.30 dB (>= 5.3 dB para BPSK)
#   *  65 spans SMF -> 26.44 - 10*log10(65)  = 8.31 dB (>= 8.3 dB para QPSK)
#   *  17 spans SMF -> 26.44 - 10*log10(17)  = 14.14 dB (>= 14.0 dB para 16-QAM)
#   *   8 spans SMF -> 26.44 - 10*log10(8)   = 17.41 dB (>= 17.2 dB para 32-QAM)
#   *   4 spans SMF -> 26.44 - 10*log10(4)   = 20.42 dB (>= 19.8 dB para 64-QAM)
GSNR_1SPAN_SMF_DB: float = 26.44

# Ganancia neta de SNR por span al utilizar fibra de núcleo hueco (HCF):
# Rango físico típico según literatura [1]-[3]: +3.0 a +4.5 dB por menor NLI y figura de ruido.
DELTA_SNR_HCF_DB: float = 4.0
GSNR_1SPAN_HCF_DB: float = GSNR_1SPAN_SMF_DB + DELTA_SNR_HCF_DB

FIBER_SMF: str = "SMF"
FIBER_HCF: str = "HCF"
VALID_FIBER_TYPES: Tuple[str, str] = (FIBER_SMF, FIBER_HCF)

BER_TARGET: float = 4.7e-3  # Pre-FEC BER objetivo de referencia

# =============================================================================
# 3. TABLA OFICIAL DE FORMATOS DE MODULACIÓN, UMBRALES SNR Y DEMANDA DE FSUs
#    (Sección 4 - Datos Taller 1)
# =============================================================================
SUPPORTED_BITRATES_GBPS: Tuple[int, ...] = (1000, 400, 100, 40, 10)


@dataclass(frozen=True)
class ModulationFormatSpec:
    """Especificación física y espectral de un formato de modulación EON."""
    name: str
    spectral_efficiency_bps_hz: int
    snr_threshold_db: float
    max_spans_smf_100km: int
    mar_smf_km: int
    fsu_by_bitrate_gbps: Dict[int, int]


# Lista ordenada de MAYOR a MENOR eficiencia espectral (64-QAM -> BPSK)
# para evaluar primero el formato más eficiente en el motor QoT/RMLSA.
MODULATION_FORMATS: Tuple[ModulationFormatSpec, ...] = (
    ModulationFormatSpec(
        name="64-QAM",
        spectral_efficiency_bps_hz=6,
        snr_threshold_db=19.8,
        max_spans_smf_100km=4,
        mar_smf_km=125,
        fsu_by_bitrate_gbps={10: 1, 40: 1, 100: 2, 400: 6, 1000: 14},
    ),
    ModulationFormatSpec(
        name="32-QAM",
        spectral_efficiency_bps_hz=5,
        snr_threshold_db=17.2,
        max_spans_smf_100km=8,
        mar_smf_km=250,
        fsu_by_bitrate_gbps={10: 1, 40: 1, 100: 2, 400: 7, 1000: 16},
    ),
    ModulationFormatSpec(
        name="16-QAM",
        spectral_efficiency_bps_hz=4,
        snr_threshold_db=14.0,
        max_spans_smf_100km=17,
        mar_smf_km=500,
        fsu_by_bitrate_gbps={10: 1, 40: 1, 100: 2, 400: 8, 1000: 20},
    ),
    ModulationFormatSpec(
        name="8-QAM",
        spectral_efficiency_bps_hz=3,
        snr_threshold_db=11.4,
        max_spans_smf_100km=35,
        mar_smf_km=1000,
        fsu_by_bitrate_gbps={10: 1, 40: 2, 100: 3, 400: 11, 1000: 27},
    ),
    ModulationFormatSpec(
        name="QPSK",
        spectral_efficiency_bps_hz=2,
        snr_threshold_db=8.3,
        max_spans_smf_100km=65,
        mar_smf_km=2000,
        fsu_by_bitrate_gbps={10: 1, 40: 2, 100: 4, 400: 16, 1000: 40},
    ),
    ModulationFormatSpec(
        name="BPSK",
        spectral_efficiency_bps_hz=1,
        snr_threshold_db=5.3,
        max_spans_smf_100km=130,
        mar_smf_km=4000,
        fsu_by_bitrate_gbps={10: 1, 40: 4, 100: 8, 400: 32, 1000: 80},
    ),
)

MODULATION_BY_NAME: Dict[str, ModulationFormatSpec] = {
    m.name: m for m in MODULATION_FORMATS
}

# =============================================================================
# 4. PARÁMETROS DE RMLSA ESTÁTICO Y EVOLUCIÓN MULTI-AÑO DE DEMANDA
# =============================================================================
DEFAULT_K_PATHS: int = 3               # k = 3 rutas más cortas (k-SP)
DEFAULT_ANNUAL_GROWTH_RATE: float = 0.30  # r = 30% anual base [4]
SENSITIVITY_GROWTH_RATES: Tuple[float, ...] = (0.24, 0.30, 0.32)  # TeleGeography [5]
DEFAULT_HORIZON_YEARS: int = 8         # k = 0 ... 8 (o hasta 10)

# =============================================================================
# 5. PARÁMETROS DEL MODELO DE COSTOS INCREMENTALES CAPEX (Sección 9)
#    C(e) = c_km * L(e) + C_amp * N_spans(e) + C_inst(modo) [Unidades Relativas UR]
# =============================================================================
COST_HCF_PER_KM_UR: float = 1.0        # 1.0 UR/km de fibra HCF
COST_AMP_PER_SPAN_UR: float = 15.0     # 15.0 UR por amplificador adaptado
COST_INST_DUCT_UR: float = 50.0        # 50.0 UR usando ducto existente (Camino 1 y 2)
COST_INST_BYPASS_UR: float = 150.0     # 150.0 UR obra civil / derecho de paso (Camino 3)

# =============================================================================
# 6. DEFINICIÓN DE TOPOLOGÍA DE REFERENCIA: NSFNet (14 Nodos, 21 Enlaces)
# =============================================================================
NSFNET_NODES: List[Dict[str, object]] = [
    {"id": 0,  "name": "N0",  "city": "Seattle",        "pos": (1.0, 4.2)},
    {"id": 1,  "name": "N1",  "city": "Palo Alto",      "pos": (0.6, 2.8)},
    {"id": 2,  "name": "N2",  "city": "San Diego",      "pos": (1.2, 1.4)},
    {"id": 3,  "name": "N3",  "city": "Salt Lake City", "pos": (2.4, 2.9)},
    {"id": 4,  "name": "N4",  "city": "Boulder",        "pos": (3.5, 2.5)},
    {"id": 5,  "name": "N5",  "city": "Houston",        "pos": (3.8, 1.0)},
    {"id": 6,  "name": "N6",  "city": "Lincoln",        "pos": (4.7, 2.6)},
    {"id": 7,  "name": "N7",  "city": "Champaign",      "pos": (5.7, 3.2)},
    {"id": 8,  "name": "N8",  "city": "Pittsburgh",     "pos": (6.9, 3.1)},
    {"id": 9,  "name": "N9",  "city": "Atlanta",        "pos": (5.6, 0.9)},
    {"id": 10, "name": "N10", "city": "Ann Arbor",      "pos": (6.3, 4.5)},
    {"id": 11, "name": "N11", "city": "Ithaca",         "pos": (7.6, 4.4)},
    {"id": 12, "name": "N12", "city": "Princeton",      "pos": (8.3, 2.4)},
    {"id": 13, "name": "N13", "city": "College Park",   "pos": (7.6, 1.2)},
]

# 21 enlaces bidireccionales de NSFNet con longitudes reales en km
# (Consistente con diagrama del Taller 3 y JSON de la Sección 6: e0_1=1100km, e1_3=600km)
NSFNET_LINKS: List[Dict[str, object]] = [
    {"id": "e0_1",   "source": 0,  "target": 1,  "length_km": 1100.0},
    {"id": "e0_2",   "source": 0,  "target": 2,  "length_km": 1600.0},
    {"id": "e0_7",   "source": 0,  "target": 7,  "length_km": 2800.0},
    {"id": "e1_2",   "source": 1,  "target": 2,  "length_km": 600.0},
    {"id": "e1_3",   "source": 1,  "target": 3,  "length_km": 600.0},
    {"id": "e2_5",   "source": 2,  "target": 5,  "length_km": 2000.0},
    {"id": "e3_4",   "source": 3,  "target": 4,  "length_km": 600.0},
    {"id": "e3_10",  "source": 3,  "target": 10, "length_km": 2400.0},
    {"id": "e4_5",   "source": 4,  "target": 5,  "length_km": 1100.0},
    {"id": "e4_6",   "source": 4,  "target": 6,  "length_km": 800.0},
    {"id": "e5_9",   "source": 5,  "target": 9,  "length_km": 1100.0},
    {"id": "e5_13",  "source": 5,  "target": 13, "length_km": 2000.0},
    {"id": "e6_7",   "source": 6,  "target": 7,  "length_km": 700.0},
    {"id": "e7_8",   "source": 7,  "target": 8,  "length_km": 700.0},
    {"id": "e8_9",   "source": 8,  "target": 9,  "length_km": 900.0},
    {"id": "e8_11",  "source": 8,  "target": 11, "length_km": 300.0},
    {"id": "e8_12",  "source": 8,  "target": 12, "length_km": 500.0},
    {"id": "e10_11", "source": 10, "target": 11, "length_km": 600.0},
    {"id": "e10_12", "source": 10, "target": 12, "length_km": 800.0},
    {"id": "e11_13", "source": 11, "target": 13, "length_km": 500.0},
    {"id": "e12_13", "source": 12, "target": 13, "length_km": 300.0},
]

# Matriz de demanda base D(0) para NSFNet calibrada para que en el año k = 0
# (red 100% SMF) haya exactamente 0 conexiones fuera y una utilización inicial
# alta en Banda C (~75-85% en enlaces troncales), generando saturación
# progresiva y monótona al crecer a tasa r = 30% anual en k = 1 ... 8.
NSFNET_BASE_DEMANDS_D0: List[Dict[str, object]] = [
    # Tráfico transcontinental Costa Oeste <-> Costa Este y Medio Oeste
    {"id": "d_0_12",  "source": 0,  "target": 12, "base_bitrate_gbps": 400},
    {"id": "d_2_11",  "source": 2,  "target": 11, "base_bitrate_gbps": 800},
    {"id": "d_1_12",  "source": 1,  "target": 12, "base_bitrate_gbps": 800},
    {"id": "d_1_11",  "source": 1,  "target": 11, "base_bitrate_gbps": 600},
    {"id": "d_0_8",   "source": 0,  "target": 8,  "base_bitrate_gbps": 600},
    {"id": "d_2_13",  "source": 2,  "target": 13, "base_bitrate_gbps": 600},
    {"id": "d_1_8",   "source": 1,  "target": 8,  "base_bitrate_gbps": 800},
    {"id": "d_3_12",  "source": 3,  "target": 12, "base_bitrate_gbps": 800},
    {"id": "d_4_11",  "source": 4,  "target": 11, "base_bitrate_gbps": 600},
    {"id": "d_4_12",  "source": 4,  "target": 12, "base_bitrate_gbps": 600},
    # Tráfico dorsal central (Nodos 3, 4, 5, 6, 7, 8, 9, 10)
    {"id": "d_0_3",   "source": 0,  "target": 3,  "base_bitrate_gbps": 600},
    {"id": "d_1_4",   "source": 1,  "target": 4,  "base_bitrate_gbps": 800},
    {"id": "d_2_4",   "source": 2,  "target": 4,  "base_bitrate_gbps": 600},
    {"id": "d_3_7",   "source": 3,  "target": 7,  "base_bitrate_gbps": 800},
    {"id": "d_4_8",   "source": 4,  "target": 8,  "base_bitrate_gbps": 800},
    {"id": "d_5_8",   "source": 5,  "target": 8,  "base_bitrate_gbps": 600},
    {"id": "d_5_12",  "source": 5,  "target": 12, "base_bitrate_gbps": 800},
    {"id": "d_6_12",  "source": 6,  "target": 12, "base_bitrate_gbps": 600},
    {"id": "d_7_12",  "source": 7,  "target": 12, "base_bitrate_gbps": 800},
    {"id": "d_7_13",  "source": 7,  "target": 13, "base_bitrate_gbps": 600},
    # Tráfico regional de alta capacidad
    {"id": "d_0_1",   "source": 0,  "target": 1,  "base_bitrate_gbps": 600},
    {"id": "d_1_2",   "source": 1,  "target": 2,  "base_bitrate_gbps": 600},
    {"id": "d_3_10",  "source": 3,  "target": 10, "base_bitrate_gbps": 600},
    {"id": "d_6_8",   "source": 6,  "target": 8,  "base_bitrate_gbps": 600},
    {"id": "d_8_12",  "source": 8,  "target": 12, "base_bitrate_gbps": 800},
    {"id": "d_9_13",  "source": 9,  "target": 13, "base_bitrate_gbps": 600},
    {"id": "d_10_12", "source": 10, "target": 12, "base_bitrate_gbps": 800},
    {"id": "d_11_13", "source": 11, "target": 13, "base_bitrate_gbps": 600},
]

# Topología secundaria opcional: COST239 / Pan-European (11 nodos, 26 enlaces)
COST239_NODES: List[Dict[str, object]] = [
    {"id": 0,  "name": "N0",  "city": "London",     "pos": (1.5, 4.0)},
    {"id": 1,  "name": "N1",  "city": "Paris",      "pos": (2.0, 2.8)},
    {"id": 2,  "name": "N2",  "city": "Brussels",   "pos": (2.6, 3.6)},
    {"id": 3,  "name": "N3",  "city": "Amsterdam",  "pos": (2.9, 4.4)},
    {"id": 4,  "name": "N4",  "city": "Copenhagen", "pos": (4.5, 5.2)},
    {"id": 5,  "name": "N5",  "city": "Berlin",     "pos": (5.0, 4.0)},
    {"id": 6,  "name": "N6",  "city": "Frankfurt",  "pos": (3.8, 3.2)},
    {"id": 7,  "name": "N7",  "city": "Prague",     "pos": (5.4, 3.0)},
    {"id": 8,  "name": "N8",  "city": "Zurich",     "pos": (3.5, 2.0)},
    {"id": 9,  "name": "N9",  "city": "Milan",      "pos": (4.0, 1.0)},
    {"id": 10, "name": "N10", "city": "Vienna",     "pos": (5.8, 2.0)},
]

COST239_LINKS: List[Dict[str, object]] = [
    {"id": "e0_1",  "source": 0, "target": 1,  "length_km": 400.0},
    {"id": "e0_2",  "source": 0, "target": 2,  "length_km": 350.0},
    {"id": "e0_3",  "source": 0, "target": 3,  "length_km": 400.0},
    {"id": "e0_4",  "source": 0, "target": 4,  "length_km": 1000.0},
    {"id": "e1_2",  "source": 1, "target": 2,  "length_km": 300.0},
    {"id": "e1_6",  "source": 1, "target": 6,  "length_km": 500.0},
    {"id": "e1_8",  "source": 1, "target": 8,  "length_km": 500.0},
    {"id": "e1_9",  "source": 1, "target": 9,  "length_km": 650.0},
    {"id": "e2_3",  "source": 2, "target": 3,  "length_km": 200.0},
    {"id": "e2_6",  "source": 2, "target": 6,  "length_km": 350.0},
    {"id": "e2_8",  "source": 2, "target": 8,  "length_km": 500.0},
    {"id": "e3_4",  "source": 3, "target": 4,  "length_km": 650.0},
    {"id": "e3_5",  "source": 3, "target": 5,  "length_km": 600.0},
    {"id": "e3_6",  "source": 3, "target": 6,  "length_km": 400.0},
    {"id": "e4_5",  "source": 4, "target": 5,  "length_km": 400.0},
    {"id": "e4_7",  "source": 4, "target": 7,  "length_km": 650.0},
    {"id": "e5_6",  "source": 5, "target": 6,  "length_km": 450.0},
    {"id": "e5_7",  "source": 5, "target": 7,  "length_km": 300.0},
    {"id": "e5_10", "source": 5, "target": 10, "length_km": 550.0},
    {"id": "e6_7",  "source": 6, "target": 7,  "length_km": 450.0},
    {"id": "e6_8",  "source": 6, "target": 8,  "length_km": 350.0},
    {"id": "e7_8",  "source": 7, "target": 8,  "length_km": 550.0},
    {"id": "e7_10", "source": 7, "target": 10, "length_km": 300.0},
    {"id": "e8_9",  "source": 8, "target": 9,  "length_km": 250.0},
    {"id": "e8_10", "source": 8, "target": 10, "length_km": 600.0},
    {"id": "e9_10", "source": 9, "target": 10, "length_km": 650.0},
]

COST239_BASE_DEMANDS_D0: List[Dict[str, object]] = [
    {"id": "d_0_9",  "source": 0, "target": 9,  "base_bitrate_gbps": 400},
    {"id": "d_0_10", "source": 0, "target": 10, "base_bitrate_gbps": 400},
    {"id": "d_1_5",  "source": 1, "target": 5,  "base_bitrate_gbps": 400},
    {"id": "d_1_10", "source": 1, "target": 10, "base_bitrate_gbps": 300},
    {"id": "d_2_9",  "source": 2, "target": 9,  "base_bitrate_gbps": 300},
    {"id": "d_3_9",  "source": 3, "target": 9,  "base_bitrate_gbps": 300},
    {"id": "d_4_9",  "source": 4, "target": 9,  "base_bitrate_gbps": 300},
    {"id": "d_4_10", "source": 4, "target": 10, "base_bitrate_gbps": 300},
    {"id": "d_0_5",  "source": 0, "target": 5,  "base_bitrate_gbps": 300},
    {"id": "d_0_7",  "source": 0, "target": 7,  "base_bitrate_gbps": 200},
    {"id": "d_1_7",  "source": 1, "target": 7,  "base_bitrate_gbps": 200},
    {"id": "d_3_10", "source": 3, "target": 10, "base_bitrate_gbps": 200},
]
