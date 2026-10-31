# Implementación de migración segura GNOME — Prompt 025

Fecha: 31 de octubre de 2026. Base: master, `407765f`. Sin commit ni push.

**Alcance:** implementación y ensayos aislados. No se ejecutó plan/apply/recover
de la nueva CLI contra GNOME real ni on/off sobre la sesión real. El journal,
catálogo, fuentes, selección y las cuatro bases productivas se conservaron.

## 1. Diagnóstico técnico

El bloqueo de 024 era correcto: `_desired()` rechaza un comando suspendido que
no coincida con el recordado, salvo confirmación por un binding actual no vacío.
Asignar ese binding manualmente reserva Fn mientras el indicador está off.
Además, la limpieza de un on fallido podía perder las combinaciones recordadas.

Se conserva `_desired()` sin cambios. Se incorpora una operación distinta,
explícita y acotada, que conserva bindings vacíos y guarda su propia intención
recuperable antes de modificar comandos. No se cambia captura, dominio, SQLite,
trabajo activo ni vinculación de fuentes.

## 2. Diseño de la operación

`CommandMigration` recibe backend mediante protocolo, journal, lector de modo y
lector de catálogo. No importa ni ejecuta GSettings concreto, mpv o Okular.
Los ensayos usan escritorio en memoria y journal/catálogo temporales.

Solo acepta los comandos canónicos generados con el intérprete absoluto original,
módulo de captura, --desktop y uno de los siete códigos. Autoriza exclusivamente:

| Anterior | Nuevo |
| --- | --- |
| TEXT | --hotkey F1 |
| PRON | --hotkey F2 |
| DICC | --hotkey F3 |
| RUID | --hotkey F4 |
| RESP | --hotkey F5 |
| INTER | --hotkey F6 |
| OTRO | --hotkey F7 |

Precondiciones: off, siete entradas propias y bindings vacíos, comandos exactos,
journal completo versión 1 con esos comandos y Fn suspendidas, catálogo válido
con mapa inicial, sin registro previo de migración. Rechaza wrappers, overrides,
entradas propias adicionales, bindings/journal inesperados y diferencias con el
snapshot confirmado. Preserva nombres/rutas y lista/atajos ajenos, incluido custom0.

CLI nueva: `shortcut_migration_cli plan/apply/status/recover`. Plan devuelve JSON
con snapshot y huella SHA-256; apply exige --execute y --confirm HUELLA y vuelve
a validar todo. Sin esas opciones no se entra en la ejecución. La huella es una
confirmación técnica del snapshot, no una autenticación frente a procesos hostiles.

La CLI toma journal.lock → jobs.lock. No abre SQLite ni necesita locks por base:
jobs.lock ya excluye las capturas de escritorio y cambios de selección de la
aplicación. No llama CLI anidadas que readquieran esos locks. El núcleo documenta
que su llamador debe mantener esta exclusión. Escritores técnicos externos deben
estar detenidos por el procedimiento de mantenimiento.

## 3. Archivos modificados

| Archivo | Cambio |
| --- | --- |
| `src/audiobook_qc/migration_state.py` | Publicación duradera privada, lectura estricta del registro, huella y detección de estado pendiente |
| `src/audiobook_qc/shortcut_migration.py` | Plan, conversión limitada, diagnóstico y recuperación con backend sustituible |
| `src/audiobook_qc/shortcut_migration_cli.py` | CLI confirmada y locking journal → jobs |
| `src/audiobook_qc/integrations/gnome_shortcuts.py` | Escritura condicionada y releída solo de command, con binding vacío |
| `src/audiobook_qc/shortcut_mode.py` | Guardia de intención pendiente antes de on/off/status; `_desired()` intacto |
| `src/audiobook_qc/correction_mode.py` | Guardia antes de validar fuentes o ejecutar el controlador en una migración pendiente |
| `tests/test_shortcut_migration.py` | Tests persistentes de protocolo, CLI, fallos, interrupciones y recuperación |
| `README.md`, `STEPS.md` | Nueva operación, sustitución de receta manual insegura para este alcance y criterios productivos pendientes |
| Este informe | Diseño, resultados y preparación del prompt 026 |

