## Slide 1 · Portada
**SUBTÍTULO/CLAIM:** Korio: El Company Brain de tu pyme.
*   Conocimiento operativo consultable en lenguaje natural.
*   Sin depender de quien se acuerde de documentarlo.
*   Para pymes, ahora.

**[DATO/GRÁFICO SUGERIDO]:** Logo limpio de Korio + Mockup minimalista de un
chat respondiendo a una pregunta operativa compleja.
**[NOTAS DEL ORADOR]:**
*(Test de los 30 segundos)*. Korio es un SaaS multi-tenant que soluciona la
gestión del conocimiento en las pymes. ¿Para quién? Para el 99,8% del tejido
empresarial que no puede pagar soluciones Enterprise. ¿Por qué ahora? Existe una
brecha masiva de acceso a IA en pymes (solo 8,7% adopción) [4]; las herramientas
están, pero requieren equipos de IT que las pymes no tienen. Korio se despliega
solo y democratiza el acceso a la información corporativa.

---

## Slide 2 · El Problema
**SUBTÍTULO/CLAIM:** El conocimiento vive en las personas, no en los sistemas.
*   Fragmentación total: Drive, SharePoint, hilos de email antiguos.
*   Pérdida crítica de *know-how* por rotación de personal.

**[DATO/GRÁFICO SUGERIDO]:** Gran número destacado: **20%** (El porcentaje de la
jornada que un empleado pierde buscando información interna) [5].
**[NOTAS DEL ORADOR]:**
El problema no es la falta de documentos, es el caos. Imaginen a un empleado
veterano que se marcha de una clínica o gestoría. Semanas de *onboarding* para
su reemplazo y errores continuos porque el "Protocolo_v3_Final.docx" convive con
un email de hace dos años que lo contradice [5]. Las empresas medianas pierden
hasta 1,8 M$ al año por conocimiento tácito no documentado [5].

---

## Slide 3 · La Solución
**SUBTÍTULO/CLAIM:** Un cerebro corporativo sin fricción de entrada ni
mantenimiento.
*   Ingesta universal automatizada.
*   RAG híbrido con gobernanza activa documental.
*   Multicanal y seguro desde el día uno.

**[DATO/GRÁFICO SUGERIDO]:** Diagrama visual simple "Antes vs. Después" (Caos de
logos de Drive/Slack → Korio → Respuesta clara en 1 segundo).
**[NOTAS DEL ORADOR]:**
La solución (nuestra promesa de valor) es integrar el conocimiento corporativo
en el flujo de trabajo diario sin pedirle a la pyme que cambie sus hábitos [6].
Korio se conecta a sus canales, lee, procesa y detecta contradicciones de forma
automática. El usuario solo tiene que preguntar en lenguaje natural y recibe una
respuesta con la fuente exacta citada.

---

## Slide 4 · Mercado (TAM/SAM/SOM)
**SUBTÍTULO/CLAIM:** Oportunidad masiva en el segmento empresarial más
desatendido.
*   3,25M empresas en España; 99,8% son pymes.
*   Mercado concentrado en grandes cuentas.

**[DATO/GRÁFICO SUGERIDO]:** Tres círculos concéntricos (Bottom-up). SOM: N.º de
pymes objetivo iniciales × ARPU estimado (~3.828 €/año).
**[NOTAS DEL ORADOR]:**
Calculamos el mercado de abajo hacia arriba (Bottom-Up) [2, 7]. No usamos
reportes abstractos de Gartner. El 69% del gasto en software de gestión del
conocimiento está en organizaciones de más de 500 empleados [4]. Nuestro SAM son
las pymes de 3 a 50 empleados en España que gastan miles de euros en horas
improductivas. Con un ticket medio anual de ~3.800€, captar solo el 1% de
nuestro nicho inicial representa un mercado direccionable altamente rentable.

---

## Slide 5 · Producto Objetivo (Visión To-Be)
**SUBTÍTULO/CLAIM:** El conocimiento corporativo integrado donde el usuario ya
trabaja.
*   Conectores OAuth (Slack, Drive, Outlook).
*   Multicanal: Chat web, Slackbot.
*   Protocolo MCP nativo.

