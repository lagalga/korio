"""
Módulo agéntico de Korio.

Mantiene los roles del pipeline multi-agente (Ingestor, Detector, Arbitrator,
Supervisor, Curator) como **clases dentro de un mismo proceso Python**, no
como microservicios separados. Esto es deliberado:

- **Latencia mínima**: la ingesta de un documento atraviesa los 5 roles sin
  saltos de red. El camino crítico (~10-30 s) sigue dominado por Ollama
  (embeddings) y Mistral (extracción de entidades), no por el sistema agéntico.
- **Transaccionalidad SQL ACID**: como todo vive en un proceso, las
  escrituras pueden envolverse en un único RPC PL/pgSQL (`ingest_document_atomic`).
  El feedback explícito del profesor en el Entregable 4 está respondido aquí.
- **Observabilidad**: cada transición emite un evento estructurado vía
  `events.emit()`. El INSERT a `pipeline_events` es síncrono y atómico; la
  difusión por webhook a n8n es fire-and-forget. Si n8n cae el sistema sigue
  funcionando; cuando vuelve, se ven los eventos en directo.

Diferencia con el sistema E3/E4 (5 microservicios en LangFlow): allí cada
nodo era un servicio independiente y los saltos visualmente claros tenían
coste real de ~200-500 ms por transición. En Korio los agentes son roles
lógicos; la visualización vive en n8n consumiendo el bus de eventos.
"""