Se conservan los tres informes anteriores, sin reescribirlos ni eliminarlos.
No se añaden dependencias, GUI, exportación o soporte multiplataforma.

## 4. Protocolo de actualización y recuperación

El registro vive en `gnome-bindings.migration.json`, junto al journal:
`$XDG_STATE_HOME/audiobook-qc/`, fallback `~/.local/state/audiobook-qc/`.
Se escribe privado mediante archivo completo, fsync y publicación exclusiva
inicial; las siguientes transiciones usan reemplazo atómico y fsync del directorio.
Una actualización detectada del propio registro también detiene su sobrescritura.

El registro incluye snapshot completo de entradas, texto original del journal,
catálogo validado, intérprete, huella, fase y prefijo de intentos. No sustituye
los respaldos externos ni actúa como otra configuración editorial.

1. **prepared:** intención sincronizada antes de cualquier set.
2. **commands:** cada índice se registra y sincroniza antes de escribir su
   comando. Se releen lista, entradas, journal, catálogo y modo entre pasos.
   Nunca se escribe binding ni indicador. El registro de intento más el estado
   observado resuelven la interrupción entre set y el paso siguiente.
3. **journal:** siete comandos nuevos confirmados; se publica el journal nuevo
   conservando las siete Fn y suspended=true.
4. **complete:** comandos/journal confirmados, modo off y teclas libres. Se
   conserva el registro como evidencia; no se puede repetir apply ciegamente.

No se supone atomicidad entre GSettings y JSON. Ante fallo no se llama al off
ordinario ni se intenta ocultar el estado parcial: se conserva la intención para
status/recover. Una muerte simulada del proceso tampoco dispara una limpieza
que pueda destruir la información necesaria para recuperar.

**Recuperación explícita:** exige la misma huella, modo off y estados reconocidos.
Acepta únicamente comando anterior o nuevo previsto en cada entrada intentada y
journal anterior/nuevo permitido. Examina todo antes de modificar; revierte los
comandos nuevos en orden inverso, restaura el texto original del journal y marca
rolled_back. No reserva teclas ni restaura árboles completos. No depende de que
el catálogo actual siga válido. Cambios externos se conservan y provocan rechazo.

Un fallo de recuperación deja recovering, intentos y snapshot duraderos. El
operador puede diagnosticar y repetir recover; no se considera éxito una
recuperación parcial. Si la confirmación terminal sí llegó al disco pero falló
su fsync posterior, status permite distinguir el estado efectivamente observado.

Las fases pendientes bloquean on/off/status ordinarios antes de tocar el journal
o consultar fuentes. El diagnóstico se realiza con status de migración. Sin
intención pendiente, su comportamiento previo se conserva; un registro corrupto
también provoca rechazo conservador. Los registros terminales no se borran:
una intervención nueva requiere revisar y archivar explícitamente la evidencia,
sin eliminar automáticamente un estado parcial para conseguir que apply funcione.

## 5. Casos de prueba y resultados

Los tests persistentes verifican:

- Siete conversiones correctas con orden distinto de entradas, Fn suspendidas,
  bindings vacíos durante cada escritura y al terminar, indicador inactivo,
  nombres/rutas/lista/terminal ajena conservados y ciclo on/status/off posterior.
- Independencia de orden/fórmulas del catálogo; añadir un tipo no desplaza las
  asociaciones. Nuevos IDs en SQLite v1 siguen fuera de esta operación.
- Rechazo por modo activo, binding ocupado, comando alterado, entrada ausente,
  nombre cambiado, entrada propia adicional, journal corrupto/incompleto/con
  duplicados/incompatible y catálogo corrupto/deshabilitado/inexistente/remapeado.
