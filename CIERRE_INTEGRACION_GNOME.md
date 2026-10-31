# Cierre documental del bloque GNOME

Fecha: 31 de octubre de 2026. Punto de partida: master en
`32ec6e970f886915aa169939be28d3b853cea595`, coincidente con origin/master
consultado por red. No había cambios de código; solo los informes 026–028
pendientes de seguimiento. Este cierre añade únicamente documentación.

## Evidencia y alcance validado

| Etapa | Resultado en su momento | Continuación |
| --- | --- | --- |
| [026](INFORME_EJECUCION_MIGRACION_GNOME.md) | Migración GNOME complete; ciclo bloqueado por mpv cerrado | Resuelto operacionalmente en 027 |
| [027](INFORME_VALIDACION_MODO_CORRECCION_REAL.md) | Fuentes recuperadas y ciclo real on/status/off; sin capturas | Pulsaciones verificadas en 028 |
| [028](INFORME_VALIDACION_FISICA_ATAJOS.md) | APTO: siete capturas físicas y protecciones verificadas | Ensayo y siete filas conservados |

Las observaciones visuales de avisos y ayuda de Okular fueron confirmadas por
el usuario. Tipos, posiciones, texto sintético, PDF/página y destino se
corroboraron en persistencia. Las 13 incidencias de las cuatro bases originales
se conservaron, separadas de las siete del ensayo.

README y STEPS actualizan solo el estado del bloque, los enlaces a evidencias,
las limitaciones pertinentes y la referencia a la propuesta de siguiente fase.
Los pendientes de los informes históricos se conservan como tales en su fecha;
no se reescriben retrospectivamente sus veredictos.

## Revisión para publicación

Se leyeron los tres informes y se revisaron rutas, identificadores, nombres de
fuentes y patrones de credenciales. No se identificaron contraseñas, claves
privadas, credenciales de servicio ni contenido editorial transcrito de fuentes
originales. Sí había detalles privados innecesarios para GitHub, eliminados
exclusivamente de las copias documentales destinadas a Git:

- Rutas personales de proyecto, trabajos, estado, fuentes y respaldos: marcadores
  `/RUTA/AL/PROYECTO`, `/RAIZ_TRABAJOS`, `/FUENTES_ORIGINALES`,
  `/RESPALDO_LOCAL`, `/RESPALDO_INDEPENDIENTE` y variables XDG descriptivas.
- Identificador del disco, nombre/uid del usuario y etiqueta personal de un
  atajo ajeno: referencias genéricas conservando la explicación técnica.
- Nombre del PDF y del capítulo originales: nombres genéricos, sin títulos
  editoriales ni referencias de pedido.
- Huella exacta de confirmación de migración: `<HUELLA_DEL_PLAN>`. Es una huella
  de snapshot, no una contraseña; no es necesario publicar el valor operativo.

Cada informe incluye una nota que justifica estas sustituciones. Los comandos
con marcadores documentan operaciones históricas y requieren adaptación; no
constituyen instrucciones para repetir la migración de la instalación validada.
`$XDG_STATE_HOME` representa aquí el directorio de estado, incluido el fallback
habitual del usuario si la variable no está definida.

Se mantienen UUID de trabajos, recuentos y hashes técnicos para contrastar
integridad, sin publicar el contenido de sus bases. Los informes originales se
preservaron fuera del repositorio antes de revisar estas copias; los respaldos
y evidencias operativas anteriores no se modificaron. La revisión no reescribe
el historial Git previo ni amplía su alcance a una depuración de documentos
históricos ya versionados.

El commit incluye solo siete archivos Markdown: README, STEPS, estos tres
informes, este cierre y la propuesta GUI. No incluye bases, fuentes, respaldos,
configuración personal ni scripts operativos de auditoría.

## Comprobación actual del entorno y calidad

La auditoría usó consultas GSettings y controladores de estado de solo lectura,
inventarios/hashes y SQLite con `mode=ro&immutable=1`, sin sidecars. No se
ejecutaron on/off, apply/recover, lanzadores, capturas ni escrituras de selección.
Se compararon instantáneas completas antes y después de las comprobaciones:
modo inactivo y sincronizado, siete bindings vacíos, journal suspendido,
migración complete/coherente, PRUEBA_A seleccionado, cinco bases con recuentos
1/3/4/5/7 y asociaciones/configuración intactas. No se leyó PRIMARY ni se inició
mpv: fuente cerrada sigue siendo indisponible y no invalida la integridad del
trabajo. No se promete que seleccionar PRUEBA_A baste para volver a capturar.

Calidad del cierre: **786 tests superados, 42,55 s**; Ruff check correcto,
Ruff format --check correcto (64 archivos) y git diff --check sin errores.
Los tests utilizan datos aislados; ningún test sustituye las confirmaciones
físicas ya registradas en 028.

## Siguiente bloque propuesto

[PROPUESTA_ARQUITECTURA_GUI.md](PROPUESTA_ARQUITECTURA_GUI.md) describe servicios
compartidos con CLI, presentadores separados del dominio, gestión/revisión,
configuración editorial y de atajos, y preparación de datos de exportación.
Compara PySide6/Widgets, Tkinter/ttk y wxPython, sin elegir definitivamente.
La recomendación inicial es evaluar PySide6 y Tkinter con el mismo caso aislado,
después servicios de consulta y una interfaz solo lectura.

No se implementa GUI ni se añaden dependencias. La biblioteca de ventanas no
resuelve por sí sola la portabilidad de captura, bloqueos o IPC a Windows/macOS
y Wayland. Excel continúa bloqueado hasta recibir la plantilla corporativa.
