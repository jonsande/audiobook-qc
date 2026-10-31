# Ejecución controlada de migración GNOME real — Prompt 026

> Nota de publicación (cierre documental): se sustituyen rutas personales,
> identificadores de soporte, nombres de fuentes originales y la huella de
> confirmación por marcadores. Los originales de auditoría siguen fuera de Git.
> Los resultados y pendientes corresponden al momento histórico de este informe.

Fecha: 31 de octubre de 2026. **Migración de comandos completada.**
Modo final inactivo, siete bindings vacíos y journal con los comandos nuevos y
F1–F7 suspendidas. No se añadieron incidencias ni se modificaron bases o fuentes.
La validación real de on/off queda pendiente porque mpv del trabajo no responde.

## 1. Estado inicial

Se contrastaron los informes 022–025, las instrucciones del proyecto, el código,
README/STEPS y los archivos reales con el inventario verificado del prompt 024.
Antes de escribir configuración se comprobó:

- Catálogo real intacto, siete tipos y mapa inicial F1–F7.
- Cuatro bases v1, 13 incidencias y los mismos hashes que en 023–025.
- PRUEBA_A seleccionado: `23acd96a-54d9-4b07-9c6b-961a943bf703`.
- Modo inactivo para DISPLAY :0, siete comandos posicionales y bindings vacíos.
- Journal íntegro, con esos comandos y F1–F7 suspendidas, verificado directamente.
- Ausencia de archivo o symlink `gnome-bindings.migration.json`.
- custom0 y Ctrl+Alt+T conservados.

Se adquirieron locks existentes journal → jobs → captura, con flock no bloqueante,
sin truncarlos ni reemplazarlos. No había captura coordinada en curso ni procesos
conocidos de edición de atajos/escritura de audiobook-qc. Se releían inventarios
y GSettings entre etapas para detectar modificaciones concurrentes.

Los bindings de sistema/extensiones y las extensiones habilitadas coincidían
con 024. No había reserva global de F1–F7 sin modificadores en los valores
consultados; los usos locales y las limitaciones de comprobación dinámica
siguen siendo los documentados. No se cerró ninguna aplicación.

## 2. HEAD y estado Git

Rama: `master`. HEAD:

`32ec6e970f886915aa169939be28d3b853cea595` — Implement safe GNOME shortcut command migration.

El árbol estaba limpio. El avance desde `407765f` corresponde al commit que ya
contiene la implementación y los informes de 025; no se hizo ese commit en esta
intervención. Se verificó que src/tests coincidían con HEAD y se inventariaron
sus hashes. No se modificó código para ejecutar la operación ni se hizo push.
El único archivo nuevo del repositorio en este prompt es este informe.

## 3. Ambos respaldos

Nuevo respaldo inmediatamente anterior a la migración:

`/RESPALDO_LOCAL/audiobook-qc/20261031T112138.592851Z-prompt026/`

Segunda copia independiente:

`/RESPALDO_INDEPENDIENTE/audiobook-qc/20261031T112138.592851Z-prompt026/`

Se verificó de nuevo que el segundo disco estaba montado, escribible, con espacio
suficiente y dispositivo distinto al original. Los filesystems comprobados son
ext4 rw. Las copias incluyen configuración, catálogo, jobs.json con selección,
estado/journal y snapshot completo GSettings. Las bases se inventariaron y se
consultaron en lectura; no se hicieron nuevas copias/restauraciones de SQLite
para una operación que solo afecta a comandos.

`manifest-before.json` registra contenidos, SHA-256, permisos, uid/gid, tamaños,
mtime, atributos extendidos, procesos, montajes, configuración de bindings y
huellas del código. `receipt.json` identifica ambas copias. Se compararon
contenido y metadatos de originales/copias, así como las dos copias entre sí.
Las evidencias de ejecución posteriores también se conservaron en ambas rutas.

Se mantuvo intacto el respaldo anterior del prompt 024. No se usó /tmp como
destino de datos reales ni respaldos: solo para el script operativo de etapas.
No se restauraron locks, sockets o árboles completos.

## 4. Plan y huella utilizados

La CLI real plan se ejecutó con:

```text
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.shortcut_migration_cli plan --interpreter /RUTA/AL/PROYECTO/.venv/bin/python
```

Se guardó el JSON completo, sin editar, en `plan.json` dentro de ambos respaldos.
Las siete conversiones revisadas están también en `reviewed-conversions.json`.
El snapshot incluye custom0 para comparar su conservación; **custom0 no es un
objetivo de conversión**. Solo las siete entradas propias son targets.

Token confirmado:

`<HUELLA_DEL_PLAN>`

SHA-256 del archivo plan.json:
`e93f05651c910237aa2d66f1e6c95e130ce346d6308e64d11c571c1bd19937db`.
El token usa la serialización canónica del snapshot interior; no es el hash del
JSON exterior guardado. Se revisaron nombres, rutas, órdenes exactas, bindings,+journal, catálogo y huella antes de apply.

