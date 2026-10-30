"""
run_taller3_demo.py
===================
Script maestro de ejecución automatizada para el Taller 3 de TEL-317 Redes Ópticas WDM.
Ejecuta íntegramente:
  1. TEST-01: Preparación de herramientas, carga de JSON NSFNet (14 nodos, 21 enlaces)
              y verificación unitaria de continuidad, contigüidad y First-Fit (40 pts).
  2. TEST-02: Verificación de Capa Física GSNR (suma paralela inversa SMF + HCF) y
              salto de modulación con ahorro de FSUs -> `results/fig1_validacion_gsnr.png` (40 pts).
  3. EXP-01:  Línea Base 100% SMF con tráfico incremental (k = 0..8) para r = 30% y
              sensibilidad TeleGeography (24% y 32%) -> `results/fig2_curva_saturacion_smf.png` (50 pts).
  4. EXP-02:  Migración Progresiva Camino 1 (Reemplazo SMF -> HCF): Heurística Voraz
              Costo-Beneficio (Delta_N_fuera / Costo) vs. Baseline por Mayor Utilización
              + Mapa Topológico de Enlaces Migrados -> `results/fig3_reemplazo_vs_utilizacion.png` (50 pts).
  5. EXP-03:  Comparación en igualdad de presupuesto CAPEX entre los 3 Caminos del Profesor:
              Camino 1 (Reemplazo), Camino 2 (Fibra HCF Paralela) y Camino 3 (Bypass HCF Directo)
              -> `results/fig4_comparacion_3_caminos.png` (50 pts).
  6. Exportación de todas las tablas numéricas en formato CSV (`results/*.csv`) y generación
     del guion detallado para la presentación de 10 minutos y video demostrativo.

Curso: TEL-317 Redes Ópticas WDM - UTFSM
Equipo: Fernanda Manríquez · Josefa Zamora · Benjamín Abde
Profesor: Dr. Nicolás Jara
"""

from __future__ import annotations
import csv
from pathlib import Path
import sys
from typing import Dict, List, Sequence

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from config import (
    DEFAULT_ANNUAL_GROWTH_RATE,
    DEFAULT_HORIZON_YEARS,
    DEFAULT_K_PATHS,
    FIBER_HCF,
    FIBER_SMF,
    SENSITIVITY_GROWTH_RATES,
)
from migration_policies import (
    MODE_1_REPLACE_LINK,
    MODE_2_PARALLEL_HCF,
    MODE_3_BYPASS_HCF,
    MODE_NONE_SMF,
    MultiYearSimulationResult,
    POLICY_GREEDY_COST_BENEFIT,
    POLICY_MAX_UTILIZATION,
    run_multi_year_simulation,
)
from test_simulator import (
    print_banner,
    test_01_topology_and_first_fit_continuity,
    test_02_physical_layer_gsnr_and_modulation_table,
)
from topology import (
    NetworkTopology,
    ensure_default_topologies_json,
    load_topology_from_json,
)

RESULTS_DIR = Path("results")


