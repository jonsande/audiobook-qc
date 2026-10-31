# Validación física de F1–F7 — Prompt 028

> Nota de publicación (cierre documental): se sustituyen rutas personales,
> identificadores de soporte, nombres de fuentes originales y la huella de
> confirmación por marcadores. Los originales de auditoría siguen fuera de Git.
> Los resultados y pendientes corresponden al momento histórico de este informe.

Fecha: 31 de octubre de 2026. **Validación física completada.**
No se han simulado teclas ni ejecutado capturas CLI. Tras la confirmación del
usuario «preparado», se verificó la selección y se activó exclusivamente el
ensayo. El usuario confirmó siete avisos sin errores y se verificaron las siete
filas. **Ahora el modo está inactivo y PRUEBA_A está restaurado.** Los intentos
con foco ajeno y audio indisponible no añadieron filas. El usuario confirmó
la recuperación de F1: ayuda de Okular sin aviso de audiobook-qc.

## 1. Estado inicial

Rama master, HEAD `32ec6e970f886915aa169939be28d3b853cea595`, sin cambios
de código. Los informes de ejecución 026 y validación 027 permanecían sin
seguimiento. Se revisaron esos informes, README/STEPS, AGENTS y las CLI/adaptadores.

La auditoría real confirmó:

- Siete comandos --desktop --hotkey F1…F7, bindings vacíos y modo inactivo.
- Journal con las siete Fn suspendidas y registro de migración complete/coherente.
- Catálogo íntegro con siete tipos y mapa inicial, sin reformulaciones.
- Cuatro trabajos originales, bases v1 y 13 incidencias, hashes conservados.
- PRUEBA_A seleccionado, UUID `23acd96a-54d9-4b07-9c6b-961a943bf703`.
- Metadatos y asociaciones originales coincidentes con la evidencia anterior.

El mpv original de PRUEBA_A volvía a rechazar conexiones; no había proceso mpv
dedicado en la lista observada. Se registró esa disponibilidad operativa sin
relanzarlo, retirar su socket ni alterar sus asociaciones. No es una migración
pendiente ni impide preparar otras fuentes independientes. La instancia Okular
original, PID 441961, se conservó.

La primera lectura conjunta de fuentes originales devolvió ese error antes de
crear el ensayo. Se completó la auditoría de conservación registrándolo como
diagnóstico, sin exigir que las aplicaciones originales estuvieran abiertas
para el ensayo nuevo. No hubo corrección ni cambio de código de la aplicación.

## 2. Trabajo de ensayo

Creado mediante `jobs_cli create VALIDACION_ATAJOS_028`, en la raíz existente,
sin ejecutar configure ni reutilizar una base anterior:

- Nombre: **VALIDACION_ATAJOS_028**.
- UUID: **55dc3d89-7b1a-4343-a609-eac36d9bd1db**.
- Carpeta:
  `/RAIZ_TRABAJOS/55dc3d89-7b1a-4343-a609-eac36d9bd1db`.
- Base: `incidencias.sqlite3` dentro de esa carpeta, **esquema v2**, integridad ok,
  **0 incidencias al preparar; 7 tras la secuencia física confirmada**.
- SHA-256 de la base vacía:
  `c750cc02c12a45d69fd7bd26c2f0a96ec2cf43ded4a97feff73588ccb471fd1b`.

Se asoció solo al UUID nuevo mediante set-pdf y launch-mpv, se seleccionó
explícitamente y jobs_cli active confirmó ese destino. Después se ejecutó off
y se restauró PRUEBA_A mediante select, validando previamente su base.
La selección temporal fue autorizada por este ensayo; su raíz nunca cambió.

Se conservan el trabajo, los recursos sintéticos y las siete incidencias para
revisión. No se borró ni recreó la base.

## 3. Fuentes de prueba

Recursos independientes en `recursos_validacion/`, dentro de la carpeta del ensayo:

| Recurso | Datos |
| --- | --- |
| `validacion_028.wav` | Sintético, tono de 440 Hz, 20 s, PCM mono 16 bits, 22050 Hz, amplitud moderada y fundidos |
| `validacion_028.pdf` | Sintético, una página, texto seleccionable Helvetica, sin contenido privado |

Se generaron con biblioteca estándar, sin modificar audios/PDFs originales.
Se validaron estructura WAV y extracción del texto PDF con pdftotext, sin usar
esa extracción como sustituto de una selección manual en Okular.

Frase objetivo, en página **1**:

> Texto de prueba 028 para validar siete atajos.

Huellas de los recursos:

- PDF: `99f5933ff79547c3ba38d34605ba0befc759e6d290896f73ad42ad15ac1bf77c`.
- WAV: `f19d963708295f00a031abebbb05d765e284fb5a577c6571f76968ab3e9acc1b`.

Se usaron launch-mpv y launch-okular sobre el UUID nuevo. Instancias de ensayo
observadas: mpv PID 580424 y Okular PID 580466; son independientes del Okular
original. Vista única del PDF: dueño D-Bus `:1.2124`, página 1.
El socket dedicado es:

`$XDG_RUNTIME_DIR/audiobook-qc/55dc3d89-7b1a-4343-a609-eac36d9bd1db.sock`

La lectura real previa a las capturas confirmó `validacion_028.wav`, duración 20,0 s, posición **0,0 s**
y **paused=true**. PID/dueño son evidencia de esta sesión, no identidades que
deban persistirse. La asociación depende del UUID y las rutas sintéticas.

## 4. Secuencia física y confirmaciones del usuario

El usuario respondió **«preparado»**. La lectura PRIMARY coincidió exactamente
con la frase objetivo, sin caracteres añadidos; PDF correcto, página 1 y audio
pausado a 0,0 s. Se volvió a seleccionar el UUID de ensayo y jobs_cli active
confirmó el destino antes de on --notify. Status devolvió activo/sincronizado.
Se verificaron los siete bindings Fn y el journal con suspended=false.
La base de ensayo seguía vacía y los cuatro trabajos originales intactos.

El usuario confirmó después: **«Aparecieron los siete avisos, y no hubo ningún
error.»** Se ejecutó off, se recuperaron las filas mediante incidents_cli con
UUID explícito y se verificaron los datos completos. Los avisos visibles están
confirmados por el usuario; los tipos/IDs/destino se corroboran en SQLite, sin
afirmar haber observado personalmente la pantalla o el contenido de cada aviso.
No se leyó PRIMARY para crear una incidencia programática.

El usuario realizó las pulsaciones físicas siguiendo la secuencia F1–F7,
una vez por tecla con foco en el PDF de ensayo. Después confirmó los dos
rechazos y finalmente: **«Sí, aparece la ayuda de Okular y no aparece ningún
aviso de audiobook-qc»**, tras F1 con modo off. Las observaciones visuales de
este informe proceden de esas confirmaciones manuales.

La evidencia de preparación está en manual-readiness.json y manual-armed.json.
La secuencia principal está en user-seven-confirmation.json,
actual-seven-incidents.json y seven-verified.json. Los intentos de protección
se registran por separado y no añadieron filas. El cierre se registra en
local-f1-confirmed.json y final-physical-integrity.json.

## 5. Incidencias capturadas

Base de ensayo: **siete incidencias**, IDs 1–7. Antes de las pulsaciones estaba
vacía. Se comprobó exactamente una fila por tipo en el orden solicitado.

En todas las filas coinciden: validacion_028.wav y su ruta sintética completa,
posición 0,0 s, validacion_028.pdf y su ruta de ensayo, página 1, texto objetivo
exacto y destino exclusivo del UUID nuevo. generic_description/custom_comment
son null, exported=false y created_at=updated_at. No se editó ninguna fila.
Las cuatro bases originales conservan su contenido y hashes.

## 6. Correspondencia F1–F7

Mapa configurado, confirmación física y persistencia concordantes:

| Tecla | Tipo esperado | Registro físico |
| --- | --- | --- |
| F1 | TEXT | ID 1, verificado |
| F2 | PRON | ID 2, verificado |
| F3 | DICC | ID 3, verificado |
| F4 | RUID | ID 4, verificado |
| F5 | RESP | ID 5, verificado |
| F6 | INTER | ID 6, verificado |
| F7 | OTRO | ID 7, verificado |

Los comandos GNOME no se reescribieron y el catálogo no cambió. No se ejecutó
ninguna captura programática para rellenar esta tabla.

## 7. Pruebas de protección

Las tres comprobaciones supervisadas están verificadas:

- Foco en aplicación ajena: **verificado**. El usuario confirmó «Aparece el
  mensaje "Activación rechazada".». Tras off, las siete filas y los hashes de
  las cinco bases permanecen idénticos; las cuatro carpetas originales tampoco
  cambiaron. Evidencia: `focus-rejection-verified.json`.
- Fuente fallida: **verificada**. El usuario confirmó «Incidencia no guardada»
  y «Error de captura». La lectura posterior del socket exclusivo del ensayo
  confirmó `Connection refused`. Las siete filas y los hashes de las cinco
  bases permanecen idénticos. No cambiaron las cuatro carpetas originales.
  Evidencia: `source-failure-verified.json`.
- Off: **verificado**. Bindings Fn vacíos y journal suspendido. El usuario
  confirmó que F1 abrió la ayuda de Okular sin aviso de audiobook-qc. Las siete
  incidencias permanecen idénticas en la lectura posterior.
  Evidencia: `local-f1-confirmed.json` y `final-physical-integrity.json`.

Leer bindings vacíos o conservar el recuento cero durante la preparación no
sustituye estas pruebas. No se deshabilitaron las protecciones ni se eliminaron
filas de ensayo.
Tras verificar el rechazo, se reactivó el modo sobre el ensayo con ambas
fuentes disponibles, audio pausado a 0 s y PDF en página 1, antes de solicitar
el cierre manual de solo el mpv de `validacion_028.wav` y F2 en el PDF de ensayo.
Tras el error confirmado se ejecutó off y se restauró PRUEBA_A.
Evidencia de cierre: `safe-close-before-local-f1.json`.

## 8. Estado final de GNOME

Modo **inactivo**, siete bindings vacíos, journal con Fn suspendidas y comandos
nuevos coherentes. Registro de migración **complete**, sin reejecución/reversión.
Lista, nombres/rutas, custom0 y Ctrl+Alt+T conservados.

Se ejecutó off --notify y status antes de ceder el control; salida 0. No se
certifica visualmente el aviso de off sin confirmación del usuario.
El ensayo y sus ventanas quedaron disponibles y se restauró PRUEBA_A al cerrar
la preparación. Después de las capturas y los dos rechazos se volvió a ejecutar
**off --notify y status**, con bindings vacíos y journal suspendido verificados.
**PRUEBA_A está restaurado**, la configuración editorial permanece intacta y el
registro de migración conserva su contenido original. El mpv del ensayo queda
cerrado tras el fallo controlado; se conserva su asociación y no se borró su socket.

## 9. Conservación de los cuatro trabajos originales

Se compararon archivos/metadatos de las cuatro carpetas originales y todas sus
bases. Permanecen idénticos a la auditoría inicial de este prompt, sin mezcla:

| UUID | Esquema | Filas | SHA-256 de la base |
| --- | --- | --- | --- |
| `01f8269a-faf8-4a86-a360-e98afee62839` | 1 | 1 | `c2a33bd62617ddd5a4421034832b0327a1787cfa2cefa542771dc3fefc0b8fbe` |
| `23acd96a-54d9-4b07-9c6b-961a943bf703` | 1 | 3 | `08018eec302964d7ff6ed67f60b7a9b6893609f270d48d9d54f7348a2d28f87f` |
| `7de5955d-63a0-4a21-874c-b6ae7cfe52ba` | 1 | 4 | `d0732207f30e3614e0afbe40d0c739d4928a9c1e76ad172613eef8b4fdff27b9` |
| `a0a0b054-c2a1-4ca2-a845-0068ed557731` | 1 | 5 | `aecaced7ef34452666a0ce29e93d0b9f4da6a7c0b5afcf63e0691d04f7c065b4` |

