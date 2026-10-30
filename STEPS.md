# Roadmap

Estado actual: Fase 0 técnicamente completada con las limitaciones documentadas.
Fase 1 completada y verificada con SQLite real tras cerrar/reabrir conexiones
y procesos. Integración mínima de captura y guardado validada mediante CLI con
mpv, Okular y PRIMARY reales. Fase 2 completada en el alcance de atajos
personalizados de GNOME, con pulsaciones reales y notificaciones confirmadas.
La protección posterior frente a activaciones involuntarias exige además modo
activo y foco autorizado; su verificación se registra al final de la Fase 2.
La gestión dinámica posterior también se validó: off libera los bindings y on
restaura las combinaciones, sin alterar entradas ajenas.

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

**Estado:** completada el 29 de octubre de 2026 en el alcance de activación
mediante atajos personalizados de GNOME y comunicación por notificaciones.
Se validaron pulsaciones reales del usuario con Okular y mpv y, posteriormente,
el modo de corrección y el rechazo de foco no autorizado.

**Objetivo:** conectar atajos por tipo de incidencia con los adaptadores y la
persistencia. El usuario pausa manualmente mpv con Espacio, selecciona una frase
en Okular y pulsa el atajo. La captura obtiene el tipo, archivo de audio,
timestamp, PDF, página y selección sin acoplar el dominio a esas aplicaciones.

**Criterio de salida:** flujo de captura completo verificado en el entorno real,
con tests de coordinación mediante dobles de los adaptadores y tratamiento
explícito de fallos de captura.
La ampliación de protección exige modo inicial inactivo, controles explícitos
on/off/status, rechazo previo a captura/escritura fuera de las ventanas
autorizadas y pruebas reales de activación/desactivación y foco ajeno.

### Mecanismo mínimo elegido

GNOME detecta los atajos personalizados y ejecuta la CLI existente con
`--desktop`; no hay proceso residente del proyecto. La combinación se configura
en el campo de GNOME y el código en el comando, sin mapa de teclas en Python.
Se reutiliza `capture_and_save_incident` sin cambiar dominio, captura ni esquema.
`notify-send` comunica código/ID solo tras guardar o el error sin éxito; un fallo
del aviso posterior al guardado conserva el éxito y lo describe en stderr.