**[DATO/GRÁFICO SUGERIDO]:** Captura visual de un asistente IA (ej. Claude
Desktop) consultando a Korio a través de MCP [6].
**[NOTAS DEL ORADOR]:**
El producto objetivo (lo que vendemos) funciona de manera invisible. Cada
cliente tiene su *tenant* aislado [8]. El administrador conecta las fuentes de
la empresa en 3 clics y el sistema se alimenta solo. La revolución real es el
soporte nativo para el *Model Context Protocol* (MCP): el conocimiento de la
empresa se expone como una herramienta a cualquier agente de IA (como ChatGPT o
Claude Desktop) que la pyme ya utilice, sin obligarlos a usar una interfaz nueva
[6].

---

## Slide 6 · Cómo Funciona (Arquitectura)
**SUBTÍTULO/CLAIM:** Procesamiento seguro con soberanía de datos europea (RGPD).
*   Ingesta estructurada.
*   Recuperación semántica y de grafos.
*   Soberanía EU garantizada.

**[DATO/GRÁFICO SUGERIDO]:** Arquitectura de 4 bloques simplificada (Fuentes →
Vector+FalkorDB → Mistral EU → Multicanal/MCP) [9].
**[NOTAS DEL ORADOR]:**
No somos un "wrapper" o envoltorio de OpenAI [10]. La inteligencia reside en
nuestro *pipeline*. Combinamos una base de datos vectorial (pgvector) con un
grafo de conocimiento (FalkorDB) para recuperación de alta precisión [9]. Todo
opera bajo infraestructura europea (Hetzner, Supabase en Frankfurt y Mistral en
Francia) con Control de Acceso Basado en Roles (RBAC) [11]. Los datos no salen
de Europa, cumpliendo con RGPD y AI Act desde el diseño.

---

## Slide 7 · Evidencia Técnica (Prototipo Implementado)
**SUBTÍTULO/CLAIM:** Motor *core* validado en producción, no en papel.
*   Operativo en 2 verticales (Clínica, Legal).
*   Alta velocidad y fiabilidad comprobada.
*   Gobernanza activa real.

**[DATO/GRÁFICO SUGERIDO]:** Panel de métricas reales: Latencia p50=1983ms,
31/31 tests exitosos, 8 workflows automáticos (n8n), 27 aristas de contradicción
detectadas automáticamente [12, 13].
**[NOTAS DEL ORADOR]:**
El prototipo de TFM no es un MVP frágil, es la validación técnica del motor.
Tenemos 20 documentos productivos mapeados en 1130 nodos de grafo [13]. Nuestro
*pipeline* ha detectado 27 contradicciones semánticas reales ("CONTRADICTS")
[13], pausando esa información y pidiendo validación humana (HITL). Respondemos
consultas híbridas con una latencia mediana inferior a 2 segundos (1983ms) de
extremo a extremo [13]. El riesgo técnico de la arquitectura está mitigado.

---

## Slide 8 · Modelo de Negocio
**SUBTÍTULO/CLAIM:** Cobramos por empresa (*tenant*), no penalizamos el
crecimiento de plantilla.
*   Tiers: Starter (149€), Pro (349€), Business (699€).
*   Márgenes brutos eficientes (81-94%).

**[DATO/GRÁFICO SUGERIDO]:** Tabla de precios limpia. Destacar los COGS reales
(28€ / 33€ / 45€) frente al precio de venta [14].
**[NOTAS DEL ORADOR]:**
Nuestro modelo es disruptivo para las pymes: *Pricing* por *tenant*, sin mínimo
de asientos [11]. Un equipo de 5 personas no paga por "asientos vacíos".
Asumiendo un mix de clientes del 50/30/20 entre los 3 tiers, el ingreso medio es
de ~319€/mes [14]. Gracias a un *stack* de código abierto optimizado sin
dependencia de GPUs costosas para el RAG base, mantenemos márgenes brutos de
software SaaS de élite (>80%) [14].

---

## Slide 9 · Go-To-Market y Verticales
**SUBTÍTULO/CLAIM:** Foco inicial hiper-segmentado para garantizar la adopción.
*   Verticales: Clínicas, Legal, Logística, RRHH.
*   Adquisición directa.
*   Break-even proyectado: 24 clientes.

