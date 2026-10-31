# Migración de atajos GNOME — prompt 024

Fecha: 31 de octubre de 2026. Rama `master`, HEAD `407765f`.

**Migración detenida antes de modificar GNOME. Veredicto: NO APTO para ejecutarla
con el mecanismo actual bajo las restricciones del prompt 024.**

Se han completado auditoría, respaldos local e independiente, pruebas aisladas
y controles de calidad. No se ha cambiado ningún comando/binding real ni el
journal, el indicador de modo, el catálogo, los trabajos o sus bases. El bloqueo
es la coordinación de cambio de comando suspendido con el journal; no la falta
de un segundo soporte. No se ha implementado una adaptación ni debilitado la
protección existente.

## 1. Estado inicial verificado

Se revisaron los dos informes anteriores, AGENTS.md, STEPS.md, README.md y el
código relevante de catálogo, captura, CLI, almacenamiento, trabajos y control
de modo. La auditoría contrastó los archivos reales con la evidencia del prompt
023 y consultó GSettings en la sesión real, sin escribir sus ajustes.

| Elemento | Estado comprobado |
| --- | --- |
| Repositorio | master, HEAD `407765f`; dos informes anteriores sin seguimiento |
| Catálogo | `/home/jon/.config/audiobook-qc/incident_types.json`, siete tipos, mapa inicial F1–F7 |
| SHA-256 del catálogo | `cd470164044e71215f87ae6b14664edb66857811c32014295db971f0f55b7e3f` |
| Trabajos | Cuatro bases v1, 13 incidencias |
| Activo | PRUEBA_A, `23acd96a-54d9-4b07-9c6b-961a943bf703` |
| Modo para DISPLAY :0 | Inactivo, indicador ausente |
| Siete entradas propias | Comandos posicionales, bindings vacíos |
| Journal | Siete comandos posicionales, F1–F7, `suspended=true` |
| custom0 | Terminal Bob, `gnome-terminal --window --maximize`, `<Primary><Alt>t` |

No se encontraron diferencias de seguridad respecto al estado esperado de 023.
No se hizo fetch para certificar el remoto actual, commit ni push.

## 2. Diseño y secuencia examinados; condición de parada

La secuencia propuesta en 022/023 era: modo off → cambiar comandos → asignar
explícitamente F1–F7 → ejecutar on. Esa secuencia **reserva teclas con indicador
inactivo** antes de que on pueda validarlas. Era una limitación documentada en
los informes anteriores; el prompt 024 prohíbe ahora dejar ese estado incoherente.
Por tanto, no se aplicó esa receta.

El código confirma el conflicto:

1. `GSettingsShortcuts` solo expone escritura protegida de `binding`; no tiene
   una operación de migración de comandos coordinada con el journal.
2. `ShortcutMode._desired()` acepta un binding actual no vacío como confirmación
   explícita. Con binding vacío y entrada suspendida, exige que el comando actual
   coincida con el guardado; si cambió, lanza `ShortcutError`.
3. Por ello, cambiar solo command manteniendo los siete bindings vacíos hace
   fallar on antes de restaurar. Reasignar bindings manualmente para satisfacer
   `_desired()` crea precisamente el intervalo off/reservado prohibido.
4. No hay una operación existente que autorice el cambio esperado de command y
   conserve su binding suspendido en el journal sin esa confirmación manual.

Se reprodujo con backend en memoria y journal temporal real. La activación
rechazó los comandos nuevos con el diagnóstico «comando cambiado; asigna la
combinación en GNOME». La limpieza por off mantuvo modo inactivo y teclas libres,
pero pudo sustituir por vacías las combinaciones recordadas al encontrar el
comando distinto. No se ensayó ese fallo sobre el journal del usuario.

`status` con modo off comprueba que no haya bindings reservados; **no certifica
que se conserven F1–F7 recuperables en el journal**. Un status satisfactorio por
sí solo no basta para aceptar esta migración fallida.

