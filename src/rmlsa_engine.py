"""
src/rmlsa_engine.py
===================
Módulo puente compatible con la Sección 10 de la especificación técnica.
Re-exporta el motor estático k-SP + First-Fit implementado en `rmlsa_static.py`.
"""

from rmlsa_static import (
    ConnectionAllocationResult,
    REJECTION_NONE,
    REJECTION_QOT,
    REJECTION_SPECTRUM,
    STATUS_ALLOCATED,
    STATUS_REJECTED,
    StaticRMLSAResult,
    allocate_connection_first_fit,
    compute_k_shortest_node_paths,
    compute_path_availability_mask,
    expand_node_path_to_link_sequences,
    find_first_fit_contiguous_slots,
    precompute_all_k_shortest_paths,
    run_static_rmlsa,
    sort_demands_deterministically,
    verify_rmlsa_invariants,
)

__all__ = [
    "ConnectionAllocationResult",
    "REJECTION_NONE",
    "REJECTION_QOT",
    "REJECTION_SPECTRUM",
    "STATUS_ALLOCATED",
    "STATUS_REJECTED",
    "StaticRMLSAResult",
    "allocate_connection_first_fit",
    "compute_k_shortest_node_paths",
    "compute_path_availability_mask",
    "expand_node_path_to_link_sequences",
    "find_first_fit_contiguous_slots",
    "precompute_all_k_shortest_paths",
    "run_static_rmlsa",
    "sort_demands_deterministically",
    "verify_rmlsa_invariants",
]