- Huella distinta, plan repetido, operación parcial/repetida, falta de confirmación
  técnica, contención de locks y guardia ordinaria previa a fuentes.
- Fallo antes de cualquier set y después de cada prefijo de las siete escrituras;
  intención visible en disco antes de cada set.
- Muerte del proceso tras cada uno de los siete sets y antes/después de publicar
  journal; recuperación desde un coordinador nuevo usando solo disco y backend.
- Fallos antes/después de publicar las fases de estado, fsync real de archivo y
  directorio, recuperación fallida en cada posición e interrupciones de recuperación.
- Fallo al restaurar journal y al publicar rolled_back; cambios externos de
  command, binding, name, lista/atajo ajeno, journal, catálogo, indicador y registro.
  Una recuperación no sobrescribe silenciosamente esos cambios.
- Escritura limitada del adaptador, rechazo de binding ocupado/cambio previo,
  readback no confirmado, registros/symlinks inválidos y preservación exacta del
  texto original del journal aunque tuviera otro formato JSON.

Las pruebas preexistentes de captura/destino siguen cubriendo errores sin altas
parciales ni escrituras en otros trabajos. La migración no contiene acceso a
repositorios SQLite ni a adaptadores de captura.

## 6. Número total de tests y calidad

Se añaden **90 tests**, conservando los **696 anteriores**: total **786**.
La ejecución final completa terminó con **786 passed en 47,15 s**.
`ruff check .`, `ruff format --check .` (64 archivos) y `git diff --check`
terminaron correctamente. La suite necesita permiso para el socket Unix temporal
de un test preexistente: el sandbox puede bloquear su bind. Eso no autoriza ni
ejecuta GSettings real desde los tests.

## 7. Evidencias de conservación del entorno real

Se realizó una comprobación explícita de solo lectura con locks existentes
journal → jobs → captura, contra el inventario del prompt 024:

`/home/jon/Respaldos/audiobook-qc/20261031T091355.401748Z-prompt024-auditoria/manifest.json`

Se compararon todos los árboles de configuración, estado y trabajos, incluidos
hashes, tamaños, propietarios, permisos, mtime y atributos extendidos. También
las entradas GSettings completas. No se crearon respaldos o registros nuevos en
el entorno real durante esta implementación.

| Trabajo (UUID) | v | Filas | Integridad | SHA-256 conservado |
| --- | --- | --- | --- | --- |
| `01f8269a-faf8-4a86-a360-e98afee62839` | 1 | 1 | ok | `c2a33bd62617ddd5a4421034832b0327a1787cfa2cefa542771dc3fefc0b8fbe` |
| `23acd96a-54d9-4b07-9c6b-961a943bf703` | 1 | 3 | ok | `08018eec302964d7ff6ed67f60b7a9b6893609f270d48d9d54f7348a2d28f87f` |
| `7de5955d-63a0-4a21-874c-b6ae7cfe52ba` | 1 | 4 | ok | `d0732207f30e3614e0afbe40d0c739d4928a9c1e76ad172613eef8b4fdff27b9` |
| `a0a0b054-c2a1-4ca2-a845-0068ed557731` | 1 | 5 | ok | `aecaced7ef34452666a0ce29e93d0b9f4da6a7c0b5afcf63e0691d04f7c065b4` |

SQLite se consultó con mode=ro&immutable=1 y sin sidecars, sin recuperación ni
apertura de escritura. Total 13 incidencias intactas. jobs.json conserva PRUEBA_A,
UUID `23acd96a-54d9-4b07-9c6b-961a943bf703`. Se conservaron sources.json y logs.

Catálogo real: siete tipos; SHA-256
`cd470164044e71215f87ae6b14664edb66857811c32014295db971f0f55b7e3f`.
GNOME conserva las siete órdenes posicionales, bindings vacíos y custom0 intacto;
el journal mantiene Fn suspendidas y el indicador sigue inactivo. **No existe
gnome-bindings.migration.json real**, lo que confirma que no se ejecutó apply.
No se invocaron on/off reales, ni se consultó PRIMARY ni controló mpv/Okular.