No se usó como atajo activar primero las órdenes antiguas y cambiarlas en
caliente: esa vía no es una operación de migración soportada; deja command y
journal distintos mientras el modo está activo, y expone capturas reales.
Tampoco se llamó a un controlador con validaciones de fuentes omitidas ni a una
CLI que necesitara locks retenidos por otro procedimiento.

La parada aplica la instrucción expresa del apartado 4 del prompt 024:
si los mecanismos actuales no permiten una migración coherente sin alterar
manualmente el journal, detenerse antes de modificar GNOME y explicar el ajuste.
No es un bloqueo por falta de permisos ni una solicitud pendiente de aprobación.

### Adaptación mínima propuesta, sin implementar

Añadir una operación explícita y acotada de migración de comandos al adaptador
de escritorio/controlador, manteniendo `_desired()` y su rechazo general:

- Exigir modo off, bindings vacíos, catálogo válido y correspondencia exacta de
  rutas, nombres, comandos anteriores y entradas suspendidas del journal.
- Autorizar explícitamente solo cada conversión esperada de tipo posicional a
  `--hotkey Fn`, conservando el intérprete absoluto y el binding Fn ya guardado.
  No aceptar arbitrariamente cualquier comando cambiado como equivalente.
- Tomar locks en orden journal → trabajos → captura, sin CLI internas que
  vuelvan a adquirirlos, y comprobar ausencia de cambios concurrentes.
- Guardar respaldo y evidencia duradera de intención/progreso antes de cambiar
  command. GSettings y JSON no forman una transacción atómica; las interrupciones
  deben quedar detectables y recuperables, sin afirmar atomicidad inexistente.
- Cambiar y releer cada comando manteniendo **binding vacío**, y actualizar el
  journal mediante la operación validada, preservando Fn y suspended=true.
  No tratar una edición manual del JSON como confirmación de seguridad.
- Ante fallo/interrupción, conservar el mapa anterior y revertir selectivamente
  solo los cambios propios todavía reconocibles. No sobrescribir cambios de
  otra aplicación ni perder combinaciones durante la limpieza.
- Dejar la migración terminada en off, comandos nuevos, bindings vacíos y
  journal nuevo suspendido coherente. Después, con los locks externos liberados,
  usar las CLI normales on/status/off para la activación deliberada y validación
  de fuentes, cerrando finalmente en off.

Esto necesita implementación y tests específicos de fallos por entrada, caída
entre GSettings y journal, concurrencia y recuperación. No se implementa en este
prompt, que ordena detenerse ante esta condición. No requiere cambiar dominio,
catálogo, SQLite, selección ni fuentes.

## 3. Archivos creados o modificados

En el repositorio solo se crea `INFORME_MIGRACION_ATAJOS_GNOME.md`.
Los dos informes anteriores se conservan sin cambios como evidencia histórica.

Fuera del repositorio se crean dos directorios nuevos de respaldo, descritos
en la sección 6. Se utilizó un script operativo temporal de auditoría en `/tmp`;
no se guardaron allí datos reales ni respaldos. Las pruebas funcionales usaron
datos sintéticos temporales y backend de escritorio en memoria.

No se modificaron código, tests, README, STEPS, dependencias ni configuración
productiva. No se implementaron nuevas funciones o interfaces.

## 4. Comandos anteriores y nuevos previstos

Ruta base común de entradas:

`/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/`

Prefijo literal común de los comandos:

```text
/home/jon/prog/python/audiobook-qc/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop
```

Cada sufijo de la tabla se concatena al prefijo con un espacio. Las órdenes
actuales fueron leídas de GNOME y guardadas completas en el respaldo:

| Entrada | Sufijo actual conservado | Sufijo nuevo propuesto | Resolución inicial |
| --- | --- | --- | --- |
| audiobook-qc-text/ | TEXT | --hotkey F1 | TEXT |
| audiobook-qc-pron/ | PRON | --hotkey F2 | PRON |
| audiobook-qc-dicc/ | DICC | --hotkey F3 | DICC |
| audiobook-qc-ruid/ | RUID | --hotkey F4 | RUID |
| audiobook-qc-resp/ | RESP | --hotkey F5 | RESP |
| audiobook-qc-inter/ | INTER | --hotkey F6 | INTER |
| audiobook-qc-otro/ | OTRO | --hotkey F7 | OTRO |