## 5. Operación aplicada y resultado

Se ejecutó una sola vez, exclusivamente por la CLI implementada en 025:

```text
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.shortcut_migration_cli apply --interpreter /RUTA/AL/PROYECTO/.venv/bin/python --confirm <HUELLA_DEL_PLAN> --execute
```

Resultado: salida 0, phase=complete, pending=false, coherent=true, attempted
0…6 y siete rutas changed. La CLI status confirmó el mismo resultado.
`apply-call.json` y `migration-status-call.json` conservan argv, salida, stderr
y código de retorno. No hubo edición directa de journal, asignación manual de
Fn ni escrituras GSettings alternativas. No se repitió apply ni se ejecutó recover.

Se liberaron los locks externos antes de plan/apply/status: cada CLI adquirió
sus propios locks journal → jobs, sin adquisiciones incompatibles anidadas.

## 6. Registro duradero final

Se conserva, sin borrar ni archivar:

`$XDG_STATE_HOME/audiobook-qc/gnome-bindings.migration.json`

Estado complete, siete intentos registrados, snapshot anterior recuperable y
token de la sección 4. El nuevo archivo es el previsto por el protocolo; no
existía antes de esta intervención. No hay migración parcial pendiente.
Permisos del registro y del journal: 0600. SHA-256 del registro:
`bb3e7159eef3c63d9da7529e202d66881168572ff599539c6576b20e194f28d4`.

## 7. Comandos GNOME antes/después

Se conservaron nombres y rutas bajo:

`/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/`

Prefijo literal común, tanto antes como después:

```text
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop
```

A ese prefijo se agrega un espacio y el sufijo de la tabla:

| Entrada | Antes | Después | Tipo inicial |
| --- | --- | --- | --- |
| audiobook-qc-text/ | TEXT | --hotkey F1 | TEXT |
| audiobook-qc-pron/ | PRON | --hotkey F2 | PRON |
| audiobook-qc-dicc/ | DICC | --hotkey F3 | DICC |
| audiobook-qc-ruid/ | RUID | --hotkey F4 | RUID |
| audiobook-qc-resp/ | RESP | --hotkey F5 | RESP |
| audiobook-qc-inter/ | INTER | --hotkey F6 | INTER |
| audiobook-qc-otro/ | OTRO | --hotkey F7 | OTRO |

No se añadieron --db, --mpv-socket ni --okular-service. La lista global y custom0
siguen intactos: atajo de terminal ajeno, `gnome-terminal --window --maximize`, `<Primary><Alt>t`.
Las órdenes completas antes/después están en las evidencias, no solo sus sufijos.

## 8. Journal y bindings

Journal persistente:
`$XDG_STATE_HOME/audiobook-qc/gnome-bindings.json`.

Cada una de las siete entradas contiene el comando nuevo correspondiente,
binding Fn y suspended=true. Los siete bindings efectivos de GSettings permanecen
vacíos. El indicador de modo sigue ausente para :0; no hay teclas reservadas.
Se comprobaron directamente las siete combinaciones recuperables, sin depender
solo de status ordinario.
SHA-256 del journal nuevo:
`3bf6a0d1e9e8b8b39249467d93109db7a57f3fa4f761d273cb5f7d55bb7da13a`.

Cambios productivos: siete propiedades command, contenido/mtime del journal,
nuevo registro de migración y cambios de directorio necesarios para publicarlo.
Los demás archivos de estado, catálogo, selección, metadatos y trabajos se
conservaron con contenido y metadatos inventariados. No se alteraron permisos
de archivos existentes ajenos a la publicación del journal por el mecanismo.

## 9. Validación del modo corrección

Después de complete, y con locks externos liberados para las CLI ordinarias,
se hizo un preflight de fuentes de solo lectura bajo exclusión de mantenimiento.
La validación conjunta no pudo concluir por:

```text
mpv del trabajo no disponible en $XDG_RUNTIME_DIR/audiobook-qc/23acd96a-54d9-4b07-9c6b-961a943bf703.sock: [Errno 111] Connection refused
```

Conforme a la sección 6 del prompt 026, **no se ejecutaron on ni off**. No se
abrió/cerró mpv u Okular, no se eliminó el socket ni se cambió la asociación.
La migración completa se conserva y la prueba de activación queda pendiente;
la falta de disponibilidad de mpv no se presenta como fallo de los comandos.

La CLI real `correction_mode status` terminó con salida 0:
`Modo de corrección inactivo; atajos sincronizados`.
Se verificó además el journal directamente. Evidencias: sources-preflight.json,
ordinary-status-inactive-call.json y final-environment.json.

## 10. Integridad de bases, selección, catálogo y fuentes

