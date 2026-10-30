# Borrador de Diapositivas: Presentación de Avance y Demo (10 Minutos) — Taller 3
**Curso:** TEL-317 Redes Ópticas WDM — UTFSM  
**Título:** Migración Progresiva de SMF a HCF en Redes Ópticas Elásticas Estáticas  
**Equipo:** Fernanda Manríquez · Josefa Zamora · Benjamín Abde  
**Profesor:** Dr. Nicolás Jara  
**Fechas de Presentación:** 5 y 7 de Noviembre  

---

## Diapositiva 1: Portada (0:00 – 0:30)
- **Título:** Migración Progresiva de SMF a HCF en Redes Ópticas Elásticas Estáticas sobre Banda C
- **Subtítulo:** Planificación Multi-Año basada en GSNR Acumulado y Evaluación de 3 Caminos de Actualización (Reemplazo, Fibra Paralela y Bypass Directo)
- **Integrantes:** Fernanda Manríquez, Josefa Zamora, Benjamín Abde
- **Curso:** TEL-317 Redes Ópticas WDM — Profesor Dr. Nicolás Jara

---

## Diapositiva 2: Parte C — Reajuste Metodológico tras Feedback Taller 2 (0:30 – 2:00) [10 pts]
### Tabla Comparativa de Ajustes Obligatorios
| Dimensión | Propuesta Original (Taller 2) | Redefinición Implementada (Taller 3) |
| :--- | :--- | :--- |
| **1. Paradigma de Simulación** | Simulación dinámica de eventos discretos con corte en 1% de bloqueo. | **Planificación Estática por Fotografías Anuales ($k = 0 \dots 8$):** En cada año $k$ se resuelve la asignación completa en Banda C desde cero. |
| **2. Métrica de Desempeño** | Probabilidad de bloqueo instantánea ($B = N_{\text{bloq}} / N_{\text{sol}}$). | **Conexiones Fuera (Rechazadas)** y **Tráfico No Atendido [Tbps]**, separando rechazo por capa física ($\text{GSNR}$) vs. saturación de espectro. |
| **3. Capa Física EON** | Modelo abstracto de calidad de transmisión. | **Suma Paralela Inversa de GSNR por span** (Pedro et al. [1]) y tabla oficial de modulaciones (`BPSK` a `64-QAM`) con $320\text{ FSUs}$ fijos de $12.5\text{ GHz}$. |
| **4. Integración de HCF** | Solo reemplazo voraz de enlaces completos. | **Evaluación de 3 Caminos:** (1) Reemplazo $\text{SMF}\to\text{HCF}$, (2) Fibra HCF paralela (*sin dark fiber*), y (3) Enlace nuevo HCF directo (*bypass*). |
| **5. Crecimiento Anual** | Factor fijo del 30% sin asociar a años calendario. | **Proyección Anual Justificada con TeleGeography [5]:** $D(k) = D(0)\times(1+r)^k$ con $r = 30\%$ base [4] y sensibilidad en $24\%$ (2025–2035) y $32\%$ (2020–2024). |

- **Guion del Orador (1.5 min):**
  > *"Siguiendo la retroalimentación del Taller 2, reajustamos el simulador hacia un motor de planificación estática por fotografías anuales en Banda C (320 FSUs). En lugar de probabilidad de bloqueo dinámica, medimos cuántas conexiones de la matriz anual quedan fuera y cuántos Tbps dejan de atenderse a medida que el tráfico crece según las tasas reportadas por TeleGeography (24%, 30% y 32% anual)."*

---

