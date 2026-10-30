"""
build_visual_dashboard.py
=========================
Genera el Dashboard Visual Interactivo Standalone (`dashboard_simulador_taller3.html`)
alimentado por los datos exactos del motor físico QoT (`physics_qot.py`), el motor
RMLSA estático (`rmlsa_static.py`) y las políticas de migración (`migration_policies.py`).

Incluye:
1. Mapa topológico interactivo SVG de NSFNet (14 nodos, 21 enlaces base + enlaces
   HCF paralelos de Camino 2 + enlaces HCF bypass de Camino 3).
2. Inspector interactivo de los 320 FSUs de Banda C por enlace y verificador visual
   de Continuidad + Contigüidad Espectral en todos los enlaces de una ruta.
3. Controles de reproducción temporal Año a Año (k = 0 ... 8, Play/Pausa) y selector
   en vivo de las 5 políticas evaluadas (100% SMF, Camino 1 Utilización, Camino 1 Voraz,
   Camino 2 HCF Paralela, Camino 3 Bypass HCF).
4. Calculadora interactiva en tiempo real de Capa Física GSNR (TEST-02) y panel de
   curvas comparativas multi-año (EXP-01, EXP-02, EXP-03).
5. Selector de Tema Visual: Modo Oscuro (Dark) y Modo Claro (Light).
"""

from __future__ import annotations
import json
from pathlib import Path
import sys
from typing import Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config import (
    DEFAULT_ANNUAL_GROWTH_RATE,
    DEFAULT_HORIZON_YEARS,
    DEFAULT_K_PATHS,
    DELTA_SNR_HCF_DB,
    GSNR_1SPAN_SMF_DB,
    MODULATION_FORMATS,
    NSFNET_NODES,
    TOTAL_SLOTS,
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
from topology import ensure_default_topologies_json, load_topology_from_json


def serialize_simulation_for_ui(sim: MultiYearSimulationResult) -> Dict[str, object]:
    """Serializa todos los años k=0..8, enlaces, espectro de 320 FSUs y conexiones."""
    years_data: List[Dict[str, object]] = []

    # Reconstruir paso a paso la topología año por año para extraer el estado exacto de cada enlace
    for snap in sim.snapshots:
        rm = snap.rmlsa_after_migration
        # Mapa rápido de conexiones atendidas por uid para enriquecer el inspector de slots
        alloc_by_uid: Dict[int, Dict[str, object]] = {}
        connections_list: List[Dict[str, object]] = []

        for alloc in rm.allocations:
            c_dict = {
                "u": alloc.uid,
                "i": alloc.demand_id,
                "s": alloc.source,
                "t": alloc.target,
                "b": alloc.bitrate_gbps,
                "a": 1 if alloc.is_allocated else 0,
                "pn": alloc.path_nodes,
                "pl": alloc.path_link_ids,
                "d": int(alloc.route_distance_km),
                "sp": alloc.route_spans,
                "g": round(alloc.gsnr_db, 2) if alloc.gsnr_db is not None else None,
                "m": alloc.modulation,
                "pf": alloc.payload_fsus,
                "tf": alloc.total_fsus,
                "s0": alloc.start_slot,
                "s1": alloc.end_slot,
            }
            connections_list.append(c_dict)

        years_data.append(
            {
                "year_k": snap.year_k,
                "factor": round((1.0 + snap.growth_rate) ** snap.year_k, 2),
                "req_conn": rm.total_connections_requested,
                "alloc_conn": rm.allocated_connections,
                "rej_conn": rm.rejected_connections,
                "rej_qot": rm.rejected_by_qot,
                "rej_spec": rm.rejected_by_spectrum,
                "rej_pct": round(100.0 * rm.connection_rejection_ratio, 2),
                "req_tbps": round(rm.total_requested_gbps / 1000.0, 2),
                "served_tbps": round(rm.served_traffic_gbps / 1000.0, 2),
                "unserved_tbps": round(rm.unserved_traffic_gbps / 1000.0, 2),
                "used_fsus": rm.total_fsus_occupied_across_links,
                "cap_fsus": rm.total_fsu_capacity_across_links,
                "global_util_pct": round(rm.global_spectrum_utilization_pct, 2),
                "max_link_util_pct": round(rm.max_link_utilization_pct, 2),
                "bottleneck_link": rm.bottleneck_link_id,
                "mod_dist": rm.modulation_distribution,
                "inc_capex_ur": round(snap.incremental_capex_ur, 1),
                "cum_capex_ur": round(snap.cumulative_capex_ur, 1),
                "actions_year": [a.action_id for a in snap.actions_taken],
                "migrated_cum": list(snap.migrated_link_ids_cumulative),
                "hcf_links_count": snap.hcf_links_count,
                "total_links_count": snap.total_links_count,
                "hcf_km": round(snap.hcf_kilometers, 1),
                "connections": connections_list,
            }
        )

    # Extraer catálogo completo de enlaces presentes en la topología final
    links_catalog: List[Dict[str, object]] = []
    for lk in sim.final_topology.links.values():
        links_catalog.append(
            {
                "id": lk.id,
                "source": lk.source,
                "target": lk.target,
                "length_km": lk.length_km,
                "spans": lk.spans,
                "is_parallel": lk.is_parallel,
                "is_bypass": lk.is_bypass,
            }
        )

    return {
        "mode": sim.mode,
        "policy": sim.policy,
        "total_capex_ur": round(sim.total_capex_ur, 1),
        "cum_served_tbps": round(sim.cumulative_served_tbps, 2),
        "cum_rejected": sim.cumulative_rejected_connections,
        "links_catalog": links_catalog,
        "years": years_data,
    }


def collect_all_simulation_data() -> Dict[str, object]:
    json_path = ensure_default_topologies_json("data/topologies.json")
    base_topo = load_topology_from_json(json_path, network_name="NSFNet_14_Transport", span_length_km=100.0)
    years = list(range(DEFAULT_HORIZON_YEARS + 1))
    capex_budget = 8500.0

    sim_smf = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_NONE_SMF,
        policy=POLICY_GREEDY_COST_BENEFIT,
        years=years,
        growth_rate=DEFAULT_ANNUAL_GROWTH_RATE,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=0,
    )
    sim_smf_24 = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_NONE_SMF,
        policy=POLICY_GREEDY_COST_BENEFIT,
        years=years,
        growth_rate=0.24,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=0,
    )
    sim_smf_32 = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_NONE_SMF,
        policy=POLICY_GREEDY_COST_BENEFIT,
        years=years,
        growth_rate=0.32,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=0,
    )

    sim_c1_util = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_1_REPLACE_LINK,
        policy=POLICY_MAX_UTILIZATION,
        years=years,
        growth_rate=DEFAULT_ANNUAL_GROWTH_RATE,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=2,
        max_total_capex_ur=capex_budget,
    )
    sim_c1_greedy = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_1_REPLACE_LINK,
        policy=POLICY_GREEDY_COST_BENEFIT,
        years=years,
        growth_rate=DEFAULT_ANNUAL_GROWTH_RATE,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=3,
        max_total_capex_ur=capex_budget,
    )
    sim_c2_parallel = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_2_PARALLEL_HCF,
        policy=POLICY_GREEDY_COST_BENEFIT,
        years=years,
        growth_rate=DEFAULT_ANNUAL_GROWTH_RATE,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=3,
        max_total_capex_ur=capex_budget,
    )
    sim_c3_bypass = run_multi_year_simulation(
        base_topology=base_topo,
        mode=MODE_3_BYPASS_HCF,
        policy=POLICY_GREEDY_COST_BENEFIT,
        years=years,
        growth_rate=DEFAULT_ANNUAL_GROWTH_RATE,
        k_paths=DEFAULT_K_PATHS,
        max_migrations_per_year=3,
        max_total_capex_ur=capex_budget,
    )

    mod_table = [
        {
            "name": m.name,
            "eff": m.spectral_efficiency_bps_hz,
            "snr_th": m.snr_threshold_db,
            "spans_smf": m.max_spans_smf_100km,
            "mar_km": m.mar_smf_km,
            "fsus": m.fsu_by_bitrate_gbps,
        }
        for m in MODULATION_FORMATS
    ]

    return {
        "nodes": NSFNET_NODES,
        "total_slots": TOTAL_SLOTS,
        "gsnr_1span_smf_db": GSNR_1SPAN_SMF_DB,
        "delta_snr_hcf_db": DELTA_SNR_HCF_DB,
        "modulations": mod_table,
        "sensitivity_smf": {
            "r24": [s.rmlsa_after_migration.rejected_connections for s in sim_smf_24.snapshots],
            "r30": [s.rmlsa_after_migration.rejected_connections for s in sim_smf.snapshots],
            "r32": [s.rmlsa_after_migration.rejected_connections for s in sim_smf_32.snapshots],
            "u24": [round(s.rmlsa_after_migration.global_spectrum_utilization_pct, 2) for s in sim_smf_24.snapshots],
            "u30": [round(s.rmlsa_after_migration.global_spectrum_utilization_pct, 2) for s in sim_smf.snapshots],
            "u32": [round(s.rmlsa_after_migration.global_spectrum_utilization_pct, 2) for s in sim_smf_32.snapshots],
        },
        "strategies": {
            "smf": serialize_simulation_for_ui(sim_smf),
            "c1_util": serialize_simulation_for_ui(sim_c1_util),
            "c1_greedy": serialize_simulation_for_ui(sim_c1_greedy),
            "c2_parallel": serialize_simulation_for_ui(sim_c2_parallel),
            "c3_bypass": serialize_simulation_for_ui(sim_c3_bypass),
        },
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Simulador Visual EON SMF → HCF | TEL-317 Redes Ópticas WDM</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    :root {
      color-scheme: dark;
    }
    body {
      background-color: #0b1120;
      color: #f1f5f9;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      transition: background-color 0.2s ease, color 0.2s ease;
    }
    .glass-card {
      background: rgba(15, 23, 42, 0.88);
      border: 1px solid rgba(51, 65, 85, 0.8);
      border-radius: 0.75rem;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.45);
      transition: background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .slot-cell {
      transition: transform 0.1s ease, filter 0.1s ease;
    }
    .slot-cell:hover {
      transform: scaleY(1.35);
      filter: brightness(1.3);
      z-index: 20;
    }
    @keyframes pulse-flow {
      0% { stroke-dashoffset: 24; }
      100% { stroke-dashoffset: 0; }
    }
    .route-animated {
      stroke-dasharray: 8 4;
      animation: pulse-flow 0.7s linear infinite;
    }
    ::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    ::-webkit-scrollbar-track {
      background: #0f172a;
    }
    ::-webkit-scrollbar-thumb {
      background: #334155;
      border-radius: 3px;
    }

    /* =========================================================================
       MODO CLARO (LIGHT THEME) - ALTO CONTRASTE
       ========================================================================= */
    body.light {
      background-color: #e2e8f0 !important;
      color: #0f172a !important;
      color-scheme: light;
    }
    body.light .glass-card {
      background: #ffffff !important;
      border: 1px solid #cbd5e1 !important;
      box-shadow: 0 4px 14px -2px rgba(15, 23, 42, 0.08) !important;
    }
    body.light h1,
    body.light h2,
    body.light h3,
    body.light strong {
      color: #0f172a;
    }
    body.light .text-white {
      color: #0f172a !important;
    }
    /* Preservar texto blanco en botones de acento y badges coloreados */
    body.light .bg-emerald-600,
    body.light .bg-emerald-600 *,
    body.light .bg-amber-600,
    body.light .bg-amber-600 *,
    body.light .bg-rose-600,
    body.light .bg-rose-600 *,
    body.light .bg-fuchsia-600,
    body.light .bg-cyan-600,
    body.light .bg-blue-600,
    body.light .mod-badge,
    body.light .calc-rate-btn.bg-emerald-600,
    body.light #play-btn,
    body.light #tab-btn-sim.bg-emerald-600,
    body.light #tab-btn-qot.bg-emerald-600,
    body.light #tab-btn-charts.bg-emerald-600 {
      color: #ffffff !important;
    }
    /* Escala de grises de texto con alto contraste sobre fondo claro */
    body.light .text-slate-500,
    body.light .text-slate-400 {
      color: #334155 !important;
    }
    body.light .text-slate-300,
    body.light .text-slate-200 {
      color: #0f172a !important;
    }
    /* Colores semánticos oscurecidos para legibilidad perfecta en fondo blanco */
    body.light .text-emerald-200,
    body.light .text-emerald-300,
    body.light .text-emerald-400 {
      color: #047857 !important;
    }
    body.light .text-sky-300,
    body.light .text-sky-400 {
      color: #0369a1 !important;
    }
    body.light .text-amber-300,
    body.light .text-amber-400 {
      color: #b45309 !important;
    }
    body.light .text-rose-300,
    body.light .text-rose-400 {
      color: #be123c !important;
    }
    body.light .text-purple-300,
    body.light .text-purple-400 {
      color: #7e22ce !important;
    }
    /* Contenedores que en modo oscuro eran slate-950 / slate-900 / slate-800 (cualquier opacidad) */
    body.light [class*="bg-slate-950"],
    body.light [class*="bg-slate-900"] {
      background-color: #f8fafc !important;
      border-color: #cbd5e1 !important;
    }
    body.light [class*="bg-slate-800"] {
      background-color: #f1f5f9 !important;
      border-color: #cbd5e1 !important;
      color: #0f172a !important;
    }
    /* Badges translúcidos adaptados a modo claro */
    body.light .bg-emerald-500\/20,
    body.light [class*="bg-emerald-900"] {
      background-color: #d1fae5 !important;
      border-color: #6ee7b7 !important;
      color: #065f46 !important;
    }
    body.light .bg-sky-500\/20 {
      background-color: #e0f2fe !important;
      border-color: #7dd3fc !important;
      color: #075985 !important;
    }
    body.light .bg-rose-500\/20 {
      background-color: #ffe4e6 !important;
      border-color: #fda4af !important;
      color: #9f1239 !important;
    }
    body.light [class*="border-slate-800"],
    body.light [class*="border-slate-700"] {
      border-color: #cbd5e1 !important;
    }
    body.light .divide-slate-800 > :not([hidden]) ~ :not([hidden]),
    body.light .divide-slate-800\/70 > :not([hidden]) ~ :not([hidden]) {
      border-color: #e2e8f0 !important;
    }
    body.light .hover\:bg-slate-700:hover,
    body.light .hover\:bg-slate-800:hover,
    body.light .hover\:bg-slate-900\/90:hover {
      background-color: #e2e8f0 !important;
    }
    body.light select,
    body.light input[type="text"] {
      background-color: #ffffff !important;
      color: #0f172a !important;
      border-color: #94a3b8 !important;
    }
    body.light table th {
      background-color: #e2e8f0 !important;
      color: #0f172a !important;
      border-color: #cbd5e1 !important;
    }
    body.light table td {
      border-color: #e2e8f0 !important;
      color: #0f172a;
    }
    body.light tr.text-slate-200,
    body.light tr.text-slate-300 {
      color: #0f172a !important;
    }
    body.light tr.bg-amber-500\/20 {
      background-color: #fef3c7 !important;
      color: #78350f !important;
    }
    body.light tr.bg-emerald-500\/25 {
      background-color: #d1fae5 !important;
      color: #065f46 !important;
    }
    body.light code.bg-slate-900 {
      background-color: #e2e8f0 !important;
      color: #065f46 !important;
    }
    body.light #kpi-rejected { color: #e11d48 !important; }
    body.light #kpi-served-tbps { color: #059669 !important; }
    body.light #kpi-util-pct { color: #0284c7 !important; }
    body.light #kpi-capex { color: #7e22ce !important; }
    body.light #year-label-badge { color: #047857 !important; }
    body.light ::-webkit-scrollbar-track {
      background: #f1f5f9;
    }
    body.light ::-webkit-scrollbar-thumb {
      background: #94a3b8;
    }
  </style>