Ejemplo exacto futuro para F2, **no ejecutado ni escrito en GNOME**:

```text
/home/jon/prog/python/audiobook-qc/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F2
```

No hacen falta --db, --mpv-socket ni --okular-service. El trabajo y las fuentes
se resuelven desde la selección persistente. F1–F7 se resuelven por ID lógico
del mapa JSON, no por índice del array de tipos o por fórmula.

## 5. Journal y modo de corrección

El journal real no se escribió, sustituyó, editó ni restauró. Conserva las siete
combinaciones y comandos anteriores suspendidos. El indicador runtime sigue
ausente y los bindings continúan vacíos.

No se ejecutaron on/off reales: no se cumplieron las precondiciones para la
migración y activación. La ejecución real de status se usa únicamente para
constatar el estado existente, sin presentarla como prueba de on/off.
La lectura directa del journal verifica además lo que status off no comprueba:
comandos originales y siete bindings Fn aún recuperables.

En las pruebas aisladas sí se verificaron ciclos on/off del controlador existente,
preservación del atajo ajeno y recuperación de una copia sintética después del
fallo. Ninguna prueba pulsó teclas físicas ni abrió las bases reales en escritura.

## 6. Respaldos y verificaciones

Se tomaron locks existentes en lectura mediante flock exclusivo no bloqueante,
sin crear/truncar ni reemplazar archivos: journal → jobs → cuatro locks de
captura. Se liberaron al terminar. Se comprobaron contenido y metadatos antes
y después. Las garantías son cooperativas; no protegen de escritores externos
que ignoren los locks. No se observaron diferencias concurrentes.

Respaldo local nuevo:

`/home/jon/Respaldos/audiobook-qc/20261031T091355.401748Z-prompt024-auditoria/`

Se comprobó la existencia y disponibilidad de otro dispositivo, sin presuponerla:
montaje ext4 rw de **/dev/sdb1** en
`/media/jon/4c83e6ba-02b7-4bed-b06d-97535d36b68f`, con dispositivo distinto al
que contiene la configuración original, acceso de escritura y espacio suficiente.
Se creó y verificó la segunda copia en:

`/media/jon/4c83e6ba-02b7-4bed-b06d-97535d36b68f/Respaldos/audiobook-qc/20261031T091355.401748Z-prompt024-auditoria/`

Ambas contienen copias completas de configuración y estado, incluido catálogo y
journal, y `manifest.json` con rutas, selección, hashes, permisos, uid/gid,
tamaños, mtime, atributos extendidos, entradas GSettings completas y auditoría
de bindings de sistema/extensiones. `second-copy-receipt.json` identifica las dos
rutas y la verificación de igualdad. Los registros del manifiesto de auditoría
previo a la copia independiente conservan `independent_copy=null`; el recibo
posterior es el que acredita la segunda copia realizada, sin reescribir la
instantánea inicial.

SHA-256 del manifiesto, comprobado al finalizar:
`1c29ed78b9656bd5b5e376e05238efacb8be8aee04cc5627501e8ded57329a6e`.

Se compararon contenido SHA-256 y metadatos/atributos entre originales y copias,
y entre ambos respaldos. No se hicieron copias nuevas ni restauraciones de las
bases: se inventariaron y consultaron en lectura para acreditar su conservación.
Las copias de estado pueden incluir archivos lock como evidencia; no se usarán
para restaurar/reemplazar los locks vivos.

### Conflictos de teclas y extensiones

Se leyeron los esquemas de bindings de WM, Mutter, Shell, media-keys y esquemas
instalados de extensiones. No se encontraron reservas de **F1–F7 sin modificador**
en esos valores. Sí hay Alt+F1/F2/F4/F5/F6/F7, Shift+Alt+F6, Super+F1 y bindings
de sesiones virtuales con Ctrl+Alt; no son las siete combinaciones propuestas.
No se cambió ningún valor.