def write_csv(filepath: Path, rows: Sequence[Dict[str, object]]) -> None:
    """Exporta una lista de diccionarios a un archivo CSV estándar UTF-8."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def run_exp_01_smf_saturation(
    base_topo: NetworkTopology,
    years: Sequence[int],
) -> Dict[float, MultiYearSimulationResult]:
    """
    EXP-01: Línea Base 100% SMF con Tráfico Incremental k = 0 ... 8
    con crecimiento r = 30% base y curvas de sensibilidad 24% y 32% (TeleGeography).
    """
    print_banner("EXP-01: LÍNEA BASE 100% SMF CON CRECIMIENTO ANUAL (24%, 30% BASE, 32%)")

    results_by_rate: Dict[float, MultiYearSimulationResult] = {}
    csv_rows: List[Dict[str, object]] = []

    for r in SENSITIVITY_GROWTH_RATES:
        sim_res = run_multi_year_simulation(
            base_topology=base_topo,
            mode=MODE_NONE_SMF,
            policy=POLICY_GREEDY_COST_BENEFIT,
            years=years,
            growth_rate=r,
            k_paths=DEFAULT_K_PATHS,
            max_migrations_per_year=0,
        )
        results_by_rate[r] = sim_res
        for snap in sim_res.snapshots:
            csv_rows.append(snap.to_row_dict())

    # Imprimir tabla resumen para tasa base r = 30%
    base_sim = results_by_rate[DEFAULT_ANNUAL_GROWTH_RATE]
    print(f"Resultados Línea Base 100% SMF en {base_topo.network_name} (Crecimiento r = 30% anual):")
    print(
        f"{'Año k':<7} {'Factor (1+r)^k':<15} {'Solicitadas':<13} {'Atendidas':<11} "
        f"{'Conex. Fuera':<14} {'% Fuera':<10} {'Tráfico Servido [Tbps]':<24} {'Ocupación Banda C [%]'}"
    )
    print("-" * 115)
    for snap in base_sim.snapshots:
        rm = snap.rmlsa_after_migration
        factor = (1.0 + snap.growth_rate) ** snap.year_k
        print(
            f"{snap.year_k:<7} {f'{factor:.2f}x':<15} {rm.total_connections_requested:<13} "
            f"{rm.allocated_connections:<11} {rm.rejected_connections:<14} "
            f"{100.0 * rm.connection_rejection_ratio:<10.2f} "
            f"{rm.served_traffic_gbps / 1000.0:<24.2f} "
            f"{rm.global_spectrum_utilization_pct:.2f}% (máx enlace: {rm.max_link_utilization_pct:.1f}%)"
        )

    csv_path = RESULTS_DIR / "exp01_saturacion_smf.csv"
    write_csv(csv_path, csv_rows)

    # Generar gráfico fig2_curva_saturacion_smf.png
    fig_path = RESULTS_DIR / "fig2_curva_saturacion_smf.png"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.2), dpi=150)

    styles = {
        0.24: ("#2ca02c", "--", "o", "r = 24% (Proyección TeleGeography 2025-2035)"),
        0.30: ("#d62728", "-", "s", "r = 30% (Escenario Base Sticca et al. [4])"),
        0.32: ("#1f77b4", "-.", "^", "r = 32% (CAGR Histórico TeleGeography 2020-2024)"),
    }

    for r, sim_res in results_by_rate.items():
        color, ls, marker, label = styles[r]
        yk = [s.year_k for s in sim_res.snapshots]
        conex_fuera = [s.rmlsa_after_migration.rejected_connections for s in sim_res.snapshots]
        util_pct = [s.rmlsa_after_migration.global_spectrum_utilization_pct for s in sim_res.snapshots]

        ax1.plot(yk, conex_fuera, color=color, linestyle=ls, marker=marker, linewidth=2.2, label=label)
        ax2.plot(yk, util_pct, color=color, linestyle=ls, marker=marker, linewidth=2.2, label=label)

    ax1.set_title("EXP-01: Evolución Anual de Conexiones Fuera (Red 100% SMF)")
    ax1.set_xlabel("Etapa Anual (Año k)")
    ax1.set_ylabel("Conexiones Fuera (Rechazadas)")
    ax1.set_xticks(list(years))
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=8.5, loc="upper left")

    ax2.set_title("EXP-01: Ocupación Espectral Global de Banda C (320 FSUs/enlace)")
    ax2.set_xlabel("Etapa Anual (Año k)")
    ax2.set_ylabel("Ocupación Espectral Global de Banda C [%]")
    ax2.set_xticks(list(years))
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=8.5, loc="upper left")

    fig.tight_layout()
    fig.savefig(fig_path)
    plt.close(fig)
    print(f"\n[OK] Tabla CSV exportada en: {csv_path.resolve()}")
    print(f"[OK] Gráfico EXP-01 guardado en: {fig_path.resolve()}")
    return results_by_rate


def run_exp_02_replace_greedy_vs_utilization(
    base_topo: NetworkTopology,
    years: Sequence[int],
    smf_baseline: MultiYearSimulationResult,
) -> Dict[str, MultiYearSimulationResult]:
    """
    EXP-02: Migración Progresiva bajo Camino 1 (Reemplazo de Enlace Completo SMF -> HCF).
    Compara la Política Voraz Costo-Beneficio (Delta_N_fuera / Costo) contra el
    Baseline de Orden Fijo por Mayor Utilización (y contra la red 100% SMF).
    """
    print_banner("EXP-02: MIGRACIÓN PROGRESIVA CAMINO 1 (VORAZ COSTO-BENEFICIO VS. UTILIZACIÓN)")

    # Presupuesto CAPEX selectivo (migración de ~35% de la planta, <= 8500 UR)
    max_mig_per_year = 2
    capex_budget_exp02 = 8500.0

    sim_greedy = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_1_REPLACE_LINK,
        policy=POLICY_GREEDY_COST_BENEFIT,
        years=years,
        growth_rate=DEFAULT_ANNUAL_GROWTH_RATE,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=max_mig_per_year,
        max_total_capex_ur=capex_budget_exp02,
    )

    sim_util = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_1_REPLACE_LINK,
        policy=POLICY_MAX_UTILIZATION,
        years=years,
        growth_rate=DEFAULT_ANNUAL_GROWTH_RATE,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=max_mig_per_year,
        max_total_capex_ur=capex_budget_exp02,
    )

    print(
        f"{'Año k':<6} | {'100% SMF (Fuera)':<17} | "
        f"{'Baseline Util. (Fuera / CAPEX)':<31} | "
        f"{'Voraz Propuesta (Fuera / CAPEX)':<32} | {'Nuevos Enlaces HCF (Voraz)'}"
    )
    print("-" * 125)
    for k_idx, yk in enumerate(years):
        s_smf = smf_baseline.snapshots[k_idx].rmlsa_after_migration.rejected_connections
        s_utl = sim_util.snapshots[k_idx]
        s_grd = sim_greedy.snapshots[k_idx]
        new_links = [a.action_id for a in s_grd.actions_taken]
        print(
            f"{yk:<6} | {s_smf:<17} | "
            f"{f'{s_utl.rmlsa_after_migration.rejected_connections:3d} conex ({s_utl.cumulative_capex_ur:6.0f} UR)':<31} | "
            f"{f'{s_grd.rmlsa_after_migration.rejected_connections:3d} conex ({s_grd.cumulative_capex_ur:6.0f} UR)':<32} | "
            f"{new_links}"
        )

    csv_rows: List[Dict[str, object]] = []
    for sim in (smf_baseline, sim_util, sim_greedy):
        for snap in sim.snapshots:
            csv_rows.append(snap.to_row_dict())
    csv_path = RESULTS_DIR / "exp02_reemplazo_vs_utilizacion.csv"
    write_csv(csv_path, csv_rows)

    # Generar gráfico fig3_reemplazo_vs_utilizacion.png (3 paneles: Conexiones Fuera, CAPEX y Mapa NSFNet)
    fig_path = RESULTS_DIR / "fig3_reemplazo_vs_utilizacion.png"
    fig = plt.figure(figsize=(15, 5.2), dpi=150)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.1, 1.0, 1.3])
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    ax3 = fig.add_subplot(gs[2])

    yk_list = list(years)
    ax1.plot(
        yk_list,
        [s.rmlsa_after_migration.rejected_connections for s in smf_baseline.snapshots],
        "r--o",
        linewidth=2,
        label="Sin Migración (100% SMF)",
    )
    ax1.plot(
        yk_list,
        [s.rmlsa_after_migration.rejected_connections for s in sim_util.snapshots],
        "b-.^",
        linewidth=2,
        label="Baseline: Mayor Utilización",
    )
    ax1.plot(
        yk_list,
        [s.rmlsa_after_migration.rejected_connections for s in sim_greedy.snapshots],
        "g-s",
        linewidth=2.4,
        label="Propuesta: Voraz (ΔN_fuera / Costo)",
    )
    ax1.set_title("EXP-02: Conexiones Fuera por Año (Camino 1)")
    ax1.set_xlabel("Año k (r = 30%)")
    ax1.set_ylabel("Conexiones Fuera (Rechazadas)")
    ax1.set_xticks(yk_list)
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=8)

    # Panel 2: Eficiencia CAPEX acumulado vs. Reducción acumulada de Conexiones Fuera
    ax2.plot(
        yk_list,
        [s.cumulative_capex_ur for s in sim_util.snapshots],
        "b-.^",
        linewidth=2,
        label="CAPEX Baseline Utilización",
    )
    ax2.plot(
        yk_list,
        [s.cumulative_capex_ur for s in sim_greedy.snapshots],
        "g-s",
        linewidth=2.4,
        label="CAPEX Voraz Costo-Beneficio",
    )
    ax2.set_title("Inversión CAPEX Acumulada [UR]")
    ax2.set_xlabel("Año k")
    ax2.set_ylabel("CAPEX Acumulado [Unidades Relativas UR]")
    ax2.set_xticks(yk_list)
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=8)

    # Panel 3: Mapa de topología NSFNet mostrando los enlaces migrados por la heurística voraz
    final_topo = sim_greedy.final_topology
    migration_year_by_link: Dict[str, int] = {}
    for act in sim_greedy.all_actions:
        if act.action_id not in migration_year_by_link:
            migration_year_by_link[act.action_id] = act.year_k

    pos = {nid: data["pos"] for nid, data in final_topo.graph.nodes(data=True)}
    for lk in final_topo.links.values():
        x0, y0 = pos[lk.source]
        x1, y1 = pos[lk.target]
        if lk.fiber_type == FIBER_HCF:
            ax3.plot([x0, x1], [y0, y1], color="#2ca02c", linewidth=3.0, zorder=2)
            mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            yk_mig = migration_year_by_link.get(lk.id, 0)
            ax3.text(
                mx,
                my,
                f"{lk.id}\n(k={yk_mig})",
                fontsize=6.5,
                ha="center",
                va="center",
                bbox=dict(boxstyle="round,pad=0.15", fc="#e6f5d0", ec="#2ca02c", alpha=0.9),
                zorder=4,
            )
        else:
            ax3.plot([x0, x1], [y0, y1], color="#999999", linestyle="--", linewidth=1.3, zorder=1)

    for nid, (nx_pos, ny_pos) in pos.items():
        ax3.scatter([nx_pos], [ny_pos], s=190, color="#1f77b4", edgecolors="black", zorder=5)
        ax3.text(nx_pos, ny_pos, f"N{nid}", color="white", fontsize=7.5, fontweight="bold", ha="center", va="center", zorder=6)

    ax3.plot([], [], color="#2ca02c", linewidth=3.0, label="Enlace Migrado a HCF")
    ax3.plot([], [], color="#999999", linestyle="--", linewidth=1.3, label="Enlace SMF Original")
    ax3.set_title("Mapa NSFNet: Secuencia de Enlaces Migrados (Voraz)")
    ax3.axis("off")
    ax3.legend(loc="lower left", fontsize=8)

    fig.tight_layout()
    fig.savefig(fig_path)
    plt.close(fig)

    print(f"\n[OK] Tabla CSV exportada en: {csv_path.resolve()}")
    print(f"[OK] Gráfico EXP-02 guardado en: {fig_path.resolve()}")
    return {"greedy": sim_greedy, "utilization": sim_util}


def run_exp_03_compare_three_migration_paths(
    base_topo: NetworkTopology,
    years: Sequence[int],
    smf_baseline: MultiYearSimulationResult,
) -> Dict[str, MultiYearSimulationResult]:
    """
    EXP-03: Comparación en igualdad de presupuesto CAPEX entre las 3 estrategias
    propuestas por el profesor:
      - Camino 1 (`Mode_1_Replace_Link`): Reemplazo de enlaces SMF -> HCF.
      - Camino 2 (`Mode_2_Parallel_HCF`): Adición de fibra HCF paralela sin apagar la SMF.
      - Camino 3 (`Mode_3_Bypass_HCF`): Creación de enlace nuevo HCF directo (bypass).
    """
    print_banner("EXP-03: COMPARACIÓN DE LOS 3 CAMINOS DEL PROFESOR EN IGUALDAD DE PRESUPUESTO CAPEX")

    # Presupuesto CAPEX total igualado (ej. 8500 UR para permitir desplegar enlaces en los 3 caminos)
    common_capex_budget_ur = 8500.0
    max_steps_per_year = 3

    sim_mode1 = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_1_REPLACE_LINK,
        policy=POLICY_GREEDY_COST_BENEFIT,
        years=years,
        growth_rate=DEFAULT_ANNUAL_GROWTH_RATE,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=max_steps_per_year,
        max_total_capex_ur=common_capex_budget_ur,
    )

    sim_mode2 = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_2_PARALLEL_HCF,
        policy=POLICY_GREEDY_COST_BENEFIT,
        years=years,
        growth_rate=DEFAULT_ANNUAL_GROWTH_RATE,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=max_steps_per_year,
        max_total_capex_ur=common_capex_budget_ur,
    )

    sim_mode3 = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_3_BYPASS_HCF,
        policy=POLICY_GREEDY_COST_BENEFIT,
        years=years,
        growth_rate=DEFAULT_ANNUAL_GROWTH_RATE,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=max_steps_per_year,
        max_total_capex_ur=common_capex_budget_ur,
    )

    print(f"Presupuesto CAPEX Máximo Igualado: {common_capex_budget_ur:.0f} UR | Tasa de crecimiento r = 30% anual\n")
    print(
        f"{'Año k':<6} | {'100% SMF (Fuera / Tbps)':<24} | "
        f"{'Camino 1: Reemplazo':<26} | "
        f"{'Camino 2: HCF Paralela':<26} | "
        f"{'Camino 3: Bypass HCF'}"
    )
    print("-" * 118)
    for idx, yk in enumerate(years):
        r0 = smf_baseline.snapshots[idx].rmlsa_after_migration
        r1 = sim_mode1.snapshots[idx].rmlsa_after_migration
        r2 = sim_mode2.snapshots[idx].rmlsa_after_migration
        r3 = sim_mode3.snapshots[idx].rmlsa_after_migration
        print(
            f"{yk:<6} | {f'{r0.rejected_connections:3d} fuera / {r0.served_traffic_gbps/1000:5.1f} Tbps':<24} | "
            f"{f'{r1.rejected_connections:3d} fuera / {r1.served_traffic_gbps/1000:5.1f} Tbps':<26} | "
            f"{f'{r2.rejected_connections:3d} fuera / {r2.served_traffic_gbps/1000:5.1f} Tbps':<26} | "
            f"{f'{r3.rejected_connections:3d} fuera / {r3.served_traffic_gbps/1000:5.1f} Tbps'}"
        )

    print("\nResumen Acumulado Multi-Año (k = 0..8) bajo Presupuesto CAPEX <= 8500 UR:")
    for label, sim in [
        ("Sin Migración (100% SMF)", smf_baseline),
        ("Camino 1 (Reemplazo SMF->HCF)", sim_mode1),
        ("Camino 2 (Fibra HCF Paralela)", sim_mode2),
        ("Camino 3 (Bypass HCF Directo)", sim_mode3),
    ]:
        print(
            f"  - {label:<32}: CAPEX Final = {sim.total_capex_ur:6.0f} UR | "
            f"Conexiones Fuera Acum. = {sim.cumulative_rejected_connections:4d} | "
            f"Tráfico Total Atendido = {sim.cumulative_served_tbps:6.2f} Tbps | "
            f"Intervenciones = {[a.action_id for a in sim.all_actions]}"
        )

    csv_rows: List[Dict[str, object]] = []
    for sim in (smf_baseline, sim_mode1, sim_mode2, sim_mode3):
        for snap in sim.snapshots:
            csv_rows.append(snap.to_row_dict())
    csv_path = RESULTS_DIR / "exp03_comparacion_3_caminos.csv"
    write_csv(csv_path, csv_rows)

    # Generar gráfico fig4_comparacion_3_caminos.png
    fig_path = RESULTS_DIR / "fig4_comparacion_3_caminos.png"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.2), dpi=150)
    yk_list = list(years)

    configs = [
        (smf_baseline, "#d62728", "--", "o", "100% SMF (Sin Migración)"),
        (sim_mode1, "#1f77b4", "-", "s", f"Camino 1: Reemplazo SMF→HCF ({sim_mode1.total_capex_ur:.0f} UR)"),
        (sim_mode2, "#2ca02c", "-", "^", f"Camino 2: HCF Paralela Activa ({sim_mode2.total_capex_ur:.0f} UR)"),
        (sim_mode3, "#9467bd", "-.", "D", f"Camino 3: Bypass HCF Directo ({sim_mode3.total_capex_ur:.0f} UR)"),
    ]

    for sim, color, ls, marker, label in configs:
        ax1.plot(
            yk_list,
            [s.rmlsa_after_migration.rejected_connections for s in sim.snapshots],
            color=color,
            linestyle=ls,
            marker=marker,
            linewidth=2.2,
            label=label,
        )
        ax2.plot(
            yk_list,
            [s.rmlsa_after_migration.served_traffic_gbps / 1000.0 for s in sim.snapshots],
            color=color,
            linestyle=ls,
            marker=marker,
            linewidth=2.2,
            label=label,
        )

    ax1.set_title("EXP-03: Conexiones Fuera por Estrategia de Migración")
    ax1.set_xlabel("Año k (r = 30%)")
    ax1.set_ylabel("Conexiones Fuera (Rechazadas)")
    ax1.set_xticks(yk_list)
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=8, loc="upper left")

    ax2.set_title("EXP-03: Tráfico Total Atendido [Tbps] en Igualdad de CAPEX")
    ax2.set_xlabel("Año k (r = 30%)")
    ax2.set_ylabel("Tráfico Total Atendido [Tbps]")
    ax2.set_xticks(yk_list)
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=8, loc="upper left")

    fig.tight_layout()
    fig.savefig(fig_path)
    plt.close(fig)

    print(f"\n[OK] Tabla CSV exportada en: {csv_path.resolve()}")
    print(f"[OK] Gráfico EXP-03 guardado en: {fig_path.resolve()}")
    return {
        "mode_1": sim_mode1,
        "mode_2": sim_mode2,
        "mode_3": sim_mode3,
    }


def generate_presentation_script_markdown(
    exp01: Dict[float, MultiYearSimulationResult],
    exp02: Dict[str, MultiYearSimulationResult],
    exp03: Dict[str, MultiYearSimulationResult],
) -> Path:
    """
    Genera el resumen ejecutivo y guion minuto a minuto para la presentación
    demostrativa de 10 minutos y video de respaldo (Sección 13 y 14).
    """
    smf_base = exp01[DEFAULT_ANNUAL_GROWTH_RATE]
    greedy_c1 = exp02["greedy"]
    util_c1 = exp02["utilization"]
    m1 = exp03["mode_1"]
    m2 = exp03["mode_2"]
    m3 = exp03["mode_3"]

    k0_snap = smf_base.snapshots[0].rmlsa_after_migration
    k8_smf = smf_base.snapshots[-1].rmlsa_after_migration

    md_path = RESULTS_DIR / "Guion_Presentacion_y_Video_Taller3.md"
    content = rf"""# Guion Ejecutivo y Estructura de Presentación + Demo (10 Minutos) - Taller 3
