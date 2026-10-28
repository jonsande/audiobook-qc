# Reglas duraderas del proyecto

- Lee `STEPS.md` antes de implementar una fase y respeta sus criterios de salida.
- Trabaja por fases pequeñas, con cambios revisables. No adelantes fases ni
  funcionalidades que no se hayan solicitado.
- Mantén la lógica de dominio independiente de mpv, Okular, atajos, GUI,
  almacenamiento y exportación Excel. Las integraciones son adaptadores externos.
- Okular debe ser sustituible por otro adaptador, incluido un posible visor PDF
  propio, sin cambiar las reglas de dominio.
- Favorece Python sencillo, tipado y testeable, compatible con Python 3.10 o
  superior. Usa la estructura `src/`.
- Evita dependencias cuando la biblioteca estándar sea suficiente. No añadas
  frameworks web ni GUI sin una petición explícita para la fase correspondiente.
- Escribe tests para comportamiento relevante. Usa pytest y ejecuta también
  `ruff check .` y `ruff format --check .` antes de dar un cambio por terminado.
- Los únicos códigos editoriales iniciales son `TEXT`, `PRON`, `DICC`, `RUID`,
  `RESP`, `INTER` y `OTRO`. No los renombres, traduzcas ni amplíes sin indicación
  explícita.
- No inventes reglas de negocio desconocidas: solicita aclaración cuando sean
  necesarias para implementar el comportamiento.
- Documenta los supuestos técnicos que necesiten verificación experimental,
  indicando qué falta comprobar y con qué criterio se considerarán validados.
- No implementes la Fase 3 sin disponer de una muestra de la plantilla Excel
  corporativa.
- Mantén la documentación y los criterios de salida acordes con lo realmente
  implementado y verificado. No marques una fase completa por tener scaffolding.