**[DATO/GRÁFICO SUGERIDO]:** Diagrama de la rampa de clientes. (Q1: 3 → 12
meses: 18 → Break-even: 24 tenants) [15].
**[NOTAS DEL ORADOR]:**
¿Cómo conseguimos a los primeros 100 clientes? [7]. No gastaremos en *Ads*
genéricos [16]. Ejecutaremos *outreach* directo a nichos con alta densidad
documental y necesidades de privacidad estricta: Clínicas y Despachos Legales
[15]. El prototipo ya está parametrizado para ellos. Con una estructura de
costes *lean* (*burn rate* de ~7,5k€/mes), alcanzamos el *break-even* operativo
con apenas 24 clientes recurrentes [15].

---

## Slide 10 · Paisaje Competitivo
**SUBTÍTULO/CLAIM:** El único *Company Brain* que ofrece gobernanza activa para
pymes.
*   Enterprise (Glean): Inaccesible.
*   Básicos (Notion AI, Slite): Sin gobernanza.
*   Hueco: Accesible + RBAC + Seguro.

**[DATO/GRÁFICO SUGERIDO]:** Matriz 2x2. Eje X: Precio/Accesibilidad (Pyme vs
Enterprise). Eje Y: Gobernanza Activa y RBAC (Baja vs Alta). Korio está solo en
el cuadrante Pyme/Alta Gobernanza [4, 11].
**[NOTAS DEL ORADOR]:**
Reconocemos la competencia [17]. Glean es increíble, pero cuesta 60k$ al año y
pide 100 usuarios mínimos [4]. Notion AI o Guru son baratos, pero no resuelven
la ingesta universal desde repositorios externos y carecen de un motor que
detecte automáticamente cuándo un documento contradice a otro [4]. Korio cubre
este hueco exacto: control de acceso desde el usuario 1, gobernanza activa, sin
cuotas mínimas y a un coste efectivo de 10-20€ por empleado [4].

---

## Slide 11 · Métricas SaaS Proyectadas
**SUBTÍTULO/CLAIM:** Crecimiento diseñado hacia la *Rule of 40* y expansión neta
[18, 19].
*   Objetivo NRR > 110%.
*   CAC Payback < 12 meses.
*   Churn anual controlado.

**[DATO/GRÁFICO SUGERIDO]:** *Dashboard* visual de los 3 KPIs críticos (NRR
[20], CAC Payback [21], LTV:CAC [22]) con sus objetivos estándar superpuestos.
**[NOTAS DEL ORADOR]:**
Construimos el negocio para cumplir los estándares Tier-1 de VC. La métrica
reina será el *Net Revenue Retention* (NRR) [20]; al cobrar por tramos de
consultas y *storage*, las pymes expandirán su uso naturalmente (upsell a
Pro/Business). Nuestro *payback* de adquisición debe mantenerse por debajo de
los 12 meses (estándar para SMB) [21] y el ratio LTV:CAC proyectado superará el
3:1 garantizando que nuestro modelo comercial genera caja real [22].

---

## Slide 12 · Equipo y Roadmap
**SUBTÍTULO/CLAIM:** Capacidad técnica probada y próximos hitos claros.
*   Ejecución y rigor demostrados (TFM).
*   Fase 1: OAuth Multi-tenant + Onboarding.
*   Fase 2: Guardrails + ROPA.

**[DATO/GRÁFICO SUGERIDO]:** Línea de tiempo simple de próximos 18 meses (Hitos
de producto, no solo técnicos) [23]. (Sin fotos ni currículum abultado, centrado
en los *milestones* del equipo).
**[NOTAS DEL ORADOR]:**
La capacidad de ejecución está demostrada con el grado de madurez técnica del
sistema actual (arquitectura ACID, grafos, RLS) [24]. Los próximos hitos que
desarrollará el equipo no son de I+D abstracto, son hitos de producto puro para
la monetización [23]: automatización *self-service* de OAuth (para que el
cliente se active solo), implementación de *guardrails* en el chat y
consolidación del *compliance* (ROPA, GDPR export) [23].