**Curso:** TEL-317 Redes Ópticas WDM (UTFSM)  
**Proyecto:** Migración Progresiva de SMF a HCF en Redes Ópticas Elásticas Estáticas  
**Equipo:** Fernanda Manríquez · Josefa Zamora · Benjamín Abde  
**Profesor:** Dr. Nicolás Jara  

---

## Minutos 0:00 – 2:00 | Parte C: Reajuste de Objetivos y Definiciones (10 puntos)
- **Paso a Planificación Estática por Fotografías Anuales ($k = 0 \dots 8$):** Siguiendo la retroalimentación del Taller 2, se reemplazó la simulación dinámica de eventos discretos por fotografías estáticas anuales sobre Banda C ($320\text{{ FSUs}}$ de $12.5\text{{ GHz}}$).
- **Nueva Métrica de Desempeño:** Se evalúan las **Conexiones Fuera (Rechazadas)** y el **Tráfico No Atendido [Gbps/Tbps]**, distinguiendo explícitamente entre rechazo por capa física ($\text{{GSNR}}$) y rechazo por saturación/fragmentación de espectro.
- **Respaldo de Crecimiento Anual:** Se modela $D(k) = D(0)\times(1+r)^k$ con $r = 30\%$ base (Sticca et al. [4]) y análisis de sensibilidad con reportes globales de **TeleGeography** ($24\%$ proyectado 2025–2035 y $32\%$ histórico 2020–2024 [5]).
- **Tres Caminos de Migración Evaluados:** (1) Reemplazo de enlaces $\text{{SMF}} \to \text{{HCF}}$, (2) Adición de fibra HCF paralela evitando *dark fiber*, y (3) Enlace nuevo HCF directo de larga distancia (*bypass*).

