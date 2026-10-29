# audiobook-qc

Proyecto Python para agilizar la corrección de audiolibros en Linux.
Requiere Python 3.10 o superior.

Estado actual: **Fase 0 técnicamente completada y Fase 1 completada**, con modelo
de dominio y persistencia SQLite. Una CLI adicional integra captura y guardado
en una sola ejecución, validada con mpv, Okular y PRIMARY reales. El modo de
escritorio la conecta a atajos personalizados de GNOME con notificaciones.
**Fase 2 completada en este alcance**, con F1–F7 comprobados mediante pulsaciones
reales en Okular y F6 también en mpv. La protección añadida exige modo de
corrección activo y foco autorizado antes de capturar. Sin GUI propia.
El modo controla también la reserva efectiva de los atajos propios de GNOME.
El roadmap está en [STEPS.md](STEPS.md) y
las reglas de desarrollo en [AGENTS.md](AGENTS.md).

## Flujo previsto

1. El corrector detecta una incidencia y pausa manualmente mpv con Espacio.
2. Selecciona la frase correspondiente en Okular.
3. Pulsa un atajo asociado al tipo de incidencia.
4. El programa obtiene tipo, archivo de audio, timestamp de mpv, PDF actual,
   página actual y texto seleccionado, y guarda la incidencia en SQLite.
5. Las incidencias se podrán revisar y exportar a una plantilla Excel corporativa.

Los únicos códigos iniciales admitidos serán `TEXT`, `PRON`, `DICC`, `RUID`,
`RESP`, `INTER` y `OTRO`. Sus reglas de negocio aún no definidas no se presuponen.

## Desarrollo

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Para aplicar el formato: `python -m ruff format .`.

`pyproject.toml` declara setuptools como backend y fija las versiones de pytest
y Ruff en el extra `dev`. No hay dependencias de ejecución. Las dependencias
transitivas de las herramientas no tienen todavía un archivo de bloqueo.
La instalación requiere acceso al índice de paquetes o una caché disponible.

La prueba inicial comprueba la importación del paquete instalado y la coherencia
de su versión con los metadatos de distribución. No requiere mpv ni Okular.

## Diagnóstico del entorno (Fase 0.2)

Con el entorno virtual activado y el paquete instalado:

```bash
python -m audiobook_qc.diagnostics
```

Muestra sistema, kernel, arquitectura, Python, variables de sesión, versiones de
mpv y Okular y ubicación de herramientas D-Bus y de selección. Solo ejecuta
`mpv --version` y `okular --version`, con un límite de cinco segundos por comando;
las demás herramientas se localizan sin ejecutarlas. No consulta servicios D-Bus
ni lee la selección, y no instala paquetes ni cambia la configuración.

Distingue variables no definidas, variables vacías, ejecutables no encontrados y
comandos fallidos. La ausencia en PATH o en las rutas Qt comprobadas no demuestra
que un paquete no esté instalado en otra ubicación. Un fallo opcional se informa
y el diagnóstico continúa; su salida normal no certifica las integraciones.

Ejecuta el diagnóstico desde la sesión gráfica de trabajo para que sus variables
y permisos sean representativos. Un sandbox o una sesión remota puede impedir
incluso consultar la versión de Okular. Las pruebas usan comandos simulados y no
dependen de las aplicaciones instaladas.

## Estructura y arquitectura prevista

```text
.
├── .gitignore
├── AGENTS.md
├── README.md
├── STEPS.md
├── pyproject.toml
├── src/
│   └── audiobook_qc/
│       ├── __init__.py
│       ├── capture.py
│       ├── capture_and_save.py
│       ├── capture_probe.py
│       ├── capture_save_probe.py
│       ├── captured_incident.py
│       ├── correction_mode.py
│       ├── desktop_policy.py
│       ├── diagnostics.py
│       ├── incident.py
│       ├── incident_probe.py
│       ├── integrations/
│       │   ├── __init__.py
│       │   ├── activation.py
│       │   ├── focus.py
│       │   ├── gnome_shortcuts.py
│       │   ├── mpv.py
│       │   ├── notifications.py
│       │   ├── okular.py
│       │   └── selection.py
│       ├── mpv_probe.py
│       ├── okular_probe.py
│       ├── selection_probe.py
│       ├── shortcut_mode.py
│       └── sqlite_repository.py
└── tests/
    ├── test_capture.py
    ├── test_capture_and_save.py
    ├── test_correction_protection.py
    ├── test_diagnostics.py
    ├── test_desktop_activation.py
    ├── test_gnome_shortcuts.py
    ├── test_incident.py
    ├── test_mpv.py
    ├── test_okular.py
    ├── test_selection.py
    ├── test_package.py
    └── test_sqlite_repository.py
```

La estructura `src/` permite comprobar el paquete instalado sin importar por
accidente una copia de la raíz del repositorio.

La lógica de dominio será independiente de los adaptadores de mpv, documentos,
atajos, almacenamiento, GUI y Excel. Okular será un adaptador sustituible por
otro visor PDF. Los adaptadores contienen consultas puntuales; `capture.py`
coordina las tres fuentes mediante funciones inyectables. El objeto provisional
de captura vive en `captured_incident.py`, sin imports de los adaptadores ni CLI.

La Fase 0 está técnicamente completada con las limitaciones documentadas en
`STEPS.md`. La Fase 1 está completada; el caso de uso `capture_and_save.py`
conecta captura, conversión explícita y guardado con dependencias sustituibles.
Los supuestos que requieren experimentación están en [STEPS.md](STEPS.md).
La Fase 3 queda bloqueada hasta recibir una muestra de la plantilla Excel.

## Prueba aislada de mpv (Fase 0.3)

Abre manualmente el audio en un terminal, usando una ruta absoluta:

```bash
mpv --input-ipc-server=/tmp/audiobook-qc-mpv.sock /ruta/absoluta/capitulo.mp3
```

En otro terminal, desde el proyecto y con el entorno virtual activado:

```bash
python -m audiobook_qc.mpv_probe
# Para una instancia que utilice otro socket:
python -m audiobook_qc.mpv_probe --socket /ruta/al/socket.sock
```

Muestra archivo, ruta comunicada por mpv, posición en `HH:MM:SS.mmm` y segundos
decimales, duración si está disponible y estado de pausa. No inicia mpv, no pausa,
no hace seek ni observa continuamente. No cambia `mpv.conf`. Para repetir la
consulta, vuelve a ejecutar el comando. Puedes pausar manualmente con Espacio en
el terminal de mpv y repetirla para comparar las posiciones.

El adaptador usa un socket Unix y solo envía `get_property` para `filename`,
`path`, `time-pos`, `duration` y `pause`. Según la
[documentación oficial de mpv](https://mpv.io/manual/stable/#property-list),
`time-pos` representa la posición en segundos en el archivo actual. Se consulta
el valor numérico nativo, conservando los decimales recibidos; el redondeo a
milisegundos es exclusivo de la presentación. No se usa la representación textual
`time-pos/full` ni `audio-pts`, que puede incluir el retardo del controlador de
audio y dar valores negativos.

El [protocolo JSON IPC](https://mpv.io/manual/stable/#json-ipc) delimita los mensajes
por salto de línea. El transporte acumula fragmentos, conserva bytes sobrantes,
asocia respuestas por `request_id` e ignora eventos no solicitados. Cada consulta
tiene un límite de tres segundos y cada mensaje un límite de 1 MiB.

Un socket ausente, conexión rechazada, error de transporte o respuesta inválida
produce un mensaje en stderr y código de salida 1, sin traza. Una propiedad
temporalmente no disponible o `null` se muestra como tal y permite consultar las
demás; otros errores de mpv se notifican. La ruta se conserva tal como la devuelve
mpv: puede ser relativa a su directorio de trabajo, por eso se recomienda abrir
el audio con ruta absoluta. Las cinco lecturas son consecutivas, no atómicas:
el audio puede avanzar o cambiar entre ellas.

La ruta predeterminada es explícita para esta prueba local. Usa un socket distinto
por instancia; la utilidad no crea ni elimina sockets. Una ruta alternativa bajo
un directorio privado permite aislar las pruebas sin interferir con otro mpv.

La comunicación se verificó con mpv 0.34.1 y un WAV del sistema, usando salida
nula y otra instancia iniciada en pausa. La evidencia y las limitaciones están
en [STEPS.md](STEPS.md): queda comprobar el audio real y la pausa manual en una
posición intermedia. No se eliminan valores temporales negativos recibidos de
mpv; se observó uno con un audio corto en bucle y aún no se ha determinado su causa.

## Prueba aislada de Okular (Fase 0.4)

Abre manualmente un PDF en la sesión gráfica:

```bash
okular /ruta/absoluta/libro.pdf
```

Desde otro terminal, con el entorno virtual activado:

```bash
python -m audiobook_qc.okular_probe
python -m audiobook_qc.okular_probe --list-services
python -m audiobook_qc.okular_probe --service org.kde.okular-12345
```

Sustituye el nombre por uno de los servicios listados. Si hay varios, la utilidad
exige una elección explícita; no identifica la ventana activa. Con un solo
servicio lo elige automáticamente. No cierra otros Okular ni inicia uno nuevo.
Para esta prueba usa **una sola ventana/documento por servicio**: seleccionar un
servicio no basta para seleccionar una vista dentro del proceso. No está validado
que `/okular` siga la ventana o pestaña activa. Abrir B desde Archivo → Abrir
creó otra ventana en la prueba manual, no una pestaña; la lista de servicios no
añadió una entrada y `/okular` del servicio de A siguió devolviendo A. Los
servicios no deben interpretarse como un listado inequívoco de ventanas.

Requiere `busctl` con salida JSON (ya disponible y comprobado en este Ubuntu),
sin bindings Python adicionales. Se usa el bus de sesión del proceso actual,
con autoactivación e interacción de autorización deshabilitadas y tiempos límite.
Se comprueban las firmas por introspección en cada consulta; una API distinta
produce un error claro. El adaptador consulta `/okular`, interfaz
`org.kde.okular`, métodos sin argumentos `currentDocument() → s` y
`currentPage() → u`. Se verificaron en Okular 21.12.3, sin asumir la API de otra
versión. `qdbus` está en PATH pero su lanzador falla en este equipo; por eso no
se utiliza. `gdbus` sirvió para la investigación inicial.

La salida incluye servicio, objeto, documento original, ruta local si puede
identificarse inequívocamente y página nativa D-Bus. La primera página se
contrastó manualmente: Okular muestra 1 y D-Bus devuelve 1; en la tercera página
ambos muestran 3. No se suma 1 al dato.
El índice interno y la etiqueta impresa del libro/PDF son conceptos distintos y
no se obtienen ni se calculan. En el PDF temporal la primera página contiene
«PRINTED 101», sin que ello cambie el 1 del visor.

Se conserva el identificador original del documento. Solo se crea `Path` para
rutas absolutas o URLs `file:` locales sin ambigüedad; las URLs remotas y las
rutas relativas se conservan sin convertirlas ni acceder a su contenido. El caso
real probado devolvió una ruta absoluta, sin prefijo `file://`.

Las lecturas de documento y página son consecutivas, no atómicas: evita cambiar
de documento o página mientras ejecutas la consulta. D-Bus inaccesible, servicio
ausente o ambiguo, método inexistente y respuestas inválidas se notifican en
stderr con salida 1, sin traza. Un documento vacío se presenta como no disponible
y su página se omite. No se infiere que una página 0 válida sea un índice interno.

Ejecuta la prueba en la sesión gráfica de Okular: el sandbox de esta sesión
bloquea el bus y la prueba real requirió ejecución autorizada fuera de él.
No se captura texto, no se navega por el documento y no se modifica la
configuración personal. Las observaciones sobre ventanas y pestañas y sus
límites se registran en [STEPS.md](STEPS.md).

## Prueba aislada de selección X11 (Fase 0.5)

Con `xclip` instalado y desde la sesión gráfica X11, selecciona texto manualmente
en un PDF seguro de Okular y consulta sin copiar:

```bash
python -m audiobook_qc.selection_probe --selection primary
```

Para consultar por separado el portapapeles:

```bash
python -m audiobook_qc.selection_probe --selection clipboard
```

La utilidad usa `xclip -selection primary|clipboard -out -target UTF8_STRING`,
sin shell y con un timeout de tres segundos. Solo lee: no copia, no cambia
selecciones ni detecta la aplicación activa. No tiene dependencias Python nuevas
y no llama a mpv ni al adaptador D-Bus de Okular. No hace fallback automático
entre PRIMARY y CLIPBOARD.

La salida muestra selección consultada, texto disponible o vacío, número de
caracteres, texto entre delimitadores y su representación Python `repr()` para
observar espacios y saltos. Los delimitadores y saltos del informe son solo
presentación, no parte del texto recuperado. Se decodifica UTF-8 estrictamente y
**no se aplica normalización alguna**: se conservan CR/LF, espacios, Unicode,
guiones y todos los terminadores finales entregados por X11.

Una lectura correcta devuelve código 0, incluso si el texto está vacío. Una
selección inexistente o sin formato de texto compatible produce un
mensaje de no disponibilidad y código 2; el error de xclip no permite distinguir
por sí solo entre esas dos causas. Otros errores (xclip ausente, DISPLAY ausente
o vacío, servidor inaccesible, timeout, fallo de ejecución o UTF-8 inválido) se
notifican en stderr con código 1, sin traza. No se convierte un fallo en texto vacío.

Según el [código de xclip 0.13](https://github.com/astrand/xclip/blob/0.13/xclip.c),
la herramienta puede intentar `STRING` si falla `UTF8_STRING`, siempre dentro de
la selección solicitada. No es un cambio a CLIPBOARD. Por eso se reconocen los
dos mensajes de target no disponible. La utilidad exige bytes UTF-8 válidos y no
intenta adivinar codificaciones de propietarios antiguos.

PRIMARY y CLIPBOARD se consultan como selecciones distintas. La lectura no prueba
que el texto pertenezca al PDF deseado ni que una aplicación lo haya actualizado
al cambiar su selección visual. Los resultados experimentales con Okular se
registran en [STEPS.md](STEPS.md); no se presupone su comportamiento por tener
`xclip` disponible.

Con Okular 21.12.3 se verificó que seleccionar «Esta es una frase de prueba.»
sin Ctrl+C hizo que PRIMARY contuviera esa frase, mientras CLIPBOARD conservó el
texto copiado anteriormente. Tras Ctrl+C manual, CLIPBOARD recibió la frase.
Al seleccionar «Otro fragmento diferente.» sin copiar, PRIMARY cambió y
CLIPBOARD mantuvo la primera frase.

Seleccionar `SELECCION_DESDE_OTRA_APLICACION` en gedit sin copiar reemplazó PRIMARY
por ese marcador: es una selección global de X11, no una selección privada de
Okular. Un primer intento devolvió `'´'`; no se determinó su origen y la repetición
controlada recuperó el marcador completo. La selección multilínea del PDF devolvió
exactamente `'Una palabra parti-\nda entre dos lineas.'`, conservando guion y
salto de línea. Después de quitar el resaltado en Okular, PRIMARY siguió
devolviendo ese mismo texto: **una respuesta no vacía no demuestra selección
visual vigente**. Los estados X11 vacío y sin formato compatible se verifican
con tests unitarios; no se forzaron en la sesión real.

PRIMARY queda validado como candidato de lectura en este entorno, con esos
límites. El futuro registro deberá leerlo inmediatamente al pulsarse el atajo:
una selección en otra aplicación puede reemplazarlo entre la selección del PDF y
el registro, y también puede persistir texto antiguo. No se verifica todavía su
correspondencia con documento o página. El atajo y la coordinación quedan fuera
de esta prueba.

## Captura conjunta provisional (Fase 0)

Abre manualmente un audio con IPC y un único PDF relevante en Okular. Pausa mpv,
sitúate en la página del PDF y selecciona la frase sin Ctrl+C:

```bash
mpv --input-ipc-server=/tmp/audiobook-qc-mpv.sock /ruta/absoluta/audio.mp3
okular /ruta/absoluta/libro.pdf
```

Con el entorno virtual activado, ejecuta desde otro terminal:

```bash
python -m audiobook_qc.capture_probe INTER \
    --mpv-socket /tmp/audiobook-qc-mpv.sock \
    --okular-service org.kde.okular-12345
```

Obtén el nombre real del servicio con `python -m audiobook_qc.okular_probe
--list-services`. `--okular-service` es opcional si solo hay un servicio; con varios
es obligatorio elegir uno. El socket predeterminado es `/tmp/audiobook-qc-mpv.sock`.
No selecciones otro texto al preparar el comando: puedes dejarlo escrito antes
de seleccionar la frase. No se detecta foco ni ventana activa.

Los únicos códigos son `TEXT`, `PRON`, `DICC`, `RUID`, `RESP`, `INTER` y `OTRO`,
exactamente en mayúsculas y sin espacios añadidos. Se valida el código **antes
de consultar las fuentes**, tanto en la CLI como en el coordinador reutilizable.

`CapturedIncident` es una dataclass inmutable provisional con `incident_type`
(enum), `audio_filename`, `audio_path`, `audio_position_seconds` (float nativo),
`document` (identificador original), `page` (valor D-Bus) y `selected_text`.
La salida muestra esos datos, tiempo legible y texto exacto con `repr()`.
El objeto solo existe en memoria: no se guarda ni se exporta nada. No incluye
comentarios, descripciones ni reglas editoriales de composición.

El orden es **PRIMARY → Okular → mpv**. PRIMARY se lee primero para reducir la
ventana en la que otra selección puede sustituirlo. Documento y página se leen
a continuación, y al final el audio, que en el flujo previsto estará pausado.
No hay pausas artificiales, reintentos ni lecturas duplicadas añadidas por el
coordinador. Se reutilizan los adaptadores y sus tiempos límite existentes.

Un error esperado de una fuente o la ausencia de nombre/ruta de audio, posición,
documento, página o texto produce un error de captura sin traza y salida 1.
No se construye una captura incompleta ni se inventan valores. Se rechaza el
texto vacío (`''`), sin recortar espacios ni modificar saltos o Unicode. Posición
cero y página cero se conservan como valores presentes; no se añade `+1`, no se
recortan timestamps negativos ni se inventan reglas sobre ellos. La duración y
el estado de pausa no forman parte del objeto y no se exige `pause=true` como
regla nueva; pausar sigue siendo responsabilidad del usuario.

Las consultas son secuenciales, **no atómicas**. No se comprueba que PRIMARY
proceda de Okular ni que siga vigente; puede conservar texto antiguo o de otra
aplicación. Tampoco se demuestra su correspondencia con el PDF/página consultado.
Seleccionar un servicio no resuelve las ambigüedades de varias vistas: usa una
sola ventana/documento por servicio. No cambies las fuentes durante la captura.

`capture_probe` sigue siendo una prueba de integración de Fase 0 en memoria.
Para capturar y guardar en una sola ejecución usa `capture_save_probe`, descrito
abajo. El modo de escritorio se configura en GNOME; no hay GUI propia ni Excel.
La evidencia real de captura está en
[STEPS.md](STEPS.md).

## Persistencia de prueba (Fase 1)

`Incident.from_capture(capture, generic_description=None, custom_comment=None)`
convierte un `CapturedIncident` en una entidad nueva, sin guardar ni consultar
aplicaciones. Reutiliza el único enum `IncidentType` existente y conserva todos
los campos de captura. Añade `id` (None antes de insertar), `created_at`,
`updated_at`, descripción genérica, comentario personalizado y `exported=False`.
Descripción y comentario son columnas separadas, admiten None o texto vacío y
no se concatenan. `exported` es solo un booleano editable; no se exporta nada ni
se cambia automáticamente al editar otros campos.

Las entidades son copias inmutables validadas: edita con `dataclasses.replace()`
y guarda con `repository.update(edited)`. SQLite es la fuente de verdad; vuelve a
consultar el repositorio para obtener el estado guardado. No hay caché de sesión.

`SQLiteIncidentRepository(path)` permite `initialize()`, `add(incident)`,
`get(id)`, `list()`, `update(incident)` y `delete(id)`. Úsalo con `with` o llama a
`close()`. Cada escritura confirma su transacción o la revierte al fallar.
`add` devuelve la entidad con ID; `update` devuelve la nueva versión. `get`
devuelve None si no existe; actualizar/eliminar un ID inexistente lanza
`IncidentNotFoundError`. La lista se ordena por `created_at`, después por `id`.

El archivo SQLite puede crearse al abrir la conexión, pero **el esquema solo se
crea mediante `initialize()`**, nunca por un INSERT. Usa una base dedicada al
proyecto. El esquema es versión 1 mediante `PRAGMA user_version`; inicializar de
nuevo conserva los datos. Se rechazan versiones desconocidas y bases con tablas
sin versión reconocida. No hay migraciones todavía.

La tabla `incidents` usa ID entero autoincremental y constraints para códigos,
datos obligatorios no vacíos, posición finita, página entera no negativa y estado
0/1. La posición se almacena en `REAL` (binary64), sin redondeo ni conversión a
texto temporal, manteniendo el `float` capturado. Se conservan los valores nativos
cero/negativos según corresponda; no se cambia la base de página.

Las rutas de audio y el identificador del documento son `str` tanto en dominio
como en SQLite: se preservan rutas relativas y URLs. No se consulta su existencia.
`created_at` se genera al construir la entidad; `updated_at` empieza igual y el
repositorio lo actualiza al guardar una edición, manteniendo `created_at`.
Se rechazan datetimes naive y se normalizan los conscientes a UTC. SQLite guarda
ISO 8601 con microsegundos y offset `+00:00`, usando conversión explícita.

La CLI mínima admite `init`, `add` y `get`; las otras operaciones están disponibles
en el repositorio, sin convertir esta prueba en una interfaz de gestión:

```bash
python -m audiobook_qc.incident_probe --db /tmp/audiobook-qc-demo.sqlite3 init
python -m audiobook_qc.incident_probe --db /tmp/audiobook-qc-demo.sqlite3 add <<'JSON'
{"incident_type":"INTER","audio_filename":"capitulo.mp3","audio_path":"/prueba/audio.mp3","audio_position_seconds":1104.5171234567,"document":"file:///prueba/libro.pdf","page":127,"selected_text":"Una frase\nparti-\nda."}
JSON
# El comando anterior termina y cierra la conexión; este abre otra.
python -m audiobook_qc.incident_probe --db /tmp/audiobook-qc-demo.sqlite3 get 1
```

`add` lee exactamente los siete campos de captura JSON por stdin; opcionalmente
acepta `--generic-description` y `--custom-comment`. Usa el ID devuelto por `add`
si reutilizas una base existente. La prueba no requiere audio, PDF, mpv, Okular ni
X11 reales. La demostración de cierre y reapertura está en [STEPS.md](STEPS.md).

## Capturar y guardar desde CLI (integración mínima de Fases 0 y 1)

Inicializa explícitamente una base dedicada, una sola vez, y ejecuta el comando
de captura con el audio pausado y la frase seleccionada como en Fase 0:

```bash
python -m audiobook_qc.incident_probe --db /tmp/audiobook-qc-capturas.sqlite3 init
python -m audiobook_qc.capture_save_probe --db /tmp/audiobook-qc-capturas.sqlite3 INTER \
    --mpv-socket /tmp/audiobook-qc-mpv.sock \
    --okular-service org.kde.okular-12345
# Sustituye el ID por el devuelto por la captura; este comando abre otra conexión.
python -m audiobook_qc.incident_probe --db /tmp/audiobook-qc-capturas.sqlite3 get 1
```

`--db` es obligatorio, sin base global predeterminada. Las opciones de mpv y
Okular tienen el mismo significado y valores predeterminados que en
`capture_probe`. Se reutiliza la captura existente con el orden validar código
→ PRIMARY → Okular → mpv; siguen vigentes sus límites sobre procedencia del
texto, varias vistas y lecturas no atómicas. No selecciones otro texto al
preparar el comando.

El caso de uso `capture_and_save_incident(code, capture=..., repository=...)`
invoca la captura inyectada, construye `Incident.from_capture()` y llama a
`repository.add()`. Devuelve la entidad con el ID asignado por el repositorio.
No conoce SQLite ni las aplicaciones: el repositorio solo necesita el método
`add`, y la captura es una función sustituible. La CLI compone los adaptadores,
abre/cierra la conexión y muestra la entidad guardada como JSON con ID, datos
capturados, fechas UTC, `generic_description=null`, `custom_comment=null` y
`exported=false`. No se editan ni se concatenan descripción y comentario.

No hay inicialización automática: se mantiene el comando `init` de Fase 1 para
que crear el esquema sea una operación deliberada. Abrir una ruta inexistente
puede crear un archivo SQLite vacío; el guardado comprueba el esquema después
de capturar y falla si falta la versión 1 compatible, sin crear tablas. Ejecuta
`init` antes de capturar. El esquema permanece en versión 1, sin migraciones.

Los errores de captura, validación o SQLite se notifican en stderr con salida 1,
sin imprimir una entidad como guardada. Un fallo de captura no llama a `add`;
el caso de uso propaga los errores de construcción y persistencia. Una captura
fallida no deja una incidencia parcial y no se reintenta automáticamente.

Los tests verifican el flujo con fuentes en memoria y SQLite temporal real;
no manipulan ventanas. Esta integración añade solo captura y guardado por
ejecución manual. El modo de escritorio descrito a continuación añade activación
por atajos. Quedan fuera daemon, GUI propia, edición interactiva,
catálogo definitivo de descripciones, Excel, sincronización, concurrencia
avanzada, migraciones e instalador. No completa la Fase 2 de atajos.

La validación real del 29 de octubre de 2026 guardó y recuperó en otro proceso
la incidencia de la página 33 del PDF del usuario, con posición **19.300243 s**,
texto PRIMARY exacto e ID **1**. Se comprobó igualdad binaria del timestamp y
que tres fallos controlados (PRIMARY inaccesible, servicio Okular inexistente y
socket mpv inexistente) no añadían registros parciales. El texto conserva el
formato extraído del PDF, incluidos saltos, guiones y espacios; la ruta del
audio se conserva relativa porque así la comunicó mpv. Los comandos, resultados
y límites están en [STEPS.md](STEPS.md#validación-real-de-captura-y-persistencia-29-de-octubre-de-2026).

## Activación mediante atajos de GNOME (Fase 2)

Se utilizan los **atajos personalizados del escritorio**, que ejecutan un
proceso breve por pulsación. No hay listener Python, daemon ni biblioteca nueva.
GNOME detecta la combinación; el código se configura en el comando; la CLI
exige modo activo y foco autorizado, compone los adaptadores y reutiliza
`capture_and_save_incident`. La comunicación
usa `notify-send` (libnotify), disponible en el entorno comprobado. El dominio
desconoce tanto las teclas como las notificaciones y el bloqueo.

Esta opción usa el mecanismo nativo ya disponible. Un listener residente de
X11 exigiría gestionar eventos, conflictos y ciclo de vida; herramientas como
xbindkeys/sxhkd añadirían otro proceso y configuración. No son necesarias para
el alcance actual. Referencias: [atajos personalizados de GNOME](https://help.gnome.org/gnome-help/keyboard-shortcuts-set)
y [notificaciones del escritorio](https://specifications.freedesktop.org/notification/latest/).

### Preparación y configuración

1. Usa una base dedicada en un directorio escribible e inicialízala explícitamente
   con `python -m audiobook_qc.incident_probe --db /RUTA/BASE/incidencias.sqlite3 init`.
   Ni el atajo ni `--desktop` crean el esquema.
2. Abre mpv con `--input-ipc-server=/RUTA/mpv.sock` y audio con ruta absoluta.
   Abre el PDF en Okular; obtén su servicio con `okular_probe --list-services`.
   El servicio puede cambiar al reiniciar Okular. Con un solo servicio se puede
   omitir la opción; con varios debe indicarse. Una ventana/documento por servicio.
3. En Ubuntu/GNOME: **Configuración → Teclado → Ver y personalizar atajos →
   Atajos personalizados → +** (los rótulos pueden variar). Añade nombre,
   comando y combinación. No reemplaces los atajos existentes de otras tareas.
4. En el campo Comando, pega lo siguiente en **una sola línea**, sustituyendo
   las rutas absolutas y el servicio por los tuyos:

```text
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --db "/RUTA/BASE/incidencias.sqlite3" --mpv-socket "/RUTA/mpv.sock" --okular-service org.kde.okular-12345 INTER
```

No uses `~`, variables de shell, `source`, redirecciones ni `gnome-terminal` en
ese campo. El intérprete es absoluto y el paquete debe estar instalado en ese
entorno (`pip install -e '.[dev]'` durante desarrollo). `--desktop` exige rutas
absolutas de base y socket para evitar depender del directorio de trabajo de
GNOME. `xclip`, `busctl` y `notify-send` deben estar en el PATH de la sesión.

La correspondencia inicial **aceptada y probada por el usuario**, tras
informarle de los conflictos, es la siguiente. Se edita exclusivamente en GNOME:

| Tecla propuesta | Código en el comando |
| --- | --- |
| F1 | TEXT |
| F2 | PRON |
| F3 | DICC |
| F4 | RUID |
| F5 | RESP |
| F6 | INTER |
| F7 | OTRO |

Crea una entrada por código cambiando el último argumento. El campo Combinación
es independiente del campo Comando: se puede cambiar F6 por Shift+F6 sin cambiar
el código INTER ni editar Python. También se puede asignar cualquier combinación
libre al código que se necesite. No hay un mapa de teclas fijo en el código.

**Conflictos detectados:** en los grupos de atajos de GNOME consultados no había
F1–F7 ni Shift+F1–F7; el atajo personalizado existente era Ctrl+Alt+T. No se
encontraron F1–F7 en los bindings predeterminados de mpv 0.34.1 ni en los scripts
personales revisados; no había `input.conf` personal. Esto no garantiza ausencia
de bindings dinámicos ni de extensiones de GNOME. Okular sí utiliza F1 (ayuda),
F3 (siguiente búsqueda), F5 (recargar), F6 (anotaciones) y F7 (panel lateral).
Shift+F1 (ayuda contextual) y Shift+F3 (búsqueda anterior) también tienen uso.
Sus overrides locales consultados no anulaban estas teclas. Fuentes:
[Okular 21.12.3](https://raw.githubusercontent.com/KDE/okular/v21.12.3/part/part.cpp),
[anotaciones de Okular](https://docs.kde.org/stable_kf6/en/okular/okular/annotations.html),
[atajos estándar KDE](https://api-staging.kde.org/kstandardshortcut.html) y
[bindings mpv 0.34.1](https://github.com/mpv-player/mpv/blob/v0.34.1/etc/input.conf).

F1–F7 se comprobaron con foco en Okular y F6 también con foco en mpv: el usuario
confirmó los avisos correctos, sin funciones locales ni cambio de foco. Mientras
estén activos, los atajos globales desplazan esas funciones de las aplicaciones.
F1–F7 afectan a todas las aplicaciones de la sesión y facilitan pulsaciones
accidentales. El usuario ha aceptado ese compromiso. Shift+F1–F7 es una alternativa
editable, pero tampoco está libre de todos los conflictos y no se ha probado.

### Uso y prueba manual

Activa explícitamente el modo con `python -m audiobook_qc.correction_mode on --notify`.
Con mpv pausado manualmente, selecciona la frase en Okular sin Ctrl+C y pulsa
el atajo **una vez**, manteniendo el foco en Okular. El texto sigue siendo
obligatorio según las reglas ya existentes. No se introduce captura sin texto.
No hay diálogo modal ni navegación automática. Tras guardar aparece
`Incidencia guardada` con código e ID. Los fallos muestran `Incidencia no guardada`
con su causa. Verifica que GNOME permita las notificaciones de audiobook-qc y
que el modo No molestar no oculte la confirmación; el servidor decide su aspecto.

Para validar, usa primero una base temporal y registra el recuento inicial.
Comprueba el código/ID del aviso y recupera la incidencia en otro proceso con
`incident_probe --db RUTA get ID`. Contrasta archivo, posición decimal exacta,
documento, página y texto, sin normalizarlos. Repite cambiando código/contexto y
comprueba que cada pulsación completada produce exactamente una alta. Verifica
con foco en Okular y en mpv que no se abre ayuda ni se ejecutan sus funciones
locales. Prueba también mantener la tecla: la repetición de GNOME no se presupone
desactivada. Para fallos, configura temporalmente un socket inexistente: debe
aparecer el error y conservarse el recuento. Restaura el comando al terminar.

El modo `--desktop` crea `BASE.sqlite3.capture.lock` al lado de la base y usa
`flock` no bloqueante durante captura y guardado. Una activación solapada de
cualquier código para la misma base se **omite**, sin cola ni lectura tardía,
con aviso `Activación omitida`. El archivo queda, pero el bloqueo se libera al
terminar o morir el proceso; no lo borres mientras haya capturas. Este mecanismo
solo coordina procesos con `--desktop`; no coordina la CLI sin esa opción ni
otros escritores. Requiere un sistema de archivos local con soporte de flock.

Una activación posterior a la finalización crea una incidencia nueva, aunque
el contexto sea idéntico. No hay cooldown, deduplicación editorial ni garantía
contra repetición del teclado: no mantener la tecla ni repetir por ausencia de
aviso sin consultar la base. Si `notify-send` falla **después** de guardar, se
mantienen el éxito (salida 0) y el JSON con ID; stderr indica que quedó guardada
pero falló el aviso. No se reintenta el INSERT. Sin servicio de notificaciones,
el stderr puede quedar solo en el registro de la sesión: validar los avisos antes
del uso continuo. La selección PRIMARY sigue siendo global y puede estar obsoleta.

### Personalización y desactivación

En Atajos personalizados, edita la combinación sin tocar el comando para
conservar el código; edita el argumento final para cambiar el código asociado.
Para desactivar una entrada, borra su combinación (Retroceso en el diálogo de
asignación); para eliminarla, usa Quitar. Repite para las siete entradas si
quieres recuperar todas las teclas. No hay servicio que detener ni base que borrar.
El cambio de atajos no cancela una captura ya iniciada. `correction_mode off`
impide registros y vacía las combinaciones propias; conserva las entradas y
comandos para restaurarlas con `on`. Véase la gestión dinámica al final.

**Verificación automática:** 285 tests superados (23 nuevos) y Ruff correcto.
Se prueban los siete códigos, reutilización del caso de uso, datos y precisión,
fallos de captura/SQLite, notificación tras commit, error de notificación tras
éxito, esquema explícito, rutas absolutas, activaciones consecutivas y exclusión
entre procesos, sin pulsaciones ni escritorio. El envío de un aviso de prueba
real terminó correctamente. Se han registrado y releído las siete entradas
F1–F7 en GNOME, conservando Ctrl+Alt+T, con comandos
explícitos hacia la base temporal `/tmp/audiobook-qc-hotkeys-gzl2v_os/incidencias.sqlite3`,
socket `/tmp/audiobook-qc-real-mjz7z4xb/mpv.sock` y servicio
`org.kde.okular-406490`. El plan y la copia de la lista de atajos anterior están
en ese directorio temporal. No convertir estas rutas de prueba en configuración
permanente: desaparecen con la limpieza de `/tmp`.

**Validación real completada el 29 de octubre de 2026:** el usuario pulsó F1–F7
con foco en Okular y F6 tres veces más al continuar la prueba con mpv. Confirmó
avisos `Incidencia guardada` con código e ID incremental, sin acciones locales
ni cambio de foco. Se recuperaron en procesos independientes las diez incidencias
(ID 1–7 en el orden de la tabla, ID 8–10 INTER), conservando todos los datos de
captura, posición 19.300243 y su binary64 exacto. No hubo duplicados en estas
pulsaciones separadas; mantener una tecla no se ha probado. Un intento de CLI
real con `--desktop` y socket inexistente devolvió error, envió la notificación
sin error de transporte y mantuvo la base con diez registros; la visibilidad
del aviso de error no fue confirmada por el usuario. Fase 2 completada para
activación manual por atajos, con las limitaciones anteriores.

## Protección frente a activaciones involuntarias

Los comandos `--desktop` exigen **modo de corrección activo y foco en Okular o
en una ventana gráfica de mpv**. Con modo inactivo, otra aplicación, identidad
ambigua, datos ausentes o error de consulta, la activación se rechaza antes de
leer PRIMARY, abrir SQLite o crear su archivo de bloqueo. La CLI manual sin
`--desktop` conserva su comportamiento explícito de prueba.

Sin indicador runtime, el modo empieza **inactivo**. Los comandos comprueban
también la sincronización con GNOME y usan la copia persistente descrita abajo.
Se controla desde el entorno virtual del proyecto:

```bash
python -m audiobook_qc.correction_mode status
python -m audiobook_qc.correction_mode on --notify
python -m audiobook_qc.correction_mode off --notify
```

Para controlarlo sin terminal puedes crear atajos personalizados adicionales
con el intérprete absoluto, `-m audiobook_qc.correction_mode` y `on --notify`,
`off --notify` o `status --notify`. Escoge combinaciones libres; no se han
asignado nuevas teclas de control ni cambiado otras preferencias personales.

El estado es un pequeño archivo atómico bajo
`$XDG_RUNTIME_DIR/audiobook-qc/correction-<identificador-del-display>.active`.
Es compartido entre procesos del mismo usuario/display y no pertenece a la base
de incidencias. Se mantiene hasta `off` o la limpieza del directorio runtime;
no se promete reiniciarlo en cada reapertura de una aplicación ni en un logout
si el runtime del usuario sigue existiendo. Un estado ilegible o corrupto
rechaza activaciones, sin suponer que está activo. `off` elimina el estado y
permite recuperarse de un contenido corrupto. El modo no cancela capturas que
ya habían superado la comprobación.

El adaptador consulta `_NET_ACTIVE_WINDOW` mediante `xprop`, después WM_CLASS y
`_NET_WM_PID`, y contrasta el ejecutable real en `/proc/PID/exe`. Solo admite
las identidades verificadas `okular/okular/okular`, `gl/mpv/mpv` y
`mpv/mpv/mpv` (instancia/clase/binario). No busca aplicaciones abiertas ni usa
el título, por lo que un terminal que ejecuta mpv sigue siendo una terminal y
se rechaza. Vuelve a leer la ventana activa y rechaza cambios durante la
identificación. Requiere `xprop`, DISPLAY y sesión declarada X11; no se añade
una dependencia Python ni soporte Wayland. La lectura de foco y captura sigue
sin ser atómica: no cambiar de ventana durante el registro. WM_CLASS/PID son
datos de clientes X11; el filtro previene errores de uso, no constituye una
frontera de seguridad frente a clientes maliciosos. Referencia:
[ventana activa en EWMH](https://specifications.freedesktop.org/wm/latest/ar01s03.html).

No se guardan PID ni ID de ventana. Al reabrir Okular o mpv se consultan sus
nuevas identidades. En nuestros siete comandos se retiró únicamente el
`--okular-service` fijado al PID anterior: el adaptador existente descubre el
único servicio. Si hay varios, se rechaza la ambigüedad y hay que elegir el
servicio explícitamente, actualizándolo si cambia. mpv debe abrirse siempre con
el mismo socket IPC configurado; si no hay ventana gráfica o socket disponible,
el intento se rechaza o falla sin guardar.

**Con modo activo las teclas siguen siendo globales**: un rechazo por foco no
las reenvía a Firefox, LibreOffice ni otras aplicaciones. Con modo inactivo,
la gestión dinámica descrita abajo vacía `binding` y libera efectivamente las
teclas. No se habilitan/deshabilitan automáticamente al cambiar de aplicación.

Validación del 29 de octubre de 2026:

1. Modo inicialmente inactivo: F6 en Okular y en otra aplicación fue rechazado;
   el usuario confirmó ambos avisos y la base permaneció en 11 registros.
2. Activación explícita: F6 en Okular y en mpv gráfico guardó ID 12 y 13;
   F6 en terminal y navegador/LibreOffice fue rechazado según confirmó el usuario.
   Se recuperaron las dos altas en otros procesos, con los datos intactos, y el
   recuento quedó en 13.
3. Desactivación explícita: F6 en Okular volvió a rechazarse, confirmado por el
   usuario; se dejó el modo inactivo como estado final.

**338 tests superados** (53 nuevos), Ruff lint y formato correctos. Los tests
de foco y modo no usan escritorio real: cubren identidades autorizadas y ajenas,
ausencias, cambios de foco, PID no verificable, reinicio de aplicación, errores,
modo inicial/activo/inactivo/corrupto, persistencia entre procesos, separación de
display, orden del filtro y ausencia de captura/apertura de SQLite/bloqueo en
rechazos. Dominio, repositorio, caso de uso y adaptadores de captura sin cambios.

## Gestión dinámica de las combinaciones de GNOME

Los mismos comandos `correction_mode on|off|status` gestionan ahora el modo y
los bindings. No hay daemon ni cambio en incidencias, SQLite o captura.

- **off:** desactiva primero el indicador de captura, guarda las combinaciones
  y vacía solo `binding` de las entradas propias. Repite la operación sin perder
  la copia. Intenta liberar todas las entradas aunque alguna falle y comunica
  cualquier fallo parcial, sin anunciar una sincronización satisfactoria.
- **on:** mantiene el modo inactivo durante la restauración y verificación.
  No lo declara activo hasta confirmar las combinaciones necesarias. Ante un
  fallo intenta dejarlas liberadas y comunica si la recuperación fue parcial.
- **status:** informa del modo y de si los atajos están sincronizados. Devuelve
  salida 1 si detecta discrepancias o errores, sin modificar los bindings.

El descubrimiento lee `custom-keybindings` y reconoce el comando directo
`python[versión] -m audiobook_qc.capture_save_probe ... --desktop ...`. No usa
índices fijos, nombres visibles ni la combinación F1–F7 como identificación.
Los comandos con wrappers/shell no se gestionan: usa el comando directo mostrado
en configuración. Solo se escribe la propiedad `binding`; ni la lista de
entradas, ni los nombres ni los comandos se modifican. Se vuelve a leer cada
entrada antes de escribir y después para detectar cambios concurrentes.

La copia versionada vive en
`$XDG_STATE_HOME/audiobook-qc/gnome-bindings.json` o, por defecto,
`~/.local/state/audiobook-qc/gnome-bindings.json`. No está bajo `/tmp` ni en
SQLite. Se guarda atómicamente antes de suspender cada combinación, con fsync,
y se conserva después de restaurar. Un bloqueo entre comandos evita que on/off
solapados se pisen. No borres la copia mientras las combinaciones estén vacías.

### Personalización sin perder cambios

Cambia las teclas en los Atajos personalizados de GNOME: no hay un mapa fijo
en Python. Una nueva combinación no vacía tiene prioridad sobre la copia
anterior. Si la asignas mientras el modo está inactivo, GNOME la reserva de
inmediato; ejecuta `off` para guardarla y liberarla, y `on` para usarla después.
Una combinación borrada manualmente mientras estaba habilitada no se restaura.
Para deshabilitar permanentemente una entrada, bórrala mientras el modo esté
activo y luego ejecuta `off`, o elimina esa entrada desde GNOME.

Hay un límite observable: borrar otra vez una combinación que el programa ya
dejó vacía no cambia GSettings y no permite distinguir una nueva intención
manual de la suspensión temporal. Usa el procedimiento anterior para ese caso.
Si cambias el comando de una entrada suspendida, no se restaura su combinación
antigua sin más: asigna explícitamente la combinación al nuevo comando en GNOME.
Si una entrada desaparece o pasa a ejecutar otra aplicación, no se recrea ni se
escribe. También se rechazan duplicados propios y conflictos exactos con otras
entradas personalizadas. No edites las entradas mientras se ejecuta on/off:
GSettings no proporciona compare-and-swap frente al editor externo; las
relecturas reducen la carrera pero no crean una transacción global.

### Recuperación y arranque

GSettings es persistente y no ofrece una transacción que incluya nuestro archivo
de modo. Una interrupción puede dejar combinaciones parcialmente reservadas,
aunque la captura ya esté desactivada. `status` detecta ese desacuerdo y `off`
vuelve a intentar liberar las entradas. La copia persistente conserva las
combinaciones incluso si se limpia el runtime o se reinicia el equipo.

Tras reiniciar normalmente falta el indicador runtime y la captura empieza
inactiva, pero GNOME puede conservar los bindings que tenía al interrumpirse.
Ejecuta `off` al entrar para sincronizar. Si quieres automatizarlo sin daemon,
añade a **Aplicaciones al inicio** el comando absoluto
`/RUTA/PROYECTO/.venv/bin/python -m audiobook_qc.correction_mode off`.
No se ha instalado una entrada de autoinicio ni se afirma haber probado un
logout o reinicio real. Si el runtime persiste tras cerrar sesión, también puede
persistir el indicador: `off` explícito al entrar sigue siendo la recuperación
recomendada. Cerrar aplicaciones no cambia el modo.

Si falla GSettings, corrige el acceso a la sesión y repite `off`. Si se pierde
o corrompe la copia, no se inventan combinaciones: una copia corrupta no se
sobrescribe, `off` prioriza liberar teclas y comunica valores observados para
recuperación manual. Conserva el archivo dañado, restaura una copia válida o
renómbralo y vuelve a asignar las combinaciones en GNOME antes de ejecutar
`off` y `on`. Con disco no escribible tampoco puede garantizarse guardar una
copia nueva; el error indica qué valores requieren anotarse manualmente.
Como último recurso, deshabilita las combinaciones propias en GNOME. No uses
`gsettings reset-recursively` ni reemplaces toda la lista de atajos.

Las lecturas confirmadas de GSettings no demuestran por sí solas la captura de
las teclas por GNOME. En esta versión (GNOME Shell **42.9**, Ubuntu 22.04/X11)
se verificó con el usuario que `binding=''` devuelve F1 a la ayuda de Okular sin
ejecutar audiobook-qc; al suspender las siete combinaciones también confirmó
las funciones locales de F6/F7. La configuración ajena se compara íntegramente
antes/después. Las pruebas unitarias de la gestión nunca ejecutan GSettings
real: usan un backend en memoria y archivos temporales.

Validación completa: tras reabrir mpv con su socket IPC, F1–F7 en Okular y F6
en mpv generaron ocho avisos y ocho registros (ID 14–21), recuperados en procesos
independientes. Esta ronda seleccionó una frase de la página 20 y posición
19.3 s, conservadas exactamente. Se verificaron on/off repetidos y la igualdad
de nombres, comandos, lista de entradas y todas las propiedades ajenas antes y
después. Estado final: **modo inactivo, atajos sincronizados y siete bindings
vacíos**, con su copia persistente guardada. Evidencias temporales en
`/tmp/audiobook-qc-dynamic-psdmalgy`.

**376 tests superados** (38 nuevos), Ruff lint y formato correctos. Incluyen
fallos parciales y recuperación simulada de interrupciones/reinicio, sin tocar
el escritorio real desde los tests. No se ha probado un reinicio/logout real.
No se han hecho commits.
