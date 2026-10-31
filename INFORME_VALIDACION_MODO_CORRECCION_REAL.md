# Recuperación de fuentes y validación real del modo — Prompt 027

> Nota de publicación (cierre documental): se sustituyen rutas personales,
> identificadores de soporte, nombres de fuentes originales y la huella de
> confirmación por marcadores. Los originales de auditoría siguen fuera de Git.
> Los resultados y pendientes corresponden al momento histórico de este informe.

Fecha: 31 de octubre de 2026. **Fuentes recuperadas y ciclo real on/status/off
validado, sin capturas.** Estado final: modo inactivo y siete bindings vacíos.

## 1. Estado inicial

Repositorio en master, HEAD `32ec6e970f886915aa169939be28d3b853cea595`.
No había cambios de código; permanecía sin seguimiento el informe de ejecución
del prompt 026. Se revisaron los informes 025/026, las instrucciones del proyecto,
README/STEPS y las implementaciones de fuentes, relanzamiento y modo.

La auditoría inicial, sin modificar aplicaciones/configuraciones, confirmó:

- Siete órdenes GNOME con --desktop --hotkey F1…F7, nombres/rutas intactos.
- Registro de migración complete, coherente, sin operación pendiente.
- Journal con los comandos nuevos, F1–F7 y suspended=true; bindings GNOME vacíos.
- Modo inactivo para DISPLAY :0; custom0/Ctrl+Alt+T intactos.
- Cuatro bases SQLite v1, 13 incidencias y hashes originales.
- PRUEBA_A activo: `23acd96a-54d9-4b07-9c6b-961a943bf703`.
- Catálogo y asociaciones persistentes intactos.

Se comparó con las evidencias finales de 026, se adquirieron locks existentes
en orden journal → jobs → captura para la auditoría y se consultó SQLite en
lectura inmutable, sin sidecars. No se repitió la migración ni se ejecutó recover.

## 2. Causa diagnosticada del fallo mpv

Socket correcto por UUID:

`$XDG_RUNTIME_DIR/audiobook-qc/23acd96a-54d9-4b07-9c6b-961a943bf703.sock`

Existía como socket del usuario de la sesión, inode 880, pero rechazaba conexiones.
No había servidor ni proceso mpv dedicado a ese IPC. Por tanto, era un **socket
obsoleto de una instancia cerrada**, no una ruta asociada a otro trabajo.

El log previo termina en `Exiting... (Quit)`, compatible con un cierre normal
de la sesión anterior. No permite atribuir quién lo cerró ni la causa exacta
del quit. No se identificó un defecto de código que exigiera corregirlo.

Había otro mpv, PID 524919, con `mpv --force-window=yes ./`, sin el IPC dedicado.
Se conservó y no se intentó capturar desde él ni controlar su reproducción.

Los **38 archivos de audio asociados** seguían presentes y legibles. No se
reconstruyó, reordenó ni sustituyó la lista de capítulos.

## 3. Operaciones para recuperar las fuentes

Se utilizó una única invocación del mecanismo existente, sin argumentos de audio:

```text
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.jobs_cli launch-mpv 23acd96a-54d9-4b07-9c6b-961a943bf703
```

Resultado: salida 0, status=started, PID 574372. El adaptador retiró únicamente
el socket propio sin servidor y creó la nueva instancia en la misma ruta.
No hubo eliminación manual de sockets. Nuevo inode observado: 1164, uid del usuario de la sesión.

El comando real de mpv usa --idle=yes, --pause, --force-window=yes y el IPC por
UUID, seguido de la lista guardada de 38 rutas. Se comprobó disponibilidad por
IPC y pertenencia del archivo cargado a esa lista.

No hizo falta lanzar Okular: el adaptador ya identificaba una vista única del
PDF asociado. No se abrió un duplicado ni se cambió el documento.

Cambios operativos previstos y observados:

- Nuevo proceso dedicado y socket operativo, manteniendo la misma ruta por UUID.
- mpv.log recibió salida del proceso: de 208416 a 208749 bytes tras el arranque.
  Se conservó el log anterior como evidencia; se verificó que permanece como
  prefijo íntegro del log actualizado. La observación final fue de 208790 bytes;
  es salida añadida del proceso, no una reescritura de la asociación.
- Los controles normales publicaron/retiraron el indicador runtime y actualizaron
  el journal al reservar/suspender las teclas. Son efectos del modo, no una nueva
  migración ni cambios de asociaciones.