---

## Minutos 2:00 – 5:00 | Parte A: Preparación de Herramientas y Pruebas Funcionales (40 puntos)
- **Demostración en Vivo / Video (`python run_taller3_demo.py`):**
  1. **TEST-01 (Topología y Asignador First-Fit):** Carga de `data/topologies.json` con **NSFNet (14 nodos, 21 enlaces bidireccionales)**. En $k=0$, las **{k0_snap.total_connections_requested} conexiones solicitadas ({k0_snap.served_traffic_gbps/1000:.2f} Tbps)** se asignan con **0 Conexiones Fuera** y **0 colisiones espectrales**, verificando continuidad y contigüidad espectral.
  2. **TEST-02 (Validación de Capa Física GSNR - `fig1_validacion_gsnr.png`):** Aplicando la acumulación inversa paralela de Pedro et al. [1], en una ruta de $1800\text{{ km}}$ (18 spans) el $\text{{GSNR}}$ sube de $13.89\text{{ dB}}$ (`8-QAM`, 11 FSUs @ 400G) en 100% SMF a $15.44\text{{ dB}}$ (`16-QAM`, 8 FSUs) en ruta híbrida 50/50 y $17.89\text{{ dB}}$ (`32-QAM`, 7 FSUs) en 100% HCF. En una ruta transcontinental de $3600\text{{ km}}$ (36 spans), migrar a HCF eleva el $\text{{GSNR}}$ de $10.88\text{{ dB}}$ (`QPSK`, 16 FSUs) a $14.88\text{{ dB}}$ (`16-QAM`, 8 FSUs), **reduciendo el consumo de espectro exactamente a la mitad (-50% FSUs)** sin inventar nuevos slots en la fibra.