Se descartó por innecesario un listener residente con bindings de X11 o un
daemon externo como xbindkeys/sxhkd: GNOME ya proporciona el mecanismo de
activación. No se han añadido dependencias Python, instaladores ni GUI propia.
Las instrucciones de preparación, configuración, personalización, uso y
desactivación están en [README.md](README.md#activación-mediante-atajos-de-gnome-fase-2).

`--db` sigue siendo obligatorio y el esquema requiere inicialización explícita.
En modo escritorio, base y socket deben ser rutas absolutas. El servicio Okular
se indica explícitamente si hay varios; su identificador puede cambiar al
reiniciar. Siguen vigentes el texto obligatorio y los límites de PRIMARY/vistas.

`activation_guard` usa flock no bloqueante por ruta SQLite resuelta, con un
archivo `.capture.lock` al lado de la base. Evita ejecuciones solapadas para
esa base entre procesos `--desktop`, sin encolar ni deduplicar contenido.
La siguiente activación completada crea otra incidencia. No hay cooldown ni
deduplicación editorial. La repetición al mantener una tecla queda sin verificar.

### Configuración y comprobaciones de esta intervención

El usuario pidió **F1→TEXT, F2→PRON, F3→DICC, F4→RUID, F5→RESP, F6→INTER,
F7→OTRO** y aceptó desplazar temporalmente las funciones locales de Okular tras
conocer sus conflictos: ayuda F1, búsqueda siguiente F3, recarga F5, anotaciones
F6 y panel lateral F7. Shift+F1/Shift+F3 tampoco están totalmente libres. No se
encontraron esas teclas en los grupos de GNOME ni en los bindings/scripts mpv
consultados; no se afirma haber comprobado todas las extensiones ni bindings
dinámicos. Se revisaron los overrides locales de Okular y fuentes oficiales
de KDE/mpv, enlazadas en README. No se considera validada una tecla solo por
poder almacenarla en gsettings.

Se configuraron y releyeron atajos personalizados mediante gsettings en las rutas
`/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/audiobook-qc-CODIGO/`
(CODIGO en minúsculas). Se conservó el atajo existente Ctrl+Alt+T. Comandos con
intérprete absoluto del proyecto y dependencias explícitas: base temporal
`/tmp/audiobook-qc-hotkeys-gzl2v_os/incidencias.sqlite3`, socket
`/tmp/audiobook-qc-real-mjz7z4xb/mpv.sock`, servicio `org.kde.okular-406490`.
Se inicializó la base vacía y se conservaron el plan `gnome-plan.json`, los
comandos `comandos.txt` y la lista anterior `gnome-before.json` en el directorio
temporal. El código no contiene estas rutas personales ni registra atajos por
su cuenta. Los atajos de prueba deben eliminarse o editarse si se borra `/tmp`.

Verificación automática: **285 tests superados** (262 previos y 23 nuevos),
Ruff lint y formato correctos. Pruebas con dobles de captura/notificaciones y
SQLite temporal real para siete códigos, invocación del caso de uso, datos y
precisión, captura/escritura fallidas, aviso posterior al commit, error del aviso
tras éxito, rutas absolutas, esquema no inicializado, consecutivas, exclusión
entre procesos, liberación tras error y alias de ruta. Se probó el adaptador
notify-send (argumentos sin shell, escape de markup, timeout, fallo y ausencia).

Prueba real: notify-send terminó correctamente al enviar un aviso informativo
que no guardó incidencias. mpv seguía pausado en 19.300243 s y el servicio indicado
de Okular estaba registrado. Después, el usuario pulsó F1–F7 en Okular y F6 tres
veces más al continuar la prueba con mpv. Confirmó avisos `Incidencia guardada`
con código e ID creciente, sin acciones locales de las aplicaciones ni cambio
de foco. Aclaró que los tres INTER adicionales procedían de sus tres pulsaciones
separadas de F6; no se observaron duplicados involuntarios en esa prueba.
No se han hecho commits.

Durante la prueba física solicitada al usuario se observaron diez incidencias:
ID 1–7 con TEXT, PRON, DICC, RUID, RESP, INTER y OTRO, seguidas por tres INTER
(ID 8–10). Se recuperaron todas mediante `incident_probe get ID`, cada una en
un proceso independiente, y se compararon con la entidad del repositorio.
Archivo, ruta relativa, PDF, página 33, posición 19.300243 (binary64
`0x1.34cdcb9a9da59p+4`), campos iniciales y texto exacto coincidieron. La selección
de esta ronda tenía 140 caracteres y no incluía el espacio inicial de la ronda
anterior; no se normalizó. Se conserva `incidencias-verificadas.json` junto a la
base temporal. La correspondencia entre pulsaciones, códigos e ID queda
contrastada con las confirmaciones del usuario.

Prueba adicional por CLI real con `--desktop` y un socket mpv inexistente: salida
1, stdout vacío, error que identifica la fuente y notificación sin error de
transporte. La base permaneció idéntica con diez incidencias. Evidencia:
`fallo-desktop.json` en el directorio de prueba. El usuario no confirmó
visualmente este aviso de error; no se presenta como una pulsación física.

Limitaciones conservadas: combinaciones globales activas también en otras
aplicaciones, riesgo de pulsación accidental, repetición al mantener teclas sin
probar, ausencia de cooldown/deduplicación, notificaciones que dependen del
servidor/modo No molestar, dependencias de sesión X11 y límites previos de captura.
No se amplía el alcance a Wayland, Windows, GUI, Excel ni servicio residente.

### Protección frente a activaciones involuntarias (Prompt 011)

**Estado:** implementada y validada mediante pulsaciones reales el 29 de octubre
de 2026. No se modifican dominio, repositorio, caso de uso ni adaptadores de
PRIMARY, Okular o mpv. La CLI `--desktop` aplica una política sustituible antes
de consultar fuentes, abrir SQLite o crear su bloqueo. Los tests previos de
captura/notificaciones inyectan un contexto autorizado; la nueva suite prueba
el filtro completo con dobles de las consultas de foco y SQLite temporal real.

- `correction_mode.py`: on/off/status, aviso opcional, estado inicial inactivo,
  archivo bajo XDG_RUNTIME_DIR por usuario/display, escritura atómica y lectura
  conservadora ante errores/corrupción; no guarda el estado en incidencias.
- `integrations/focus.py`: xprop consulta la ventana activa de X11, WM_CLASS y
  PID; verifica `/proc/PID/exe` y vuelve a leer la ventana activa. Solo acepta
  Okular o mpv gráfico con clase y binario coherentes. Terminales y otras
  aplicaciones se rechazan aunque tengan ejecutándose mpv/Okular. Sin identidad
  fiable se rechaza. No se cachean PID ni ventanas.
- `desktop_policy.py`: combina modo y foco, separada del dominio. Un rechazo
  informa `Activación rechazada`, sin capturar ni escribir.

La inspección real verificó WM_CLASS `okular/okular`, PID 406490 y binario
`okular`; mpv gráfico `gl/mpv`, PID 406664 y binario `mpv`. Esos PID solo son
evidencia experimental, no configuración. Los siete comandos propios de GNOME
conservaron sus teclas/base/socket; se retiró el servicio Okular fijado al PID
antiguo para usar el descubrimiento único existente al reabrir la aplicación.
Se conservó `before-focus-protection.json` con los comandos anteriores junto a
la base temporal de pruebas. No se cambiaron otros atajos personales.

En el Prompt 011, F1–F7 permanecían **reservadas incluso con modo inactivo**. El
modo impedía incidencias pero no devolvía las teclas. Se valoró
automatizar las asignaciones propias: requeriría snapshot/restauración de la
configuración personalizable y recuperación ante fallos parciales. Se mantienen
las asignaciones y se documenta su desactivación manual en GNOME; no se añade
sincronización con dconf ni daemon de foco. Las combinaciones siguen editables.

Pruebas reales con la base `/tmp/audiobook-qc-hotkeys-gzl2v_os/incidencias.sqlite3`:

- Baseline de esta ronda: **11 incidencias**. Modo inicialmente inactivo y F6
  en Okular y aplicación ajena: el usuario confirmó rechazos; recuento intacto.
- `correction_mode on --notify`, F6 en Okular y en mpv gráfico: dos registros,
  ID **12** y **13**, recuperados mediante `incident_probe get` en procesos
  separados y contrastados con el repositorio. F6 en terminal y otra aplicación:
  el usuario confirmó rechazo; total **13**, sin altas adicionales.
- `correction_mode off --notify`, F6 en Okular: el usuario confirmó un nuevo
  rechazo. Se deja el modo inactivo al finalizar.

Suite completa: **338 tests superados** (285 previos y 53 nuevos); Ruff lint y
formato correctos. Cubre modo inicial/activo/inactivo/corrupto, errores y avisos,
estado entre procesos y por display, foco Okular/mpv/ajeno/desconocido, cambios
durante consulta, proceso no verificable, identificación tras reinicio y ausencia
de captura/apertura de SQLite/creación de bloqueo ante rechazo. No se presenta
la prueba automatizada de reinicio como una reapertura gráfica real.

Límites: X11 y propiedades del cliente, no frontera contra aplicaciones hostiles;
la comprobación y captura no son atómicas; desactivar no cancela una captura
iniciada. Modo activo hasta off o limpieza de runtime, sin reinicio automático
al cerrar aplicaciones. Al reabrir mpv debe conservarse la ruta IPC; múltiples
servicios Okular requieren resolver explícitamente la ambigüedad. Siguen los
límites de PRIMARY, deduplicación, teclado y notificaciones ya documentados.
Esta limitación se aborda en el Prompt 012, descrito a continuación.
Comandos e instrucciones completos en
[README.md](README.md#protección-frente-a-activaciones-involuntarias). Sin commits.

### Gestión dinámica de atajos GNOME (Prompt 012)

**Estado:** completada el 29 de octubre de 2026 tras validar físicamente la
liberación, restauración y registro con GNOME 42.9. La evidencia incluye
pulsaciones del usuario y comparación de toda la configuración, no solo lecturas.

Mecanismo: `GSettingsShortcuts` descubre las entradas registradas mediante la
firma del comando directo Python que ejecuta `audiobook_qc.capture_save_probe`
con `--desktop`. No usa índices fijos, nombre visible ni teclas concretas.
Solo modifica binding, dejando intactos name, command y custom-keybindings.
Se comprueba que la entrada siga registrada y sin cambios antes de escribir,
y se relee después. Las carreras con el editor externo no son una transacción
atómica; no se deben editar entradas durante on/off.

`ShortcutMode` coordina:

- `off`: desactivar primero el indicador de captura; guardar combinación y
  comando en la copia persistente antes de vaciar cada binding; intentar todas
  las entradas aunque fallen algunas. Comunicar fallos parciales y valores
  para recuperación manual si no se pudo guardar la copia.
- `on`: conservar el modo inactivo durante la restauración; verificar todo
  antes de marcarlo activo. Ante fallo, intentar liberar de nuevo las entradas
  propias, sin afirmar que la recuperación fue completa si también falló.
- `status`: informar modo y sincronización; discrepancias devuelven salida 1
  sin modificar GSettings.

La copia versionada `gnome-bindings.json` se guarda bajo
`$XDG_STATE_HOME/audiobook-qc` o `~/.local/state/audiobook-qc`, con reemplazo
atómico, fsync y bloqueo entre controles de modo. Sobrevive a la limpieza del
runtime. Distingue bindings suspendidos por el programa de borrados manuales
observables mientras estaban habilitados. Adopta nuevas combinaciones manuales,
conserva nombres/comandos, no recrea entradas borradas ni toca las destinadas
a otra aplicación. Rechaza comandos cambiados en entradas suspendidas sin una
combinación explícita nueva, duplicados y conflictos exactos con atajos ajenos.
No hay combinación F1–F7 fija en el código.

Limitaciones explicadas antes de implementar: vaciar otra vez un binding que
ya estaba vacío no deja un cambio observable; para desactivar permanentemente
una entrada hay que vaciarla mientras esté habilitada o eliminarla en GNOME.
Un reinicio/interrupción puede dejar bindings persistentes con modo inactivo:
no hay daemon que los libere automáticamente. `status` lo detecta y `off`
permite recuperar. Se documenta un comando off opcional en Aplicaciones al
inicio, sin instalarlo ni probar logout/reinicio real. Una copia perdida o
corrupta no se sustituye por teclas inventadas: conservarla y reconfigurar
manualmente si no hay una copia válida. off prioriza liberar las teclas.

Entorno real: GNOME Shell **42.9**, Ubuntu 22.04/X11. El esquema instalado usa
cadena vacía como valor predeterminado de binding. Se revisó además la fuente
oficial de gnome-settings-daemon 42.1. La prueba física confirmó que vaciar solo
TEXT devolvía F1 a la ayuda de Okular sin aviso de audiobook-qc. Después, el
nuevo off vació las siete combinaciones; el usuario confirmó las funciones
locales de F1 y F6/F7, sin avisos del programa. Se compararon íntegramente las
entradas antes/después: registro, nombres, comandos y atajos ajenos intactos.

Evidencias bajo `/tmp/audiobook-qc-dynamic-psdmalgy`: `gnome-before.json`,
`before-managed-off.json`, `after-managed-off.json` y `after-managed-on.json`.
La copia persistente real quedó en
`/home/jon/.local/state/audiobook-qc/gnome-bindings.json`. El nuevo on restauró
exactamente las combinaciones iniciales. La base partía de 13 incidencias y
seguía en 13 al probar las funciones locales. El primer intento de captura
activa falló por mpv cerrado, sin añadir incidencias; se facilitó el comando
para reabrir mpv con el socket esperado. Tras reabrirlo, el usuario repitió
F1–F7 con foco en Okular y F6 en mpv gráfico, confirmando los ocho avisos de
guardado, sin funciones locales. Se recuperaron ID **14–21** en procesos
independientes: TEXT, PRON, DICC, RUID, RESP, INTER, OTRO e INTER. El contexto
de esta ronda fue página **20**, posición **19.3 s**, binary64
`0x1.34ccccccccccdp+4` y texto exacto:

```text
'Emite un bufido y aprieta el volante. Conozco ese ale-\nteo en la nariz. '
```

La comparación de recuperación fue exacta. No se usa una lectura posterior de
PRIMARY como referencia del instante de captura: puede cambiar después de que
el usuario termine la prueba. Se verificaron on y off repetidos: mismas
combinaciones/copia, ninguna alta adicional. Al finalizar, **modo inactivo,
atajos sincronizados y siete bindings vacíos**; las entradas ajenas, nombres,
comandos y lista registrada permanecieron idénticos. Total final: **21**
incidencias. Evidencias adicionales: `capturas-verificadas.json`,
`final-gnome.json` y `validacion.json` en el directorio temporal indicado.

Suite completa: **376 tests superados** (338 previos y 38 nuevos), Ruff lint y
formato correctos. Tests con backend de atajos en memoria y archivos temporales,
sin GSettings real: personalización, idempotencia, exclusión, fallos parciales
de lectura/escritura/indicador, readback fallido, recuperación de interrupción,
runtime desaparecido, copia perdida/corrupta/no escribible, cambios manuales,
entradas borradas o reconvertidas, conflictos, sincronización y alcance de las
escrituras del adaptador. Los tests previos del indicador runtime se aislaron
de la nueva gestión GNOME para no ejecutar comandos reales por accidente.
Sin cambios en dominio, SQLite ni fuentes de captura; sin gestión de trabajos,
daemon ni commits. Instrucciones y recuperación en
[README.md](README.md#gestión-dinámica-de-las-combinaciones-de-gnome).

## Ampliación acotada: gestión de trabajos (Prompt 013)

El roadmap original no incluía gestión de proyectos/trabajos explícita. Esta
ampliación solicitada incorpora solo organización, configuración y selección,
sin adelantar la Fase 3 ni la interfaz de revisión de Fase 4. La Fase 5 conserva
su alcance futuro de robustez general.

**Arquitectura:** `CorrectionJob` identifica cada audiolibro (UUID, título,
carpeta y fecha UTC). `JobStore` implementa catálogo local, configuración XDG y
resolución del destino; `jobs_cli` ofrece gestión sin GUI. Una SQLite versión 1
por UUID mantiene aislamiento sin cambiar `Incident`, migrar tablas o duplicar
`capture_and_save_incident`. Cada carpeta contiene `job.json` portable y
`incidencias.sqlite3`. Se admiten títulos repetidos sin colisión de carpetas.
No se introduce estado editorial: selección y modo siguen siendo independientes.

No hay raíz de trabajos por defecto: `jobs_cli configure RUTA` la establece
explícitamente y la persiste junto con el UUID seleccionado en
`$XDG_CONFIG_HOME/audiobook-qc/jobs.json` o `~/.config/audiobook-qc/jobs.json`.
Cambiarla no mueve datos y limpia la selección; repetir la misma la conserva.
Configuración/selección se escriben con reemplazo atómico y fsync. La carpeta
se identifica por UUID completo, sin inferencia por título.

`jobs_cli` permite configure/config/create/list/get/select/active/clear.
`active` comprueba que metadatos/base sean válidos. `on` valida el destino antes
de habilitar atajos; cada `--desktop` resuelve el trabajo de nuevo y abre SQLite
con URI `mode=rw`, comprobando permisos, versión y columnas antes de leer las
fuentes. Una prueba local confirmó que una base solo legible permite consultar
el esquema; por eso se comprueban también los permisos de base y carpeta.
No se crea ni inicializa una base durante la pulsación. La confirmación tras
commit incluye título. Ausencia de selección, trabajo inválido, captura y
persistencia tienen mensajes diferenciados. Los comandos técnicos `--db`
siguen disponibles; en escritorio una ruta explícita solo se acepta si coincide
con el trabajo seleccionado. Para alternar títulos hay que retirar --db de las
entradas GNOME una sola vez; no se modifica automáticamente GSettings personal.

**Concurrencia:** un flock exclusivo no bloqueante junto a la configuración
coordina las mutaciones, selección, modo on y captura completa hasta el commit.
La selección efectiva es la observada al adquirir ese bloqueo, no el instante
físico de la tecla. Operaciones simultáneas se rechazan, sin cola ni cambio de
destino durante una captura. Se conserva el bloqueo previo por base y todas las
protecciones de foco/modo/notificaciones. off no cancela una captura ya iniciada.
Una selección perdida mientras el modo sigue activo rechaza nuevas capturas.

**Criterios de salida:** dos trabajos coexistiendo con bases distintas; captura
de escritorio usando exclusivamente el destino seleccionado; rechazos antes de
captura ante ausencia de selección/base/esquema; persistencia entre procesos;
cambio/activación/capturas simultáneas sin mezcla; precisión intacta; suite,
lint y formato correctos. **Criterios automatizados verificados:** 424 tests
superados (376 previos adaptados al destino seleccionado y 48 nuevos),
`ruff check .` y `ruff format --check .` correctos. Tests con fuentes y GNOME
sustituidos, SQLite real y configuración temporal aislada.
No se considera realizada una prueba física de esta ampliación por conservar
las pruebas históricas de Fase 2.

**Limitaciones y recuperación:** filesystem local con flock y reemplazo atómico;
misma configuración entre procesos; no coordina escritores técnicos o cambios
manuales de archivos durante captura. No se certifica NFS ni almacenamiento
sin locks fiables. Los títulos no verifican el audio/PDF abierto: el corrector
debe cambiar recursos y consultar active. Sin importación automática, eliminación,
estados editoriales, GUI o Excel. Una creación interrumpida puede dejar una
carpeta incompleta que se rechaza; conservarla y apartarla manualmente con modo
apagado. Para copias, esperar operaciones y copiar la carpeta completa; para
recuperar, restaurar datos conocidos, seleccionar y validar antes de on. JSON
corrupto no se sobrescribe automáticamente. No se usan rutas personales ni /tmp
como destino predeterminado. Los tests sí usan bases y configuración temporales.

**Integración adicional ejecutada:** CLI en procesos separados para configurar,
crear A/B, seleccionar A → B → A, capturar y recuperar cada ID. Resultado:
«El partido» contiene TEXT #1 y OTRO #2; «La montaña mágica», INTER #1.
Texto exacto (CR/LF, espacios, Unicode) y timestamp binary64 conservados.
Pipeline y SQLite reales, fuentes/foco/notificación sustituidos; no se presenta
como pulsación física. Evidencia y bases temporales conservadas en
`/tmp/audiobook-qc-jobs-integration-5_z4qjyu/verification.json`.

**Validación física posterior:** el usuario confirma que las capturas quedaron
separadas entre trabajos y que los siete comandos GNOME ya no incluyen --db.
Esta confirmación pertenece a la gestión de trabajos; no demuestra todavía la
vinculación de fuentes de la ampliación siguiente. Se conserva el procedimiento
de regresión en README. Sin commits.

## Vinculación explícita de fuentes por trabajo

**Problema:** las bases ya estaban aisladas, pero los comandos GNOME conservaban
un socket mpv temporal y el descubrimiento Okular no identificaba el documento
del trabajo. Esta ampliación limita la captura de escritorio a fuentes asociadas
explícitamente; no implementa fases posteriores, GUI ni migraciones de Incident.

**Arquitectura implementada:** `job_sources.py` compone adaptadores y configuración
por trabajo en `sources.json`, separado de `CorrectionJob`, `Incident` y SQLite.
Guarda ruta absoluta/canónica del PDF y lista ordenada de capítulos locales.
`integrations/job_mpv.py` deriva el socket del UUID persistente bajo
`$XDG_RUNTIME_DIR/audiobook-qc/<UUID>.sock`; no guarda sockets de prueba o PIDs.
`integrations/document_binding.py` identifica vistas por documento, dueño único
D-Bus y ruta de objeto. El dominio y el esquema SQLite siguen intactos.

**CLI:** `jobs_cli set-pdf UUID RUTA`, `sources UUID`,
`launch-mpv UUID [CAPITULOS...]`, `launch-okular UUID`. La primera preparación
expresa los archivos; al retomar, launch-mpv sin capítulos reutiliza la instancia
que responde o relanza con la lista persistida. Arranca pausado, con ventana e
idle para conservar la instancia entre capítulos. Otra lista exige cerrar antes
el mpv dedicado. No se restauran automáticamente capítulo/posición de una sesión
anterior. Solo se aceptan archivos locales declarados, no playlists externas o
URLs; archivos ajenos arrastrados al reproductor se rechazan en la captura.

Solo el lanzamiento explícito puede retirar un socket propio sin servidor;
no reemplaza archivos/enlaces, ni interfiere con instancias ordinarias de mpv.
Un arranque sin socket termina exclusivamente el proceso que acaba de iniciar;
los errores quedan en mpv.log dentro del trabajo. El runtime debe ser absoluto,
la carpeta privada (0700) y la ruta IPC no exceder 107 bytes. La captura no crea
sockets ni inicia aplicaciones. La configuración persistente no usa /tmp.

**Okular:** se revisó la fuente de Okular 21.12.3: cada Part publica /okular,
/okular2, etc. Se enumeran todos esos objetos, incluso dentro del mismo proceso,
y se exige una única vista del PDF configurado. GetNameOwner fija la conexión;
los alias del mismo dueño se deduplican. No se elige por foco, PID, orden ni por
ser la primera instancia. Tras reabrir, el documento permite redescubrir dueño
y objeto. Un PDF duplicado, servicio no inspeccionable o API desconocida rechaza
la captura; no se ocultan errores que pudieran encubrir otra copia del PDF.

**Integración:** `--desktop` rechaza --mpv-socket/--okular-service con mensaje de
migración y resuelve sus fuentes dentro del mismo bloqueo que fija el trabajo.
Se reutiliza capture_and_save_incident. La lectura mpv conserva una conexión y
comprueba archivo antes y después de filename/path/time-pos/duration/pause.
Okular comprueba documento antes/después de la página; tras capturar se revalida
la identidad, unicidad, documento y página antes de add. Si una fuente falta o
cambia, no hay escritura ni fallback a otras instancias. on valida fuentes
antes de restaurar GNOME. Las CLI técnicas sin --desktop conservan sus opciones.
Los atajos definitivos solo necesitan intérprete absoluto, módulo, --desktop y
código. README incluye la generación exacta de sus siete comandos y migración
manual respetando el journal; no se modifica GSettings real automáticamente.

**Verificación:** la suite conserva los 424 tests anteriores y añade 52
específicos (476 en total). Cobertura: A → B → A con fuentes y SQLite distintas,
mpv ajeno ignorado, capítulos sucesivos y precisión binary64, socket caído,
archivos no declarados, configuración persistente entre procesos, PDF duplicado,
vistas del mismo proceso, dueño desaparecido, reapertura con otro objeto,
cambios de documento/página antes del INSERT, ausencia de overrides GNOME,
lanzamiento/reutilización y arranque fallido, conflictos de archivos runtime,
socket obsoleto y permisos. La suite aísla XDG; no arranca aplicaciones gráficas
ni usa preferencias personales. Una prueba de socket Unix temporal requiere
salir del sandbox que bloquea bind. Resultado final: **476 tests superados**,
`ruff check .`, `ruff format --check .` y `git diff --check` correctos.

**Comprobación real limitada, 29 de octubre de 2026:** consulta de solo lectura
al Okular ya abierto mediante el nuevo adaptador. El servicio observado exponía
KBookmarkManager, okular y okularshell; solo okular es la vista de documento.
Se resolvió su dueño único, /okular y página 60, verificando coincidencia con el
documento comunicado. No se capturaron incidencias ni se abrieron ventanas o
modificaron configuración/atajos. No equivale a una prueba física A/B completa.

**Límites y criterio experimental pendiente:** no hay lectura D-Bus atómica de
documento/página, ni snapshot atómico de las propiedades mpv. Las comprobaciones
rechazan cambios observados; no certifican cambios de ida y vuelta entre lecturas.
No navegar/cambiar documentos o capítulos mientras se registra. PRIMARY sigue
siendo global y no demuestra origen/vigencia del texto; seleccionar la frase en
el PDF asociado inmediatamente antes de pulsar. El filtro de foco autoriza, no
elige fuentes. No se promete seguridad contra procesos maliciosos del mismo
usuario que manipulen sockets/configuración. Metadatos de fuentes con rutas
absolutas requieren reasociación si se mueven sus archivos.

El usuario confirmó posteriormente la prueba física A → B → A, sin mezcla de
incidencias/fuentes incluso con mpv ajenos abiertos. README conserva los pasos
con dos PDFs, dos mpv dedicados, otro mpv ajeno, A → B → A, capítulos, sockets
caídos y PDF duplicado. Criterio: cada alta identifica el archivo/timestamp y
PDF/página de su asociación, A/B permanecen separados y las ambigüedades no
escriben; comprobar también notificaciones y restauración de teclas con off.
No hay decisiones bloqueantes abiertas. Sin commits.

### Ampliación pequeña: capítulos desde directorios

`jobs_cli launch-mpv UUID [RUTAS...]` acepta archivos, directorios y mezclas.
Cada carpeta se expande sin recursión a archivos con las extensiones de audio
indicadas en README (sin distinguir mayúsculas). Orden natural determinista por
nombre, con números comparados numéricamente y desempate por nombre original.
Se conserva el orden de argumentos y se deduplica por ruta canónica, manteniendo
la primera aparición. Una carpeta sin audios admitidos falla antes del lanzamiento
y conserva la configuración anterior.

`sources.json` guarda únicamente la lista concreta expandida; la comprobación de
pertenencia del audio activo sigue usando esa lista. Relanzar sin argumentos no
rescanea carpetas. Para incorporar capítulos nuevos hay que cerrar el mpv dedicado
y volver a pasar la carpeta. La detección por extensión no certifica el contenido
ni los codecs: mpv sigue comprobando la decodificación al abrir los archivos.

Verificación: 11 tests nuevos sobre expansión, orden, carpetas vacías/sin audios,
subcarpetas ignoradas, mezclas, alias/duplicados, persistencia, relanzamiento y
rechazo de archivos que se añadieron después de guardar la asociación. Configuración
y archivos temporales; lanzamiento sustituido, sin abrir el mpv real del usuario.
Resultado: **487 tests superados**; `ruff check .`, `ruff format --check .` y
`git diff --check` correctos. No se modifican dominio, esquema SQLite ni
configuración GNOME. Sin commits.

## Primera capa de consulta y edición de incidencias por trabajo

**Alcance:** base de revisión solicitada, previa a la GUI de Fase 4, sin adelantar
Excel (Fase 3 continúa bloqueada). La rama master partía limpia del commit
b2de1df y 487 tests. No se introducen migraciones, dependencias o cambios de GNOME.

**Arquitectura:** `incident_review.py` contiene consulta por ID y edición con
lista cerrada de campos y validación de Incident, mediante protocolo de repositorio
sustituible. `incidents_cli.py` compone presentación humana/JSON, trabajo y SQLite.
JobStore.destination acepta opcionalmente UUID explícito bajo el mismo bloqueo;
sin UUID conserva la resolución del trabajo activo. No modifica la selección ni
acepta rutas SQLite arbitrarias. El repositorio existente ya ofrece get/list/update
parametrizados y no cambia su API/esquema.

**Edición:** incident_type (solo los siete códigos), audio_position_seconds,
document, page, selected_text, generic_description y custom_comment. Se protegen
id, created_at, updated_at, audio_filename, audio_path y exported. El repositorio
actualiza updated_at al cambiar datos; una edición sin cambios no escribe. No se
expone borrado ni cambio del booleano exported en esta capa.

**Regla editorial:** Incident centraliza componentes efectivos, completitud y
composición con separador obligatorio elegido por el consumidor. NULL/vacío/solo
whitespace no cuentan como contenido, pero se conservan exactamente en almacenamiento.
Basta uno de los dos componentes. La CLI une con salto de línea solo su vista
previa; no concatena campos persistidos ni fija el formato corporativo. exported
permanece independiente. No se implementa catálogo editorial definitivo.

**Interfaz:** incidents_cli list/get ID/edit ID, --job UUID y --json antes o
después del subcomando. Los nullable permiten cadena vacía o clear explícito a
NULL, con opciones mutuamente excluyentes. El listado es determinista por creación
e ID, con textos resumidos; get/JSON conservan todos los datos. JSON añade posición
formateada, editorially_complete y editorial_description_preview, e identifica
trabajo en cada respuesta. Fechas ISO UTC; segundos conservan binary64. La
representación editorial usa HH:MM:SS por truncamiento hacia cero, sin redondear
ni alterar los decimales almacenados o expuestos en JSON. README contiene flujo diario,
comandos de edición y ejemplos multilínea/Unicode.

**Concurrencia:** el flock existente fija trabajo y base durante lectura, edición,
validación y commit. Otra captura, revisión o selección simultánea se rechaza;
no hay nuevo bloqueo global, cola ni fallback. Las operaciones técnicas externas
que eludan JobStore no se coordinan. Fuentes mpv/Okular y modo no son requisitos
para revisar; la nueva CLI no los consulta ni cambia sus asociaciones.

**Criterios de salida:** listado vacío/ordenado, consulta completa, campos
permitidos/protegidos, nullable y Unicode preservados, timestamps/fechas correctos,
completitud independiente de exported, A/B aislados por selección y UUID, rechazos
concurrentes y JSON estable. Se añaden 57 tests de revisión y 16 del formato,
con SQLite y configuración temporales. Resultado: **560 tests superados**,
`ruff check .`, `ruff format --check .` y `git diff --check` correctos. No se
presenta esta capa como GUI de revisión terminada ni como exportación implementada.

**Integración ejecutada:** CLI en procesos independientes, dos trabajos y SQLite
reales. A contiene cuatro casos: solo genérica, solo comentario, ambos y vacío/NULL;
completitud true/true/true/false. Se editó A usando selección y también UUID mientras
B estaba activo; selección de B conservada. B permaneció lógica y byte a byte
idéntico (SHA-256 registrado). Recarga en procesos nuevos, texto exacto y precisión
binary64 verificados. Evidencia y bases en
`/tmp/audiobook-qc-review-integration-kf1hm4zq/verification.json`.
Sin cambios en configuración real o GNOME. Sin commits.

**Ajuste final de Prompt 016:** la prueba física del usuario confirmó la
precisión de 120.081537 s. Se centraliza el formato editorial en la función pura
`audio_position.format_audio_position`: HH:MM:SS sin milisegundos, truncando
hacia cero (120.999 → 00:02:00), con horas sin reinicio tras 24. La CLI técnica
de diagnóstico conserva su presentación con milisegundos. Se prueban los ejemplos
solicitados, límites de minuto/hora, más de 24/99 horas y conservación exacta
del float en SQLite/JSON. No se cambia la persistencia.

**Decisiones pendientes/límites:** el catálogo y separador definitivo de la futura
Descripción incidencia requieren el acuerdo posterior de exportación. No hay
historial/deshacer, operaciones de exported, búsqueda avanzada ni edición de la
identidad de audio. La regla implementada solo expresa preparación editorial
mínima, sin declarar listas para una plantilla desconocida las demás propiedades.

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
