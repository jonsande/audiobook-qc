# Roadmap

Estado actual: Fase 0 técnicamente completada con las limitaciones documentadas.
Fase 1 completada y verificada con SQLite real tras cerrar/reabrir conexiones
y procesos. Integración mínima de captura y guardado validada mediante CLI con
mpv, Okular y PRIMARY reales; la Fase 2 de atajos sigue pendiente.

## Fase 0: fundación y pruebas de integración con el entorno

**Estado:** técnicamente completada por decisión del usuario el 28 de octubre de
2026, aceptando las limitaciones experimentales siguientes. Los atajos se abordan
en la Fase 2; no se da por realizada ninguna prueba de atajos globales.

**Objetivo:** establecer la base Python y comprobar experimentalmente la
interacción con el entorno Linux, mpv, Okular y la selección de texto. Documentar
los mecanismos disponibles y sus límites antes de diseñar la captura real.

**Criterio de salida:** paquete instalable y comprobaciones de pytest y Ruff
correctas; pruebas de integración reproducibles documentadas para obtener archivo
y timestamp de mpv, PDF y página de Okular, y texto seleccionado. Registrar entorno,
resultados y limitaciones. Las comprobaciones verificadas se registran abajo;
la coordinación actual es una prueba manual sin persistencia ni atajos.

### Comprobaciones realizadas

- [x] Fundación: paquete instalable, pytest y Ruff configurados.
- [x] Fase 0.2: diagnóstico informativo con biblioteca estándar, ejecutable como
  `python -m audiobook_qc.diagnostics`, con tests independientes del entorno.
- [x] Fase 0.3: consulta aislada de mpv mediante JSON IPC, verificada con mpv real.
- [x] Fase 0.4: comunicación real con Okular y consulta aislada de documento/página.
- [x] Fase 0.5: lectura de PRIMARY/CLIPBOARD verificada con Okular y gedit (A–E).
- [x] Captura conjunta provisional: objeto en memoria y CLI, verificados con las
  tres fuentes reales; códigos estrictos y validación de datos imprescindibles.

Las pruebas de mecanismos de atajos quedan pendientes de la Fase 2.

Diagnóstico ejecutado el 28 de octubre de 2026: Ubuntu 22.04.5 LTS, kernel
6.8.0-138-generic, x86_64, Python 3.10.12; sesión declarada X11, escritorio
`ubuntu:GNOME`, `DISPLAY=:0` y `WAYLAND_DISPLAY` no definida. Versiones consultadas:
mpv 0.34.1 y Okular 21.12.3. Se localizaron `dbus-send`, `dbus-monitor`, `gdbus`,
`busctl`, `qdbus` y `xclip`. No se encontraron `xsel`, `wl-paste` ni las variantes
de qdbus/rutas Qt adicionales comprobadas; esto no descarta otras ubicaciones.

Limitación observada: dentro del sandbox, `okular --version` terminó con código
-6 y error Qt/xcb al acceder a `DISPLAY=:0`; fuera del sandbox, con ejecución
autorizada, devolvió su versión correctamente. No se modificó el sistema.
La presencia de ejecutables y variables no valida acceso al bus, APIs, selección
ni atajos. Queda por verificar experimentalmente desde la sesión de trabajo si
`qdbus` es operativo, cómo expone Okular sus datos y cómo se obtiene la selección
deseada en X11. No se han consultado esas interfaces ni leído texto seleccionado.

### Fase 0.3: evidencia de la prueba real con mpv

Verificada el 28 de octubre de 2026 con mpv 0.34.1 y el audio del sistema
`/usr/share/sounds/speech-dispatcher/dummy-message.wav`, sin modificarlo. Se
iniciaron desde el terminal dos instancias temporales, con sockets distintos bajo
un directorio privado de `/tmp`, `--no-config --no-terminal --no-video
--audio-display=no --ao=null`; una reproduciendo y otra iniciada con `--pause`.
La utilidad Python no inició ni controló mpv: solo consultó propiedades.

- Se verificaron `filename`, `path`, `time-pos`, `duration` y `pause` por JSON IPC,
  así como la CLI `python -m audiobook_qc.mpv_probe --socket ...`.
- Duración recibida: 29.435 s. En reproducción, dos lecturas separadas por 0.5 s
  pasaron de 0.368355 a 0.869852 s, con `pause=false`.
- En la instancia iniciada en pausa, las lecturas fueron 0.0 y 0.0 s, con
  `pause=true`. No se probó una transición de reproducción a pausa ni una pausa
  manual en una posición intermedia.
- El sandbox impidió enlazar los sockets (`Could not bind IPC socket`); la
  comunicación se demostró en ejecución autorizada fuera del sandbox. Las
  instancias de prueba finalizaron al terminar, sin cambiar la configuración.
- En un ensayo previo con `test.wav` (0.5426875 s), bucle y salida nula, mpv
  devolvió 0.029895 y -0.311595 s. Se conserva el valor nativo, sin recortarlo ni
  ocultarlo. No se ha determinado la causa del valor negativo.

