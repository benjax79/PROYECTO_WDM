# Guion Ejecutivo y Estructura de Presentación + Demo (10 Minutos) - Taller 3
**Curso:** TEL-317 Redes Ópticas WDM (UTFSM)  
**Proyecto:** Migración Progresiva de SMF a HCF en Redes Ópticas Elásticas Estáticas  
**Equipo:** Fernanda Manríquez · Josefa Zamora · Benjamín Abde  
**Profesor:** Dr. Nicolás Jara  

---

## Minutos 0:00 – 2:00 | Parte C: Reajuste de Objetivos y Definiciones (10 puntos)
- **Paso a Planificación Estática por Fotografías Anuales ($k = 0 \dots 8$):** Siguiendo la retroalimentación del Taller 2, se reemplazó la simulación dinámica de eventos discretos por fotografías estáticas anuales sobre Banda C ($320\text{ FSUs}$ de $12.5\text{ GHz}$).
- **Nueva Métrica de Desempeño:** Se evalúan las **Conexiones Fuera (Rechazadas)** y el **Tráfico No Atendido [Gbps/Tbps]**, distinguiendo explícitamente entre rechazo por capa física ($\text{GSNR}$) y rechazo por saturación/fragmentación de espectro.
- **Respaldo de Crecimiento Anual:** Se modela $D(k) = D(0)\times(1+r)^k$ con $r = 30\%$ base (Sticca et al. [4]) y análisis de sensibilidad con reportes globales de **TeleGeography** ($24\%$ proyectado 2025–2035 y $32\%$ histórico 2020–2024 [5]).
- **Tres Caminos de Migración Evaluados:** (1) Reemplazo de enlaces $\text{SMF} \to \text{HCF}$, (2) Adición de fibra HCF paralela evitando *dark fiber*, y (3) Enlace nuevo HCF directo de larga distancia (*bypass*).

---

## Minutos 2:00 – 5:00 | Parte A: Preparación de Herramientas y Pruebas Funcionales (40 puntos)
- **Demostración en Vivo / Video (`python run_taller3_demo.py`):**
  1. **TEST-01 (Topología y Asignador First-Fit):** Carga de `data/topologies.json` con **NSFNet (14 nodos, 21 enlaces bidireccionales)**. En $k=0$, las **71 conexiones solicitadas (18.80 Tbps)** se asignan con **0 Conexiones Fuera** y **0 colisiones espectrales**, verificando continuidad y contigüidad espectral.
  2. **TEST-02 (Validación de Capa Física GSNR - `fig1_validacion_gsnr.png`):** Aplicando la acumulación inversa paralela de Pedro et al. [1], en una ruta de $1800\text{ km}$ (18 spans) el $\text{GSNR}$ sube de $13.89\text{ dB}$ (`8-QAM`, 11 FSUs @ 400G) en 100% SMF a $15.44\text{ dB}$ (`16-QAM`, 8 FSUs) en ruta híbrida 50/50 y $17.89\text{ dB}$ (`32-QAM`, 7 FSUs) en 100% HCF. En una ruta transcontinental de $3600\text{ km}$ (36 spans), migrar a HCF eleva el $\text{GSNR}$ de $10.88\text{ dB}$ (`QPSK`, 16 FSUs) a $14.88\text{ dB}$ (`16-QAM`, 8 FSUs), **reduciendo el consumo de espectro exactamente a la mitad (-50% FSUs)** sin inventar nuevos slots en la fibra.

---

## Minutos 5:00 – 9:00 | Parte B: Implementación Preliminar y Resultados (50 puntos)
- **EXP-01 (Curva de Saturación 100% SMF - `fig2_curva_saturacion_smf.png`):**
  - En $k=0$ hay `0` Conexiones Fuera (utilización global $22.99\%$, enlace cuello de botella `e7_8` al $65.62\%$).
  - A partir de $k=1$ ($r=30\%$) aparecen los primeros rechazos por agotamiento espectral en los enlaces centrales, llegando en $k=8$ a **902 Conexiones Fuera** de 1203 solicitadas.
- **EXP-02 (Heurística Voraz Costo-Beneficio vs. Baseline Utilización en Camino 1 - `fig3_reemplazo_vs_utilizacion.png`):**
  - La política voraz ($\Delta N_{\text{fuera}} / C(e)$) selecciona los enlaces que destraban simultáneamente la modulación de múltiples rutas largas (`['e3_4', 'e3_10', 'e8_9', 'e5_9', 'e7_8', 'e6_7']`), logrando **2394 Conexiones Fuera acumuladas** frente a **2416** del orden fijo por utilización y **2720** de la red 100% SMF.
- **EXP-03 (Comparación de los 3 Caminos en Igualdad de CAPEX $\le 8500\text{ UR}$ - `fig4_comparacion_3_caminos.png`):**
  - **Camino 1 (Reemplazo SMF $\to$ HCF):** 2306 Conexiones Fuera acumuladas | 439.37 Tbps atendidos (8285 UR).
  - **Camino 2 (Fibra HCF Paralela sin apagar SMF):** 1461 Conexiones Fuera acumuladas | 526.93 Tbps atendidos (8335 UR). Al conservar los 320 FSUs de la SMF activa y sumar una fibra HCF paralela para rutas exigentes en GSNR, logra la mayor reducción de rechazos.
  - **Camino 3 (Enlace Nuevo HCF Bypass Directo):** 1738 Conexiones Fuera acumuladas | 492.63 Tbps atendidos (7810 UR), descargando múltiples saltos intermedios mediante enlaces directos de larga distancia.

---

## Minutos 9:00 – 10:00 | Conclusiones Preliminares y Pasos al Informe Final
- **Hallazgo Principal:** En Camino 1, aunque HCF mantiene fijos los 320 FSUs de Banda C, su ganancia de $+4.0\text{ dB}$ por span permite saltar de `QPSK`/`8-QAM` a `16-QAM`/`32-QAM`, liberando entre $27\%$ y $50\%$ de los slots por conexión. Por su parte, Camino 2 y Camino 3 evitan desperdiciar la planta SMF instalada (*dark fiber*) y descongestionan los cuellos de botella centrales de NSFNet.
- **Trabajo hacia el Informe Final:** Análisis de sensibilidad paramétrica sobre costos CAPEX ($c_{\text{km}}, C_{\text{inst}}$), evaluación sobre la topología europea **COST239 (11 nodos, 26 enlaces)** ya integrada en `data/topologies.json` y optimización conjunta de los Caminos 1, 2 y 3.