## Diapositiva 3: Parte A — Modelo Físico Exacto GSNR y Tabla EON (2:00 – 3:30) [40 pts]
- **Invariante Física #1:** Conectar fibras SMF y HCF sin conversión de longitud de onda exige **continuidad** y **contigüidad espectral** sobre los mismos **320 FSUs** de Banda C ($4.0\text{ THz}$, grilla de $12.5\text{ GHz}$). Instalar HCF **no aumenta los slots**; reduce la atenuación y el ruido no lineal (NLI).
- **Acumulación Paralela Inversa de GSNR (Pedro et al. [1], [3]):**
  $$\text{GSNR}_{\text{ruta}}(p)^{-1} = \sum_{e \in p} \sum_{s=1}^{N_{\text{spans}}(e)} \text{GSNR}_{\text{span}}(\tau(e, s))^{-1} = \frac{N_{\text{SMF}}}{\text{GSNR}_{1,\text{SMF}}} + \frac{N_{\text{HCF}}}{\text{GSNR}_{1,\text{HCF}}}$$
  - Calibración exacta en Banda C ($L_{\text{span}} = 100\text{ km}$): $\text{GSNR}_{1,\text{SMF}}^{\text{dB}} = 26.44\text{ dB}$ y $\Delta\text{SNR}_{\text{HCF}}^{\text{dB}} = +4.0\text{ dB/span}$.
- **Validación `TEST-02` (`results/fig1_validacion_gsnr.png`):**
  - **Ruta $1800\text{ km}$ (18 spans, $400\text{ Gbps}$):** Pasa de $13.89\text{ dB}$ (`8-QAM`, $11\text{ FSUs}$) en 100% SMF $\to$ $15.44\text{ dB}$ (`16-QAM`, $8\text{ FSUs}$) en híbrida 50/50 $\to$ $17.89\text{ dB}$ (`32-QAM`, $7\text{ FSUs}$) en 100% HCF.
  - **Ruta Transcontinental $3600\text{ km}$ (36 spans, $400\text{ Gbps}$):** Pasa de $10.88\text{ dB}$ (`QPSK`, $16\text{ FSUs}$) en 100% SMF a $14.88\text{ dB}$ (`16-QAM`, $8\text{ FSUs}$) en 100% HCF, **reduciendo el espectro ocupado exactamente a la mitad (-50% FSUs)**.

---

## Diapositiva 4: Parte A — Arquitectura del Motor RMLSA Estático y Demo en Vivo (3:30 – 5:00) [40 pts]
- **Pipeline en Python (`config.py`, `topology.py`, `physics_qot.py`, `rmlsa_static.py`, `migration_policies.py`):**
  1. **Cuantización Acumulativa de Demanda $C(k)$:** Transpondedores discretos $\{400, 100, 40, 10\}\text{ Gbps}$.
  2. **Ordenamiento Determinista:** Descendente por $(\text{Bitrate} \times \text{Distancia\_Ruta\_Más\_Corta})$.
  3. **Ruteo $k$-Shortest Paths ($k=3$) + Selección QoT:** Elige el formato $m$ de mayor eficiencia (`64-QAM` $\to$ `BPSK`) + $G = 1$ FSU de guarda.
  4. **Asignación First-Fit Vectorial:** Intersección booleana de disponibilidad sobre los 320 slots de todos los enlaces de la ruta.
- **Demostración en Vivo (`dashboard_simulador_taller3.html` / `TEST-01`):**
  - En $k=0$ sobre **NSFNet (14 nodos, 21 enlaces, 100% SMF)**: **71 conexiones solicitadas ($18.80\text{ Tbps}$) $\to$ 71 atendidas, 0 Conexiones Fuera, 0 colisiones espectrales**.

---

## Diapositiva 5: Parte B — Resultados Multi-Año `EXP-01` y `EXP-02` (5:00 – 7:00) [50 pts]
- **`EXP-01` (Curva de Saturación 100% SMF — `results/fig2_curva_saturacion_smf.png`):**
  - En $k=0$ y $k=1$ la red SMF absorbe todo el tráfico (`0` Conexiones Fuera, aunque el enlace central `e7_8` llega al $95.6\%$ en $k=1$).
  - Desde $k=2$ ($31$ fuera) hasta $k=8$ ($902$ fuera de $1203$ solicitadas), el cuello de botella espectral rechaza hasta el $75\%$ de las conexiones.
