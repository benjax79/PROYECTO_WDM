"""
test_simulator.py
=================
Script de prueba integral y validación funcional para la arquitectura base del
Simulador Estático EON SMF/HCF (Taller 3 - TEL-317 Redes Ópticas WDM):
  - Prueba 1 (TEST-01): Carga de JSON NSFNet (14 nodos, 21 enlaces), cálculo de
    spans (80 km y 100 km), y verificación unitaria de continuidad, contigüidad
    y asignación First-Fit sobre los 320 FSUs de Banda C (en anillo de 5 nodos
    y malla NSFNet) con 0 colisiones espectrales.
  - Prueba 2 (TEST-02): Verificación matemática del modelo físico de acumulación
    paralela inversa de GSNR (SMF -> Híbrida 50/50 -> 100% HCF), validación de la
    Tabla de Modulaciones (BPSK a 64-QAM) y salto de QPSK a 16-QAM reduciendo los
    FSUs a la mitad.
  - Prueba 3: Demostración end-to-end del impacto de migrar enlaces troncales de
    SMF a HCF en NSFNet ante crecimiento de tráfico (reducción de FSUs y de
    Conexiones Fuera).
"""

from __future__ import annotations
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from config import (
    DELTA_SNR_HCF_DB,
    FIBER_HCF,
    FIBER_SMF,
    GSNR_1SPAN_SMF_DB,
    MODULATION_FORMATS,
    SUPPORTED_BITRATES_GBPS,
    TOTAL_SLOTS,
)
from physics_qot import (
    compute_hybrid_spans_gsnr_db,
    compute_path_gsnr_db,
    evaluate_path_qot,
    get_required_fsus,
    select_modulation,
)
from rmlsa_static import run_static_rmlsa, verify_rmlsa_invariants
from topology import (
    build_nsfnet_topology,
    build_ring5_test_topology,
    calculate_num_spans,
    ensure_default_topologies_json,
    load_topology_from_json,
)


def print_banner(title: str) -> None:
    print("\n" + "=" * 88)
    print(f" {title}")
    print("=" * 88)