Extensiones habilitadas: Desktop Icons NG (DING), Ubuntu AppIndicators y Ubuntu
Dock. Se revisaron sus puntos de teclado en el código instalado: Ubuntu Dock
registra combinaciones mediante claves de su esquema; DING maneja localmente F2
(renombrar) y F5 (actualizar) al tener el foco. Eso no equivale a una reserva
global ajena de Fn, pero recuerda que teclas globales activas desplazan usos
locales incluso si la aplicación rechaza una captura por foco.

Esta revisión estática/GSettings no demuestra entrega física de eventos ni
descarta cualquier registro dinámico de otro proceso. La prueba física queda
pendiente. Los conflictos locales conocidos de Okular siguen documentados.

## 7. Pruebas automatizadas y funcionales

| Comprobación ejecutada | Resultado |
| --- | --- |
| `.venv/bin/pytest -q -p no:cacheprovider` | **696 passed**, 31,51 s |
| `.venv/bin/ruff check --no-cache .` | Correcto |
| `.venv/bin/ruff format --check --no-cache .` | 60 archivos correctos |
| `git diff --check` | Correcto |
| Pruebas adicionales de catálogo y controlador, aisladas | Correctas; reproducen la condición de parada |

Pruebas adicionales, sin modificar catálogo real:

- F1–F7 conservan su resolución al invertir el orden de los tipos y cambiar
  todas las fórmulas genéricas.
- Añadir MUSI al principio no desplaza ninguna asociación. Asignar explícitamente
  F2 a MUSI resuelve MUSI. Esto prueba resolución, no persistencia de MUSI en v1.
- Referencia a tipo inexistente o a PRON deshabilitado en el mapa: rechazo.
- Backend simulado con siete entradas propias y terminal ajena: on/off normal
  deja estados coherentes y conserva la terminal.
- Cambiar solo los comandos suspendidos: rechazo reproducido y observación de
  la pérdida de combinaciones recordadas durante la limpieza del fallo.
- Restaurar comandos y snapshot del journal **solo sintético**: recuperación
  correcta y ciclos on/off otra vez válidos.
- Asignar F1–F7 con indicador off: status simulado señala desincronización;
  esa solución no se aplica al escritorio real.

La batería existente cubre además errores antes de fuentes/escritura, aislamiento
entre trabajos, catálogo inválido/deshabilitado y fallos de captura que no añaden
filas. No se añadieron tests al repositorio ni se cuentan los ensayos operativos
como nuevos tests de pytest. No hay evidencia de una migración productiva exitosa.

## 8. Estado final de GNOME

Las siete entradas permanecen con sus nombres/rutas/comandos posicionales
originales y binding vacío. La lista global y custom0 permanecen intactos.
Ctrl+Alt+T conserva el comando externo de la terminal Bob.

Modo inactivo para :0; siete combinaciones suspendidas en el journal, con sus
comandos originales. Ninguna tecla fue reservada, liberada o reasignada en este
prompt. No fue necesario recuperar el estado real porque no se modificó.

La CLI real `correction_mode status` terminó con salida 0 y:
`Modo de corrección inactivo; atajos sincronizados`. Se ejecutó sin locks
externos retenidos; las comparaciones posteriores confirmaron originales
idénticos y las dos copias coincidentes, también después de toda la batería.

## 9. Integridad de bases, incidencias y trabajo activo

Se consultó SQLite con URI `mode=ro&immutable=1`, bajo exclusión cooperativa,
sin sidecars WAL/SHM/journal. No se abrieron conexiones de escritura, se migró,
se inicializó ni se reconstruyó ninguna base. Integridad `ok` en las cuatro.
Los hashes coinciden con 023 y con el inventario de este prompt.

| UUID | Versión | Incidencias | SHA-256 |
| --- | --- | --- | --- |
| `01f8269a-faf8-4a86-a360-e98afee62839` | 1 | 1 | `c2a33bd62617ddd5a4421034832b0327a1787cfa2cefa542771dc3fefc0b8fbe` |
| `23acd96a-54d9-4b07-9c6b-961a943bf703` | 1 | 3 | `08018eec302964d7ff6ed67f60b7a9b6893609f270d48d9d54f7348a2d28f87f` |
| `7de5955d-63a0-4a21-874c-b6ae7cfe52ba` | 1 | 4 | `d0732207f30e3614e0afbe40d0c739d4928a9c1e76ad172613eef8b4fdff27b9` |
| `a0a0b054-c2a1-4ca2-a845-0068ed557731` | 1 | 5 | `aecaced7ef34452666a0ce29e93d0b9f4da6a7c0b5afcf63e0691d04f7c065b4` |

