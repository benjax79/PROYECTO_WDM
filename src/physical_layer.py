"""
src/physical_layer.py
=====================
Módulo puente compatible con la Sección 10 de la especificación técnica.
Re-exporta todas las funciones y tablas físicas implementadas en `physics_qot.py` y `config.py`.
"""

from config import (
    DELTA_SNR_HCF_DB,
    FIBER_HCF,
    FIBER_SMF,
    GSNR_1SPAN_HCF_DB,
    GSNR_1SPAN_SMF_DB,
    GUARD_BAND_SLOTS,
    MODULATION_BY_NAME,
    MODULATION_FORMATS,
    ModulationFormatSpec,
    SLOT_WIDTH_GHZ,
    SUPPORTED_BITRATES_GBPS,
    TOTAL_SLOTS,
)
from physics_qot import (
    ModulationDecision,
    compute_hybrid_spans_gsnr_db,
    compute_path_gsnr_db,
    compute_spans_gsnr_db,
    db_to_linear,
    evaluate_path_qot,
    extract_route_links,
    get_required_fsus,
    get_span_gsnr_db,
    get_span_gsnr_linear,
    linear_to_db,
    select_modulation,
)

__all__ = [
    "DELTA_SNR_HCF_DB",
    "FIBER_HCF",
    "FIBER_SMF",
    "GSNR_1SPAN_HCF_DB",
    "GSNR_1SPAN_SMF_DB",
    "GUARD_BAND_SLOTS",
    "MODULATION_BY_NAME",
    "MODULATION_FORMATS",
    "ModulationFormatSpec",
    "SLOT_WIDTH_GHZ",
    "SUPPORTED_BITRATES_GBPS",
    "TOTAL_SLOTS",
    "ModulationDecision",
    "compute_hybrid_spans_gsnr_db",
    "compute_path_gsnr_db",
    "compute_spans_gsnr_db",
    "db_to_linear",
    "evaluate_path_qot",
    "extract_route_links",
    "get_required_fsus",
    "get_span_gsnr_db",
    "get_span_gsnr_linear",
    "linear_to_db",
    "select_modulation",
]