Los tests automáticos no ejecutan mpv: cubren formato temporal, precisión,
fragmentación/agrupación de mensajes, eventos, `request_id`, propiedades no
disponibles, errores de mpv, protocolo, transporte y CLI.

Límites pendientes: verificar con el audiolibro y salida de audio reales la
correspondencia entre `time-pos` y lo escuchado, y la estabilidad tras pausar
manualmente en una posición intermedia. La salida nula valida el IPC, no la
latencia del dispositivo de audio. Las cinco propiedades se leen de forma
secuencial y no constituyen una instantánea atómica. Se conserva `path` tal como
lo entrega mpv, sin resolver rutas relativas desde el proceso Python.

### Fase 0.4: evidencia de la prueba real con Okular

Prueba el 28 de octubre de 2026 con Okular 21.12.3 en la sesión X11/GNOME.
Se introspeccionó primero el servicio existente `org.kde.okular-7333`, sin cambiar
su documento ni página. Se encontraron `/okular` y `/okularshell`.
En `/okular`, la interfaz `org.kde.okular` expone métodos de consulta sin
argumentos: `currentDocument() → s`, `currentPage() → u` y `pages() → u`.
`/okularshell` expone operaciones de apertura, no estas consultas. No se emplean
métodos de navegación ni de apertura en la integración.

`qdbus` falló con «could not find a Qt installation of ''»; su presencia en PATH
no garantiza que sea operativo. `gdbus` permitió introspeccionar la API y `busctl`
devolvió JSON tipado (`s`, `u`, `as`), por lo que se eligió para el adaptador.
El sandbox bloqueó el acceso al bus (`Operation not permitted`); la investigación
y la prueba real se ejecutaron con autorización fuera de él.

Se crearon PDFs temporales de tres páginas en `/tmp/audiobook-qc-okular.Wtdaib`,
sin explorar documentos personales. Los Okular de prueba usaron
`XDG_CONFIG_HOME`, `XDG_DATA_HOME` y `XDG_CACHE_HOME` bajo ese directorio para
preservar la configuración personal. El programa Python no lanzó Okular.

- Ventana A: servicio `org.kde.okular-338126`; `currentDocument()` devolvió
  `/tmp/audiobook-qc-okular.Wtdaib/prueba-A.pdf`, una ruta absoluta sin `file://`.
- Primera página: el usuario confirmó visualmente que Okular mostraba **1** y el
  texto del PDF decía «TEST A - PDF PAGE 1 - PRINTED 101»; D-Bus devolvió **1**.
  En la tercera página, el usuario confirmó **3** y el texto «TEST A - PDF PAGE 3
  - PRINTED 103»; D-Bus devolvió **3**. No se aplica ninguna suma `+1`.
- Ventana independiente C, abierta con `okular --page 2 .../prueba-C.pdf`:
  nuevo servicio `org.kde.okular-338707`, documento C y página **2**.
  El servicio de A siguió registrado, al igual que el Okular original.
- Se comprobó la CLI real con `--list-services`, `--service` y sin selección:
  al haber varios servicios, la última opción devolvió un error legible sin
  escoger arbitrariamente el primero. Se observaron nombres con el PID del
  proceso (`org.kde.okular-<PID>`); no son identificadores permanentes.

La numeración observada en el PDF de prueba empieza en 1. No se consulta el
índice interno del visor ni la numeración impresa; no se resuelven desfases ni
etiquetas de página del PDF. La ruta/URL original se conserva; solo rutas
absolutas y URLs `file:` locales inequívocas se convierten a `Path` sin leerlas.
La normalización de URLs remotas o `file:` se cubre con tests, no con documentos
remotos reales.

Al abrir B manualmente desde Archivo → Abrir de A, el usuario indicó que se abrió
como otra ventana, no como pestaña. La lista de servicios no añadió otra entrada
y `/okular` de A siguió devolviendo A, página 3. La introspección de raíz y
`/okular` no mostró otro objeto de consulta para B. No se ha determinado aún
inequívocamente cómo se asigna esa ventana a un proceso/objeto. No se puede
tratar la lista de servicios como un listado fiable de ventanas, ni garantizar
que `/okular` siga la vista activa. El cambio entre pestañas no se verificó:
la configuración usada abrió ventanas y no se cambiaron preferencias para
habilitar pestañas.

El usuario confirmó después que había cuatro ventanas abiertas: A, B, C y la
de su trabajo previo. B mostraba «TEST B - PDF PAGE 1 - PRINTED 101». En ese
estado se habían enumerado solo tres servicios: `org.kde.okular-338126`,
`org.kde.okular-338707` y `org.kde.okular-7333`. Por tanto, en esta prueba no hubo
correspondencia uno a uno entre ventanas y servicios. No se consultó el documento
del trabajo previo para intentar asignar B a otro objeto.

