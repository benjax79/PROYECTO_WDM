"""
build_powerpoint_taller3.py
===========================
Genera la presentación oficial en formato PowerPoint Widescreen 16:9
(`Presentacion_Taller3_SMF_HCF.pptx` y `results/Presentacion_Taller3_SMF_HCF.pptx`)
diseñada específicamente para obtener la nota máxima (100/100) en el Taller 3
de TEL-317 Redes Ópticas WDM (UTFSM).

Incluye:
- 10 diapositivas estructuradas según la rúbrica oficial (Parte C: 10 pts,
  Parte A: 40 pts, Parte B: 50 pts) y el tiempo reglamentario de 10 minutos.
- Diagrama de topología NSFNet generado en alta resolución (`results/fig0_topologia_nsfnet.png`).
- Figuras experimentales incrustadas (`fig1` a `fig4`).
- Tablas ejecutivas de alto contraste, tarjetas KPI y ecuaciones físicas.
- Notas del orador (Speaker Notes) detalladas con tiempos minuto a minuto en cada diapositiva.
"""

from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

from config import NSFNET_NODES, NSFNET_LINKS
from topology import calculate_num_spans


# Paleta de colores corporativa / académica de alto contraste (Modo Claro Ejecutivo)
C_NAVY_DARK = RGBColor(15, 23, 42)      # #0F172A - Encabezados oscuros y texto principal
C_SLATE_DARK = RGBColor(30, 41, 59)     # #1E293B - Subtítulos y cabeceras de tabla
C_SLATE_MUTED = RGBColor(71, 85, 105)   # #475569 - Texto secundario
C_BG_LIGHT = RGBColor(248, 250, 252)    # #F8FAFC - Fondo general de diapositiva
C_CARD_WHITE = RGBColor(255, 255, 255)  # #FFFFFF - Fondo de tarjetas
C_CARD_BORDER = RGBColor(203, 213, 225) # #CBD5E1 - Borde de tarjetas

C_EMERALD = RGBColor(5, 150, 105)       # #059669 - Éxito / HCF / Camino 2
C_EMERALD_BG = RGBColor(209, 250, 229)  # #D1FAE5 - Fondo suave verde
C_SKY = RGBColor(2, 132, 199)           # #0284C7 - SMF / Camino 1
C_SKY_BG = RGBColor(224, 242, 254)      # #E0F2FE - Fondo suave azul
C_PURPLE = RGBColor(126, 34, 206)       # #7E22CE - Bypass / Camino 3
C_PURPLE_BG = RGBColor(243, 232, 255)   # #F3E8FF - Fondo suave morado
C_ROSE = RGBColor(225, 29, 72)          # #E11D48 - Rechazos / Alerta SMF
C_ROSE_BG = RGBColor(255, 228, 230)     # #FFE4E6 - Fondo suave rojo
C_AMBER = RGBColor(180, 83, 9)          # #B45309 - Advertencia / Destacado
C_AMBER_BG = RGBColor(254, 243, 199)    # #FEF3C7 - Fondo suave ámbar
C_WHITE = RGBColor(255, 255, 255)


def generate_nsfnet_topology_figure(out_path: Path) -> Path:
    """Genera un diagrama limpio y de alta resolución de la topología NSFNet (14 nodos, 21 enlaces)."""
    fig, ax = plt.subplots(figsize=(8.2, 4.8), dpi=240)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    pos = {int(n["id"]): n["pos"] for n in NSFNET_NODES}
    cities = {int(n["id"]): str(n["city"]) for n in NSFNET_NODES}

    # Enlaces críticos que migran primero o son cuellos de botella centrales
    core_links = {"e3_4", "e3_10", "e7_8", "e6_7", "e4_6", "e8_9"}

    for lk in NSFNET_LINKS:
        u, v = int(lk["source"]), int(lk["target"])
        dist = float(lk["length_km"])
        spans = calculate_num_spans(dist, 100.0)
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        is_core = lk["id"] in core_links

        ax.plot(
            [x1, x2],
            [y1, y2],
            color="#059669" if is_core else "#64748B",
            linewidth=2.8 if is_core else 2.0,
            zorder=2,
        )
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        ax.text(
            mx,
            my,
            f"{lk['id']}\n{int(dist)}km ({spans}sp)",
            fontsize=6.5,
            fontweight="bold",
            color="#065F46" if is_core else "#1E293B",
            ha="center",
            va="center",
            bbox=dict(
                boxstyle="round,pad=0.18",
                facecolor="#D1FAE5" if is_core else "#FFFFFF",
                edgecolor="#059669" if is_core else "#CBD5E1",
                linewidth=0.8,
                alpha=0.92,
            ),
            zorder=3,
        )

    # Dibujar algunos bypasses candidatos de Camino 3 en línea punteada morada
    bypasses = [(4, 8, "Bypass e4_8 (1600km)"), (4, 11, "Bypass e4_11 (1900km)")]
    for u, v, blabel in bypasses:
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="-",
                color="#7E22CE",
                lw=1.8,
                ls="--",
                connectionstyle="arc3,rad=0.22",
            ),
            zorder=1,
        )

    for nid, (x, y) in pos.items():
        ax.scatter(x, y, s=390, color="#0284C7", edgecolors="#0F172A", linewidth=1.8, zorder=4)
        ax.text(x, y, f"N{nid}", color="white", fontsize=8, fontweight="bold", ha="center", va="center", zorder=5)
        ax.text(
            x,
            y - 0.34,
            cities[nid],
            color="#0F172A",
            fontsize=7.5,
            fontweight="bold",
            ha="center",
            va="top",
            bbox=dict(boxstyle="round,pad=0.12", facecolor="#FFFFFF", edgecolor="none", alpha=0.8),
            zorder=5,
        )

    ax.set_title(
        "Topología Estándar NSFNet (14 Nodos, 21 Enlaces Base, Banda C = 320 FSUs @ 12.5 GHz)\n"
        "Verde: Corredores Dorsales Críticos | Punteado Morado: Ejemplos de Enlaces Bypass HCF (Camino 3)",
        fontsize=9.5,
        fontweight="bold",
        color="#0F172A",
        pad=10,
    )
    ax.set_xlim(0.3, 9.7)
    ax.set_ylim(0.3, 4.8)
    ax.axis("off")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=240)
    plt.close(fig)
    return out_path


def set_slide_background(slide, color: RGBColor = C_BG_LIGHT) -> None:
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_header_banner(
    slide,
    title_text: str,
    subtitle_text: str,
    badge_text: str,
    badge_color: RGBColor = C_EMERALD,
) -> None:
    """Agrega un encabezado superior limpio y uniforme con insignia de rúbrica y tiempo."""
    # Barra superior oscura
    banner = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(1.05)
    )
    banner.fill.solid()
    banner.fill.fore_color.rgb = C_NAVY_DARK
    banner.line.fill.background()

    # Franja de acento inferior en el banner
    stripe = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(1.01), Inches(13.333), Inches(0.05)
    )
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = badge_color
    stripe.line.fill.background()

    # Título y subtítulo
    tb = slide.shapes.add_textbox(Inches(0.45), Inches(0.10), Inches(9.6), Inches(0.88))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p0 = tf.paragraphs[0]
    p0.text = title_text
    p0.font.size = Pt(21)
    p0.font.bold = True
    p0.font.color.rgb = C_WHITE
    p0.font.name = "Calibri"

    p1 = tf.add_paragraph()
    p1.text = subtitle_text
    p1.font.size = Pt(11.5)
    p1.font.color.rgb = RGBColor(203, 213, 225)
    p1.font.name = "Calibri"

    # Badge derecho (Rúbrica / Tiempo)
    badge = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(10.25), Inches(0.22), Inches(2.70), Inches(0.58)
    )
    badge.fill.solid()
    badge.fill.fore_color.rgb = badge_color
    badge.line.fill.background()
    btf = badge.text_frame
    btf.word_wrap = True
    btf.vertical_anchor = MSO_ANCHOR.MIDDLE
    bp = btf.paragraphs[0]
    bp.text = badge_text
    bp.alignment = PP_ALIGN.CENTER
    bp.font.size = Pt(10.5)
    bp.font.bold = True
    bp.font.color.rgb = C_WHITE
    bp.font.name = "Calibri"