- **`EXP-02` (Camino 1: Heurística Voraz $\Delta N_{\text{fuera}}/C(e)$ vs. Baseline por Mayor Utilización — `results/fig3_reemplazo_vs_utilizacion.png`):**
  - Bajo el mismo límite de presupuesto ($\le 8500\text{ UR}$), la heurística voraz prioriza enlaces troncales (`e3_4, e3_10, e7_8, e6_7, e4_6, e8_9, e10_12`) que elevan la modulación de múltiples rutas largas, reduciendo las Conexiones Fuera acumuladas a **2306** (frente a **2416** de Mayor Utilización y **2720** de 100% SMF) y atendiendo **$+23.58\text{ Tbps}$ más** que el baseline por utilización.

---

## Diapositiva 6: Parte B — Resultados `EXP-03`: Comparación de los 3 Caminos del Profesor (7:00 – 9:00) [50 pts]
- **Comparación en Igualdad de Presupuesto CAPEX ($\le 8500\text{ UR}$, $k = 0 \dots 8$, $r = 30\%$ — `results/fig4_comparacion_3_caminos.png`):**

| Estrategia de Migración | CAPEX Invertido | Conexiones Fuera ($k=4$) | Conexiones Fuera Acum. ($k=0..8$) | Tráfico Total Atendido ($k=0..8$) | Ganancia vs. 100% SMF |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Sin Migración (100% SMF)** | $0\text{ UR}$ | 182 | 2720 | $385.64\text{ Tbps}$ | Base |
| **Camino 1: Reemplazo SMF $\to$ HCF** | $8285\text{ UR}$ | 119 | 2306 | $439.37\text{ Tbps}$ | $-15.2\%$ rechazos / $+53.7\text{ Tbps}$ |
| **Camino 2: Fibra HCF Paralela** | $8335\text{ UR}$ | **0** | **1461** | **$526.93\text{ Tbps}$** | **$-46.3\%$ rechazos / $+141.3\text{ Tbps}$** |
| **Camino 3: Bypass HCF Directo** | $7810\text{ UR}$ | **38** | **1738** | **$492.63\text{ Tbps}$** | **$-36.1\%$ rechazos / $+107.0\text{ Tbps}$** |

- **Interpretación Física:**
  - **Camino 1** demuestra que mejorar solo el GSNR permite comprimir FSUs hasta un 50%, pero sigue limitado por el techo único de 320 slots por enlace.
  - **Camino 2** evita dejar la fibra SMF como *dark fiber*, ruteando tráfico largo por HCF (en `16/32-QAM`) y tráfico corto por SMF, logrando **0 rechazos hasta el año $k=4$**.
  - **Camino 3** instala 3 enlaces *bypass* transcontinentales (`e4_8`, `e4_11`, `e1_11`), descargando de golpe los saltos centrales de NSFNet con menor CAPEX ($7810\text{ UR}$).

---

## Diapositiva 7: Conclusiones Preliminares y Pasos hacia el Informe Final (9:00 – 10:00)
1. **Herramienta 100% Operativa y Validada:** Simulador estático EON modular en Python + Dashboard Visual Interactivo en Banda C con verificación automática de invariantes físicas.
2. **Hallazgo Clave del Taller 3:** En etapas tempranas ($k = 2, 3$), el reemplazo $\text{SMF}\to\text{HCF}$ (Camino 1) destraba la red mediante eficiencia espectral (`QPSK` $\to$ `16-QAM`); en etapas de alta congestión ($k \ge 4$), conservar la SMF activa junto a HCF paralela (Camino 2) o instalar enlaces *bypass* HCF de larga distancia (Camino 3) multiplica por $2.6\times$ la reducción de conexiones rechazadas bajo el mismo presupuesto CAPEX.
3. **Hoja de Ruta al Informe Final:**
   - Evaluar las 3 políticas sobre la topología europea **COST239 (11 nodos, 26 enlaces)** ya cargada en `data/topologies.json`.
   - Análisis de sensibilidad paramétrica del costo de obra civil en enlaces *bypass* ($C_{\text{inst}}$).
   - Estrategia híbrida combinada (Camino 1 + Camino 2 + Camino 3).