Para uso de esta prueba se requiere **una sola ventana/documento por servicio** y
una elección explícita si hay varios Okular relevantes. La CLI muestra esta
restricción; no detecta la ventana activa. La selección automática con un solo
servicio está cubierta por tests; la sesión real ya tenía otro Okular abierto y
no se cerró.

Los tests unitarios no necesitan Okular ni bus de sesión. Cubren JSON tipado,
selección cero/uno/varios servicios, firmas XML, documento vacío, página nativa,
normalización de identificadores, fallos de comandos/D-Bus y presentación CLI.
Documento y página se leen consecutivamente, no de forma atómica: no cambiar de
documento o página durante la consulta. Un error D-Bus de un método se notifica,
sin inventar un documento o una página alternativos.

### Fase 0.5: prueba aislada de selección X11

Utilidad `python -m audiobook_qc.selection_probe --selection primary|clipboard`,
independiente de mpv y del adaptador D-Bus de Okular. Solo ejecuta
`xclip -selection primary|clipboard -out -target UTF8_STRING` con un timeout de
tres segundos y sin shell. No escribe en las selecciones, no simula teclas y no
identifica al propietario. Se usa `LC_ALL=C` solo en el subproceso para que los
mensajes de error sean interpretables; no se cambia la configuración del sistema.

Se decodifica UTF-8 estrictamente y no se normaliza el texto: se conservan todos
los saltos y terminadores finales, espacios, guiones, puntuación y Unicode. La CLI
incluye `repr()` para hacer visibles esos caracteres. Una salida correcta vacía
es distinta de un fallo: no se convierte un error en cadena vacía. La ausencia
del target de texto se informa como selección inexistente **o** sin formato
compatible; ese mensaje de xclip no basta para diferenciar las dos causas.