def add_footer(slide, current_slide: int, total_slides: int = 10) -> None:
    tb = slide.shapes.add_textbox(Inches(0.45), Inches(7.15), Inches(12.43), Inches(0.28))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    p.text = (
        f"TEL-317 Redes Ópticas WDM (UTFSM)  |  Taller 3: Migración Progresiva SMF a HCF en EON  |  "
        f"Manríquez · Zamora · Abde  |  Diapositiva {current_slide} de {total_slides}"
    )
    p.font.size = Pt(9)
    p.font.color.rgb = C_SLATE_MUTED
    p.font.name = "Calibri"


def add_card(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    title: str,
    bullets: list[str],
    border_color: RGBColor = C_CARD_BORDER,
    bg_color: RGBColor = C_CARD_WHITE,
    title_color: RGBColor = C_NAVY_DARK,
    font_size: float = 11.5,
) -> None:
    card = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height)
    )
    card.adjustments[0] = 0.03
    card.fill.solid()
    card.fill.fore_color.rgb = bg_color
    card.line.color.rgb = border_color
    card.line.width = Pt(1.5)

    tb = slide.shapes.add_textbox(
        Inches(left + 0.18), Inches(top + 0.14), Inches(width - 0.36), Inches(height - 0.24)
    )
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p_title = tf.paragraphs[0]
    p_title.text = title
    p_title.font.size = Pt(font_size + 1.5)
    p_title.font.bold = True
    p_title.font.color.rgb = title_color
    p_title.font.name = "Calibri"
    p_title.space_after = Pt(5)

    for b in bullets:
        p = tf.add_paragraph()
        p.text = f"• {b}"
        p.font.size = Pt(font_size)
        p.font.color.rgb = C_NAVY_DARK
        p.font.name = "Calibri"
        p.space_after = Pt(4)


def add_kpi_box(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    label: str,
    big_value: str,
    subtext: str,
    accent_color: RGBColor,
    bg_color: RGBColor = C_CARD_WHITE,
) -> None:
    box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height)
    )
    box.adjustments[0] = 0.05
    box.fill.solid()
    box.fill.fore_color.rgb = bg_color
    box.line.color.rgb = accent_color
    box.line.width = Pt(2.0)

    tb = slide.shapes.add_textbox(
        Inches(left + 0.15), Inches(top + 0.10), Inches(width - 0.30), Inches(height - 0.18)
    )
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p0 = tf.paragraphs[0]
    p0.text = label.upper()
    p0.font.size = Pt(9.5)
    p0.font.bold = True
    p0.font.color.rgb = C_SLATE_MUTED
    p0.font.name = "Calibri"

    p1 = tf.add_paragraph()
    p1.text = big_value
    p1.font.size = Pt(22)
    p1.font.bold = True
    p1.font.color.rgb = accent_color
    p1.font.name = "Calibri"
    p1.space_before = Pt(2)
    p1.space_after = Pt(2)

    p2 = tf.add_paragraph()
    p2.text = subtext
    p2.font.size = Pt(9.5)
    p2.font.bold = True
    p2.font.color.rgb = C_NAVY_DARK
    p2.font.name = "Calibri"


def set_speaker_notes(slide, text: str) -> None:
    notes_slide = slide.notes_slide
    tf = notes_slide.notes_text_frame
    tf.text = text.strip()


def style_table_cell(
    cell,
    text: str,
    font_size: float = 10.5,
    bold: bool = False,
    text_color: RGBColor = C_NAVY_DARK,
    bg_color: RGBColor | None = None,
    align=PP_ALIGN.LEFT,
) -> None:
    if bg_color is not None:
        cell.fill.solid()
        cell.fill.fore_color.rgb = bg_color
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf = cell.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.04)
    tf.margin_bottom = Inches(0.04)
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = align
    p.font.size = Pt(font_size)
    p.font.bold = bold
    p.font.color.rgb = text_color
    p.font.name = "Calibri"