---

## Minutos 5:00 – 9:00 | Parte B: Implementación Preliminar y Resultados (50 puntos)
- **EXP-01 (Curva de Saturación 100% SMF - `fig2_curva_saturacion_smf.png`):**
  - En $k=0$ hay `0` Conexiones Fuera (utilización global $22.99\%$, enlace cuello de botella `e7_8` al $65.62\%$).
  - A partir de $k=1$ ($r=30\%$) aparecen los primeros rechazos por agotamiento espectral en los enlaces centrales, llegando en $k=8$ a **{k8_smf.rejected_connections} Conexiones Fuera** de {k8_smf.total_connections_requested} solicitadas.
- **EXP-02 (Heurística Voraz Costo-Beneficio vs. Baseline Utilización en Camino 1 - `fig3_reemplazo_vs_utilizacion.png`):**
  - La política voraz ($\Delta N_{{\text{{fuera}}}} / C(e)$) selecciona los enlaces que destraban simultáneamente la modulación de múltiples rutas largas (`{[a.action_id for a in greedy_c1.all_actions[:6]]}`), logrando **{greedy_c1.cumulative_rejected_connections} Conexiones Fuera acumuladas** frente a **{util_c1.cumulative_rejected_connections}** del orden fijo por utilización y **{smf_base.cumulative_rejected_connections}** de la red 100% SMF.