Total original: **13**. Las cinco bases pasan integrity_check, incluidas la nueva
v2 con siete incidencias y las cuatro v1 intactas. No se ejecutaron migraciones SQLite.

El catálogo conserva siete tipos y SHA-256
`cd470164044e71215f87ae6b14664edb66857811c32014295db971f0f55b7e3f`.
Las asociaciones originales sources.json no se tocaron. jobs.json conserva la
raíz y recuperó el activo original; sus fechas de modificación pueden cambiar
legítimamente por select/restore. El único trabajo añadido es el UUID de ensayo.

## 10. Pruebas automatizadas y calidad

| Comprobación | Resultado |
| --- | --- |
| pytest completo, cierre final | **786 passed**, 42,31 s |
| Ruff check | Correcto |
| Ruff format --check | 64 archivos correctos |
| git diff --check | Correcto |
| PDF/WAV sintéticos y metadatos reales de sus fuentes | Correctos |
| Base nueva v2, fuentes y selección temporal comprobadas | Correctas |
| Conservación original y cierre seguro tras tests | Correctos |
| Secuencia física F1–F7 y siete avisos | Confirmados; siete filas verificadas |
| Protecciones físicas | Foco ajeno, fuente fallida y F1 local verificados |

Los tests usan datos aislados; el test preexistente de socket Unix requirió
ejecución autorizada fuera del sandbox. No se añadió ni modificó código de la
aplicación o tests para preparar el ensayo. No se simularon eventos de teclado.

## 11. Incidencias y limitaciones

No quedan comprobaciones pendientes dentro del alcance de este ensayo. La
validación corresponde a esta sesión GNOME/X11, los siete tipos iniciales y los
recursos sintéticos descritos. No certifica otras sesiones o visores, ni la
vigencia/procedencia de PRIMARY más allá de la selección manual contrastada.

El mpv original de PRUEBA_A estaba indisponible al inicio y no se relanzó ni se
alteró. Su selección final está restaurada y sus datos son válidos; para volver
a capturar en ese trabajo deberá disponerse de sus fuentes. El mpv del ensayo
queda cerrado por la prueba de fallo; sus recursos y asociaciones se conservan.

Los datos de auditoría están en:

`/RESPALDO_LOCAL/audiobook-qc/20261031T143840.102327Z-prompt028/`

Y su copia en el disco independiente disponible:

`/RESPALDO_INDEPENDIENTE/audiobook-qc/20261031T143840.102327Z-prompt028/`

Incluyen manifest-before.json, trial.json, resources.json, prepared-sources.json,
las llamadas CLI y verificaciones prepared-safe-handoff/post-tests-safe-handoff
y post-tests-sources. Se conservaron UUID, base y recursos para no repetir la
preparación. No se borraron respaldos ni registros anteriores.

La secuencia principal y las tres protecciones tienen confirmación manual y
verificación de persistencia. `final-physical-integrity.json` registra cinco
bases íntegras, las cuatro carpetas originales sin cambios, recursos de ensayo
intactos, configuración editorial conservada, PRUEBA_A seleccionado y modo off.

## 12. Veredicto

**APTO en el alcance del Prompt 028.**

Siete capturas físicas correctas; rechazo por foco ajeno y fallo de audio sin
escrituras; recuperación local de F1 confirmada. El modo queda off, F1–F7 libres
y PRUEBA_A restaurado. Se conservan las siete incidencias de ensayo y las 13
originales, sin mezcla entre trabajos.

Sin cambios de código, commits ni pushes. Informe entregado para revisión.