## 8. Instrucciones para una migración real posterior

Estos pasos pertenecen al prompt 026 autorizado; no se ejecutan ahora:

1. Repetir auditoría y confirmar código revisado, catálogo/mapa inicial, estado
   off, bindings vacíos y journal esperado. Detenerse ante diferencias.
2. Acordar ventana sin escritores técnicos/editores GNOME/JSON y revisar conflictos
   de sistema/extensiones. Guardar respaldos inmediatamente anteriores, local e
   independiente, con contenido y metadatos verificados como en 024.
3. Usar los comandos plan/apply/status documentados en README, con intérprete
   `/home/jon/prog/python/audiobook-qc/.venv/bin/python`. Guardar el JSON de plan
   en un archivo nuevo del respaldo persistente y revisarlo. Extraer su token;
   apply exige `--interpreter RUTA --confirm TOKEN --execute`.
4. Comprobar phase=complete, pending=false, siete changed, journal nuevo con Fn
   suspendidas, indicador off y bindings vacíos. No asignar Fn manualmente.
5. Ante error, conservar intención y diagnosticar con
   `python -m audiobook_qc.shortcut_migration_cli status`. Recuperar solo con
   `recover --confirm TOKEN --execute`, respetando rechazos por cambios externos.
6. Solo tras complete y verificación de fuentes asociadas existentes, con locks
   externos liberados, ejecutar `correction_mode on --notify`, `status` y
   `off --notify`. Terminar inactivo y sin bindings. Si faltan fuentes, detenerse;
   no abrir/cerrar aplicaciones ni insertar pruebas en trabajos reales para
   forzar que esta comprobación pase.
7. Recomparar bases, active, catálogo, fuentes, comandos, journal y atajos ajenos.
   Preservar informes, registros y resultados. Las pruebas físicas se realizarán
   después con alcance y trabajos de ensayo expresamente autorizados.

Si se quiere volver a órdenes posicionales tras complete, primero modo off y
binding vacío, después recover confirmado. Se conserva el catálogo instalado
por 023; no hace falta restaurar bases ni selección.

## 9. Riesgos residuales

- GSettings no ofrece compare-and-swap ni una transacción conjunta con el journal.
  Las relecturas detectan cambios observados; no garantizan exclusión contra
  editores no cooperativos en el intervalo lectura/set o lectura/reemplazo.
  Se exige la ventana sin escritores externos. Un cambio externo exactamente
  igual a los bytes esperados es indistinguible de nuestra escritura.
- fsync/reemplazo/flock requieren filesystem local con esas garantías. Un fallo
  físico de disco puede impedir persistir intención o recuperación; se necesitan
  copias verificadas y detenerse ante fallos de almacenamiento.
- Modo inesperadamente activo o estado externo desconocido bloquea recuperación;
  no se fuerza ni sobrescribe para conseguir una apariencia de éxito.
- El snapshot del plan/registro no sustituye backups en soporte independiente.
  Los tokens son comprobaciones técnicas, no protección frente a manipulación
  deliberada de archivos por procesos del mismo usuario.
- Pruebas simuladas y lecturas de configuración no prueban entrega física de
  teclas, notificaciones visibles ni conectividad de fuentes reales. Pendiente
  validación productiva y física posterior según el alcance autorizado.

## 10. Veredicto para el prompt 026

**APTO CON CONDICIONES** para una ejecución posterior revisada: auditoría y
respaldos nuevos, exclusión de escritores externos y las comprobaciones de
almacenamiento/sesión descritas. La implementación resuelve el bloqueo lógico
de 024 sin reservar Fn ni relajar `_desired()`; no se da por ejecutada la
migración real ni por completada la validación física.

Se detiene el trabajo para revisión. Sin commits ni pushes.