def test_01_topology_and_first_fit_continuity() -> None:
    """
    TEST-01: Carga de JSON (NSFNet 14 nodos), cálculo de spans (80-100 km) y
    verificación unitaria de continuidad y contigüidad en anillo de 5 nodos y malla.
    """
    print_banner("TEST-01: TOPOLOGÍA NSFNET (JSON), SPANS (80-100 km) Y ASIGNACIÓN FIRST-FIT")

    json_path = ensure_default_topologies_json("data/topologies.json")
    topo_100 = load_topology_from_json(json_path, network_name="NSFNet_14_Transport", span_length_km=100.0)
    topo_80 = load_topology_from_json(json_path, network_name="NSFNet_14_Transport", span_length_km=80.0)

    assert topo_100.graph.number_of_nodes() == 14, "NSFNet debe tener 14 nodos."
    assert len(topo_100.links) == 21, "NSFNet debe tener 21 enlaces bidireccionales."
    assert calculate_num_spans(1100.0, 100.0) == 11
    assert calculate_num_spans(1100.0, 80.0) == 14

    print(f"[OK] Archivo JSON cargado desde: {json_path.resolve()}")
    print(
        f"[OK] Red: {topo_100.network_name} | Nodos: {topo_100.graph.number_of_nodes()} | "
        f"Enlaces bidireccionales: {len(topo_100.links)} | Banda: {topo_100.band} ({topo_100.total_slots} FSUs)"
    )
    print(
        f"[OK] Verificación de spans en enlace e0_1 (1100 km): "
        f"L_span=100 km -> {topo_100.get_link_by_id('e0_1').spans} spans | "
        f"L_span=80 km -> {topo_80.get_link_by_id('e0_1').spans} spans"
    )

    # 1.A Verificación unitaria en Anillo de 5 Nodos (solapamiento de rutas)
    print("\n--- 1.A Verificación Unitaria de Continuidad y Contigüidad en Anillo de 5 Nodos ---")
    ring5 = build_ring5_test_topology(span_length_km=100.0)
    res_ring = run_static_rmlsa(ring5, year_k=0, k_paths=2, verify_invariants=True)

    print(f"{'Conexión':<15} {'Origen->Dest':<14} {'Tasa':<8} {'Ruta Nodos':<15} {'Enlaces':<18} {'Modulación':<10} {'GSNR [dB]':<11} {'Slots [s*, s_end]':<18}")
    print("-" * 115)
    for alloc in res_ring.allocations:
        slots_str = f"[{alloc.start_slot}, {alloc.end_slot}] ({alloc.total_fsus} FSUs)"
        print(
            f"{alloc.demand_id:<15} {f'{alloc.source}->{alloc.target}':<14} "
            f"{f'{alloc.bitrate_gbps}G':<8} {str(alloc.path_nodes):<15} "
            f"{','.join(alloc.path_link_ids):<18} {str(alloc.modulation):<10} "
            f"{alloc.gsnr_db:<11.2f} {slots_str:<18}"
        )

    print("\nEstado de los primeros 20 FSUs de los 320 slots por enlace en Ring_5 (-1 = libre, >=0 = ID conexión):")
    for lid, lk in ring5.links.items():
        print(f"  Enlace {lid} ({lk.length_km:.0f} km, {lk.fiber_type}, {lk.total_slots} FSUs): {lk.spectrum_owner[:20].tolist()}")

    # 1.B Fotografía Base Año k = 0 sobre Malla NSFNet (14 nodos, 21 enlaces)
    print("\n--- 1.B Fotografía Base Año k = 0 en Malla NSFNet (14 Nodos, 21 Enlaces, 100% SMF) ---")
    res_nsf_k0 = run_static_rmlsa(topo_100, year_k=0, k_paths=3, verify_invariants=True)
    assert res_nsf_k0.rejected_connections == 0, "En k = 0 debe haber 0 Conexiones Fuera."
    assert res_nsf_k0.invariants_verified is True

    print(
        f"[OK] Año k=0 | Conexiones Solicitadas: {res_nsf_k0.total_connections_requested} | "
        f"Atendidas: {res_nsf_k0.allocated_connections} | "
        f"Conexiones Fuera: {res_nsf_k0.rejected_connections} (0 colisiones espectrales)"
    )
    print(
        f"[OK] Tráfico Total Atendido: {res_nsf_k0.served_traffic_gbps:.0f} Gbps "
        f"({res_nsf_k0.served_traffic_gbps / 1000.0:.2f} Tbps) | "
        f"Ocupación Global Banda C: {res_nsf_k0.global_spectrum_utilization_pct:.2f}% | "
        f"Enlace más cargado: {res_nsf_k0.bottleneck_link_id} ({res_nsf_k0.max_link_utilization_pct:.2f}%)"
    )
    print(f"[OK] Distribución de Formatos de Modulación en k=0: {res_nsf_k0.modulation_distribution}")