</head>
<body class="min-h-screen p-4 md:p-6 antialiased selection:bg-emerald-500 selection:text-white">

  <!-- HEADER PRINCIPAL -->
  <header class="glass-card p-4 mb-5 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-l-4 border-l-emerald-500">
    <div>
      <div class="flex items-center gap-2.5">
        <span class="px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 rounded-full">
          TEL-317 · UTFSM · Taller 3
        </span>
        <span class="px-2.5 py-0.5 text-xs font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/40 rounded-full">
          Banda C · 320 FSUs (12.5 GHz)
        </span>
      </div>
      <h1 class="text-xl md:text-2xl font-bold text-white mt-1">
        Simulador Estático EON: Migración Progresiva de SMF a HCF
      </h1>
      <p class="text-xs text-slate-400">
        Equipo: Fernanda Manríquez · Josefa Zamora · Benjamín Abde &nbsp;|&nbsp; Profesor: Dr. Nicolás Jara &nbsp;|&nbsp; Topología: NSFNet (14 nodos, 21 enlaces)
      </p>
    </div>

    <!-- NAVEGACIÓN DE PESTAÑAS Y SELECTOR DE TEMA -->
    <div class="flex flex-wrap items-center gap-2">
      <button onclick="switchMainTab('sim')" id="tab-btn-sim" class="px-3.5 py-2 rounded-lg text-xs font-bold bg-emerald-600 text-white shadow">
        1. Topología &amp; Espectro 320 FSUs
      </button>
      <button onclick="switchMainTab('qot')" id="tab-btn-qot" class="px-3.5 py-2 rounded-lg text-xs font-bold bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700">
        2. Laboratorio Capa Física GSNR (TEST-02)
      </button>
      <button onclick="switchMainTab('charts')" id="tab-btn-charts" class="px-3.5 py-2 rounded-lg text-xs font-bold bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700">
        3. Curvas Multi-Año (EXP-01 a EXP-03)
      </button>
      <button onclick="toggleTheme()" id="theme-toggle-btn" class="px-3.5 py-2 rounded-lg text-xs font-bold bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700 flex items-center gap-1.5 transition shadow" title="Alternar Modo Claro / Modo Oscuro">
        <span id="theme-icon">☀️</span> <span id="theme-text">Modo Claro</span>
      </button>
    </div>
  </header>

  <!-- CONTROLES GLOBALES DE ESTRATEGIA Y AÑO k -->
  <section id="global-controls" class="glass-card p-4 mb-5">
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
      <!-- Selector de Estrategia -->
      <div class="lg:col-span-7">
        <label class="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
          Estrategia de Migración Activa (Comparación en Igualdad de CAPEX &le; 8500 UR):
        </label>
        <div class="grid grid-cols-2 sm:grid-cols-5 gap-2">
          <button onclick="selectStrategy('smf')" id="strat-smf" class="strat-btn px-2.5 py-2 rounded-lg text-xs font-semibold border text-left transition">
            <div class="font-bold">100% SMF</div>
            <div class="text-slate-400 text-xs">Sin migración</div>
          </button>
          <button onclick="selectStrategy('c1_util')" id="strat-c1_util" class="strat-btn px-2.5 py-2 rounded-lg text-xs font-semibold border text-left transition">
            <div class="font-bold">Camino 1 (Util.)</div>
            <div class="text-slate-400 text-xs">Orden fijo slots</div>
          </button>
          <button onclick="selectStrategy('c1_greedy')" id="strat-c1_greedy" class="strat-btn px-2.5 py-2 rounded-lg text-xs font-semibold border text-left transition">
            <div class="font-bold">Camino 1 (Voraz)</div>
            <div class="text-slate-400 text-xs">Reemplazo &Delta;N/C</div>
          </button>
          <button onclick="selectStrategy('c2_parallel')" id="strat-c2_parallel" class="strat-btn px-2.5 py-2 rounded-lg text-xs font-semibold border text-left transition">
            <div class="font-bold">Camino 2 (Paralela)</div>
            <div class="text-slate-400 text-xs">SMF + HCF activa</div>
          </button>
          <button onclick="selectStrategy('c3_bypass')" id="strat-c3_bypass" class="strat-btn px-2.5 py-2 rounded-lg text-xs font-semibold border text-left transition">
            <div class="font-bold">Camino 3 (Bypass)</div>
            <div class="text-slate-400 text-xs">Enlace HCF directo</div>
          </button>
        </div>
      </div>

      <!-- Línea de Tiempo Año k = 0..8 -->
      <div class="lg:col-span-5 flex flex-col gap-2">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold uppercase tracking-wider text-slate-400">
            Fotografía Anual: <strong id="year-label-badge" class="text-emerald-400 text-sm">Año k = 0 (Factor 1.00x)</strong>
          </span>
          <div class="flex items-center gap-1.5">
            <button onclick="setYear(0)" class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-semibold border border-slate-700" title="Reiniciar a k=0">⏮ k=0</button>
            <button onclick="stepYear(-1)" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-bold border border-slate-700">◀</button>
            <button onclick="togglePlay()" id="play-btn" class="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow">▶ Play Demo</button>
            <button onclick="stepYear(1)" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-bold border border-slate-700">▶</button>
          </div>
        </div>
        <input type="range" id="year-slider" min="0" max="8" step="1" value="0" oninput="setYear(parseInt(this.value))" class="w-full accent-emerald-500 cursor-pointer" />
        <div class="flex justify-between text-xs text-slate-400 font-mono px-1">
          <span>k=0 (1.0x)</span>
          <span>k=2 (1.7x)</span>
          <span>k=4 (2.9x)</span>
          <span>k=6 (4.8x)</span>
          <span>k=8 (8.2x)</span>
        </div>
      </div>
    </div>
  </section>

  <!-- TARJETAS DE MÉTRICAS KPI EN VIVO -->
  <section class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
    <div class="glass-card p-4 border-t-2 border-t-rose-500">
      <div class="text-xs text-slate-400 font-semibold uppercase">Conexiones Fuera (Rechazadas)</div>
      <div class="flex items-baseline gap-2 mt-1">
        <span id="kpi-rejected" class="text-2xl md:text-3xl font-extrabold text-rose-400">0</span>
        <span id="kpi-rejected-pct" class="text-xs font-semibold text-slate-400">/ 71 solic. (0.0%)</span>
      </div>
      <div id="kpi-rejected-diff" class="text-xs text-emerald-400 mt-1 font-medium">
        Espectro: 0 | Capa Física GSNR: 0
      </div>
    </div>

    <div class="glass-card p-4 border-t-2 border-t-emerald-500">
      <div class="text-xs text-slate-400 font-semibold uppercase">Tráfico Atendido [Tbps]</div>
      <div class="flex items-baseline gap-2 mt-1">
        <span id="kpi-served-tbps" class="text-2xl md:text-3xl font-extrabold text-emerald-400">18.80</span>
        <span id="kpi-req-tbps" class="text-xs font-semibold text-slate-400">/ 18.80 Tbps</span>
      </div>
      <div id="kpi-unserved-tbps" class="text-xs text-slate-400 mt-1">
        No atendido: 0.00 Tbps
      </div>
    </div>

    <div class="glass-card p-4 border-t-2 border-t-sky-500">
      <div class="text-xs text-slate-400 font-semibold uppercase">Ocupación Espectral Banda C</div>
      <div class="flex items-baseline gap-2 mt-1">
        <span id="kpi-util-pct" class="text-2xl md:text-3xl font-extrabold text-sky-400">22.99%</span>
        <span id="kpi-used-fsus" class="text-xs font-semibold text-slate-400">(1545 / 6720 FSUs)</span>
      </div>
      <div id="kpi-bottleneck" class="text-xs text-amber-300 mt-1">
        Cuello de botella: e7_8 (65.6%)
      </div>
    </div>

    <div class="glass-card p-4 border-t-2 border-t-purple-500">
      <div class="text-xs text-slate-400 font-semibold uppercase">CAPEX Acumulado &amp; Fibra HCF</div>
      <div class="flex items-baseline gap-2 mt-1">
        <span id="kpi-capex" class="text-2xl md:text-3xl font-extrabold text-purple-400">0 UR</span>
        <span id="kpi-hcf-links" class="text-xs font-semibold text-slate-400">(0 enlaces HCF)</span>
      </div>
      <div id="kpi-actions-year" class="text-xs text-emerald-300 mt-1 truncate">
        Intervenciones año k: Ninguna
      </div>
    </div>
  </section>

  <!-- ======================================================================= -->
  <!-- PESTAÑA 1: SIMULADOR INTERACTIVO TOPOLOGÍA + ESPECTRO 320 FSUs          -->
  <!-- ======================================================================= -->
  <main id="tab-content-sim" class="space-y-5">
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
      <!-- MAPA TOPOLÓGICO INTERACTIVO NSFNET (SVG) -->
      <div class="lg:col-span-7 glass-card p-4 flex flex-col justify-between">
        <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div>
            <h2 class="text-base font-bold text-white">Topología de Transporte NSFNet (14 Nodos, Banda C)</h2>
            <p class="text-xs text-slate-400">Haz clic en cualquier enlace para inspeccionar sus 320 FSUs. Haz clic en una conexión para iluminar su ruta.</p>
          </div>
          <div class="flex flex-wrap items-center gap-3 text-xs">
            <span class="flex items-center gap-1.5"><span class="w-3 h-1 bg-slate-400 inline-block rounded"></span> SMF Activa</span>
            <span class="flex items-center gap-1.5"><span class="w-3 h-1 bg-emerald-400 inline-block rounded"></span> HCF Migrada / Paralela</span>
            <span class="flex items-center gap-1.5"><span class="w-3 h-1 bg-purple-400 inline-block rounded"></span> Bypass HCF Directo</span>
            <span class="flex items-center gap-1.5"><span class="w-3 h-1 bg-amber-400 inline-block rounded"></span> Ruta Seleccionada</span>
          </div>
        </div>

        <div class="relative w-full bg-slate-950/80 rounded-xl border border-slate-800 overflow-hidden" style="height: 390px;">
          <svg id="nsfnet-svg" viewBox="0 0 920 480" class="w-full h-full select-none"></svg>
        </div>

        <div id="selected-route-banner" class="mt-3 px-3 py-2 rounded-lg bg-slate-900/90 border border-slate-800 text-xs flex flex-wrap items-center justify-between gap-2">
          <span class="text-slate-300">Selecciona una conexión en la tabla derecha o un slot en el inspector inferior para auditar su ruta y GSNR.</span>
          <button onclick="clearSelectedConnection()" class="text-xs text-sky-400 hover:underline">Limpiar selección</button>
        </div>
      </div>

      <!-- TABLA DE CONEXIONES SOLICITADAS C(k) Y DISTRIBUCIÓN DE MODULACIONES -->
      <div class="lg:col-span-5 glass-card p-4 flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between mb-2">
            <h2 class="text-base font-bold text-white">Distribución de Modulaciones y Conexiones C(k)</h2>
            <select id="conn-filter" onchange="renderConnectionsTable()" class="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200">
              <option value="ALL">Todas las conexiones</option>
              <option value="ATENDIDA">Solo Atendidas</option>
              <option value="CONEXION_FUERA">Solo Conexiones Fuera (Rechazadas)</option>
            </select>
          </div>

          <!-- Barras de distribución de formatos de modulación -->
          <div id="mod-bars-container" class="grid grid-cols-6 gap-1.5 mb-3"></div>
        </div>

        <!-- Tabla scrollable de conexiones -->
        <div class="overflow-y-auto border border-slate-800 rounded-lg bg-slate-950/60" style="height: 295px;">
          <table class="w-full text-left border-collapse text-xs">
            <thead class="bg-slate-900 text-slate-400 sticky top-0 z-10">
              <tr>
                <th class="py-2 px-2.5">Conexión</th>
                <th class="py-2 px-2">O&rarr;D</th>
                <th class="py-2 px-2">Tasa</th>
                <th class="py-2 px-2">Modulación</th>
                <th class="py-2 px-2">GSNR</th>
                <th class="py-2 px-2">Slots [s*, s_f]</th>
              </tr>
            </thead>
            <tbody id="connections-tbody" class="divide-y divide-slate-800/70 font-mono"></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- INSPECTOR ESPECTRAL DE 320 FSUs Y CONTINUIDAD ESPECTRAL -->
    <div class="glass-card p-4">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-2 mb-3">
        <div>
          <h2 class="text-base font-bold text-white flex items-center gap-2">
            <span>Inspector Espectral de Banda C (320 Frequency Slot Units de 12.5 GHz)</span>
            <span id="inspector-link-badge" class="px-2.5 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/40 text-xs font-mono">Enlace e7_8</span>
          </h2>
          <p class="text-xs text-slate-400">
            Invariante Física #1: Tanto fibras SMF como HCF poseen exactamente 320 FSUs. HCF eleva el GSNR (+4.0 dB/span), permitiendo modulaciones superiores que usan menos FSUs por conexión.
          </p>
        </div>
        <!-- Leyenda de colores por formato de modulación -->
        <div class="flex flex-wrap gap-2 text-xs font-semibold">
          <span class="px-2 py-0.5 rounded bg-fuchsia-600 text-white">64-QAM (6b)</span>
          <span class="px-2 py-0.5 rounded bg-cyan-600 text-white">32-QAM (5b)</span>
          <span class="px-2 py-0.5 rounded bg-emerald-600 text-white">16-QAM (4b)</span>
          <span class="px-2 py-0.5 rounded bg-blue-600 text-white">8-QAM (3b)</span>
          <span class="px-2 py-0.5 rounded bg-amber-600 text-white">QPSK (2b)</span>
          <span class="px-2 py-0.5 rounded bg-rose-600 text-white">BPSK (1b)</span>
          <span class="px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">Libre</span>
        </div>
      </div>

      <!-- Barra de 320 slots del enlace seleccionado -->
      <div id="single-link-spectrum-bar" class="w-full h-10 bg-slate-950 rounded-lg border border-slate-800 p-1 flex gap-px overflow-hidden"></div>
      <div class="flex justify-between text-xs text-slate-500 font-mono mt-1 px-1">
        <span>Slot 0 (191.30 THz)</span>
        <span>Slot 80</span>
        <span>Slot 160 (193.30 THz)</span>
        <span>Slot 240</span>
        <span>Slot 319 (195.30 THz)</span>
      </div>

      <div id="slot-hover-info" class="mt-2 px-3 py-2 rounded bg-slate-900/90 border border-slate-800 text-xs font-mono text-slate-300">
        Pasa el cursor sobre cualquiera de los 320 slots para ver el detalle de la conexión alojada, su GSNR y su bloque contiguo.
      </div>

      <!-- DEMOSTRACIÓN VISUAL DE CONTINUIDAD Y CONTIGÜIDAD EN RUTA MULTI-SALTO -->
      <div id="route-continuity-panel" class="mt-4 pt-3 border-t border-slate-800">
        <div class="text-xs font-bold uppercase tracking-wider text-emerald-400 mb-2">
          Verificación Visual de Continuidad y Contigüidad Espectral en Ruta (Todos los enlaces de la conexión seleccionada):
        </div>
        <div id="route-continuity-stacks" class="space-y-2"></div>
      </div>
    </div>
  </main>

  <!-- ======================================================================= -->
  <!-- PESTAÑA 2: LABORATORIO INTERACTIVO CAPA FÍSICA GSNR (TEST-02)           -->
  <!-- ======================================================================= -->
  <section id="tab-content-qot" class="hidden space-y-5">
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
      <div class="lg:col-span-6 glass-card p-5 space-y-4">
        <h2 class="text-lg font-bold text-white">Calculadora Interactiva de GSNR por Suma Paralela Inversa</h2>
        <p class="text-xs text-slate-300 leading-relaxed">
          Ecuación física (Pedro et al. [1], [3]):
          <code class="px-2 py-0.5 rounded bg-slate-900 text-emerald-300 font-mono">
            GSNR_ruta(p)^(-1) = N_SMF / GSNR_1,SMF + N_HCF / GSNR_1,HCF
          </code>
          con <code class="text-sky-300">GSNR_1,SMF = 26.44 dB</code> (100 km) y <code class="text-emerald-300">&Delta;SNR_HCF = +4.0 dB</code>.
        </p>

        <!-- Sliders interactivos -->
        <div class="space-y-3 pt-2">
          <div>
            <div class="flex justify-between text-xs font-semibold mb-1">
              <span>Spans en Fibra SMF Estándar (100 km c/u):</span>
              <span id="calc-smf-val" class="text-sky-400 font-mono font-bold">18 spans (1800 km)</span>
            </div>
            <input type="range" id="calc-smf-slider" min="0" max="60" value="18" oninput="updateQoTCalculator()" class="w-full accent-sky-500" />
          </div>

          <div>
            <div class="flex justify-between text-xs font-semibold mb-1">
              <span>Spans Migrados a Fibra HCF (100 km c/u):</span>
              <span id="calc-hcf-val" class="text-emerald-400 font-mono font-bold">0 spans (0 km)</span>
            </div>
            <input type="range" id="calc-hcf-slider" min="0" max="60" value="0" oninput="updateQoTCalculator()" class="w-full accent-emerald-500" />
          </div>

          <div>
            <div class="flex justify-between text-xs font-semibold mb-1">
              <span>Tasa de Línea Solicitada (Bitrate):</span>
              <span id="calc-rate-val" class="text-purple-400 font-mono font-bold">400 Gbps</span>
            </div>
            <div class="flex gap-2">
              <button onclick="setCalcBitrate(10)" class="calc-rate-btn px-3 py-1 rounded bg-slate-800 text-xs font-bold border border-slate-700">10G</button>
              <button onclick="setCalcBitrate(40)" class="calc-rate-btn px-3 py-1 rounded bg-slate-800 text-xs font-bold border border-slate-700">40G</button>
              <button onclick="setCalcBitrate(100)" class="calc-rate-btn px-3 py-1 rounded bg-slate-800 text-xs font-bold border border-slate-700">100G</button>
              <button onclick="setCalcBitrate(400)" class="calc-rate-btn px-3 py-1 rounded bg-emerald-600 text-white text-xs font-bold">400G</button>
              <button onclick="setCalcBitrate(1000)" class="calc-rate-btn px-3 py-1 rounded bg-slate-800 text-xs font-bold border border-slate-700">1000G</button>
            </div>
          </div>
        </div>

        <!-- Botones rápidos de demostración TEST-02 -->
        <div class="pt-2 border-t border-slate-800">
          <div class="text-xs font-bold text-slate-400 uppercase mb-2">Escenarios Preconfigurados (TEST-02 para Demo):</div>
          <div class="flex flex-wrap gap-2">
            <button onclick="setCalcPreset(18, 0, 400)" class="px-2.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs border border-slate-700">1800 km: 100% SMF (8-QAM)</button>
            <button onclick="setCalcPreset(9, 9, 400)" class="px-2.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs border border-slate-700">1800 km: 50/50 Híbrida (16-QAM)</button>
            <button onclick="setCalcPreset(0, 18, 400)" class="px-2.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs border border-slate-700">1800 km: 100% HCF (32-QAM)</button>
            <button onclick="setCalcPreset(36, 0, 400)" class="px-2.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs border border-slate-700">3600 km: 100% SMF (QPSK, 16 FSUs)</button>
            <button onclick="setCalcPreset(0, 36, 400)" class="px-2.5 py-1.5 rounded bg-emerald-900/60 hover:bg-emerald-800/70 text-emerald-200 text-xs border border-emerald-600">3600 km: 100% HCF (16-QAM, 8 FSUs -50%)</button>
          </div>
        </div>

        <!-- Resultado en vivo -->
        <div id="calc-result-box" class="p-4 rounded-xl bg-slate-900 border border-emerald-500/40 grid grid-cols-3 gap-3 text-center"></div>
      </div>

      <!-- TABLA OFICIAL DE FORMATOS DE MODULACIÓN (TALLER 1 / SECCIÓN 4) -->
      <div class="lg:col-span-6 glass-card p-5">
        <h2 class="text-lg font-bold text-white mb-2">Tabla Oficial de Modulación, Umbrales SNR y FSUs (Sección 4)</h2>
        <p class="text-xs text-slate-400 mb-3">
          La fila resaltada en verde indica el formato de modulación seleccionado automáticamente para los parámetros del laboratorio.
        </p>
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs font-mono">
            <thead class="bg-slate-900 text-slate-300">
              <tr>
                <th class="p-2.5">Formato (m)</th>
                <th class="p-2">Eficiencia</th>
                <th class="p-2">Umbral SNR_th</th>
                <th class="p-2">Alcance SMF</th>
                <th class="p-2">10G</th>
                <th class="p-2">40G</th>
                <th class="p-2">100G</th>
                <th class="p-2">400G</th>
                <th class="p-2">1000G</th>
              </tr>
            </thead>
            <tbody id="mod-spec-tbody" class="divide-y divide-slate-800"></tbody>
          </table>
        </div>
      </div>
    </div>
  </section>

  <!-- ======================================================================= -->
  <!-- PESTAÑA 3: CURVAS MULTI-AÑO INTERACTIVAS (EXP-01, EXP-02, EXP-03)       -->
  <!-- ======================================================================= -->
  <section id="tab-content-charts" class="hidden space-y-5">
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div class="glass-card p-5">
        <h3 class="text-base font-bold text-white mb-1">EXP-01: Sensibilidad de Crecimiento Anual en Red 100% SMF</h3>
        <p class="text-xs text-slate-400 mb-3">Comparación de Conexiones Fuera para tasas TeleGeography (r = 24%, 30% base y 32%).</p>
        <svg id="chart-exp01-svg" viewBox="0 0 560 280" class="w-full bg-slate-950/70 rounded-lg border border-slate-800"></svg>
      </div>

      <div class="glass-card p-5">
        <h3 class="text-base font-bold text-white mb-1">EXP-03: Conexiones Fuera por Camino de Migración (CAPEX &le; 8500 UR)</h3>
        <p class="text-xs text-slate-400 mb-3">Comparación directa entre 100% SMF, Camino 1 (Reemplazo), Camino 2 (HCF Paralela) y Camino 3 (Bypass).</p>
        <svg id="chart-exp03-rej-svg" viewBox="0 0 560 280" class="w-full bg-slate-950/70 rounded-lg border border-slate-800"></svg>
      </div>

      <div class="glass-card p-5">
        <h3 class="text-base font-bold text-white mb-1">EXP-03: Tráfico Total Atendido [Tbps] en Igualdad de Presupuesto CAPEX</h3>
        <p class="text-xs text-slate-400 mb-3">Evolución anual del tráfico servido (k = 0 ... 8) con r = 30%.</p>
        <svg id="chart-exp03-tbps-svg" viewBox="0 0 560 280" class="w-full bg-slate-950/70 rounded-lg border border-slate-800"></svg>
      </div>

      <div class="glass-card p-5">
        <h3 class="text-base font-bold text-white mb-1">Resumen Comparativo Acumulado Multi-Año (k = 0 ... 8)</h3>
        <p class="text-xs text-slate-400 mb-3">Síntesis cuantitativa lista para las diapositivas del Taller 3.</p>
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs font-mono">
            <thead class="bg-slate-900 text-slate-300">
              <tr>
                <th class="p-2.5">Estrategia</th>
                <th class="p-2">CAPEX [UR]</th>
                <th class="p-2">Fuera (k=4)</th>
                <th class="p-2">Fuera Acum.</th>
                <th class="p-2">Tbps Servidos</th>
              </tr>
            </thead>
            <tbody id="summary-exp-tbody" class="divide-y divide-slate-800"></tbody>
          </table>
        </div>
      </div>
    </div>
  </section>

  <script>
    // DATOS REALES INYECTADOS DESDE EL MOTOR RMLSA EN PYTHON
    const SIM_DATA = __SIM_DATA_JSON__;
    Object.values(SIM_DATA.strategies).forEach(st => {
      st.years.forEach(yr => {
        yr.connections = yr.connections.map(c => ({
          uid: c.u,
          id: c.i,
          source: c.s,
          target: c.t,
          bitrate_gbps: c.b,
          status: c.a === 1 ? 'ATENDIDA' : 'CONEXION_FUERA',
          path_nodes: c.pn || [],
          path_links: c.pl || [],
          distance_km: c.d || 0,
          spans: c.sp || 0,
          gsnr_db: c.g,
          modulation: c.m,
          payload_fsus: c.pf || 0,
          total_fsus: c.tf || 0,
          start_slot: c.s0,
          end_slot: c.s1
        }));
      });
    });

    let currentStrategyKey = 'c1_greedy';
    let currentYear = 0;
    let selectedLinkId = 'e7_8';
    let selectedConnectionUid = null;
    let playInterval = null;
    let calcBitrate = 400;
    let currentTheme = localStorage.getItem('eon_theme') || 'dark';

    const MOD_COLORS = {
      '64-QAM': '#c026d3',
      '32-QAM': '#0891b2',
      '16-QAM': '#059669',
      '8-QAM':  '#2563eb',
      'QPSK':   '#d97706',
      'BPSK':   '#e11d48'
    };

    function applyTheme(theme) {
      currentTheme = theme;
      const isLight = (theme === 'light');
      document.body.classList.toggle('light', isLight);
      localStorage.setItem('eon_theme', theme);

      const btn = document.getElementById('theme-toggle-btn');
      const icon = document.getElementById('theme-icon');
      const text = document.getElementById('theme-text');
      if (btn && icon && text) {
        if (isLight) {
          icon.textContent = '🌙';
          text.textContent = 'Modo Oscuro';
          btn.className = 'px-3.5 py-2 rounded-lg text-xs font-bold bg-slate-100 text-slate-800 hover:bg-slate-200 border border-slate-300 flex items-center gap-1.5 shadow transition';
        } else {
          icon.textContent = '☀️';
          text.textContent = 'Modo Claro';
          btn.className = 'px-3.5 py-2 rounded-lg text-xs font-bold bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700 flex items-center gap-1.5 transition shadow';
        }
      }

      // Sincronizar estilo de pestañas y botones de estrategia
      const activeTab = ['sim', 'qot', 'charts'].find(t => !document.getElementById('tab-content-' + t).classList.contains('hidden')) || 'sim';
      switchMainTab(activeTab);
      selectStrategy(currentStrategyKey);
      setCalcBitrate(calcBitrate);

      // Redibujar SVG y gráficos con los colores del tema
      updateDashboard();
      if (!document.getElementById('tab-content-charts').classList.contains('hidden')) {
        renderAllCharts();
      }
    }

    function toggleTheme() {
      applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
    }

    function switchMainTab(tab) {
      const isLight = document.body.classList.contains('light');
      ['sim', 'qot', 'charts'].forEach(t => {
        document.getElementById('tab-content-' + t).classList.toggle('hidden', t !== tab);
        const btn = document.getElementById('tab-btn-' + t);
        if (t === tab) {
          btn.className = 'px-3.5 py-2 rounded-lg text-xs font-bold bg-emerald-600 text-white shadow';
        } else {
          btn.className = isLight
            ? 'px-3.5 py-2 rounded-lg text-xs font-bold bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-300 shadow-sm transition'
            : 'px-3.5 py-2 rounded-lg text-xs font-bold bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700 transition';
        }
      });
      if (tab === 'qot') updateQoTCalculator();
      if (tab === 'charts') renderAllCharts();
    }

    function selectStrategy(stratKey) {
      currentStrategyKey = stratKey;
      const isLight = document.body.classList.contains('light');
      ['smf', 'c1_util', 'c1_greedy', 'c2_parallel', 'c3_bypass'].forEach(k => {
        const btn = document.getElementById('strat-' + k);
        if (k === stratKey) {
          btn.className = isLight
            ? 'strat-btn px-2.5 py-2 rounded-lg text-xs font-semibold border-2 border-emerald-600 bg-emerald-50 text-emerald-900 shadow transition'
            : 'strat-btn px-2.5 py-2 rounded-lg text-xs font-semibold border border-emerald-400 bg-emerald-500/20 text-white shadow transition';
        } else {
          btn.className = isLight
            ? 'strat-btn px-2.5 py-2 rounded-lg text-xs font-semibold border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 transition'
            : 'strat-btn px-2.5 py-2 rounded-lg text-xs font-semibold border border-slate-700 bg-slate-900/80 text-slate-300 hover:bg-slate-800 transition';
        }
      });
      updateDashboard();
    }

    function setYear(yk) {
      currentYear = Math.max(0, Math.min(8, yk));
      document.getElementById('year-slider').value = currentYear;
      updateDashboard();
    }

    function stepYear(delta) {
      let next = currentYear + delta;
      if (next > 8) next = 0;
      if (next < 0) next = 8;
      setYear(next);
    }

    function togglePlay() {
      const btn = document.getElementById('play-btn');
      if (playInterval) {
        clearInterval(playInterval);
        playInterval = null;
        btn.textContent = '▶ Play Demo';
        btn.className = 'px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow';
      } else {
        btn.textContent = '⏸ Pausa';
        btn.className = 'px-3 py-1 rounded bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold shadow';
        playInterval = setInterval(() => {
          stepYear(1);
        }, 1600);
      }
    }

    function getCurrentYearSnapshot() {
      return SIM_DATA.strategies[currentStrategyKey].years[currentYear];
    }

    function getActiveLinksForCurrentState() {
      const strat = SIM_DATA.strategies[currentStrategyKey];
      const snap = strat.years[currentYear];
      const migratedSet = new Set(snap.migrated_cum);

      // Reconstruir estado y ocupación de cada enlace en el año actual a partir de las conexiones atendidas
      const linksMap = {};
      strat.links_catalog.forEach(lk => {
        // Si es paralelo o bypass, solo existe en la red si ya fue instalado en o antes del año actual
        if ((lk.is_parallel || lk.is_bypass) && !migratedSet.has(lk.id)) {
          return;
        }
        let fiber = 'SMF';
        if (lk.is_parallel || lk.is_bypass || migratedSet.has(lk.id)) {
          fiber = 'HCF';
        }
        linksMap[lk.id] = {
          ...lk,
          fiber_type: fiber,
          slots: new Array(320).fill(null),
          used_slots: 0
        };
      });

      snap.connections.forEach(conn => {
        if (conn.status !== 'ATENDIDA') return;
        conn.path_links.forEach(lid => {
          const linkObj = linksMap[lid];
          if (!linkObj) return;
          for (let s = conn.start_slot; s <= conn.end_slot; s++) {
            linkObj.slots[s] = conn;
          }
          linkObj.used_slots += conn.total_fsus;
        });
      });

      return linksMap;
    }

    function updateDashboard() {
      const snap = getCurrentYearSnapshot();
      const smfSnap = SIM_DATA.strategies['smf'].years[currentYear];
      const linksMap = getActiveLinksForCurrentState();

      if (!linksMap[selectedLinkId]) {
        selectedLinkId = 'e7_8';
      }

      document.getElementById('year-label-badge').textContent = `Año k = ${snap.year_k} (Factor ${snap.factor.toFixed(2)}x)`;

      // KPIs
      document.getElementById('kpi-rejected').textContent = snap.rej_conn;
      document.getElementById('kpi-rejected-pct').textContent = `/ ${snap.req_conn} solic. (${snap.rej_pct}%)`;
      const savedVsSmf = smfSnap.rej_conn - snap.rej_conn;
      const savedText = savedVsSmf > 0 ? ` (-${savedVsSmf} vs SMF)` : '';
      document.getElementById('kpi-rejected-diff').textContent = `Espectro: ${snap.rej_spec} | GSNR: ${snap.rej_qot}${savedText}`;

      document.getElementById('kpi-served-tbps').textContent = snap.served_tbps.toFixed(2);
      document.getElementById('kpi-req-tbps').textContent = `/ ${snap.req_tbps.toFixed(2)} Tbps`;
      document.getElementById('kpi-unserved-tbps').textContent = `No atendido: ${snap.unserved_tbps.toFixed(2)} Tbps`;

      document.getElementById('kpi-util-pct').textContent = `${snap.global_util_pct.toFixed(2)}%`;
      document.getElementById('kpi-used-fsus').textContent = `(${snap.used_fsus} / ${snap.cap_fsus} FSUs)`;
      document.getElementById('kpi-bottleneck').textContent = `Cuello de botella: ${snap.bottleneck_link} (${snap.max_link_util_pct.toFixed(1)}%)`;

      document.getElementById('kpi-capex').textContent = `${snap.cum_capex_ur.toFixed(0)} UR`;
      document.getElementById('kpi-hcf-links').textContent = `(${snap.hcf_links_count} enlaces HCF / ${snap.hcf_km} km)`;
      document.getElementById('kpi-actions-year').textContent = snap.actions_year.length > 0
        ? `Migrados en k=${snap.year_k}: ${snap.actions_year.join(', ')}`
        : `Intervenciones en k=${snap.year_k}: Ninguna`;

      renderTopologySVG(linksMap, snap);
      renderModulationBars(snap);
      renderConnectionsTable();
      renderSpectrumInspector(linksMap, snap);
    }

    function renderTopologySVG(linksMap, snap) {
      const svg = document.getElementById('nsfnet-svg');
      svg.innerHTML = '';
      const isLight = document.body.classList.contains('light');

      // Escalar coordenadas de nodos al canvas 920x480
      const nodeCoords = {};
      SIM_DATA.nodes.forEach(n => {
        const x = 60 + (n.pos[0] - 0.5) * 98;
        const y = 435 - (n.pos[1] - 0.8) * 95;
        nodeCoords[n.id] = { x, y, name: n.name, city: n.city };
      });

      const selectedConn = snap.connections.find(c => c.uid === selectedConnectionUid);
      const highlightedLinks = new Set(selectedConn && selectedConn.path_links ? selectedConn.path_links : []);

      // Dibujar enlaces
      Object.values(linksMap).forEach(lk => {
        const p1 = nodeCoords[lk.source];
        const p2 = nodeCoords[lk.target];
        const utilRatio = lk.used_slots / 320.0;
        const isSelectedLink = lk.id === selectedLinkId;
        const isHighlightedRoute = highlightedLinks.has(lk.id);

        let strokeColor = isLight ? '#64748b' : '#64748b';
        if (lk.is_bypass) {
          strokeColor = isLight ? '#9333ea' : '#c084fc';
        } else if (lk.fiber_type === 'HCF') {
          strokeColor = isLight ? '#059669' : '#10b981';
        } else if (utilRatio >= 0.9) {
          strokeColor = isLight ? '#e11d48' : '#f43f5e';
        } else if (utilRatio >= 0.7) {
          strokeColor = isLight ? '#d97706' : '#f59e0b';
        }

        if (isHighlightedRoute) {
          strokeColor = isLight ? '#d97706' : '#fbbf24';
        }

        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.style.cursor = 'pointer';
        g.onclick = () => {
          selectedLinkId = lk.id;
          renderTopologySVG(linksMap, snap);
          renderSpectrumInspector(linksMap, snap);
        };

        // Si es paralelo o bypass, dibujar curva desplazada para distinguir ambas fibras
        let pathD = `M ${p1.x} ${p1.y} L ${p2.x} ${p2.y}`;
        let labelX = (p1.x + p2.x) / 2;
        let labelY = (p1.y + p2.y) / 2;

        if (lk.is_parallel || lk.is_bypass) {
          const dx = p2.x - p1.x;
          const dy = p2.y - p1.y;
          const norm = Math.hypot(dx, dy) || 1;
          const offset = lk.is_bypass ? 42 : 18;
          const cx = (p1.x + p2.x) / 2 - (dy / norm) * offset;
          const cy = (p1.y + p2.y) / 2 + (dx / norm) * offset;
          pathD = `M ${p1.x} ${p1.y} Q ${cx} ${cy} ${p2.x} ${p2.y}`;
          labelX = (p1.x + 2 * cx + p2.x) / 4;
          labelY = (p1.y + 2 * cy + p2.y) / 4;
        }

        if (isSelectedLink || isHighlightedRoute) {
          const halo = document.createElementNS('http://www.w3.org/2000/svg', 'path');
          halo.setAttribute('d', pathD);
          halo.setAttribute('fill', 'none');
          halo.setAttribute('stroke', isHighlightedRoute ? '#fbbf24' : '#38bdf8');
          halo.setAttribute('stroke-width', '9');
          halo.setAttribute('stroke-opacity', isLight ? '0.45' : '0.28');
          g.appendChild(halo);
        }

        const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        pathEl.setAttribute('d', pathD);
        pathEl.setAttribute('fill', 'none');
        pathEl.setAttribute('stroke', strokeColor);
        pathEl.setAttribute('stroke-width', isSelectedLink || isHighlightedRoute ? '4.2' : '2.8');
        if (isHighlightedRoute) {
          pathEl.setAttribute('class', 'route-animated');
        }
        g.appendChild(pathEl);

        // Etiqueta compacta del enlace con halo de alto contraste
        const tag = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        tag.setAttribute('x', labelX);
        tag.setAttribute('y', labelY - 5);
        tag.setAttribute('text-anchor', 'middle');
        tag.setAttribute('fill', lk.fiber_type === 'HCF' ? (isLight ? '#065f46' : '#6ee7b7') : (isLight ? '#0f172a' : '#f1f5f9'));
        tag.setAttribute('font-size', '10.5');
        tag.setAttribute('font-weight', '800');
        tag.setAttribute('style', isLight
          ? 'paint-order: stroke; stroke: #f8fafc; stroke-width: 3.5px; stroke-linecap: round; stroke-linejoin: round;'
          : 'paint-order: stroke; stroke: #020617; stroke-width: 3.5px; stroke-linecap: round; stroke-linejoin: round;');
        tag.textContent = `${lk.id} (${Math.round(utilRatio * 100)}%)`;
        g.appendChild(tag);

        svg.appendChild(g);
      });

      // Dibujar los 14 nodos de NSFNet
      SIM_DATA.nodes.forEach(n => {
        const c = nodeCoords[n.id];
        const isEndpoint = selectedConn && (selectedConn.source === n.id || selectedConn.target === n.id);
        const isInPath = selectedConn && selectedConn.path_nodes && selectedConn.path_nodes.includes(n.id);

        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');

        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', c.x);
        circle.setAttribute('cy', c.y);
        circle.setAttribute('r', isEndpoint ? '16' : '13');
        circle.setAttribute('fill', isEndpoint ? (isLight ? '#d97706' : '#f59e0b') : (isInPath ? '#0284c7' : (isLight ? '#ffffff' : '#1e293b')));
        circle.setAttribute('stroke', isEndpoint ? (isLight ? '#b45309' : '#fde68a') : (isLight ? '#0284c7' : '#38bdf8'));
        circle.setAttribute('stroke-width', '2.5');
        g.appendChild(circle);

        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.setAttribute('x', c.x);
        label.setAttribute('y', c.y + 4);
        label.setAttribute('text-anchor', 'middle');
        label.setAttribute('fill', (isEndpoint || isInPath) ? '#ffffff' : (isLight ? '#0f172a' : '#ffffff'));
        label.setAttribute('font-size', '10.5');
        label.setAttribute('font-weight', '800');
        label.textContent = `N${n.id}`;
        g.appendChild(label);

        const city = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        city.setAttribute('x', c.x);
        city.setAttribute('y', c.y + 26);
        city.setAttribute('text-anchor', 'middle');
        city.setAttribute('fill', isLight ? '#0f172a' : '#e2e8f0');
        city.setAttribute('font-size', '10.5');
        city.setAttribute('font-weight', isLight ? '700' : '600');
        city.setAttribute('style', isLight
          ? 'paint-order: stroke; stroke: #f8fafc; stroke-width: 3px; stroke-linecap: round; stroke-linejoin: round;'
          : 'paint-order: stroke; stroke: #020617; stroke-width: 3px; stroke-linecap: round; stroke-linejoin: round;');
        city.textContent = n.city;
        g.appendChild(city);

        svg.appendChild(g);
      });
    }

    function renderModulationBars(snap) {
      const container = document.getElementById('mod-bars-container');
      container.innerHTML = '';
      const mods = ['64-QAM', '32-QAM', '16-QAM', '8-QAM', 'QPSK', 'BPSK'];
      const totalAlloc = Math.max(1, snap.alloc_conn);

      mods.forEach(m => {
        const count = snap.mod_dist[m] || 0;
        const pct = Math.round((100 * count) / totalAlloc);
        const div = document.createElement('div');
        div.className = 'p-2 rounded-lg bg-slate-900 border border-slate-800 text-center';
        div.innerHTML = `
          <div class="text-xs font-bold" style="color:${MOD_COLORS[m]}">${m}</div>
          <div class="text-sm font-extrabold text-white mt-0.5">${count}</div>
          <div class="text-xs text-slate-400">${pct}%</div>
        `;
        container.appendChild(div);
      });
    }

    function renderConnectionsTable() {
      const snap = getCurrentYearSnapshot();
      const filterVal = document.getElementById('conn-filter').value;
      const tbody = document.getElementById('connections-tbody');
      tbody.innerHTML = '';

      const filtered = snap.connections.filter(c => filterVal === 'ALL' || c.status === filterVal);

      filtered.forEach(c => {
        const tr = document.createElement('tr');
        const isSel = c.uid === selectedConnectionUid;
        tr.className = `cursor-pointer transition ${isSel ? 'bg-amber-500/20 text-white' : 'hover:bg-slate-900/90 text-slate-300'}`;
        tr.onclick = () => {
          selectedConnectionUid = c.uid;
          if (c.path_links && c.path_links.length > 0) {
            selectedLinkId = c.path_links[0];
          }
          updateDashboard();
        };

        const statusBadge = c.status === 'ATENDIDA'
          ? `<span class="mod-badge px-1.5 py-0.5 rounded text-white text-xs font-bold" style="background:${MOD_COLORS[c.modulation] || '#475569'}">${c.modulation}</span>`
          : `<span class="px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 text-xs font-bold">FUERA (Espectro)</span>`;

        const slotsText = c.status === 'ATENDIDA'
          ? `[${c.start_slot}, ${c.end_slot}] (${c.total_fsus})`
          : '-';

        tr.innerHTML = `
          <td class="py-1.5 px-2.5 font-semibold">${c.id}</td>
          <td class="py-1.5 px-2">N${c.source}&rarr;N${c.target}</td>
          <td class="py-1.5 px-2">${c.bitrate_gbps}G</td>
          <td class="py-1.5 px-2">${statusBadge}</td>
          <td class="py-1.5 px-2">${c.gsnr_db ? c.gsnr_db + ' dB' : '-'}</td>
          <td class="py-1.5 px-2">${slotsText}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function clearSelectedConnection() {
      selectedConnectionUid = null;
      updateDashboard();
    }

    function renderSpectrumInspector(linksMap, snap) {
      const linkObj = linksMap[selectedLinkId] || Object.values(linksMap)[0];
      if (!linkObj) return;
      const isLight = document.body.classList.contains('light');

      document.getElementById('inspector-link-badge').textContent =
        `${linkObj.id} (N${linkObj.source}↔N${linkObj.target} | ${linkObj.length_km} km | ${linkObj.spans} spans | ${linkObj.fiber_type} | ${linkObj.used_slots}/320 FSUs ocupados)`;

      const bar = document.getElementById('single-link-spectrum-bar');
      bar.innerHTML = '';
      const hoverInfo = document.getElementById('slot-hover-info');

      for (let s = 0; s < 320; s++) {
        const conn = linkObj.slots[s];
        const cell = document.createElement('div');
        cell.className = 'slot-cell flex-1 h-full rounded-[1px] cursor-pointer';
        if (conn) {
          const isGuard = (s === conn.end_slot);
          cell.style.backgroundColor = isGuard ? (isLight ? '#475569' : '#f8fafc') : (MOD_COLORS[conn.modulation] || '#10b981');
          cell.style.opacity = (selectedConnectionUid === null || selectedConnectionUid === conn.uid) ? '1.0' : '0.35';
          cell.onmouseenter = () => {
            hoverInfo.innerHTML = `
              <strong class="text-emerald-400">Slot #${s}</strong> (${isGuard ? 'Banda de Guarda G=1' : 'Payload Activo'}) &nbsp;|&nbsp;
              <strong>Conexión:</strong> ${conn.id} (N${conn.source}&rarr;N${conn.target}, ${conn.bitrate_gbps} Gbps) &nbsp;|&nbsp;
              <strong>Ruta:</strong> [${conn.path_nodes.map(n => 'N'+n).join('&rarr;')}] (${conn.distance_km} km) &nbsp;|&nbsp;
              <strong>GSNR:</strong> ${conn.gsnr_db} dB (${conn.modulation}) &nbsp;|&nbsp;
              <strong>Bloque Contiguo:</strong> [${conn.start_slot}, ${conn.end_slot}] (${conn.payload_fsus} FSUs + 1 guarda = ${conn.total_fsus} slots)
            `;
          };
          cell.onclick = () => {
            selectedConnectionUid = conn.uid;
            updateDashboard();
          };
        } else {
          cell.style.backgroundColor = isLight ? '#e2e8f0' : '#1e293b';
          cell.onmouseenter = () => {
            hoverInfo.innerHTML = `<strong class="text-slate-400">Slot #${s}</strong>: Libre en el enlace <strong>${linkObj.id}</strong>.`;
          };
        }
        bar.appendChild(cell);
      }

      // Renderizar pila de continuidad espectral para la conexión seleccionada (o la primera conexión del enlace)
      const activeConn = snap.connections.find(c => c.uid === selectedConnectionUid && c.status === 'ATENDIDA')
        || linkObj.slots.find(x => x !== null);

      const banner = document.getElementById('selected-route-banner');
      const stackContainer = document.getElementById('route-continuity-stacks');
      stackContainer.innerHTML = '';

      if (activeConn && activeConn.status === 'ATENDIDA') {
        banner.innerHTML = `
          <span>
            <strong class="text-amber-300">Ruta Seleccionada:</strong> ${activeConn.id} (N${activeConn.source}&rarr;N${activeConn.target}, ${activeConn.bitrate_gbps} Gbps)
            &nbsp;|&nbsp; <strong>Nodos:</strong> ${activeConn.path_nodes.map(n => 'N'+n).join(' &rarr; ')}
            &nbsp;|&nbsp; <strong>GSNR:</strong> ${activeConn.gsnr_db} dB (${activeConn.modulation})
            &nbsp;|&nbsp; <strong>Slots Continuos:</strong> [${activeConn.start_slot}, ${activeConn.end_slot}] (${activeConn.total_fsus} FSUs)
          </span>
          <button onclick="clearSelectedConnection()" class="text-xs text-sky-400 hover:underline">Limpiar selección</button>
        `;

        activeConn.path_links.forEach(lid => {
          const hopLink = linksMap[lid];
          if (!hopLink) return;
          const row = document.createElement('div');
          row.className = 'flex items-center gap-3';

          const label = document.createElement('div');
          label.className = 'w-44 text-xs font-mono text-slate-300 shrink-0';
          label.innerHTML = `<span class="font-bold text-white">${hopLink.id}</span> <span class="${hopLink.fiber_type==='HCF'?'text-emerald-400':'text-slate-400'}">(${hopLink.fiber_type}, ${hopLink.length_km}km)</span>`;
          row.appendChild(label);

          const miniBar = document.createElement('div');
          miniBar.className = 'flex-1 h-5 bg-slate-950 rounded border border-slate-800 p-0.5 flex gap-px overflow-hidden';
          for (let s = 0; s < 320; s++) {
            const c = hopLink.slots[s];
            const d = document.createElement('div');
            d.className = 'flex-1 h-full';
            if (c && c.uid === activeConn.uid) {
              d.style.backgroundColor = '#fbbf24';
            } else if (c) {
              d.style.backgroundColor = isLight ? '#94a3b8' : '#334155';
            } else {
              d.style.backgroundColor = isLight ? '#e2e8f0' : '#0f172a';
            }
            miniBar.appendChild(d);
          }
          row.appendChild(miniBar);
          stackContainer.appendChild(row);
        });
      }
    }

    // =========================================================================
    // PESTAÑA 2: CALCULADORA INTERACTIVA DE CAPA FÍSICA GSNR (TEST-02)
    // =========================================================================
    function setCalcBitrate(rate) {
      calcBitrate = rate;
      document.getElementById('calc-rate-val').textContent = `${rate} Gbps`;
      const isLight = document.body.classList.contains('light');
      document.querySelectorAll('.calc-rate-btn').forEach(btn => {
        if (btn.textContent === rate + 'G') {
          btn.className = 'calc-rate-btn px-3 py-1 rounded bg-emerald-600 text-white text-xs font-bold shadow';
        } else {
          btn.className = isLight
            ? 'calc-rate-btn px-3 py-1 rounded bg-slate-100 text-slate-700 hover:bg-slate-200 text-xs font-bold border border-slate-300'
            : 'calc-rate-btn px-3 py-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs font-bold border border-slate-700';
        }
      });
      updateQoTCalculator();
    }

    function setCalcPreset(nSmf, nHcf, rate) {
      document.getElementById('calc-smf-slider').value = nSmf;
      document.getElementById('calc-hcf-slider').value = nHcf;
      setCalcBitrate(rate);
    }

    function updateQoTCalculator() {
      const nSmf = parseInt(document.getElementById('calc-smf-slider').value);
      const nHcf = parseInt(document.getElementById('calc-hcf-slider').value);
      const totalSpans = Math.max(1, nSmf + nHcf);

      document.getElementById('calc-smf-val').textContent = `${nSmf} spans (${nSmf * 100} km)`;
      document.getElementById('calc-hcf-val').textContent = `${nHcf} spans (${nHcf * 100} km)`;

      const gsnrSmfLin = Math.pow(10, SIM_DATA.gsnr_1span_smf_db / 10.0);
      const gsnrHcfLin = Math.pow(10, (SIM_DATA.gsnr_1span_smf_db + SIM_DATA.delta_snr_hcf_db) / 10.0);
      const invSum = (nSmf / gsnrSmfLin) + (nHcf / gsnrHcfLin);
      const gsnrDb = invSum > 0 ? 10 * Math.log10(1.0 / invSum) : 0.0;

      // Buscar formato de modulación factible
      let chosenMod = null;
      for (const m of SIM_DATA.modulations) {
        if (gsnrDb + 1e-9 >= m.snr_th) {
          chosenMod = m;
          break;
        }
      }

      const box = document.getElementById('calc-result-box');
      if (chosenMod) {
        const nFsu = chosenMod.fsus[String(calcBitrate)];
        box.innerHTML = `
          <div>
            <div class="text-xs text-slate-400">Distancia Total</div>
            <div class="text-xl font-extrabold text-white mt-0.5">${totalSpans * 100} km</div>
            <div class="text-xs text-slate-400">${nSmf} SMF + ${nHcf} HCF</div>
          </div>
          <div>
            <div class="text-xs text-slate-400">GSNR Acumulado</div>
            <div class="text-xl font-extrabold text-emerald-400 mt-0.5">${gsnrDb.toFixed(2)} dB</div>
            <div class="text-xs text-slate-400">Umbral: ${chosenMod.snr_th} dB</div>
          </div>
          <div>
            <div class="text-xs text-slate-400">Modulación &amp; FSUs</div>
            <div class="text-xl font-extrabold text-amber-300 mt-0.5">${chosenMod.name}</div>
            <div class="text-xs text-emerald-300 font-bold">${nFsu} FSUs (+1 guarda = ${nFsu + 1})</div>
          </div>
        `;
      } else {
        box.innerHTML = `
          <div class="col-span-3 text-rose-400 font-bold">
            Ruta Físicamente Infactible: GSNR = ${gsnrDb.toFixed(2)} dB &lt; 5.3 dB (Umbral mínimo BPSK)
          </div>
        `;
      }

      // Renderizar tabla de modulaciones resaltando la fila elegida
      const tbody = document.getElementById('mod-spec-tbody');
      tbody.innerHTML = '';
      SIM_DATA.modulations.slice().reverse().forEach(m => {
        const isActive = chosenMod && chosenMod.name === m.name;
        const tr = document.createElement('tr');
        tr.className = isActive ? 'bg-emerald-500/25 text-white font-bold' : 'text-slate-300';
        tr.innerHTML = `
          <td class="p-2.5">${m.name}</td>
          <td class="p-2">${m.eff} bit/s/Hz</td>
          <td class="p-2">${m.snr_th.toFixed(1)} dB</td>
          <td class="p-2">${m.spans_smf} spans</td>
          <td class="p-2">${m.fsus['10']}</td>
          <td class="p-2">${m.fsus['40']}</td>
          <td class="p-2">${m.fsus['100']}</td>
          <td class="p-2">${m.fsus['400']}</td>
          <td class="p-2">${m.fsus['1000']}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    // =========================================================================
    // PESTAÑA 3: GRÁFICOS MULTI-AÑO SVG (EXP-01, EXP-02, EXP-03)
    // =========================================================================
    function drawLineChartSVG(svgId, seriesList, yMax, yLabel) {
      const svg = document.getElementById(svgId);
      svg.innerHTML = '';
      const isLight = document.body.classList.contains('light');
      const gridColor = isLight ? '#cbd5e1' : '#1e293b';
      const textColor = isLight ? '#0f172a' : '#94a3b8';
      const legendTextColor = isLight ? '#0f172a' : '#e2e8f0';

      const W = 560, H = 280, padL = 52, padR = 20, padT = 22, padB = 36;
      const plotW = W - padL - padR;
      const plotH = H - padT - padB;

      // Ejes y grilla
      for (let i = 0; i <= 4; i++) {
        const yVal = Math.round((yMax * i) / 4);
        const yPos = padT + plotH - (plotH * i) / 4;
        svg.innerHTML += `
          <line x1="${padL}" y1="${yPos}" x2="${W - padR}" y2="${yPos}" stroke="${gridColor}" stroke-width="1" />
          <text x="${padL - 8}" y="${yPos + 4}" text-anchor="end" fill="${textColor}" font-size="10" font-weight="600">${yVal}</text>
        `;
      }

      for (let k = 0; k <= 8; k++) {
        const xPos = padL + (plotW * k) / 8;
        svg.innerHTML += `
          <line x1="${xPos}" y1="${padT}" x2="${xPos}" y2="${padT + plotH}" stroke="${gridColor}" stroke-width="1" />
          <text x="${xPos}" y="${H - 12}" text-anchor="middle" fill="${textColor}" font-size="10" font-weight="600">k=${k}</text>
        `;
      }

      // Series
      seriesList.forEach((s, idx) => {
        const pts = s.values.map((v, k) => {
          const x = padL + (plotW * k) / 8;
          const y = padT + plotH - (plotH * Math.min(yMax, v)) / yMax;
          return `${x},${y}`;
        }).join(' ');

        svg.innerHTML += `<polyline fill="none" stroke="${s.color}" stroke-width="2.6" points="${pts}" />`;
        s.values.forEach((v, k) => {
          const x = padL + (plotW * k) / 8;
          const y = padT + plotH - (plotH * Math.min(yMax, v)) / yMax;
          svg.innerHTML += `<circle cx="${x}" cy="${y}" r="3.5" fill="${s.color}" />`;
        });

        // Leyenda
        const lx = padL + 12;
        const ly = padT + 14 + idx * 16;
        svg.innerHTML += `
          <rect x="${lx}" y="${ly - 7}" width="12" height="3" fill="${s.color}" />
          <text x="${lx + 18}" y="${ly - 2}" fill="${legendTextColor}" font-size="10" font-weight="bold">${s.label}</text>
        `;
      });
    }

    function renderAllCharts() {
      drawLineChartSVG('chart-exp01-svg', [
        { label: 'r = 32% (CAGR Histórico 2020-2024)', color: '#38bdf8', values: SIM_DATA.sensitivity_smf.r32 },
        { label: 'r = 30% (Escenario Base Taller 3)', color: '#f43f5e', values: SIM_DATA.sensitivity_smf.r30 },
        { label: 'r = 24% (Proyección 2025-2035)', color: '#10b981', values: SIM_DATA.sensitivity_smf.r24 }
      ], 1000, 'Conexiones Fuera');

      drawLineChartSVG('chart-exp03-rej-svg', [
        { label: '100% SMF (Sin Migración)', color: '#f43f5e', values: SIM_DATA.strategies.smf.years.map(y => y.rej_conn) },
        { label: 'Camino 1: Reemplazo SMF→HCF (8285 UR)', color: '#38bdf8', values: SIM_DATA.strategies.c1_greedy.years.map(y => y.rej_conn) },
        { label: 'Camino 3: Bypass HCF Directo (7810 UR)', color: '#c084fc', values: SIM_DATA.strategies.c3_bypass.years.map(y => y.rej_conn) },
        { label: 'Camino 2: HCF Paralela Activa (8335 UR)', color: '#10b981', values: SIM_DATA.strategies.c2_parallel.years.map(y => y.rej_conn) }
      ], 1000, 'Conexiones Fuera');

      drawLineChartSVG('chart-exp03-tbps-svg', [
        { label: 'Camino 2: HCF Paralela Activa (526.9 Tbps acum.)', color: '#10b981', values: SIM_DATA.strategies.c2_parallel.years.map(y => y.served_tbps) },
        { label: 'Camino 3: Bypass HCF Directo (492.6 Tbps acum.)', color: '#c084fc', values: SIM_DATA.strategies.c3_bypass.years.map(y => y.served_tbps) },
        { label: 'Camino 1: Reemplazo SMF→HCF (439.4 Tbps acum.)', color: '#38bdf8', values: SIM_DATA.strategies.c1_greedy.years.map(y => y.served_tbps) },
        { label: '100% SMF Sin Migración (385.6 Tbps acum.)', color: '#f43f5e', values: SIM_DATA.strategies.smf.years.map(y => y.served_tbps) }
      ], 115, 'Tbps Atendidos');

      const tbody = document.getElementById('summary-exp-tbody');
      tbody.innerHTML = '';
      const rows = [
        { name: 'Sin Migración (100% SMF)', s: SIM_DATA.strategies.smf },
        { name: 'Camino 1: Baseline Utilización', s: SIM_DATA.strategies.c1_util },
        { name: 'Camino 1: Voraz (ΔN_fuera/Costo)', s: SIM_DATA.strategies.c1_greedy },
        { name: 'Camino 2: Fibra HCF Paralela', s: SIM_DATA.strategies.c2_parallel },
        { name: 'Camino 3: Bypass HCF Directo', s: SIM_DATA.strategies.c3_bypass }
      ];
      rows.forEach(r => {
        tbody.innerHTML += `
          <tr class="text-slate-200">
            <td class="p-2.5 font-bold">${r.name}</td>
            <td class="p-2">${r.s.total_capex_ur} UR</td>
            <td class="p-2">${r.s.years[4].rej_conn}</td>
            <td class="p-2 font-bold text-rose-300">${r.s.cum_rejected}</td>
            <td class="p-2 font-bold text-emerald-300">${r.s.cum_served_tbps} Tbps</td>
          </tr>
        `;
      });
    }

    // Inicializar aplicación
    window.addEventListener('DOMContentLoaded', () => {
      if (currentTheme === 'light') {
        applyTheme('light');
      } else {
        selectStrategy('c1_greedy');
        updateQoTCalculator();
        renderAllCharts();
      }
    });
  </script>
</body>
</html>
"""


def build_dashboard_files() -> Path:
    data = collect_all_simulation_data()
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html_content = HTML_TEMPLATE.replace("__SIM_DATA_JSON__", json_str)

    out_project = Path("dashboard_simulador_taller3.html")
    out_project.write_text(html_content, encoding="utf-8")
    print(f"[OK] Dashboard interactivo generado en: {out_project.resolve()}")
    return out_project


if __name__ == "__main__":
    build_dashboard_files()