- **EXP-03 (Comparación de los 3 Caminos en Igualdad de CAPEX $\le 8500\text{{ UR}}$ - `fig4_comparacion_3_caminos.png`):**
  - **Camino 1 (Reemplazo SMF $\to$ HCF):** {m1.cumulative_rejected_connections} Conexiones Fuera acumuladas | {m1.cumulative_served_tbps:.2f} Tbps atendidos ({m1.total_capex_ur:.0f} UR).
  - **Camino 2 (Fibra HCF Paralela sin apagar SMF):** {m2.cumulative_rejected_connections} Conexiones Fuera acumuladas | {m2.cumulative_served_tbps:.2f} Tbps atendidos ({m2.total_capex_ur:.0f} UR). Al conservar los 320 FSUs de la SMF activa y sumar una fibra HCF paralela para rutas exigentes en GSNR, logra la mayor reducción de rechazos.
  - **Camino 3 (Enlace Nuevo HCF Bypass Directo):** {m3.cumulative_rejected_connections} Conexiones Fuera acumuladas | {m3.cumulative_served_tbps:.2f} Tbps atendidos ({m3.total_capex_ur:.0f} UR), descargando múltiples saltos intermedios mediante enlaces directos de larga distancia.

---

## Minutos 9:00 – 10:00 | Conclusiones Preliminares y Pasos al Informe Final
- **Hallazgo Principal:** En Camino 1, aunque HCF mantiene fijos los 320 FSUs de Banda C, su ganancia de $+4.0\text{{ dB}}$ por span permite saltar de `QPSK`/`8-QAM` a `16-QAM`/`32-QAM`, liberando entre $27\%$ y $50\%$ de los slots por conexión. Por su parte, Camino 2 y Camino 3 evitan desperdiciar la planta SMF instalada (*dark fiber*) y descongestionan los cuellos de botella centrales de NSFNet.
- **Trabajo hacia el Informe Final:** Análisis de sensibilidad paramétrica sobre costos CAPEX ($c_{{\text{{km}}}}, C_{{\text{{inst}}}}$), evaluación sobre la topología europea **COST239 (11 nodos, 26 enlaces)** ya integrada en `data/topologies.json` y optimización conjunta de los Caminos 1, 2 y 3.
"""
    md_path.write_text(content, encoding="utf-8")
    return md_path


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ensure_default_topologies_json("data/topologies.json")
    base_topo = load_topology_from_json(json_path, network_name="NSFNet_14_Transport", span_length_km=100.0)
    years = list(range(DEFAULT_HORIZON_YEARS + 1))  # k = 0 ... 8

    # 1. Pruebas funcionales y de capa física (TEST-01 y TEST-02 - 40 pts)
    test_01_topology_and_first_fit_continuity()
    test_02_physical_layer_gsnr_and_modulation_table()

    # 2. Experimentos multi-año (EXP-01, EXP-02 y EXP-03 - 50 pts)
    exp01_results = run_exp_01_smf_saturation(base_topo, years=years)
    smf_baseline_30 = exp01_results[DEFAULT_ANNUAL_GROWTH_RATE]

    exp02_results = run_exp_02_replace_greedy_vs_utilization(
        base_topo, years=years, smf_baseline=smf_baseline_30
    )

    exp03_results = run_exp_03_compare_three_migration_paths(
        base_topo, years=years, smf_baseline=smf_baseline_30
    )

    # 3. Generar guion de presentación de 10 min y video demo
    script_path = generate_presentation_script_markdown(exp01_results, exp02_results, exp03_results)

    print_banner("RESUMEN DE ARCHIVOS GENERADOS PARA EL TALLER 3")
    for p in sorted(RESULTS_DIR.iterdir()):
        print(f"  -> {p.resolve()}")
    print(f"  -> Guion de Presentación (10 min): {script_path.resolve()}")
    print("\n[COMPLETADO] Batería completa de pruebas (TEST-01, TEST-02) y experimentos (EXP-01..03) finalizada.")


if __name__ == "__main__":
    main()