Las cuatro bases conservan versión, contenido y hashes. Se consultaron con
mode=ro&immutable=1, sin sidecars WAL/SHM/journal, bajo bloqueo cooperativo y sin
aperturas de escritura. Integridad ok en las cuatro:

| UUID | Versión | Filas | SHA-256 |
| --- | --- | --- | --- |
| `01f8269a-faf8-4a86-a360-e98afee62839` | 1 | 1 | `c2a33bd62617ddd5a4421034832b0327a1787cfa2cefa542771dc3fefc0b8fbe` |
| `23acd96a-54d9-4b07-9c6b-961a943bf703` | 1 | 3 | `08018eec302964d7ff6ed67f60b7a9b6893609f270d48d9d54f7348a2d28f87f` |
| `7de5955d-63a0-4a21-874c-b6ae7cfe52ba` | 1 | 4 | `d0732207f30e3614e0afbe40d0c739d4928a9c1e76ad172613eef8b4fdff27b9` |
| `a0a0b054-c2a1-4ca2-a845-0068ed557731` | 1 | 5 | `aecaced7ef34452666a0ce29e93d0b9f4da6a7c0b5afcf63e0691d04f7c065b4` |

Total: 13 incidencias, ninguna nueva ni editada. La igualdad de bytes conserva
también IDs, fechas, textos, posiciones y exported. No se migró ninguna base.

jobs.json conserva root y PRUEBA_A como activo. job.json, sources.json y mpv.log
permanecen idénticos. Catálogo: siete tipos, mapa inicial y SHA-256 intactos:
`cd470164044e71215f87ae6b14664edb66857811c32014295db971f0f55b7e3f`.

## 11. Pruebas y controles de calidad

Resultados sobre el código sin cambios de HEAD:

| Comprobación | Resultado |
| --- | --- |
| pytest completo | **786 passed**, 45,58 s |
| Ruff check | Correcto |
| Ruff format --check | 64 archivos correctos |
| git diff --check | Correcto |
| Verificación real después de pytest | Comandos/journal/registro coherentes; bases, catálogo, selección y fuentes intactos; modo inactivo |

Los tests usan datos aislados; el test preexistente de socket Unix requirió
ejecución autorizada fuera del sandbox. Después de la batería se repitieron
ambos status y la comparación directa del entorno. Las evidencias
post-tests-migration-status-call.json, post-tests-ordinary-status-call.json y
post-tests-environment.json están en ambas copias verificadas.

No se pulsaron atajos físicos, no se capturó PRIMARY ni se generaron incidencias
ficticias en trabajos reales. Las evidencias de entorno son lecturas/configuración,
no una validación física de entrega de eventos de teclado.

## 12. Fallos, recuperaciones y pendientes

No hubo fallos de plan/apply/status ni recuperación de migración. No se retocó
código ni se forzó una operación real fallida. La única condición pendiente es
la disponibilidad de fuentes para probar on/status/off; mpv rechaza el IPC.

Sigue pendiente la validación física de pulsaciones en una etapa autorizada,
con trabajo de ensayo dedicado. No corresponde a este prompt ni se infiere de
tests previos o del éxito de GSettings.

## 13. Recuperación posterior

**No hay recuperación que ejecutar ahora:** el estado solicitado está alcanzado.
Para revertir posteriormente los comandos, previa revisión/autorización:

1. Conservar evidencia nueva y comparar entradas, journal, indicador y registro.
   Exigir modo off y bindings vacíos; identificar cambios externos antes de actuar.
2. Mantener intacto el registro y usar el diagnóstico de la misma CLI:

```text
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.shortcut_migration_cli status
```

3. Solo si el estado es reconocido, recuperar con el token registrado:

```text
/RUTA/AL/PROYECTO/.venv/bin/python -m audiobook_qc.shortcut_migration_cli recover --confirm <HUELLA_DEL_PLAN> --execute
```

4. Verificar rolled_back, comandos posicionales, bindings vacíos, journal con Fn
   suspendidas e indicador inactivo. Si hay diferencias externas, detenerse sin
   sobrescribirlas. Una recuperación parcial debe diagnosticarse como tal.

No ejecutar apply de nuevo ni usar off para limpiar una migración parcial.
No borrar el registro, hacer resets globales, restaurar árboles completos o tocar
bases, selección, catálogo, fuentes, locks, sockets o indicadores antiguos.
No invocar estas CLI mientras otro procedimiento retenga sus locks incompatibles.

## 14. Veredicto

**APTO CON CONDICIONES:** migración real de comandos completada y estado final
coherente, inactivo y recuperable. Las condiciones pendientes son disponibilidad
de fuentes para el ciclo on/status/off y, en otra etapa, validación física de
pulsaciones. No se consideran fallos de la conversión ya completada.

Sin commits ni pushes. Se detiene el trabajo para revisión.