---

## Slide 13 · Unit Economics y Finanzas
**SUBTÍTULO/CLAIM:** Supervivencia garantizada con un *burn rate* mínimo.
*   Estructura *Lean* en Fase 1.
*   Gastos controlados.
*   Rumbo a la rentabilidad.

**[DATO/GRÁFICO SUGERIDO]:** Gráfico de barras acumuladas: *Burn rate* mensual
(7,3k - 7,8k €) vs. crecimiento proyectado de ingresos mensuales hasta cruzar la
línea de *break-even* [15].
**[NOTAS DEL ORADOR]:**
Nuestra estructura inicial para los próximos 12-18 meses requiere un equipo
operativo mínimo y altamente eficiente [15]. Sumando compensación a fundadores,
desarrolladores *freelance* clave y costes estructurales (marketing, servidores
SaaS), nuestra quema neta de caja (*burn rate*) oscila estrictamente entre
7.300€ y 7.800€ al mes [15]. Con este perfil de riesgo, la tracción orgánica es
suficiente para cruzar al terreno de la rentabilidad [15].

---

## Slide 14 · The Ask (Solicitud de Capital)
**SUBTÍTULO/CLAIM:** Capital para escalar, no para descubrir.
*   Hito previo: 15-20 clientes reales + Churn <3%.
*   Ronda Pre-Seed: 300k€ - 500k€.
*   *Runway*: 18-24 meses.

**[DATO/GRÁFICO SUGERIDO]:** Gráfico de destino de los fondos (Ej. 60%
Ventas/GTM, 40% Producto/Infra) junto a los hitos numéricos [25].
**[NOTAS DEL ORADOR]:**
No pedimos capital hoy para averiguar si el producto funciona. La estrategia es
cerrar los primeros 15-20 clientes *bootstrap*, documentar el ahorro de sus
casos de uso en 3 verticales y demostrar que no cancelan (Churn <3%) [15]. Solo
en ese punto de inflexión saldremos al mercado a levantar entre 300k€ y 500k€
(Lanzadera, Business Angels, Fondos Early) [15]. Esos fondos financiarán la
maquinaria GTM con un *runway* seguro de 18-24 meses.

---

## Slide 15 · Cierre y Visión
**SUBTÍTULO/CLAIM:** El conocimiento tácito convertido en el mayor activo de la
pyme.
*   Solución validada técnicamente.
*   Modelo recurrente escalable.
*   Diferenciación defendible.

**[DATO/GRÁFICO SUGERIDO]:** Logo final centrado + Email/Contacto del
responsable. URL de la demo [25].
**[NOTAS DEL ORADOR]:**
Korio transforma un dolor estructural y costoso en una ventaja competitiva
automática [26]. Tenemos un producto robusto (8 workflows, p50 < 2s), una
estrategia económica innegable (81-94% de margen) y un foso competitivo
fundamentado en gobernanza activa y soberanía europea [26]. Este es el momento
de democratizar el conocimiento en el tejido empresarial de la UE. Muchas
gracias.

---

### Checklist Final de Validación antes de Exportar (Para Diseño/Exportación)
*    **Prueba de los 30 Segundos:** La Portada dice exactamente qué es el
producto, para quién y por qué.
*    **Densidad de Información:** Ninguna diapositiva excede las 30 palabras de
texto visible. Hay 1 idea por slide [3].
*    **Continuidad Narrativa:** Si se leen solo los *Subtítulos/Claims*, cuentan
la historia de inicio a fin lógicamente [1].
*    **Evidencia sobre Afirmaciones:** Los "claims" del TAM, tracción y
prototipo están anclados a números verificables (31 tests, 20 docs, Bottom-up)
[27].
*    **Competencia Honesta:** La matriz 2x2 muestra ejes reales de decisión
(Gobernanza/Accesibilidad) y menciona competidores líderes [17, 28].
*    **The Ask Realista:** No hay rondas vagas; se especifica objetivo
(300-500k) condicionado a tracción previa [29, 30].
*    **Separación Producto vs. Prototipo:** Queda claro qué es el objetivo SaaS
SaaS y qué está ya implementado como evidencia de TFM.