Se revisó el [código de xclip 0.13](https://github.com/astrand/xclip/blob/0.13/xclip.c):
puede intentar `STRING` si falla `UTF8_STRING` dentro de la misma selección.
Se reconocen los dos diagnósticos de formato ausente; los bytes se decodifican
estrictamente como UTF-8, sin adivinar otra codificación. Esto no implica ningún
fallback entre PRIMARY y CLIPBOARD.

Pruebas el 28 de octubre de 2026, con Okular 21.12.3, X11/GNOME y xclip 0.13.
Se creó `/tmp/audiobook-qc-selection-p9tye4tl/seleccion.pdf` con frases conocidas
y un texto de prueba para otra aplicación. Okular se abrió desde el terminal,
usando configuración, datos y caché temporales separados para preservar las
preferencias personales. El usuario realizó las selecciones y el Ctrl+C de
forma manual. La utilidad Python no abrió aplicaciones ni envió teclas.

Resultados exactos (las comillas representan el texto, no forman parte de él):

| Prueba | Acción manual | PRIMARY | CLIPBOARD |
| --- | --- | --- | --- |
| A/B | Seleccionar primera frase sin Ctrl+C | `'Esta es una frase de prueba.'` (28 caracteres) | `'Es una aplicación Linux para agilizar mi trabajo'` (48 caracteres) |
| C | Ctrl+C de la primera frase en Okular | No consultado en este paso | `'Esta es una frase de prueba.'` (28 caracteres) |
| D | Seleccionar segunda frase sin Ctrl+C | `'Otro fragmento diferente.'` (25 caracteres) | `'Esta es una frase de prueba.'` (28 caracteres) |
| E, repetición | Seleccionar marcador en gedit, sin copiar | `'SELECCION_DESDE_OTRA_APLICACION'` (31 caracteres) | No consultado en la repetición |
| F | Seleccionar dos líneas con guion en Okular, sin copiar | `'Una palabra parti-\nda entre dos lineas.'` (39 caracteres) | No consultado en este paso |
| G | Quitar el resaltado de Okular con clic en blanco | `'Una palabra parti-\nda entre dos lineas.'` (39 caracteres) | No consultado en este paso |

El usuario aclaró que antes de A/B había copiado «Es una aplicación Linux para
agilizar mi trabajo» en lugar del marcador propuesto `CLIPBOARD_PREVIO_QC`.
Por tanto, B conservó el contenido previo confirmado por el usuario. En D se
comparó también con la lectura de C: CLIPBOARD mantuvo la frase copiada aunque
PRIMARY cambió a la segunda. PRIMARY se actualizó sin Ctrl+C en la primera
consulta posterior a la selección manual; no se midió la latencia en milisegundos.

Primer intento de E: el usuario indicó que seleccionó el marcador en gedit, pero
PRIMARY devolvió `'´'` (1 carácter), no el marcador esperado. CLIPBOARD mantuvo
`'Esta es una frase de prueba.'`. No se ha identificado el origen de ese carácter
ni se atribuye a gedit. Al repetir la selección en gedit y responder únicamente
`E` escrito a mano, PRIMARY devolvió el marcador completo esperado. La causa
del resultado anterior no está determinada; no se garantiza la procedencia
de un texto solo por poder leerlo. La repetición demuestra que una selección en
gedit reemplaza PRIMARY y que no está ligado permanentemente a Okular.

El sandbox impidió acceder a X11 (`Can't open display: :0`). Las lecturas reales
se realizaron con autorización fuera del sandbox, sin cambiar DISPLAY ni permisos.

Las pruebas A–E quedaron verificadas en aplicaciones reales. En F, el guion y
el salto interno del PDF se conservaron y no apareció un salto final. En G,
el usuario confirmó que quitó el resaltado; PRIMARY siguió conteniendo el texto
de F. Por tanto, **sin selección visual no implica PRIMARY vacío o inexistente**.
No se forzó un propietario vacío ni se eliminó el propietario X11: esos estados
se cubren con tests unitarios y no se presentan como comprobaciones reales.

PRIMARY es un candidato válido para la lectura sin Ctrl+C en este entorno, con
límites: no asegura origen, vigencia ni correspondencia con documento/página.
El futuro registro deberá leer PRIMARY inmediatamente al pulsarse el atajo,
porque otra selección puede reemplazarlo entre medias; también debe tenerse en
cuenta que puede conservar un texto anterior. No se implementa todavía el atajo,
la detección de foco, comprobaciones de propiedad ni la coordinación con los
otros adaptadores. No se extrapola el resultado a Wayland, otras versiones de
Okular ni a todos los PDFs (columnas, OCR, ligaduras, guiones blandos, etc.).

Los tests no requieren X11, xclip ni Okular: cubren ambas selecciones explícitas,
conservación exacta del texto, respuesta vacía, errores de ejecución, DISPLAY,
servidor inaccesible, timeout, formato no disponible, UTF-8 inválido, ausencia de
fallback y CLI. Una selección de espacios es texto disponible, no una cadena vacía.

### Captura conjunta provisional: prueba de integración de Fase 0

`CapturedIncident` es una dataclass inmutable independiente de adaptadores y CLI:
tipo editorial (enum de los siete códigos), nombre/ruta del audio, posición
decimal nativa, identificador de documento, página D-Bus y texto exacto. No es el
modelo persistente definitivo. El coordinador `capture_incident()` recibe tres
funciones sustituibles y no duplica los mecanismos de los adaptadores.

Orden elegido: validar código → leer PRIMARY → consultar Okular → consultar mpv.
Se prioriza PRIMARY por su carácter global y riesgo de sustitución; después se
lee documento/página, y finalmente audio, que el flujo previsto mantiene en
pausa manual. No se añaden esperas, reintentos ni lecturas duplicadas. La operación
no es atómica y no verifica origen, vigencia ni correspondencia del texto.

Se rechazan códigos distintos de los siete exactos, PRIMARY vacío y ausencia
de archivo/ruta de audio, posición, documento o página. No se normalizan textos,
rutas, códigos ni numeración. Los errores esperados se envuelven con contexto
de fuente en `CaptureError` y conservan la causa; no se ocultan errores de
programación inesperados. Se conservan valores cero y texto compuesto de espacios;
no se introducen reglas de negocio adicionales. Duración y pausa no son campos
de la captura ni nuevos requisitos de validez. No se exige `pause=true`, aunque
el procedimiento de prueba pide al usuario pausar manualmente.

Prueba real el 28 de octubre de 2026, fuera del sandbox: PDF temporal de tres
páginas `/tmp/audiobook-qc-capture-8vtck_7s/captura.pdf`, servicio
`org.kde.okular-341255`, y audio del sistema
`/usr/share/sounds/speech-dispatcher/dummy-message.wav`. mpv se inició desde el
terminal con `--no-config --force-window=yes --no-audio-display --ao=null --pause
--start=1.25 --input-ipc-server=/tmp/audiobook-qc-capture-8vtck_7s/mpv.sock` y el
audio indicado. Okular usó configuración, datos y caché de prueba bajo el mismo
directorio temporal. No se modificaron preferencias personales ni archivos del
usuario. El programa Python solo leyó las tres fuentes.

Comando real:

```bash
.venv/bin/python -m audiobook_qc.capture_probe INTER \
    --mpv-socket /tmp/audiobook-qc-capture-8vtck_7s/mpv.sock \
    --okular-service org.kde.okular-341255
```

| Captura | Posición nativa (s) | Página D-Bus | Texto |
| --- | --- | --- | --- |
| A | 1.249938 | 1 | `'Esta es una frase de prueba.'` |
| B | 6.249938 | 1 | `'Otro fragmento diferente.'` |
| C | 6.249938 | 2 | `'Otro fragmento diferente.'` |

El usuario desplazó manualmente mpv con Flecha derecha manteniéndolo en pausa,
navegó en Okular y cambió la selección sin Ctrl+C. B todavía devolvió página 1
pese a haberse solicitado ir a la 2; no se atribuye una causa. Tras confirmar
visualmente «2 de 3» y el texto «Pagina 2:», C devolvió página 2. Se verificaron
así cambios de timestamp, página y selección, sin automatizar teclas ni navegación.

También se ejecutó `python -m audiobook_qc.capture_probe inter`: argparse lo
rechazó con salida 2 antes de consultar fuentes. Los tests verifican la misma
validación temprana en la función reutilizable, sin depender de la CLI.

Salida completa de C:

```text
Captura provisional
Tipo: INTER
Audio: dummy-message.wav
Ruta audio: /usr/share/sounds/speech-dispatcher/dummy-message.wav
Posición: 00:00:06.250
Posición (segundos): 6.249938
PDF: /tmp/audiobook-qc-capture-8vtck_7s/captura.pdf
Página (D-Bus): 2
Texto:
«Otro fragmento diferente.»
Texto exacto: 'Otro fragmento diferente.'
Captura en memoria; lectura secuencial. Origen de PRIMARY no verificado.
```

Verificación automática: 146 tests superados, incluidos 32 del coordinador/CLI;
Ruff lint y formato correctos. Los tests usan fuentes en memoria y cubren los
siete códigos, rechazo temprano de códigos inválidos, errores de las tres
fuentes, datos ausentes, ausencia de fallback a CLIPBOARD, conservación exacta del
texto/precisión, orden de lectura y presentación. Ruff detectó inicialmente una
línea larga en el informe; se corrigió y las comprobaciones quedaron correctas.

Límites: se heredan la ambigüedad de vistas de Okular, las rutas/URLs nativas,
la falta de atomicidad, el carácter global y la persistencia de PRIMARY antiguo.
La salida nula de audio no verifica latencia auditiva. No se garantiza coherencia
si el usuario cambia de estado durante las lecturas. No se guarda la captura,
no hay comentarios/descripciones, ni se han iniciado las Fases 1 o 2.

## Fase 1: modelo de incidencia y persistencia SQLite

**Objetivo:** definir el modelo de incidencia y su persistencia en SQLite,
manteniendo el dominio separado del almacenamiento. Incluir tipo, archivo de
audio, timestamp, PDF, página y texto seleccionado. Usar exclusivamente `TEXT`,
`PRON`, `DICC`, `RUID`, `RESP`, `INTER` y `OTRO` como códigos iniciales.

**Criterio de salida:** modelo y persistencia probados, con guardado y recuperación
de incidencias y reglas de validación acordadas explícitamente. Los tests de
dominio no dependen de mpv, Okular ni una GUI.

**Estado:** completada en el alcance de modelo, conversión y CRUD SQLite de esta
intervención. Persistencia real demostrada tras cerrar y reabrir la base.

- `Incident` es una entidad de dominio independiente de SQL, CLI y adaptadores.
  Conserva los siete campos de captura y añade identidad, fechas, descripciones
  separadas y estado booleano de exportación. Se edita mediante copias validadas
  con `dataclasses.replace()` y `update()`; no se concatena descripción/comentario.
- `CapturedIncident` sigue siendo la captura técnica inmutable. La conversión
  explícita es `Incident.from_capture()`. No se cambia `capture_probe` ni se añade
  autoguardado. El enum existente es la única fuente de los siete códigos y
  genera también el CHECK del esquema; no se duplicó la lista en producción.
- `SQLiteIncidentRepository` proporciona inicialización, alta, consulta, listado,
  actualización y borrado. Cada escritura es transaccional; las lecturas siempre
  consultan SQLite, sin caché. `get` devuelve None para un ID ausente;
  `update`/`delete` lanzan `IncidentNotFoundError` en ese caso. El orden es fecha
  de creación UTC y, en caso de empate, ID. Los IDs borrados no se reutilizan.
- Esquema explícito versión 1 (`PRAGMA user_version`), con inicialización
  transaccional e idempotente sobre una base dedicada, sin migraciones automáticas.
  Se rechazan versiones desconocidas y tablas previas sin versión reconocida.
  Hay constraints para tipos/códigos, campos obligatorios, tiempo finito,
  página no negativa, timestamps UTC y booleano 0/1, además de validación Python.
- Posición: `float` en dominio y `REAL` binary64 en SQLite, sin redondeo ni formato
  temporal intermedio. Se conserva incluso un float adyacente a 1.0 en los tests.
  Se mantienen timestamps negativos observados y página 0 como datos nativos,
  sin inventar nuevas reglas editoriales.
- Rutas e identificadores: texto tanto en Python como en SQLite, incluidas URLs
  y rutas relativas, sin resolverlas ni comprobar que los archivos existan.
- Fechas: datetimes conscientes normalizados a UTC; SQLite almacena ISO 8601 con
  microsegundos y `+00:00`. La creación nace al construir Incident; al insertar,
  modificación y creación coinciden. Actualizar conserva la creación y establece
  la modificación al reloj UTC actual. No se admiten datetimes naive.

### Prueba real de persistencia de Fase 1

Ejecutada el 28 de octubre de 2026 con Python 3.10.12, sin aplicaciones externas:

```bash
.venv/bin/python -m audiobook_qc.incident_probe --db /tmp/audiobook-qc-phase1-7dxtzoxn/incidents.sqlite3 init
.venv/bin/python -m audiobook_qc.incident_probe --db /tmp/audiobook-qc-phase1-7dxtzoxn/incidents.sqlite3 add --generic-description 'Descripción de prueba' --custom-comment 'Comentario separado' < /tmp/audiobook-qc-phase1-7dxtzoxn/capture.json
.venv/bin/python -m audiobook_qc.incident_probe --db /tmp/audiobook-qc-phase1-7dxtzoxn/incidents.sqlite3 get 1
```

Los tres comandos se ejecutaron en procesos separados. `init` creó el esquema,
`add` insertó ID 1 y terminó; `get` recuperó la entidad desde otra conexión/proceso.
Ambas salidas JSON coincidieron, con tipo INTER, página 127, descripciones
separadas, `exported=false` y fechas conscientes UTC. Los archivos de audio/PDF
indicados deliberadamente no existían; no se comprobó su existencia.

Una cuarta conexión verificó todos los campos de captura contra el JSON original,
texto Unicode multilínea exacto y el mismo valor binario del tiempo:

```text
Reapertura y comparación exacta: correctas.
Posición binary64: 0x1.1421188cfba15p+10
Texto exacto: '¿Qué quieres decir?\nUna palabra parti-\nda. é\n'
Incidencias: 1
```

La posición recuperada fue `1104.5171234567`; las fechas persistidas fueron
`2026-10-28T13:34:01.014862+00:00` para creación y modificación. Se usaron solo
datos sintéticos y archivos temporales bajo `/tmp`, sin tocar configuración.

Verificación automática: 250 tests superados (los 146 previos y 104 nuevos),
Ruff lint y formato correctos. Bases SQLite reales temporales para esquema,
CRUD/reapertura, orden, rollback, constraints SQL eludiendo el modelo, campos
obligatorios, códigos, descripciones nulas/vacías, Unicode, precisión, fechas,
estado de exportación, conversión y CLI; sin depender de archivos externos.

Decisiones pendientes de otra intervención: migraciones al cambiar el esquema,
resolución de ediciones concurrentes (ahora gana la última escritura), política
sobre editar incidencias exportadas (el booleano solo cambia explícitamente),
reglas editoriales de descripción y conexión de captura con atajos.
No hay exportación, Excel, GUI, hotkeys ni configuración de usuario.

## Integración mínima de Fases 0 y 1: capturar y guardar desde CLI

**Estado:** completada en este alcance mínimo y verificada el 28 de octubre de
2026 mediante tests y demostración con SQLite real y fuentes simuladas.

**Alcance:** una acción manual que captura el contexto existente, convierte
explícitamente a `Incident`, guarda en SQLite y devuelve la entidad con su ID.
No implica completar la Fase 2 de atajos.

**Criterio de salida:** tests del caso de uso con captura y repositorio
sustituibles; integración con SQLite temporal real que conserve todos los datos
y los valores iniciales de Fase 1, devuelva el ID y demuestre que los fallos no se
presentan como éxito; CLI con ruta de base explícita; suite completa y Ruff
correctos. La demostración sin escritorio no certifica una nueva prueba con
PRIMARY, Okular y mpv reales.

### Diseño y límites

- `capture_and_save_incident` recibe una función de captura y un repositorio con
  `add` (protocolo mínimo). Ejecuta captura → `Incident.from_capture` → `add` y
  devuelve exactamente la entidad guardada, propagando errores.
- `capture_save_probe --db RUTA CODIGO` compone las fuentes existentes; acepta
  `--mpv-socket` y `--okular-service`, cierra la conexión y muestra JSON con ID.
  `capture_probe` conserva su comportamiento en memoria. No se han modificado
  captura, entidad ni repositorio de las fases anteriores.
- Inicialización deliberadamente separada: `incident_probe --db RUTA init`.
  Abrir una base puede crear un archivo vacío; el intento de guardar tras la
  captura rechaza esquemas no inicializados o incompatibles sin crear tablas.
  Sin base global, cambio de esquema ni inicialización dentro del caso de uso.
- Descripción genérica y comentario particular empiezan en None, por separado;
  `exported=False`, ID asignado por SQLite y fechas conscientes UTC.
- Sin hotkeys, daemon, GUI, edición interactiva, catálogo definitivo de
  descripciones, Excel, sincronización, concurrencia avanzada, migraciones ni
  instalador. Persisten los límites experimentales de Fase 0: no atomicidad,
  procedencia/vigencia de PRIMARY y ambigüedad de varias vistas por servicio.

### Verificación y demostración

Suite completa: **262 tests superados** (250 previos y 12 nuevos).
`ruff check .` y `ruff format --check .` correctos. Los tests nuevos cubren
conversión antes de guardar, repositorio sustituible, devolución de su entidad,
captura existente con fuentes en memoria y orden conservado, SQLite real tras
reabrir, ID secuencial, datos y precisión intactos, valores iniciales, errores de
captura/conversión/persistencia, CLI con ruta explícita y validación de argumentos,
esquema no inicializado y fallo de escritura SQL sin éxito ni registro parcial.

Demostración con un directorio temporal privado
`/tmp/audiobook-qc-save-demo-0wch1z_5`: un proceso ejecutó `incident_probe init`;
se ejecutó `capture_save_probe.main` con las tres lecturas sustituidas por datos
sintéticos, manteniendo el coordinador de captura y SQLite reales. Después,
otro proceso ejecutó `incident_probe get 1`; se comparó su JSON completo con la
entidad leída en una nueva conexión. Resultado: una incidencia, ID **1**, tipo
`INTER`, página **127**, ruta relativa y URL originales conservadas, descripción
y comentario nulos y estado no exportado. La posición fue `1104.5171234567`, con
representación binary64 `0x1.1421188cfba15p+10`, y el texto exacto:

```text
'  ¿Qué quieres decir?\nUna palabra parti-\r\nda. é\n'
```

La base temporal se eliminó al terminar la demostración. No se manipularon
ventanas, selecciones X11, archivos del usuario ni configuración personal.
Este ensayo con dobles no valida el entorno gráfico ni los atajos. La validación
posterior con las tres fuentes reales se documenta a continuación.

### Validación real de captura y persistencia (29 de octubre de 2026)

**Resultado:** flujo por CLI validado con las aplicaciones del usuario, sin
dobles ni cambios de código. No completa la Fase 2 de atajos del roadmap.

Entorno: Ubuntu 22.04.5, sesión X11/GNOME, mpv 0.34.1, Okular 21.12.3,
`busctl` y `xclip`. El usuario abrió el audio con IPC, lo pausó manualmente y
seleccionó la frase en su PDF, indicando página 33 y texto esperado. El sandbox
bloqueó consultas de X11/IPC; las comprobaciones reales se hicieron fuera de él
con autorización. Inicialmente no había servicio de Okular y el socket de la
prueba antigua rechazaba conexiones: un archivo socket existente no demuestra
que mpv siga activo.

Base temporal dedicada, inicializada explícitamente antes de capturar:
`/tmp/audiobook-qc-real-mjz7z4xb/incidencias.sqlite3`. Se conserva junto con
`fuentes.json`, `captura.json`, `recuperada.json` y `fallos.json` como evidencia
temporal; no se han modificado los archivos ni las preferencias del usuario.

Comandos de consulta y captura ejecutados (desde la raíz del proyecto):

```bash
.venv/bin/python -m audiobook_qc.okular_probe --list-services
.venv/bin/python -m audiobook_qc.okular_probe --service org.kde.okular-406490
.venv/bin/python -m audiobook_qc.mpv_probe --socket /tmp/audiobook-qc-real-mjz7z4xb/mpv.sock
.venv/bin/python -m audiobook_qc.selection_probe --selection primary
.venv/bin/python -m audiobook_qc.capture_save_probe \
    --db /tmp/audiobook-qc-real-mjz7z4xb/incidencias.sqlite3 INTER \
    --mpv-socket /tmp/audiobook-qc-real-mjz7z4xb/mpv.sock \
    --okular-service org.kde.okular-406490
.venv/bin/python -m audiobook_qc.incident_probe \
    --db /tmp/audiobook-qc-real-mjz7z4xb/incidencias.sqlite3 get 1
```

El servicio y el directorio temporal corresponden a esta sesión: al repetir,
crear otro directorio privado/base mediante `mktemp -d` e `incident_probe init`,
arrancar mpv con `--input-ipc-server=RUTA/mpv.sock`, abrir el PDF y listar los
servicios actuales. No se requiere configuración oculta. Una nueva captura
añade otra incidencia; usar siempre el ID devuelto.

Resultados contrastados contra las fuentes antes de capturar, la salida JSON de
la CLI y la lectura posterior mediante el repositorio en otro proceso:

- ID **1**, tipo técnico de prueba `INTER`, una sola incidencia guardada.
- Audio `011_El_partido_Part1_Cap02_v1.wav`, pausado en **19.300243 s**. mpv
  comunicó `./011_El_partido_Part1_Cap02_v1.wav`; se conserva esa ruta relativa,
  sin reconstruir la ruta absoluta indicada por el usuario.
- Documento `/home/jon/Documentos/correcciones/bocachica/pedidos/10_2026/el_partido/El_partido_TRIPAS.pdf`,
  servicio `org.kde.okular-406490`, página nativa **33**, coincidente con la
  página que el usuario indicó ver en Okular.
- PRIMARY devolvió **141 caracteres**. Se conservó exactamente el texto del
  PDF, incluyendo espacios exteriores, saltos, minúsculas en `xix` y guion:

```text
' Pero el\nimpetuoso desarrollo industrial de finales del siglo xix relega inexo-\nrablemente el mundo rural a los márgenes de la vida moderna. '
```

- La comparación de todos los campos capturados y de la entidad recuperada fue
  exacta. El timestamp nativo, JSON y SQLite conservaron el mismo binary64:
  `0x1.34cdcb9a9da59p+4`. Se volvió a consultar mpv y seguía en esa posición.
- Descripción genérica y comentario particular nulos, `exported=False`.
- Tres intentos adicionales ejecutaron la CLI real con fallos controlados:
  `DISPLAY` vacío solo en el subproceso (PRIMARY inaccesible), servicio Okular
  inexistente y socket mpv inexistente. Cada uno devolvió salida **1**, stderr
  con la fuente correspondiente y stdout vacío. Tras cada intento, el repositorio
  conservó exactamente la misma incidencia: sin altas parciales ni cambios.

No se detectó un defecto que requiriera corregir código. Esta prueba valida la
captura y persistencia manuales; no demuestra atomicidad, origen/vigencia de
PRIMARY en general, resolución de varias vistas ni atajos globales.

## Fase 2: captura real mediante atajos

**Estado:** pendiente. El flujo manual de captura y guardado está validado con
aplicaciones reales; los atajos siguen sin implementar ni verificar.

**Objetivo:** conectar atajos por tipo de incidencia con los adaptadores y la
persistencia. El usuario pausa manualmente mpv con Espacio, selecciona una frase
en Okular y pulsa el atajo. La captura obtiene el tipo, archivo de audio,
timestamp, PDF, página y selección sin acoplar el dominio a esas aplicaciones.

**Criterio de salida:** flujo de captura completo verificado en el entorno real,
con tests de coordinación mediante dobles de los adaptadores y tratamiento
explícito de fallos de captura.

## Fase 3: exportación a plantilla Excel corporativa

**BLOQUEADA: no implementar hasta disponer de una muestra de la plantilla Excel
corporativa.** No inventar columnas, formato, fórmulas ni reglas de exportación.

**Objetivo:** exportar las incidencias a la plantilla facilitada respetando su
estructura y las reglas corporativas confirmadas.

**Criterio de salida:** muestra disponible, correspondencia de campos acordada y
exportación probada sobre ella, con revisión de que conserva el formato y los
elementos requeridos de la plantilla.

## Fase 4: interfaz de revisión

**Objetivo:** incorporar una interfaz para revisar las incidencias guardadas,
definiendo con el usuario las operaciones necesarias y manteniendo la GUI
separada de la lógica de dominio.

**Criterio de salida:** operaciones de revisión acordadas y verificadas sobre
datos persistidos, con tests de la lógica independiente de la interfaz.

## Fase 5: configuración y robustez

**Objetivo:** consolidar la configuración y el comportamiento ante errores del
entorno y de las integraciones, según los problemas observados en uso real.

**Criterio de salida:** opciones documentadas, validación de configuración y
pruebas de los escenarios de fallo acordados, con instrucciones de diagnóstico
y recuperación reproducibles.

## Fase 6: posible visor PDF integrado

**Objetivo:** evaluar un visor PDF propio como alternativa a Okular y, si se
aprueba su desarrollo, conectarlo mediante el adaptador de documentos.

**Criterio de salida:** decisión documentada sobre su viabilidad y alcance; si se
implementa, captura de PDF, página y selección verificada sin modificar las reglas
de dominio.

## Fase 7: mejoras avanzadas

**Objetivo:** evaluar mejoras como voz, estadísticas y otras propuestas a partir
de necesidades reales, acordando cada una antes de implementarla.

**Criterio de salida:** cada mejora aprobada tiene alcance, criterios de aceptación
y tests propios; las propuestas no aprobadas permanecen pendientes.

## Supuestos técnicos pendientes de verificación experimental

- **mpv:** archivo y timestamp obtenidos mediante JSON IPC en la Fase 0.3.
  Queda comprobar el uso con audio real y pausa manual intermedia, además de
  investigar los valores negativos observados con el audio corto en bucle.
- **Okular:** documento y página obtenidos mediante D-Bus en la Fase 0.4; lectura
  de texto seleccionado mediante PRIMARY de X11 verificada de forma aislada en
  la Fase 0.5. Quedan los límites de vistas, PDFs y vigencia indicados arriba.
- **Selección y atajos en Linux:** PRIMARY/CLIPBOARD comprobados en X11; la
  coordinación solo se ha probado mediante CLI manual. Atajos y foco siguen
  pendientes, sin asumir portabilidad a Wayland.
- **Coherencia de la captura:** captura conjunta verificada con recursos de prueba
  y cambios manuales de posición, página y texto. Queda contrastarla en uso real,
  sin asumir atomicidad ni procedencia/vigencia del texto obtenido de PRIMARY.

Las comprobaciones pendientes requieren una intervención posterior. La prueba de
mpv no demuestra todavía la viabilidad de las otras integraciones.