def build_presentation() -> Path:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    fig0_path = generate_nsfnet_topology_figure(Path("results/fig0_topologia_nsfnet.png"))
    fig1_path = Path("results/fig1_validacion_gsnr.png")
    fig2_path = Path("results/fig2_curva_saturacion_smf.png")
    fig3_path = Path("results/fig3_reemplazo_vs_utilizacion.png")
    fig4_path = Path("results/fig4_comparacion_3_caminos.png")

    # =========================================================================
    # DIAPOSITIVA 1: PORTADA EJECUTIVA
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1, C_NAVY_DARK)

    # Franja decorativa lateral izquierda
    left_bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.35), Inches(7.5))
    left_bar.fill.solid()
    left_bar.fill.fore_color.rgb = C_EMERALD
    left_bar.line.fill.background()

    # Insignia superior
    b1 = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.85), Inches(0.65), Inches(5.8), Inches(0.48))
    b1.fill.solid()
    b1.fill.fore_color.rgb = RGBColor(30, 41, 59)
    b1.line.color.rgb = C_EMERALD
    b1.line.width = Pt(1.5)
    p = b1.text_frame.paragraphs[0]
    p.text = "UTFSM · TEL-317 REDES ÓPTICAS WDM · TALLER 3 (AVANCE Y DEMO)"
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = RGBColor(110, 231, 183)

    # Título principal
    tb1 = s1.shapes.add_textbox(Inches(0.85), Inches(1.35), Inches(11.6), Inches(2.6))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p_title = tf1.paragraphs[0]
    p_title.text = "Migración Progresiva de SMF a HCF en Redes Ópticas Elásticas Estáticas sobre Banda C"
    p_title.font.size = Pt(34)
    p_title.font.bold = True
    p_title.font.color.rgb = C_WHITE
    p_title.font.name = "Calibri"
    p_title.space_after = Pt(12)

    p_sub = tf1.add_paragraph()
    p_sub.text = (
        "Planificación Multi-Año (k = 0..8) basada en GSNR Acumulado por Span y Evaluación "
        "en Igualdad de CAPEX de 3 Caminos: Reemplazo SMF→HCF, Fibra HCF Paralela y Bypass Directo"
    )
    p_sub.font.size = Pt(16)
    p_sub.font.color.rgb = RGBColor(148, 163, 184)
    p_sub.font.name = "Calibri"

    # Tarjetas de resumen en portada
    add_kpi_box(
        s1, 0.85, 4.15, 2.75, 1.35,
        "Invariante Banda C", "320 FSUs", "Grilla Flex-Grid 12.5 GHz (4 THz)", C_SKY, C_BG_LIGHT
    )
    add_kpi_box(
        s1, 3.80, 4.15, 2.75, 1.35,
        "Ganancia Física HCF", "+4.0 dB/span", "Hasta -50% FSUs (QPSK → 16-QAM)", C_EMERALD, C_BG_LIGHT
    )
    add_kpi_box(
        s1, 6.75, 4.15, 2.75, 1.35,
        "Mejor Estrategia (Camino 2)", "-46.3% Bloqueo", "0 Fuera hasta k=4 | +141.3 Tbps", C_EMERALD, C_BG_LIGHT
    )
    add_kpi_box(
        s1, 9.70, 4.15, 2.75, 1.35,
        "Bypass Directo (Camino 3)", "-36.1% Bloqueo", "3 Enlaces Nuevos | 7810 UR CAPEX", C_PURPLE, C_BG_LIGHT
    )

    # Caja de Autores y Profesor
    authors_box = s1.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.85), Inches(5.85), Inches(11.6), Inches(1.05)
    )
    authors_box.fill.solid()
    authors_box.fill.fore_color.rgb = RGBColor(30, 41, 59)
    authors_box.line.color.rgb = RGBColor(71, 85, 105)
    atf = authors_box.text_frame
    atf.vertical_anchor = MSO_ANCHOR.MIDDLE
    ap1 = atf.paragraphs[0]
    ap1.text = "Equipo: Fernanda Manríquez  ·  Josefa Zamora  ·  Benjamín Abde"
    ap1.font.size = Pt(15)
    ap1.font.bold = True
    ap1.font.color.rgb = C_WHITE
    ap1.alignment = PP_ALIGN.CENTER

    ap2 = atf.add_paragraph()
    ap2.text = "Profesor: Dr. Nicolás Jara  |  Topología de Referencia: NSFNet (14 Nodos, 21 Enlaces)  |  Noviembre 2026"
    ap2.font.size = Pt(12)
    ap2.font.color.rgb = RGBColor(148, 163, 184)
    ap2.alignment = PP_ALIGN.CENTER

    set_speaker_notes(
        s1,
        """[TIEMPO: 0:00 - 0:30 | Orador 1]
Buenos días/tardes profesor Nicolás Jara y compañeros. Somos Fernanda Manríquez, Josefa Zamora y Benjamín Abde.
Hoy presentamos nuestro avance y demostración del Taller 3: el estudio y simulador estático de migración progresiva de fibra monomodo estándar (SMF) a fibra de núcleo hueco (HCF) en Redes Ópticas Elásticas sobre Banda C, evaluando los tres caminos de actualización propuestos en clases bajo igualdad de presupuesto CAPEX."""
    )

    # =========================================================================
    # DIAPOSITIVA 2: PARTE C — REAJUSTE METODOLÓGICO TRAS FEEDBACK TALLER 2
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2)
    add_header_banner(
        s2,
        "1. Reajuste Metodológico tras Feedback del Taller 2",
        "Alineación estricta con las correcciones del Profesor: de simulación dinámica a planificación estática anual EON",
        "PARTE C: 10 PTS\nMin 0:30 – 2:00",
        C_ROSE,
    )

    rows, cols = 6, 3
    tbl_shape2 = s2.shapes.add_table(rows, cols, Inches(0.45), Inches(1.25), Inches(12.43), Inches(4.75))
    t2 = tbl_shape2.table
    t2.columns[0].width = Inches(2.35)
    t2.columns[1].width = Inches(4.35)
    t2.columns[2].width = Inches(5.73)

    headers2 = [
        "Dimensión Técnica",
        "Propuesta Original (Taller 2)",
        "Redefinición Validada e Implementada (Taller 3)",
    ]
    for c_idx, h in enumerate(headers2):
        style_table_cell(
            t2.cell(0, c_idx), h, font_size=11.5, bold=True, text_color=C_WHITE, bg_color=C_NAVY_DARK, align=PP_ALIGN.CENTER
        )

    reajuste_rows = [
        (
            "1. Paradigma de\nSimulación",
            "Simulación dinámica de eventos discretos (colas de llegadas/salidas) con umbral de corte en 1% de bloqueo.",
            "Planificación Estática por Fotografías Anuales (k = 0..8): En cada año k se asigna la matriz completa D(k) desde cero sobre los 320 FSUs de Banda C.",
        ),
        (
            "2. Métrica Principal\nde Desempeño",
            "Probabilidad de bloqueo instantánea (B = N_bloq / N_sol).",
            "Conexiones Fuera (Rechazadas) y Tráfico No Atendido [Tbps], clasificando explícitamente la causa: Capa Física (GSNR) vs. Saturación Espectral.",
        ),
        (
            "3. Modelo Físico y\nGrilla Espectral",
            "Modelo de calidad de transmisión abstracto sin acumulación física por span.",
            "Suma Paralela Inversa de GSNR por span (Pedro et al. [1]) y grilla Flex-Grid ITU-T de 320 FSUs (12.5 GHz) con modulaciones BPSK a 64-QAM.",
        ),
        (
            "4. Estrategias de\nDespliegue HCF",
            "Únicamente reemplazo voraz de enlaces completos SMF por HCF.",
            "Comparación en Igualdad de CAPEX de 3 Caminos: (1) Reemplazo SMF→HCF, (2) Fibra HCF Paralela activa (sin dark fiber), y (3) Enlace Bypass HCF directo.",
        ),
        (
            "5. Evolución Anual\ndel Tráfico",
            "Incremento del 30% por etapa sin vinculación a años calendario ni fuentes globales.",
            "Crecimiento Anual Respaldado por TeleGeography [5]: D(k) = D(0)·(1+r)^k con r = 30% base [4] y análisis de sensibilidad en r = 24% y r = 32%.",
        ),
    ]

    for r_idx, (dim, old_val, new_val) in enumerate(reajuste_rows, start=1):
        row_bg = C_CARD_WHITE if r_idx % 2 == 1 else RGBColor(241, 245, 249)
        style_table_cell(t2.cell(r_idx, 0), dim, font_size=10.5, bold=True, text_color=C_NAVY_DARK, bg_color=row_bg)
        style_table_cell(t2.cell(r_idx, 1), old_val, font_size=10.0, bold=False, text_color=C_ROSE, bg_color=C_ROSE_BG)
        style_table_cell(t2.cell(r_idx, 2), new_val, font_size=10.0, bold=True, text_color=C_NAVY_DARK, bg_color=C_EMERALD_BG)

    add_card(
        s2, 0.45, 6.12, 12.43, 0.92,
        "Síntesis del Reajuste Metodológico:",
        [
            "La migración SMF → HCF es una decisión de inversión de infraestructura multi-año (CAPEX). Por ello, un planificador estático determinista por fotografías anuales refleja fielmente la ingeniería de capacidad de un operador de transporte óptico."
        ],
        border_color=C_EMERALD, bg_color=C_CARD_WHITE, title_color=C_EMERALD, font_size=10.5
    )
    add_footer(s2, 2)

    set_speaker_notes(
        s2,
        """[TIEMPO: 0:30 - 2:00 | Orador 1 - Parte C (10 pts)]
Siguiendo directamente el feedback recibido en el Taller 2, realizamos cinco reajustes estructurales obligatorios:
1) Primero, pasamos de una simulación dinámica de eventos discretos a una planificación estática por fotografías anuales desde el año k=0 hasta k=8.
2) Segundo, reemplazamos la probabilidad de bloqueo instantánea por el conteo exacto de Conexiones Fuera de la matriz anual y el Tráfico No Atendido en Terabits por segundo, distinguiendo si un rechazo ocurre por GSNR insuficiente o por falta de slots contiguos.
3) Tercero, implementamos el modelo físico exacto de acumulación inversa paralela de GSNR por span de 100 km sobre los 320 FSUs de Banda C.
4) Cuarto, ampliamos el análisis a los tres caminos sugeridos por el profesor: reemplazo del enlace, fibra HCF paralela para no dejar dark fiber, y enlaces nuevos bypass.
5) Quinto, justificamos la tasa anual del 30% base y su sensibilidad en 24% y 32% con datos reales de TeleGeography."""
    )

    # =========================================================================
    # DIAPOSITIVA 3: PARTE A — MODELO FÍSICO GSNR E INVARIANTE DE 320 FSUs
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3)
    add_header_banner(
        s3,
        "2. Capa Física EON: Acumulación de GSNR e Invariante de 320 FSUs",
        "Modelo físico en Banda C (4.0 THz, grilla de 12.5 GHz) y tabla oficial de formatos de modulación adaptativos",
        "PARTE A: 40 PTS\nMin 2:00 – 3:15",
        C_SKY,
    )

    add_card(
        s3, 0.45, 1.25, 5.75, 2.65,
        "Invariante Física #1: Continuidad en Banda C (320 FSUs)",
        [
            "Los amplificadores ópticos EDFA operan en Banda C (4.0 THz ÷ 12.5 GHz = 320 FSUs fijos por fibra).",
            "Conectar enlaces SMF y HCF sin conversión de longitud de onda exige mantener exactamente los mismos 320 slots.",
            "HCF NO añade ranuras espectrales: reduce la atenuación (0.14 dB/km) y el coeficiente no lineal Kerr (γ ≈ 0).",
            "Esto eleva el GSNR en +4.0 dB por span, habilitando modulaciones de orden superior que comprimen los FSUs por conexión.",
        ],
        border_color=C_SKY, bg_color=C_CARD_WHITE, title_color=C_SKY, font_size=10.5
    )

    add_card(
        s3, 0.45, 4.05, 5.75, 2.95,
        "Ecuación de Acumulación Paralela Inversa de GSNR",
        [
            "Fórmula física extremo a extremo (Pedro et al. [1], [3]):\n"
            "   GSNR_ruta(p)⁻¹ = (N_SMF / GSNR_1,SMF) + (N_HCF / GSNR_1,HCF)",
            "Calibración en Banda C para spans estándar de L_span = 100 km:\n"
            "   • GSNR_1,SMF = 26.44 dB  (440.55 en escala lineal)\n"
            "   • ΔSNR_HCF   = +4.00 dB  →  GSNR_1,HCF = 30.44 dB (1106.62 lineal)",
            "Selección EON: Se elige el formato m de mayor eficiencia espectral cuyo umbral cumpla GSNR_ruta(p) ≥ SNR_th(m) + 1 FSU de banda de guarda (G = 1).",
        ],
        border_color=C_EMERALD, bg_color=C_EMERALD_BG, title_color=C_EMERALD, font_size=10.5
    )

    # Tabla Oficial de Formatos de Modulación a la derecha
    tb_title3 = s3.shapes.add_textbox(Inches(6.40), Inches(1.22), Inches(6.48), Inches(0.35))
    p_t3 = tb_title3.text_frame.paragraphs[0]
    p_t3.text = "Tabla Oficial de Formatos de Modulación, Umbrales SNR y Consumo de FSUs (Sección 4)"
    p_t3.font.size = Pt(12)
    p_t3.font.bold = True
    p_t3.font.color.rgb = C_NAVY_DARK

    tbl_shape3 = s3.shapes.add_table(7, 9, Inches(6.40), Inches(1.60), Inches(6.48), Inches(4.25))
    t3 = tbl_shape3.table
    col_widths3 = [1.05, 0.72, 0.85, 0.86, 0.56, 0.56, 0.58, 0.62, 0.68]
    for idx, w in enumerate(col_widths3):
        t3.columns[idx].width = Inches(w)

    headers3 = ["Formato", "Eficiencia", "SNR_th", "Spans SMF", "10G", "40G", "100G", "400G", "1000G"]
    for idx, h in enumerate(headers3):
        style_table_cell(t3.cell(0, idx), h, font_size=9.5, bold=True, text_color=C_WHITE, bg_color=C_NAVY_DARK, align=PP_ALIGN.CENTER)

    mod_rows = [
        ("BPSK",   "1 b/s/Hz", "5.3 dB",  "130", "1", "4", "8", "32", "80"),
        ("QPSK",   "2 b/s/Hz", "8.3 dB",  "65",  "1", "2", "4", "16", "40"),
        ("8-QAM",  "3 b/s/Hz", "11.4 dB", "35",  "1", "2", "3", "11", "27"),
        ("16-QAM", "4 b/s/Hz", "14.0 dB", "17",  "1", "1", "2", "8",  "20"),
        ("32-QAM", "5 b/s/Hz", "16.7 dB", "8",   "1", "1", "2", "7",  "16"),
        ("64-QAM", "6 b/s/Hz", "19.2 dB", "4",   "1", "1", "2", "6",  "14"),
    ]
    for r_idx, row_vals in enumerate(mod_rows, start=1):
        is_highlight = row_vals[0] in ("QPSK", "16-QAM")
        bg = C_AMBER_BG if is_highlight else (C_CARD_WHITE if r_idx % 2 == 1 else RGBColor(241, 245, 249))
        for c_idx, val in enumerate(row_vals):
            style_table_cell(
                t3.cell(r_idx, c_idx),
                val,
                font_size=9.5,
                bold=(c_idx in (0, 2, 7) or is_highlight),
                text_color=C_NAVY_DARK,
                bg_color=bg,
                align=PP_ALIGN.CENTER,
            )

    add_card(
        s3, 6.40, 5.98, 6.48, 1.02,
        "Efecto Clave en 400 Gbps (Filas resaltadas):",
        [
            "Al migrar una ruta larga de QPSK (SNR ≥ 8.3 dB) a 16-QAM (SNR ≥ 14.0 dB), el requerimiento cae de 16 FSUs a 8 FSUs (−50% de espectro en todos los enlaces de la ruta)."
        ],
        border_color=C_AMBER, bg_color=C_AMBER_BG, title_color=C_AMBER, font_size=10.0
    )
    add_footer(s3, 3)

    set_speaker_notes(
        s3,
        """[TIEMPO: 2:00 - 3:15 | Orador 1 - Parte A (40 pts)]
En la capa física respetamos la Invariante Fundamental de Banda C: tanto SMF como HCF poseen exactamente 320 Frequency Slot Units de 12.5 GHz. Instalar HCF no inventa nuevos slots en la fibra; lo que hace es disminuir la atenuación y prácticamente eliminar la no linealidad de Kerr, aportando una ganancia de +4.0 dB de GSNR por cada span de 100 km.
Usando la fórmula de suma paralela inversa de ruido de Pedro et al., el motor calcula el GSNR extremo a extremo de cada ruta híbrida y consulta la tabla oficial de modulaciones. Observen las filas resaltadas: para una demanda de 400 Gbps, subir de QPSK a 16-QAM reduce el consumo de 16 slots a solo 8 slots."""
    )

    # =========================================================================
    # DIAPOSITIVA 4: VALIDACIÓN FÍSICA TEST-02 (FIGURA 1)
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4)
    add_header_banner(
        s4,
        "3. Validación de Capa Física (TEST-02): Saltos de Modulación y Ahorro de FSUs",
        "Verificación analítica y experimental de rutas SMF, Híbridas (50/50) y HCF a 400 Gbps",
        "PARTE A: 40 PTS\nMin 3:15 – 4:00",
        C_SKY,
    )

    if fig1_path.exists():
        s4.shapes.add_picture(str(fig1_path), Inches(0.45), Inches(1.25), width=Inches(7.35))

    add_card(
        s4, 7.95, 1.25, 4.93, 2.75,
        "Caso 1: Ruta Dorsal 1800 km (18 spans @ 400G)",
        [
            "100% SMF (18 SMF, 0 HCF):\n   GSNR = 13.89 dB  →  8-QAM (11 FSUs + 1 guarda)",
            "Híbrida 50/50 (9 SMF + 9 HCF):\n   GSNR = 15.44 dB  →  16-QAM (8 FSUs + 1 guarda)",
            "100% HCF (0 SMF, 18 HCF):\n   GSNR = 17.89 dB  →  32-QAM (7 FSUs + 1 guarda)",
            "Resultado: Migrar solo la mitad de la ruta basta para superar el umbral de 14.0 dB y saltar a 16-QAM.",
        ],
        border_color=C_SKY, bg_color=C_CARD_WHITE, title_color=C_SKY, font_size=10.5
    )

    add_card(
        s4, 7.95, 4.15, 4.93, 2.85,
        "Caso 2: Ruta Costa a Costa 3600 km (36 spans @ 400G)",
        [
            "100% SMF (36 SMF, 0 HCF):\n   GSNR = 10.88 dB  →  QPSK (16 FSUs + 1 guarda)",
            "Híbrida 50/50 (18 SMF + 18 HCF):\n   GSNR = 12.43 dB  →  8-QAM (11 FSUs + 1 guarda)",
            "100% HCF (0 SMF, 36 HCF):\n   GSNR = 14.88 dB  →  16-QAM (8 FSUs + 1 guarda)",
            "Resultado: Reducción exacta del 50% en FSUs de payload (de 16 a 8 slots) en cada enlace atravesado.",
        ],
        border_color=C_EMERALD, bg_color=C_EMERALD_BG, title_color=C_EMERALD, font_size=10.5
    )
    add_footer(s4, 4)

    set_speaker_notes(
        s4,
        """[TIEMPO: 3:15 - 4:00 | Orador 2 - Parte A (40 pts)]
Aquí mostramos los resultados de la prueba de validación física TEST-02 generados por nuestro módulo physics_qot.py.
A la izquierda observamos la caída logarítmica del GSNR con el número de spans y los escalones de consumo de FSUs.
A la derecha vemos dos rutas reales de NSFNet: en una ruta de 1800 km (18 spans), basta con migrar la mitad de los spans a HCF para pasar de 13.89 dB a 15.44 dB, saltando de 8-QAM a 16-QAM. Y en una ruta transcontinental de 3600 km (36 spans), pasar de SMF a HCF sube el GSNR de 10.88 dB (QPSK, 16 FSUs) a 14.88 dB (16-QAM, 8 FSUs), liberando exactamente el 50% del espectro."""
    )

    # =========================================================================
    # DIAPOSITIVA 5: TOPOLOGÍA NSFNET Y MOTOR RMLSA ESTÁTICO (TEST-01)
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5)
    add_header_banner(
        s5,
        "4. Topología NSFNet, Motor RMLSA Estático y Auditoría TEST-01",
        "Arquitectura modular en Python, algoritmo k-SP + First-Fit Vectorial y verificación en Año Base k = 0",
        "PARTE A: 40 PTS\nMin 4:00 – 5:00",
        C_SKY,
    )

    if fig0_path.exists():
        s5.shapes.add_picture(str(fig0_path), Inches(0.45), Inches(1.25), width=Inches(6.95))

    add_card(
        s5, 7.55, 1.25, 5.33, 3.35,
        "Pipeline del Motor RMLSA Estático (rmlsa_static.py)",
        [
            "1. Cuantización Monótona de Demanda C(k):\n"
            "   28 corredores troncales D(0) escalados por (1+r)^k y descompuestos en transpondedores de {400, 100, 40, 10} Gbps.",
            "2. Ordenamiento Determinista:\n"
            "   Descendente por (Bitrate × Distancia_Ruta_Más_Corta) para priorizar flujos transcontinentales de alta capacidad.",
            "3. Evaluación k-Shortest Paths (k = 3, Yen) + QoT:\n"
            "   Para cada ruta candidata se calcula GSNR, modulación m y ancho espectral n_FSU + 1 slot de guarda.",
            "4. Asignación First-Fit Vectorial (320 FSUs):\n"
            "   Intersección booleana de disponibilidad en todos los enlaces de la ruta (Continuidad + Contigüidad estricta).",
        ],
        border_color=C_NAVY_DARK, bg_color=C_CARD_WHITE, title_color=C_NAVY_DARK, font_size=10.0
    )

    add_card(
        s5, 7.55, 4.75, 5.33, 2.25,
        "Auditoría Automática TEST-01 (Año Base k = 0, 100% SMF)",
        [
            "Solicitudes Año k = 0: 71 conexiones ópticas (18.80 Tbps).",
            "Resultado RMLSA: 71 Atendidas (100%) | 0 Conexiones Fuera.",
            "Ocupación global Banda C: 22.99% (Enlace cuello de botella inicial: e7_8 con 65.6% = 210/320 FSUs).",
            "Verificación de Invariantes: 0 colisiones de slots, 100% continuidad extremo a extremo y 100% cumplimiento de umbral GSNR.",
        ],
        border_color=C_EMERALD, bg_color=C_EMERALD_BG, title_color=C_EMERALD, font_size=10.0
    )
    add_footer(s5, 5)

    set_speaker_notes(
        s5,
        """[TIEMPO: 4:00 - 5:00 | Orador 2 - Parte A (40 pts) + Demo Interactiva]
Sobre la topología NSFNet de 14 nodos y 21 enlaces, nuestro motor RMLSA estático opera en cuatro etapas deterministas para cada fotografía anual k:
Primero cuantiza la matriz D(k) en transpondedores discretos; segundo, ordena las solicitudes por el producto Bitrate por distancia; tercero, evalúa las k=3 rutas más cortas de Yen seleccionando la mejor modulación factible; y cuarto, ejecuta First-Fit buscando el primer bloque contiguo y continuo libre en los 320 slots.
En la auditoría TEST-01 del año base k=0 con red 100% SMF, las 71 conexiones (18.80 Tbps) se asignan con 0 rechazos y 0 colisiones, dejando el enlace central e7_8 al 65.6% de ocupación, listo para observar la saturación en los años siguientes."""
    )

    # =========================================================================
    # DIAPOSITIVA 6: LOS 3 CAMINOS DE MIGRACIÓN Y MODELO DE COSTOS CAPEX
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6)
    add_header_banner(
        s6,
        "5. Tres Caminos de Migración a HCF y Modelo Incremental CAPEX",
        "Formulación técnico-económica para comparar estrategias bajo igualdad de presupuesto (CAPEX ≤ 8500 UR)",
        "PARTE A / B\nMin 5:00 – 5:45",
        C_PURPLE,
    )

    add_card(
        s6, 0.45, 1.25, 3.95, 3.65,
        "Camino 1: Reemplazo SMF → HCF",
        [
            "Sustituye la fibra SMF de un enlace existente por fibra HCF en el mismo ducto.",
            "Mantiene 1 enlace de 320 FSUs entre (u, v), pero todos sus spans pasan a tener GSNR_1,HCF = 30.44 dB (+4 dB/span).",
            "Costo de instalación: C_inst = 50 UR (usa ducto existente).",
            "Ventaja: Comprime el número de FSUs por conexión al subir de modulación.",
            "Límite: El techo sigue siendo 320 slots únicos por enlace.",
        ],
        border_color=C_SKY, bg_color=C_SKY_BG, title_color=C_SKY, font_size=10.5
    )

    add_card(
        s6, 4.69, 1.25, 3.95, 3.65,
        "Camino 2: Fibra HCF Paralela Activa",
        [
            "Instala una fibra HCF paralela en el mismo ducto SIN apagar la fibra SMF existente (evita dejar dark fiber).",
            "El par (u, v) queda con dos fibras activas: 320 FSUs en HCF + 320 FSUs en SMF.",
            "Costo de instalación: C_inst = 50 UR (mismo ducto existente).",
            "El motor RMLSA prioriza el enlace HCF (mejor GSNR y menos FSUs) y usa la SMF como capacidad de desborde.",
        ],
        border_color=C_EMERALD, bg_color=C_EMERALD_BG, title_color=C_EMERALD, font_size=10.5
    )

    add_card(
        s6, 8.93, 1.25, 3.95, 3.65,
        "Camino 3: Enlace Nuevo Bypass HCF",
        [
            "Crea un enlace directo HCF entre dos nodos no adyacentes de alto tráfico (ej. N4↔N8, N4↔N11, N1↔N11).",
            "Distancia física estimada: L_bypass ≈ 1.15 × distancia euclidiana.",
            "Costo de instalación mayor: C_inst = 150 UR (obra civil / nuevo derecho de paso).",
            "Ventaja: Evita múltiples saltos intermedios SMF, descargando simultáneamente todo el núcleo de la red.",
        ],
        border_color=C_PURPLE, bg_color=C_PURPLE_BG, title_color=C_PURPLE, font_size=10.5
    )

    add_card(
        s6, 0.45, 5.10, 12.43, 1.90,
        "Modelo de Costo Incremental CAPEX y Heurística Voraz de Costo-Beneficio (migration_policies.py)",
        [
            "Fórmula de Costo CAPEX por intervención [Unidades Relativas UR]:\n"
            "   C(e) = c_km · L(e) + C_amp · N_spans(e) + C_inst(modo)     con  c_km = 1.0 UR/km,  C_amp = 15.0 UR/span,  C_inst ∈ {50 UR ducto, 150 UR bypass}.",
            "Heurística Voraz Anual: En cada año k con bloqueo (N_fuera > 0), evalúa todos los candidatos factibles dentro del presupuesto remanente y selecciona aquel que maximiza la eficiencia de destrabe por unidad monetaria:   e* = argmax [ ΔN_fuera(e) / C(e) ].",
            "Herencia Permanente: Toda fibra HCF instalada en el año k se conserva activa en la topología para los años k+1 ... 8.",
        ],
        border_color=C_NAVY_DARK, bg_color=C_CARD_WHITE, title_color=C_NAVY_DARK, font_size=10.5
    )
    add_footer(s6, 6)

    set_speaker_notes(
        s6,
        """[TIEMPO: 5:00 - 5:45 | Orador 2 - Parte A/B]
Para comparar de manera justa los tres caminos propuestos por el profesor, definimos un modelo de costos CAPEX común en Unidades Relativas: 1 UR por kilómetro de fibra HCF, 15 UR por amplificador adaptado en cada span, y un costo fijo de instalación de 50 UR cuando se usa el ducto existente (Caminos 1 y 2) o 150 UR cuando se requiere obra civil o nuevo derecho de paso en un enlace bypass (Camino 3).
En todos los casos fijamos exactamente el mismo techo presupuestario acumulado de 8500 UR para el horizonte de 8 años, y nuestra heurística voraz elige en cada año la intervención que maximiza la reducción de conexiones fuera dividida por su costo C(e)."""
    )

    # =========================================================================
    # DIAPOSITIVA 7: RESULTADOS EXP-01 — SATURACIÓN RED 100% SMF (FIGURA 2)
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7)
    add_header_banner(
        s7,
        "6. Resultados EXP-01: Curva de Saturación en Red 100% SMF (Sin Migración)",
        "Evolución multi-año (k = 0..8) bajo tasas de crecimiento TeleGeography: r = 24%, r = 30% (Base) y r = 32%",
        "PARTE B: 50 PTS\nMin 5:45 – 6:45",
        C_ROSE,
    )

    if fig2_path.exists():
        s7.shapes.add_picture(str(fig2_path), Inches(0.45), Inches(1.25), width=Inches(7.35))

    add_card(
        s7, 7.95, 1.25, 4.93, 3.10,
        "Análisis de Saturación Espectral (r = 30% Base)",
        [
            "Años k = 0 y k = 1 (0 Conexiones Fuera):\n"
            "   La red SMF absorbe el crecimiento inicial, pero en k = 1 el enlace central e7_8 llega al 95.6% (306/320 FSUs).",
            "Año k = 2 (Punto de Quiebre — 31 Conexiones Fuera):\n"
            "   Se agotan los 320 slots en los enlaces dorsales (e7_8 y e6_7 al 100%), rechazando el 21.8% de las conexiones.",
            "Años k = 4 a k = 8 (Colapso de Capacidad):\n"
            "   • En k = 4: 182 fuera de 263 (69.2% rechazadas).\n"
            "   • En k = 8: 902 fuera de 1203 (75.0% rechazadas).",
        ],
        border_color=C_ROSE, bg_color=C_CARD_WHITE, title_color=C_ROSE, font_size=10.0
    )

    add_card(
        s7, 7.95, 4.50, 4.93, 2.50,
        "Diagnóstico de Causa de Rechazo (QoT vs. Espectro)",
        [
            "Rechazos por GSNR físico insuficiente (< 5.3 dB): 0%",
            "Rechazos por Saturación/Fragmentación Espectral: 100%",
            "Explicación Física: En NSFNet las rutas SMF cumplen el umbral mínimo BPSK/QPSK, pero al operar en QPSK/8-QAM consumen entre 11 y 16 FSUs por flujo de 400G, llenando rápidamente los 320 slots de Banda C.",
        ],
        border_color=C_AMBER, bg_color=C_AMBER_BG, title_color=C_AMBER, font_size=10.0
    )
    add_footer(s7, 7)

    set_speaker_notes(
        s7,
        """[TIEMPO: 5:45 - 6:45 | Orador 3 - Parte B (50 pts)]
Pasando a los resultados preliminares (Parte B), en el Experimento 1 evaluamos la red 100% SMF sin ninguna migración para las tres tasas de TeleGeography: 24%, 30% base y 32%.
En los años k=0 y k=1 hay cero conexiones fuera, pero el enlace central e7_8 ya alcanza un 95.6% de ocupación en k=1.
En k=2 ocurre el quiebre con 31 conexiones fuera, escalando a 182 conexiones fuera en k=4 y 902 en k=8 (un total acumulado de 2720 rechazos).
Un hallazgo fundamental del clasificador de nuestro simulador es que el 100% de estos rechazos ocurre por agotamiento de los 320 slots espectrales: en SMF las rutas largas son físicamente viables pero solo alcanzan QPSK u 8-QAM, consumiendo el doble de espectro y saturando los enlaces centrales."""
    )

    # =========================================================================
    # DIAPOSITIVA 8: RESULTADOS EXP-02 — CAMINO 1: VORAZ VS MAYOR UTILIZACIÓN
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_background(s8)
    add_header_banner(
        s8,
        "7. Resultados EXP-02 (Camino 1): Heurística Voraz vs. Mayor Utilización",
        "Evaluación del reemplazo puro SMF → HCF bajo límite de presupuesto CAPEX ≤ 8500 UR (r = 30%)",
        "PARTE B: 50 PTS\nMin 6:45 – 7:45",
        C_SKY,
    )

    if fig3_path.exists():
        s8.shapes.add_picture(str(fig3_path), Inches(0.45), Inches(1.25), width=Inches(7.35))

    add_card(
        s8, 7.95, 1.25, 4.93, 2.85,
        "Comparación en Camino 1 (Reemplazo SMF → HCF)",
        [
            "Sin Migración (100% SMF):\n"
            "   2720 Conexiones Fuera acum. | 385.64 Tbps servidos.",
            "Baseline Orden Fijo por Mayor Utilización (8470 UR):\n"
            "   2416 Conexiones Fuera acum. (-11.2%) | 415.79 Tbps.",
            "Heurística Voraz Costo-Beneficio ΔN_fuera/C(e) (8285 UR):\n"
            "   2306 Conexiones Fuera acum. (-15.2%) | 439.37 Tbps.",
            "Ventaja de la Heurística Voraz:\n"
            "   Salva 110 conexiones adicionales y cursa +23.58 Tbps más que el criterio de utilización, gastando menos CAPEX.",
        ],
        border_color=C_SKY, bg_color=C_CARD_WHITE, title_color=C_SKY, font_size=10.0
    )

    add_card(
        s8, 7.95, 4.25, 4.93, 2.75,
        "¿Por qué la Heurística Voraz supera a Mayor Utilización?",
        [
            "El criterio de Mayor Utilización migra enlaces cortos muy llenos donde las conexiones ya operaban en 16-QAM o 32-QAM; subir allí el GSNR casi no reduce FSUs.",
            "Nuestra Heurística Voraz identifica enlaces dorsales (e3_4, e3_10, e7_8, e6_7) que forman parte de rutas transcontinentales.",
            "Al migrarlos a HCF, decenas de conexiones saltan de QPSK (16 FSUs) a 16-QAM (8 FSUs), liberando espectro en cadena.",
        ],
        border_color=C_EMERALD, bg_color=C_EMERALD_BG, title_color=C_EMERALD, font_size=10.0
    )
    add_footer(s8, 8)

    set_speaker_notes(
        s8,
        """[TIEMPO: 6:45 - 7:45 | Orador 3 - Parte B (50 pts)]
En el Experimento 2 evaluamos el Camino 1 (reemplazo de SMF por HCF) comparando dos políticas bajo el mismo presupuesto de 8500 UR: el baseline clásico que migra el enlace con más slots ocupados (Mayor Utilización) versus nuestra heurística voraz de costo-beneficio.
Como se aprecia en las curvas, la heurística voraz logra reducir las conexiones fuera acumuladas de 2720 a 2306, superando por 110 conexiones y +23.6 Terabits por segundo al criterio de mayor utilización.
¿Por qué ocurre esto? Porque un enlace puede estar muy lleno de conexiones regionales cortas que ya operan en 32-QAM y no ahorran slots al pasar a HCF; en cambio, la heurística voraz detecta qué enlace específico hace que múltiples rutas largas crucen el umbral de 14 dB hacia 16-QAM."""
    )

    # =========================================================================
    # DIAPOSITIVA 9: RESULTADOS EXP-03 — COMPARACIÓN DE LOS 3 CAMINOS (FIGURA 4)
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    set_slide_background(s9)
    add_header_banner(
        s9,
        "8. Resultados EXP-03: Comparación de los 3 Caminos bajo Igualdad de CAPEX",
        "Evaluación integral multi-año (k = 0..8, r = 30%, CAPEX ≤ 8500 UR): Reemplazo vs. HCF Paralela vs. Bypass",
        "PARTE B: 50 PTS\nMin 7:45 – 9:00",
        C_EMERALD,
    )

    if fig4_path.exists():
        s9.shapes.add_picture(str(fig4_path), Inches(0.45), Inches(1.22), width=Inches(6.55))

    # Tabla comparativa maestra a la derecha
    tbl_shape9 = s9.shapes.add_table(5, 6, Inches(7.12), Inches(1.25), Inches(5.76), Inches(3.15))
    t9 = tbl_shape9.table
    w9 = [1.56, 0.78, 0.72, 0.85, 0.90, 0.95]
    for idx, w in enumerate(w9):
        t9.columns[idx].width = Inches(w)

    h9 = ["Estrategia", "CAPEX", "Fuera k=4", "Fuera Acum.", "Tbps Serv.", "Mejora vs SMF"]
    for idx, h in enumerate(h9):
        style_table_cell(t9.cell(0, idx), h, font_size=9.0, bold=True, text_color=C_WHITE, bg_color=C_NAVY_DARK, align=PP_ALIGN.CENTER)

    rows9 = [
        ("100% SMF (Base)", "0 UR", "182", "2720", "385.6 Tbps", "Referencia", C_ROSE_BG, C_ROSE),
        ("Camino 1: Reemplazo", "8285 UR", "119", "2306", "439.4 Tbps", "-15.2% blq\n+53.7 Tbps", C_SKY_BG, C_SKY),
        ("Camino 2: HCF Paralela", "8335 UR", "0", "1461", "526.9 Tbps", "-46.3% blq\n+141.3 Tbps", C_EMERALD_BG, C_EMERALD),
        ("Camino 3: Bypass HCF", "7810 UR", "38", "1738", "492.6 Tbps", "-36.1% blq\n+107.0 Tbps", C_PURPLE_BG, C_PURPLE),
    ]
    for r_idx, (name, capex, fk4, facum, tbps, gain, bg, col) in enumerate(rows9, start=1):
        style_table_cell(t9.cell(r_idx, 0), name, font_size=9.0, bold=True, text_color=col, bg_color=bg)
        style_table_cell(t9.cell(r_idx, 1), capex, font_size=9.0, bold=False, text_color=C_NAVY_DARK, bg_color=bg, align=PP_ALIGN.CENTER)
        style_table_cell(t9.cell(r_idx, 2), fk4, font_size=9.5, bold=True, text_color=col, bg_color=bg, align=PP_ALIGN.CENTER)
        style_table_cell(t9.cell(r_idx, 3), facum, font_size=9.5, bold=True, text_color=col, bg_color=bg, align=PP_ALIGN.CENTER)
        style_table_cell(t9.cell(r_idx, 4), tbps, font_size=9.0, bold=True, text_color=C_NAVY_DARK, bg_color=bg, align=PP_ALIGN.CENTER)
        style_table_cell(t9.cell(r_idx, 5), gain, font_size=8.5, bold=True, text_color=col, bg_color=bg, align=PP_ALIGN.CENTER)

    add_card(
        s9, 7.12, 4.55, 5.76, 2.45,
        "Hallazgos Físicos y de Ingeniería de Red (EXP-03)",
        [
            "1. Camino 2 (HCF Paralela) es el ganador absoluto: Al no apagar la SMF (evitando dark fiber), suma 320 FSUs de alto GSNR sobre los cuellos de botella, logrando 0 Conexiones Fuera hasta el año k = 4 y reduciendo el bloqueo acumulado en -46.3% (+141.3 Tbps servidos).",
            "2. Camino 3 (Bypass Directo) logra el 2° mejor desempeño con menor CAPEX (7810 UR): Instalar solo 3 enlaces directos largos (e4_8, e4_11, e1_11) descarga múltiples saltos centrales SMF a la vez (-36.1% de rechazos).",
            "3. Camino 1 (Reemplazo) mejora la eficiencia espectral, pero en alta carga (k ≥ 5) choca contra el límite único de 320 slots por enlace.",
        ],
        border_color=C_EMERALD, bg_color=C_CARD_WHITE, title_color=C_NAVY_DARK, font_size=9.5
    )
    add_footer(s9, 9)

    set_speaker_notes(
        s9,
        """[TIEMPO: 7:45 - 9:00 | Orador 3 - Parte B (50 pts)]
En el Experimento 3 presentamos la comparación central del Taller 3: los tres caminos evaluados bajo el mismo límite de presupuesto CAPEX de 8500 UR.
1) En el Camino 1 (línea azul), reemplazar SMF por HCF reduce las conexiones fuera en un 15.2% gracias al salto de modulación, pero a partir de k=4 los 320 slots únicos vuelven a llenarse.
2) En el Camino 2 (línea verde), conservar la fibra SMF activa e iluminar fibra HCF paralela en los cuellos de botella mantiene CERO conexiones fuera hasta el año k=4 inclusive, reduciendo los rechazos acumulados en un 46.3% (de 2720 a 1461) y cursando 526.9 Terabits por segundo.
3) Y en el Camino 3 (línea morada), construir apenas 3 enlaces bypass directos de larga distancia (e4_8, e4_11 y e1_11) logra una reducción del 36.1% en conexiones fuera con el menor gasto de CAPEX (7810 UR), ya que cada bypass evita atravesar entre 3 y 4 enlaces centrales congestionados."""
    )

    # =========================================================================
    # DIAPOSITIVA 10: CONCLUSIONES, CUMPLIMIENTO Y PRÓXIMOS PASOS
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    set_slide_background(s10)
    add_header_banner(
        s10,
        "9. Conclusiones Preliminares y Hoja de Ruta hacia el Informe Final",
        "Síntesis de hallazgos del Taller 3, verificación de entregables y trabajo proyectado para el cierre del curso",
        "CIERRE Y Q&A\nMin 9:00 – 10:00",
        C_NAVY_DARK,
    )

    add_card(
        s10, 0.45, 1.25, 6.05, 3.65,
        "Conclusiones Técnicas Validadas en este Avance",
        [
            "1. Simulador Estático EON 100% Operativo:\n"
            "   Integra cálculo exacto de GSNR por suma paralela inversa, grilla fija de 320 FSUs en Banda C y ruteo k-SP + First-Fit sin colisiones.",
            "2. Valor de la Compresión Espectral (HCF):\n"
            "   La ganancia de +4.0 dB/span permite saltar de QPSK a 16-QAM en rutas transcontinentales, reduciendo a la mitad los FSUs requeridos.",
            "3. Superioridad de Camino 2 y Camino 3 en Alta Congestión:\n"
            "   En igualdad de CAPEX, conservar la SMF activa junto a HCF paralela (Camino 2, -46.3% rechazos) o crear atajos ópticos directos (Camino 3, -36.1% rechazos) triplica el beneficio del reemplazo puro (Camino 1, -15.2%).",
        ],
        border_color=C_EMERALD, bg_color=C_CARD_WHITE, title_color=C_EMERALD, font_size=10.5
    )

    add_card(
        s10, 6.80, 1.25, 6.08, 3.65,
        "Hoja de Ruta para el Informe Final (Próximos Pasos)",
        [
            "1. Segunda Topología de Transporte (COST239 Europea):\n"
            "   Ejecutar los experimentos EXP-01 a EXP-03 sobre COST239 (11 nodos, 26 enlaces, alta conectividad mallada), ya integrada en data/topologies.json.",
            "2. Sensibilidad Paramétrica de Costos CAPEX:\n"
            "   Evaluar el punto de equilibrio económico variando el sobrecosto de obra civil (C_inst) del Camino 3 frente al Camino 2.",
            "3. Estrategia Híbrida Combinada (Camino 1 + 2 + 3):\n"
            "   Permitir que el planificador voraz combine enlaces paralelos en el núcleo y bypasses costa a costa en un mismo portafolio anual.",
        ],
        border_color=C_SKY, bg_color=C_CARD_WHITE, title_color=C_SKY, font_size=10.5
    )

    # Banner inferior de checklist de rúbrica
    add_card(
        s10, 0.45, 5.10, 12.43, 1.85,
        "Checklist de Cumplimiento de Evaluación — Taller 3 (100% Completado)",
        [
            "✔ Parte C (10 pts): Reajuste metodológico completo (Fotografías estáticas k=0..8, Conexiones Fuera, TeleGeography 24%/30%/32%).",
            "✔ Parte A (40 pts): Modelo físico GSNR + Invariante 320 FSUs + Motor RMLSA k-SP First-Fit + Demo Interactiva (dashboard_simulador_taller3.html).",
            "✔ Parte B (50 pts): Resultados multi-año completos (EXP-01, EXP-02 y EXP-03) comparando los 3 Caminos bajo igualdad de CAPEX.",
        ],
        border_color=C_NAVY_DARK, bg_color=C_EMERALD_BG, title_color=C_NAVY_DARK, font_size=11.0
    )
    add_footer(s10, 10)

    set_speaker_notes(
        s10,
        """[TIEMPO: 9:00 - 10:00 | Todos / Cierre]
Para concluir:
1) Contamos con el simulador estático EON y el dashboard visual 100% operativos, validados sin colisiones espectrales y cumpliendo estrictamente la invariante de 320 FSUs en Banda C.
2) Demostramos cuantitativamente que, bajo el mismo presupuesto CAPEX, la estrategia voraz supera al baseline de utilización, y que los Caminos 2 (HCF Paralela activa) y 3 (Bypass HCF directo) reducen las conexiones fuera en un 46.3% y 36.1% respectivamente, frente al 15.2% del reemplazo puro.
3) Hacia el informe final extenderemos estas simulaciones a la topología europea COST239 (que ya está cargada en nuestro código) y evaluaremos estrategias mixtas combinando los 3 caminos.
Muchas gracias, quedamos atentos a sus preguntas y podemos mostrar cualquier enlace o año en vivo en el simulador."""
    )

    out_root = Path("Presentacion_Taller3_SMF_HCF.pptx")
    out_results = Path("results/Presentacion_Taller3_SMF_HCF.pptx")
    prs.save(out_root)
    prs.save(out_results)
    print(f"[OK] PowerPoint generado exitosamente en: {out_root.resolve()}")
    print(f"[OK] Copia en results: {out_results.resolve()}")
    return out_root


if __name__ == "__main__":
    build_presentation()