Total: 13 incidencias conservadas. jobs.json mantiene PRUEBA_A como activo,
su root original y el mismo contenido. Catálogo, job.json, sources.json,
mpv.log, journal y archivos lock también conservan contenido/metadatos
inventariados. No se cambió asociación alguna ni se controló mpv/Okular.

## 10. Procedimiento de recuperación

**Ahora no hay que restaurar nada.** Los originales ya están en el estado de
recuperación previsto: comandos posicionales, bindings vacíos, off, catálogo de
023 conservado y mismo active. No reemplazar archivos para simular recuperación.

Para una futura ejecución de la operación propuesta:

1. Guardar evidencia del fallo y releer modo, todas las entradas y journal.
   Identificar los cambios propios desde el respaldo inmediatamente anterior.
2. Bloquear nuevas capturas de forma controlada; off no cancela una captura ya
   iniciada. Confirmar quietud antes de recuperar, usando los locks en orden.
3. Con el alcance de recuperación autorizado, retirar el indicador/liberar solo
   bindings propios. Off puede dar recuperación parcial si cambió un comando
   suspendido: no invocarlo repetidamente sin conservar antes el journal fallido.
4. Restaurar selectivamente solo los siete comandos/bindings propios desde el
   snapshot, con bindings vacíos primero, verificando antes/después que ninguna
   entrada haya cambiado por otra intervención. No hacer resets globales ni
   modificar lista, nombres o custom0.
5. Recuperar el journal suspendido original después de restablecer comandos y
   bindings, bajo su lock y conservando antes la versión fallida. Eso es una
   restauración explícita, no editarlo para hacer aceptar comandos nuevos.
6. No restaurar locks, sockets ni indicadores activos antiguos; no tocar SQLite,
   root, active ni asociaciones. Mantener el catálogo instalado por 023.
7. Releer las siete entradas, journal, indicador y status. Además de status,
   comprobar directamente Fn y comandos guardados. Terminar off sin reactivar.

Si una entrada pertenece ahora a otra aplicación o hay cambios externos,
detener la restauración de esa entrada y conciliar manualmente. Los respaldos
de configuración/estado no autorizan restauraciones de árboles completos ni
reemplazar los originales sin comparar. Las bases no forman parte de esta
recuperación de GNOME.

## 11. Pruebas manuales pendientes con mpv/Okular

Quedan pendientes tanto la migración real como on --notify/status/off --notify
del conjunto migrado, bajo la adaptación validada propuesta. No se omitió una
prueba ya segura: no se alcanzaron sus precondiciones, por lo que se aplica la
condición de parada del prompt.

Posteriormente, y con un trabajo de ensayo dedicado/autorizado: comprobar
pulsaciones F1–F7, cambio F2 por JSON, desactivación/reactivación RESP, foco
autorizado/ajeno, avisos, correspondencia de fuentes y liberación de usos locales
al ejecutar off. No usar los cuatro trabajos reales para capturas ficticias.
Las pruebas físicas históricas no sustituyen la validación de comandos migrados.

## 12. Veredicto

**NO APTO para ejecutar la migración con los mecanismos actuales y la restricción
de no reservar F1–F7 con indicador off fuera del flujo controlado de activación.**

El catálogo y el funcionamiento normal on/off tienen pruebas correctas; la
carencia está en una migración coordinada y recuperable de comandos suspendidos.
Existe segundo soporte y las dos copias ya están verificadas: no es un bloqueo
de almacenamiento. La adaptación mínima está descrita, sin implementarla.

No se han hecho commits ni pushes. Se termina con entorno original conservado,
modo inactivo, teclas libres y la migración pendiente de revisión.