def test_02_physical_layer_gsnr_and_modulation_table() -> None:
    """
    TEST-02: Verificación matemática de la Capa Física GSNR (suma paralela inversa),
    calibración exacta de alcances en Banda C (Sección 4 y 5) y evaluación de rutas
    pasando de 100% SMF a Híbrida (50% SMF + 50% HCF) y 100% HCF.
    """
    print_banner("TEST-02: VERIFICACIÓN FÍSICA DE GSNR (SUMA PARALELA INVERSA) Y MODULACIONES")

    # 2.A Verificación de calibración exacta con la Tabla de la Sección 4 y 5
    print("--- 2.A Verificación de Calibración Exacta de Alcance SMF (GSNR_1,SMF = 26.44 dB) ---")
    print(
        f"{'Modulación':<10} {'Eficiencia':<12} {'Umbral SNR_th':<15} "
        f"{'Spans Tabla 4':<15} {'Spans Exactos':<15} {'GSNR Exacto':<14} {'FSUs (10/40/100/400/1000G)'}"
    )
    print("-" * 112)
    for spec in reversed(MODULATION_FORMATS):
        exact_max_spans = int(10.0 ** ((GSNR_1SPAN_SMF_DB - spec.snr_threshold_db) / 10.0))
        gsnr_at_reach = compute_hybrid_spans_gsnr_db(
            num_spans_smf=exact_max_spans,
            num_spans_hcf=0,
        )
        decision = select_modulation(gsnr_at_reach, bitrate_gbps=100)
        assert decision.feasible and decision.modulation == spec.name, (
            f"Fallo de calibración en {spec.name}: GSNR={gsnr_at_reach:.2f} dB"
        )
        fsu_tuple = tuple(get_required_fsus(spec.name, b) for b in (10, 40, 100, 400, 1000))
        print(
            f"{spec.name:<10} {f'{spec.spectral_efficiency_bps_hz} bit/s/Hz':<12} "
            f"{f'{spec.snr_threshold_db:.1f} dB':<15} "
            f"{f'{spec.max_spans_smf_100km} spans':<15} "
            f"{f'{exact_max_spans} spans':<15} "
            f"{f'{gsnr_at_reach:.2f} dB':<14} {str(fsu_tuple)}"
        )

    # 2.B Evaluación de Ruta de 1800 km (18 spans: N2 -> N1 -> N3 -> N4) y Ruta Larga de 3600 km (36 spans: N0 -> N2 -> N5)
    print("\n--- 2.B Evaluación de Rutas en NSFNet: 100% SMF vs. Híbrida (50% SMF + 50% HCF) vs. 100% HCF ---")
    topo = build_nsfnet_topology(span_length_km=100.0)

    # Caso 1: Ruta de 1800 km (18 spans) en NSFNet: N2 -> N1 -> N3 -> N4 (600 + 600 + 600 km)
    route_1800_nodes = [2, 1, 3, 4]
    route_1800_links = ["e1_2", "e1_3", "e3_4"]

    # Escenario 1: 100% SMF (18 spans SMF)
    qot_18_smf = evaluate_path_qot(route_1800_nodes, bitrate_gbps=400, topology_or_graph=topo)

    # Escenario 2: Híbrida 50% SMF + 50% HCF (9 spans SMF + 9 spans HCF)
    topo_hyb = topo.copy()
    topo_hyb.set_link_fiber_type("e1_2", FIBER_HCF)  # 6 spans HCF
    topo_hyb.get_link_by_id("e1_3").set_span_types([FIBER_HCF] * 3 + [FIBER_SMF] * 3)  # 3 HCF + 3 SMF
    # e3_4 permanece con 6 spans SMF -> Total = 9 spans HCF + 9 spans SMF
    qot_18_hyb = evaluate_path_qot(route_1800_nodes, bitrate_gbps=400, topology_or_graph=topo_hyb)

    # Escenario 3: 100% HCF (18 spans HCF)
    topo_hcf = topo.copy()
    for lid in route_1800_links:
        topo_hcf.set_link_fiber_type(lid, FIBER_HCF)
    qot_18_hcf = evaluate_path_qot(route_1800_nodes, bitrate_gbps=400, topology_or_graph=topo_hcf)

    print("\n[Ruta A: N2 -> N1 -> N3 -> N4 | 1800 km (18 spans de 100 km) | Demanda: 400 Gbps]")
    for label, qot in [
        ("100% SMF (18 SMF, 0 HCF)", qot_18_smf),
        ("Híbrida 50/50 (9 SMF, 9 HCF)", qot_18_hyb),
        ("100% HCF (0 SMF, 18 HCF)", qot_18_hcf),
    ]:
        print(
            f"  {label:<30} -> GSNR = {qot.gsnr_db:6.2f} dB | "
            f"Modulación = {str(qot.modulation):<7} | "
            f"FSUs = {qot.payload_fsus} (+{qot.guard_band_fsus} guarda = {qot.total_fsus_required} slots)"
        )

    # Caso 2: Ruta Transcontinental de 3600 km (36 spans: N0 -> N2 -> N5: 1600 + 2000 km)
    # Muestra el salto exacto de QPSK (16 FSUs @ 400G / 4 FSUs @ 100G) a 16-QAM (8 FSUs @ 400G / 2 FSUs @ 100G)
    print("\n[Ruta B: N0 -> N2 -> N5 | 3600 km (36 spans de 100 km) | Demanda: 400 Gbps (Salto QPSK -> 16-QAM)]")
    gsnr_36_smf = compute_hybrid_spans_gsnr_db(36, 0)
    gsnr_36_hyb = compute_hybrid_spans_gsnr_db(18, 18)
    gsnr_36_hcf = compute_hybrid_spans_gsnr_db(0, 36)

    qot_36_smf = select_modulation(gsnr_36_smf, bitrate_gbps=400)
    qot_36_hyb = select_modulation(gsnr_36_hyb, bitrate_gbps=400)
    qot_36_hcf = select_modulation(gsnr_36_hcf, bitrate_gbps=400)

    assert qot_36_smf.modulation == "QPSK" and qot_36_smf.payload_fsus == 16
    assert qot_36_hcf.modulation == "16-QAM" and qot_36_hcf.payload_fsus == 8

    for label, qot in [
        ("100% SMF (36 SMF, 0 HCF)", qot_36_smf),
        ("Híbrida 50/50 (18 SMF, 18 HCF)", qot_36_hyb),
        ("100% HCF (0 SMF, 36 HCF)", qot_36_hcf),
    ]:
        print(
            f"  {label:<30} -> GSNR = {qot.gsnr_db:6.2f} dB | "
            f"Modulación = {str(qot.modulation):<7} | "
            f"FSUs = {qot.payload_fsus} (+{qot.guard_band_fsus} guarda = {qot.total_fsus_required} slots)"
        )

    # Generar gráfico de validación física fig1_validacion_gsnr.png (TEST-02)
    out_dir = Path("results")
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_path = out_dir / "fig1_validacion_gsnr.png"

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=150)
    stages = ["100% SMF", "Híbrida\n(50% SMF + 50% HCF)", "100% HCF"]

    # Subplot 1: Ruta 1800 km (18 spans) y 3600 km (36 spans) GSNR [dB]
    x = np.arange(len(stages))
    width = 0.35
    b1 = ax1.bar(
        x - width / 2,
        [qot_18_smf.gsnr_db, qot_18_hyb.gsnr_db, qot_18_hcf.gsnr_db],
        width,
        label="Ruta 1800 km (18 spans)",
        color="#1f77b4",
    )
    b2 = ax1.bar(
        x + width / 2,
        [qot_36_smf.gsnr_db, qot_36_hyb.gsnr_db, qot_36_hcf.gsnr_db],
        width,
        label="Ruta 3600 km (36 spans)",
        color="#2ca02c",
    )
    ax1.axhline(14.0, color="#d62728", linestyle="--", linewidth=1.2, label="Umbral 16-QAM (14.0 dB)")
    ax1.axhline(11.4, color="#ff7f0e", linestyle=":", linewidth=1.2, label="Umbral 8-QAM (11.4 dB)")
    ax1.axhline(8.3, color="#9467bd", linestyle="-.", linewidth=1.2, label="Umbral QPSK (8.3 dB)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(stages)
    ax1.set_ylabel("GSNR Acumulado en Receptor [dB]")
    ax1.set_title("TEST-02: Mejora de GSNR por Suma Paralela Inversa")
    ax1.set_ylim(0, 22)
    ax1.grid(axis="y", alpha=0.3)
    ax1.legend(loc="upper left", fontsize=8)

    for bars, qots in [(b1, [qot_18_smf, qot_18_hyb, qot_18_hcf]), (b2, [qot_36_smf, qot_36_hyb, qot_36_hcf])]:
        for bar, q in zip(bars, qots):
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.35,
                f"{q.gsnr_db:.1f} dB\n({q.modulation})",
                ha="center",
                va="bottom",
                fontsize=7.5,
                fontweight="bold",
            )

    # Subplot 2: Reducción de FSUs requeridos para 400 Gbps
    b3 = ax2.bar(
        x - width / 2,
        [qot_18_smf.payload_fsus, qot_18_hyb.payload_fsus, qot_18_hcf.payload_fsus],
        width,
        label="Ruta 1800 km (400G)",
        color="#1f77b4",
    )
    b4 = ax2.bar(
        x + width / 2,
        [qot_36_smf.payload_fsus, qot_36_hyb.payload_fsus, qot_36_hcf.payload_fsus],
        width,
        label="Ruta 3600 km (400G: Salto QPSK -> 16-QAM)",
        color="#2ca02c",
    )
    ax2.set_xticks(x)
    ax2.set_xticklabels(stages)
    ax2.set_ylabel("Slots Espectrales Requeridos (n_FSU sin guarda)")
    ax2.set_title("Reducción de Consumo de Espectro (FSUs @ 400 Gbps)")
    ax2.set_ylim(0, 20)
    ax2.grid(axis="y", alpha=0.3)
    ax2.legend(loc="upper right", fontsize=8)

    for bars, qots in [(b3, [qot_18_smf, qot_18_hyb, qot_18_hcf]), (b4, [qot_36_smf, qot_36_hyb, qot_36_hcf])]:
        for bar, q in zip(bars, qots):
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.35,
                f"{q.payload_fsus} FSUs\n({q.modulation})",
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
            )

    fig.tight_layout()
    fig.savefig(fig_path)
    plt.close(fig)
    print(f"\n[OK] Gráfico de validación física guardado en: {fig_path.resolve()}")