No se invocaron select, configure, set-pdf, set de capítulos, migrate-types,
apply ni recover. No se modificaron código, dependencias o funcionalidades.
En el repositorio solo se añade este informe; se mantienen los informes anteriores.

Evidencias persistentes de esta intervención:

`/RESPALDO_LOCAL/audiobook-qc/20261031T120038.385940Z-prompt027/`

Copia verificada en el disco independiente disponible:

`/RESPALDO_INDEPENDIENTE/audiobook-qc/20261031T120038.385940Z-prompt027/`

Incluyen manifest-initial.json, log y journal previos, resultados de las CLI,
estados activo/final y verificaciones posteriores. No se borraron respaldos o
registros anteriores. /tmp solo alojó el script operativo, no datos reales ni
respaldos definitivos.

## 4. Estado de mpv y Okular

mpv dedicado recuperado, PID 574372, responde por el IPC de PRUEBA_A.
Archivo cargado al recuperar:

`<capitulo_original.wav>`

Ruta dentro de los capítulos guardados; posición **0,0 s**, duración
**1235,785261 s**, **paused=true**. El relanzamiento comienza con el primer
archivo de la lista y no restaura automáticamente el capítulo/timestamp anterior.
No se hizo seek ni se eligió un punto de continuación editorial.

Okular existente: PID 441961, dueño D-Bus `:1.1112`, objeto `/okular`.
PDF asociado e identificado inequívocamente:

`/FUENTES_ORIGINALES/documento.pdf`

Las lecturas mostraron páginas 236 y 242 en distintos momentos. Son observaciones
del estado de la vista, no cambios de asociación. Las herramientas solo enviaron
consultas, ninguna orden de navegación. PID y dueño D-Bus son evidencia de esta
sesión, no nueva configuración persistente.

## 5. Resultado de on/status/off

Después de verificar ambas fuentes se liberaron locks externos antes de llamar
las CLI ordinarias. No se invocó una CLI sobre un lock retenido de forma incompatible.

| Operación real | Salida | Estado informado |
| --- | --- | --- |
| correction_mode status inicial | 0 | Inactivo; atajos sincronizados |
| correction_mode on --notify | 0 | Activo; atajos sincronizados |
| correction_mode status activo | 0 | Activo; atajos sincronizados |
| correction_mode off --notify | 0 | Inactivo; atajos sincronizados |
| correction_mode status final | 0 | Inactivo; atajos sincronizados |

Todas se ejecutaron con el intérprete absoluto del entorno virtual; stderr vacío.
No se observaron fallos de transporte de notificaciones, aunque no se certifica
visualmente su presentación en pantalla.

Se contrastó directamente el escritorio además de status:

- **Activo:** indicador presente, siete comandos nuevos intactos, bindings F1–F7
  y journal con esos mismos comandos/bindings y suspended=false.
- **Final:** indicador ausente, siete bindings vacíos y journal con F1–F7
  suspendidas y recuperables. Mismo registro de migración complete.

No se pulsaron atajos para registrar incidencias, ni se leyó PRIMARY como captura.
Este ciclo valida el control real de bindings/indicador/journal, no la captura
física desde teclas.

## 6. Estado final de GNOME y journal

Permanecen las siete órdenes:

```text
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F1
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F2
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F3
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F4
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F5
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F6
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F7
```

Bindings efectivos vacíos; modo inactivo. El journal conserva la correspondencia
F1→TEXT, F2→PRON, F3→DICC, F4→RUID, F5→RESP, F6→INTER, F7→OTRO a través del
catálogo y las siete combinaciones suspendidas.

La lista global, nombres/rutas y atajos ajenos permanecen intactos, incluido
custom0: `gnome-terminal --window --maximize`, `<Primary><Alt>t`.
El registro gnome-bindings.migration.json conserva contenido y metadatos; no se
reescribió, archivó ni borró. El journal solo fue actualizado por on/off normales.
Su contenido final vuelve a coincidir con el previo al ciclo, SHA-256:
`3bf6a0d1e9e8b8b39249467d93109db7a57f3fa4f761d273cb5f7d55bb7da13a`.
Su fecha de modificación cambia legítimamente al publicarlo los controles.

## 7. Conservación de bases y trabajo activo

Las cuatro bases siguen en v1 y con las mismas 13 incidencias. Lecturas mediante
mode=ro&immutable=1, sin journals auxiliares, comprobaron integridad ok y hashes
idénticos. No se migró ninguna base ni se insertó/editó una incidencia:

| UUID | Filas | SHA-256 |
| --- | --- | --- |
| `01f8269a-faf8-4a86-a360-e98afee62839` | 1 | `c2a33bd62617ddd5a4421034832b0327a1787cfa2cefa542771dc3fefc0b8fbe` |
| `23acd96a-54d9-4b07-9c6b-961a943bf703` | 3 | `08018eec302964d7ff6ed67f60b7a9b6893609f270d48d9d54f7348a2d28f87f` |
| `7de5955d-63a0-4a21-874c-b6ae7cfe52ba` | 4 | `d0732207f30e3614e0afbe40d0c739d4928a9c1e76ad172613eef8b4fdff27b9` |
| `a0a0b054-c2a1-4ca2-a845-0068ed557731` | 5 | `aecaced7ef34452666a0ce29e93d0b9f4da6a7c0b5afcf63e0691d04f7c065b4` |

jobs.json mantiene root y activo PRUEBA_A. Se conservan metadatos y asociaciones
sources.json, incluido el orden concreto de 38 audios y el PDF. Los archivos de
los demás trabajos permanecen idénticos. La única diferencia permitida dentro
de los trabajos es la salida añadida a mpv.log de PRUEBA_A.

Catálogo real intacto, siete tipos y mapa inicial:
`cd470164044e71215f87ae6b14664edb66857811c32014295db971f0f55b7e3f`.
No se cambió ninguna configuración persistente de fuentes para conseguir que
la validación pasase.

## 8. Pruebas ejecutadas

| Comprobación | Resultado |
| --- | --- |
| pytest completo | **786 passed**, 42,22 s |
| Ruff check | Correcto |
| Ruff format --check | 64 archivos correctos |
| git diff --check | Correcto |
| Relanzamiento existente y validación IPC | Correctos, lista guardada intacta |
| Resolución de vista Okular | Única y coincidente |
| Ciclo real de modo y verificación directa | Correcto, terminando off |

La suite usó configuración/datos aislados y autorización para el socket Unix
temporal de un test preexistente. No se añadió ni modificó código para hacer
pasar una operación real fallida. Las pruebas automatizadas no sustituyen las
lecturas y comprobaciones reales descritas en este informe.

Después de la batería se repitieron status y verificaciones directas: modo
inactivo, Fn vacías/suspendidas, bases/configuración/fuentes conservadas y
registro de migración intacto. mpv seguía en pausa a 0,0 s y Okular conservaba
su vista única, página 242. Evidencias: status-post-tests-call.json,
post-tests-final.json y sources-post-tests.json, en ambas copias coincidentes.

## 9. Incidencias encontradas

La incidencia operacional era el socket persistente sin servidor tras el cierre
de mpv. El mecanismo ya implementado la resolvió sin cambiar asociaciones.
No hubo fallos de on/off ni recuperación parcial de bindings; no fue necesario
repetir/revertir la migración.

El capítulo/timestamp anterior no se restaura al relanzar: quedó abierto el
primer capítulo guardado, en pausa. La elección del punto editorial donde
continuar corresponde al usuario antes de futuras capturas; no se inventó ni
automatizó una correspondencia entre página PDF y posición de audio.

Los locks y las comparaciones protegen operaciones coordinadas y detectan
cambios observados; no prometen exclusión contra escritores técnicos externos
que eludan el protocolo ni atomicidad conjunta de las fuentes.

## 10. Pruebas físicas pendientes

Queda pendiente, bajo autorización y con un trabajo de ensayo dedicado, pulsar
F1–F7 y verificar cada captura, tipo, texto, posición, documento/página, avisos,
aislamiento y comportamiento con foco ajeno. No se deben crear incidencias
ficticias en los cuatro trabajos conservados.

Antes de esas pruebas, seleccionar manualmente el contexto editorial correcto
en las aplicaciones y activar el modo deliberadamente. Este prompt termina
con modo inactivo; el mpv dedicado queda abierto en pausa y Okular se conserva.
No se da por certificada la entrega física de teclas por leer GSettings.

## 11. Veredicto

**APTO para la recuperación de fuentes y validación real controlada del modo.**
El bloqueo de disponibilidad detectado en 026 está resuelto y on/status/off
funciona con las órdenes migradas y el journal, terminando con teclas libres.
La validación de captura mediante pulsaciones permanece pendiente y fuera de
este alcance.

Sin commits ni pushes. Se detiene el trabajo para revisión antes de pruebas físicas.