def test_03_static_rmlsa_smf_vs_hcf_under_traffic_growth() -> None:
    """
    Prueba 3: Comparación directa en el año k = 4 (con crecimiento anual r = 30%)
    entre NSFNet 100% SMF y NSFNet migrando enlaces troncales críticos a HCF,
    demostrando cómo el aumento de GSNR destraba el espectro y reduce las
    Conexiones Fuera sin agregar FSUs adicionales a la fibra.
    """
    print_banner("TEST-03: IMPACTO DE MIGRACIÓN SMF -> HCF EN RMLSA ESTÁTICO (AÑO k = 4, r = 30%)")

    year_test = 4
    topo_smf = build_nsfnet_topology(span_length_km=100.0)
    res_smf = run_static_rmlsa(topo_smf, year_k=year_test, growth_rate=0.30, k_paths=3, verify_invariants=True)

    # Migrar un conjunto de enlaces troncales clave a HCF (Camino 1: manteniendo 320 FSUs fijos)
    topo_migrated = build_nsfnet_topology(span_length_km=100.0)
    core_links_to_hcf = ["e4_6", "e6_7", "e7_8", "e1_3", "e3_4", "e8_12"]
    total_capex_ur = 0.0
    for lid in core_links_to_hcf:
        topo_migrated.set_link_fiber_type(lid, FIBER_HCF)
        total_capex_ur += topo_migrated.compute_capex_cost(lid, mode="replace")

    res_hcf = run_static_rmlsa(topo_migrated, year_k=year_test, growth_rate=0.30, k_paths=3, verify_invariants=True)

    print(f"Año evaluado: k = {year_test} (Factor de crecimiento (1+r)^k = {1.3**year_test:.3f}x)")
    print(f"Enlaces migrados a HCF (Camino 1): {core_links_to_hcf} | CAPEX Acumulado: {total_capex_ur:.1f} UR\n")
    print(f"{'Métrica de Desempeño':<42} {'Red 100% SMF':<22} {'Red Híbrida SMF+HCF':<22}")
    print("-" * 88)
    print(f"{'Conexiones Solicitadas C(k)':<42} {res_smf.total_connections_requested:<22} {res_hcf.total_connections_requested:<22}")
    print(f"{'Conexiones Atendidas':<42} {res_smf.allocated_connections:<22} {res_hcf.allocated_connections:<22}")
    print(f"{'Conexiones Fuera (Rechazadas)':<42} {res_smf.rejected_connections:<22} {res_hcf.rejected_connections:<22}")
    print(f"{'  - Rechazo por Capa Física (GSNR)':<42} {res_smf.rejected_by_qot:<22} {res_hcf.rejected_by_qot:<22}")
    print(f"{'  - Rechazo por Espectro (320 FSUs)':<42} {res_smf.rejected_by_spectrum:<22} {res_hcf.rejected_by_spectrum:<22}")
    print(f"{'Tráfico Atendido [Gbps]':<42} {res_smf.served_traffic_gbps:<22.0f} {res_hcf.served_traffic_gbps:<22.0f}")
    print(f"{'Tráfico No Atendido [Gbps]':<42} {res_smf.unserved_traffic_gbps:<22.0f} {res_hcf.unserved_traffic_gbps:<22.0f}")
    print(f"{'FSUs Totales Ocupados en la Red':<42} {res_smf.total_fsus_occupied_across_links:<22} {res_hcf.total_fsus_occupied_across_links:<22}")
    print(f"{'Ocupación Espectral Global Banda C [%]':<42} {res_smf.global_spectrum_utilization_pct:<22.2f} {res_hcf.global_spectrum_utilization_pct:<22.2f}")
    print(f"{'Invariantes Físicas Verificadas (320 FSUs)':<42} {str(res_smf.invariants_verified):<22} {str(res_hcf.invariants_verified):<22}")
    print(f"\nDistribución de Modulaciones (100% SMF):     {res_smf.modulation_distribution}")
    print(f"Distribución de Modulaciones (SMF + HCF):    {res_hcf.modulation_distribution}")


if __name__ == "__main__":
    test_01_topology_and_first_fit_continuity()
    test_02_physical_layer_gsnr_and_modulation_table()
    test_03_static_rmlsa_smf_vs_hcf_under_traffic_growth()
    print("\n[ÉXITO TOTAL] Todas las pruebas unitarias, físicas y espectrales finalizaron sin errores.")
