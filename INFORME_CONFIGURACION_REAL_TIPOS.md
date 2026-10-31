# Configuración persistente real de tipos — prompt 023

Fecha: 31 de octubre de 2026. Código: `407765f`, rama `master`.

**Resultado: APTO para la etapa de configuración.** Se ha instalado y verificado
el catálogo real. No se han migrado bases, cambiado el trabajo activo, alterado
fuentes ni modificado/activado/desactivado atajos o modo de corrección.
La integración de GNOME queda propuesta, sin ejecutar.

## 1. Estado inicial encontrado

Se revisaron íntegramente el informe del prompt 022, las instrucciones del
proyecto y las secciones relevantes de STEPS/README. Se contrastaron las rutas,
el recurso JSON y los mecanismos de instalación/carga/captura/persistencia.

- Rama master, HEAD `407765f`, coincidente con la referencia local origin/master.
  No se hizo fetch, commit ni push.
- El único archivo pendiente inicial era INFORME_MIGRACION_ENTORNO_REAL.md,
  sin seguimiento. Se conserva como evidencia histórica, sin modificarlo.
- XDG_CONFIG_HOME y XDG_STATE_HOME ausentes: se utilizan los fallbacks del código.
- `incident_types.json` ausente, sin enlace simbólico en su lugar ni antecesores
  simbólicos en los árboles inventariados.
- Cuatro trabajos, con bases v1 y 13 incidencias en total.
- Activo: `23acd96a-54d9-4b07-9c6b-961a943bf703`, PRUEBA_A.
- Indicador de modo para DISPLAY `:0` ausente; no se ejecutó on/off/status.
- Las siete entradas GNOME conservaban tipos posicionales y bindings vacíos.
  Su journal conservaba F1–F7 suspendidas. Ctrl+Alt+T seguía perteneciendo a
  la terminal Bob, ajena al proyecto.

## 2. Archivos creados o modificados y seguridad aplicada

Se ejecutó el mecanismo existente, en un proceso nuevo:

```bash
/home/jon/prog/python/audiobook-qc/.venv/bin/python -m audiobook_qc.types_cli init --json
```

No se implementó otro mecanismo de configuración. El instalador publica el
recurso completo por enlace exclusivo y rechaza archivo o symlink existente;
no hubo sobrescritura ni incompatibilidad. Se comprobó ausencia antes de actuar.

Antes de instalar se tomaron los locks **existentes**, en lectura y sin
truncarlos, mediante flock exclusivo no bloqueante: journal → jobs → los cuatro
locks de captura. Cualquier error habría detenido el procedimiento. Se mantuvo
la exclusión hasta la verificación posterior, liberándola al terminar. No se
abrieron bases reales en escritura ni se invocaron CLI de selección de trabajo.

Se creó y verificó un respaldo persistente en:

`/home/jon/Respaldos/audiobook-qc/20261031T090123.359996Z-prompt023/`

Contiene:

- `config/`, `state/`, `jobs/`: copias completas previas con `cp -a`.
- `manifest-before.json`: rutas, inventario, SHA-256, tamaños, permisos,
  propietarios, fechas de modificación y atributos extendidos; selección,
  versión del código, estado de modo y todas las entradas GNOME.
- `installed-incident_types.json`: copia de verificación del catálogo instalado.
- `verification-after.json`: resultados de conservación e integridad.

Se compararon originales antes/después y copias, incluidos atributos extendidos.
No había sidecars WAL/SHM/journal. La integridad SQLite se consultó en las copias
verificadas mediante lectura inmutable; los originales permanecieron cerrados
para SQLite. El contenido completo de los árboles anteriores se conservó.

Los únicos cambios persistentes autorizados fueron el nuevo catálogo y estos
archivos de respaldo. En el repositorio se añade este informe. No se cambió
código, tests, dependencias, README ni STEPS; no se completó ninguna fase adicional.
Se usó un script operativo temporal en `/tmp` para coordinar comprobaciones,
sin guardar allí datos reales ni respaldos. Los datos funcionales temporales
eran exclusivamente sintéticos.

**Ajuste de alcance respecto al informe 022:** no se ejecutó su secuencia completa
de migración/activación ni el ensayo de migración de bases reales copiadas, pues
esta etapa solo añade un archivo de forma exclusiva. Se hizo un respaldo local
verificado; no se creó una segunda copia en soporte independiente, cuyo destino
no está definido. Este respaldo no protege de fallo del disco. Esa segunda copia
sigue pendiente antes de operaciones destructivas/restauraciones o integración
posterior que la requiera. No se eludió una sobrescritura: ninguna fue necesaria.

## 3. Ubicación definitiva y contenido

Archivo: `/home/jon/.config/audiobook-qc/incident_types.json`.

Permisos: **0600**, propietario jon; directorio existente **0700**. Se añadió el
archivo sin cambiar permisos de otros elementos. Su ubicación es persistente,
fuera de runtime y `/tmp`; el usuario puede editarlo posteriormente.

SHA-256:

`cd470164044e71215f87ae6b14664edb66857811c32014295db971f0f55b7e3f`

El esquema existente es `version: 1`, `types` y `hotkeys`. En cada tipo se usan
`id`, `label`, `enabled` y `default_generic_description`. Todos están habilitados:

| ID | Etiqueta | Fórmula exacta | Atajo lógico |
| --- | --- | --- | --- |
| TEXT | Texto | null | F1 |
| PRON | Pronunciación | Revisar pronunciación. | F2 |
| DICC | Dicción | Revisar dicción. | F3 |
| RUID | Ruido | Ruido. | F4 |
| RESP | Respiración | Respiración. | F5 |
| INTER | Entonación | Revisar entonación. | F6 |
| OTRO | Otro | null | F7 |

`null` representa ausencia de fórmula. Capturar sigue dejando la genérica vacía;
instalar el catálogo no rellena textos históricos. Aplicar fórmula es una edición
explícita. El catálogo adicional descriptions.json se conserva exactamente.

Para futuras modificaciones: editar el documento completo, preferiblemente con
reemplazo atómico, y validar. Labels/fórmulas son editables; se pueden añadir tipos.
Para deshabilitar un tipo hay que desasignar también sus hotkeys en el mismo
guardado. No reutilizar ni renombrar IDs históricos para otro concepto.
Los IDs nuevos requieren v2 en las bases donde se quieran guardar; no se han
migrado las cuatro bases v1 por anticipado.

## 4. Comprobaciones de compatibilidad

- Carga de los siete tipos reales y comparación exacta de fórmulas, null,
  habilitación y F1–F7 con los valores solicitados.
- `types_cli list`, `validate` y `hotkeys` en procesos separados después de init:
  la configuración se recarga del archivo persistente, sin depender del proceso
  instalador. Validación final: `valid=true`, `count=7`.
- Prueba funcional con copia del catálogo en XDG aislado: captura con el
  coordinador existente y fuentes simuladas, guardado mediante el caso de uso
  existente y repositorio SQLite real temporal, para los siete tipos.
- Se repitió en esquema **v1 y v2**, sin migrar los originales: 14 incidencias
  sintéticas en total. Se verificaron IDs recuperables, tipo, texto Unicode con
  espacios/salto, posición `120.081537`, documento/página y genérica inicialmente
  vacía. La reapertura del repositorio conservó todas las entidades exactamente.
- Las cinco fórmulas se aplicaron con el mecanismo existente y coincidieron
  exactamente. TEXT/OTRO rechazaron una fórmula inexistente sin alterar la fila.
- En una configuración solo de ensayo, RESP se deshabilitó y F5 se desasignó:
  nuevas capturas fueron rechazadas; el histórico permaneció idéntico y legible.
- Un proceso CLI nuevo recuperó una incidencia sintética desde cada base.
  Ambas bases temporales conservaron su versión e integridad `ok`.

Los tests existentes cubren además alta de tipos, reforma de fórmulas/labels,
reactivación y lectura histórica de IDs retirados. No se consultó PRIMARY ni se
controlaron mpv/Okular reales durante estas pruebas.

La supervivencia se comprobó entre procesos nuevos. No se reinició la sesión
gráfica ni el equipo: la persistencia entre sesiones se apoya en el archivo
regular bajo ~/.config, no en estado runtime.

## 5. Resultado de las pruebas

| Comprobación | Resultado |
| --- | --- |
| `.venv/bin/pytest -q -p no:cacheprovider` | **696 passed**, 29,79 s |
| `.venv/bin/ruff check --no-cache .` | Correcto |
| `.venv/bin/ruff format --check --no-cache .` | 60 archivos correctos |
| `git diff --check` | Correcto |
| Prueba funcional adicional v1/v2 aislada | Correcta |
| Recarga del catálogo real en procesos nuevos | Correcta |
| Comparación final de árboles reales con manifiesto | Correcta, salvo incorporación prevista del catálogo |

No fue necesario ajustar código ni añadir tests al repositorio. Los ensayos
operativos adicionales no se contabilizan como nuevos tests de pytest.

## 6. Conservación de bases, historial y trabajo activo

SHA-256 idéntico antes de instalar, después de instalar y en la comprobación
posterior a las pruebas. Se comprobaron todos los archivos previos de trabajos,
configuración y estado, con sus metadatos y atributos. Solo se exceptuaron el
nuevo catálogo y la fecha del directorio que necesariamente cambia al añadirlo.

| Trabajo | Versión | Filas | sqlite_sequence | SHA-256 de la base |
| --- | --- | --- | --- | --- |
| PRUEBA_B (`01f8269a…`) | 1 | 1 | 1 | `c2a33bd62617ddd5a4421034832b0327a1787cfa2cefa542771dc3fefc0b8fbe` |
| PRUEBA_A (`23acd96a…`) | 1 | 3 | 3 | `08018eec302964d7ff6ed67f60b7a9b6893609f270d48d9d54f7348a2d28f87f` |
| Prueba_trabajo_B (`7de5955d…`) | 1 | 4 | 4 | `d0732207f30e3614e0afbe40d0c739d4928a9c1e76ad172613eef8b4fdff27b9` |
| Espinas_en_el_aire_PRUEBA (`a0a0b054…`) | 1 | 5 | 5 | `aecaced7ef34452666a0ce29e93d0b9f4da6a7c0b5afcf63e0691d04f7c065b4` |

Cada copia exacta pasó `PRAGMA integrity_check` con resultado `ok`. El manifiesto
guarda además una huella de todas las columnas/filas y la secuencia. La igualdad
de bytes de los originales con esas copias permite verificar conservación e
integridad sin abrir los originales para operaciones SQLite. No hubo cambios
en incidencias, fechas, tipos, texto, comentarios, posiciones ni exported.

jobs.json permanece idéntico, con el mismo root y activo:
`23acd96a-54d9-4b07-9c6b-961a943bf703` (PRUEBA_A).
También permanecen idénticos job.json, sources.json, mpv.log y journal/locks.
No se iniciaron ni cerraron procesos de mpv/Okular, ni se cambiaron vínculos.

La instantánea GSettings anterior y posterior a la instalación coincide en
lista, nombres, comandos y bindings. Las pruebas automáticas posteriores usan
adaptadores sustituidos; no escriben GNOME. El modo continúa inactivo para :0.

Los locks son cooperativos: no impiden un escritor técnico externo que los
eluda. No se observaron diferencias concurrentes en los inventarios. Esta etapa
no constituye una prueba de conectividad de las fuentes ni de pulsaciones reales.

## 7. Propuesta precisa para migrar GNOME — NO EJECUTADA

Cada ruta está bajo:

`/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/`

Los comandos actuales comparten este prefijo literal:

```text
/home/jon/prog/python/audiobook-qc/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop
```

El sufijo actual y el propuesto se concatenan con un espacio a ese prefijo:

| Entrada | Sufijo actual | Sufijo propuesto | Binding actual | Binding futuro |
| --- | --- | --- | --- | --- |
| audiobook-qc-text/ | TEXT | --hotkey F1 | vacío | F1 |
| audiobook-qc-pron/ | PRON | --hotkey F2 | vacío | F2 |
| audiobook-qc-dicc/ | DICC | --hotkey F3 | vacío | F3 |
| audiobook-qc-ruid/ | RUID | --hotkey F4 | vacío | F4 |
| audiobook-qc-resp/ | RESP | --hotkey F5 | vacío | F5 |
| audiobook-qc-inter/ | INTER | --hotkey F6 | vacío | F6 |
| audiobook-qc-otro/ | OTRO | --hotkey F7 | vacío | F7 |

Las siete órdenes completas que se propondrán para las entradas son:

```text
/home/jon/prog/python/audiobook-qc/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F1
/home/jon/prog/python/audiobook-qc/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F2
/home/jon/prog/python/audiobook-qc/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F3
/home/jon/prog/python/audiobook-qc/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F4
/home/jon/prog/python/audiobook-qc/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F5
/home/jon/prog/python/audiobook-qc/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F6
/home/jon/prog/python/audiobook-qc/.venv/bin/python -m audiobook_qc.capture_save_probe --desktop --hotkey F7
```

No añadir --db, --mpv-socket o --okular-service. El tipo posicional funciona
ahora con el catálogo instalado, pero no sigue reasignaciones hotkeys del JSON.
Estas órdenes sí las resolverán en cada ejecución. F1–F7 dentro del JSON son
identificadores lógicos, no reservan ninguna tecla GNOME por sí solos.

Procedimiento futuro, sujeto a revisión y autorización:

1. Releer configuración, modo, todas las entradas GNOME y journal. Confirmar
   que siguen coincidiendo con el estado aquí registrado; si difieren, detenerse.
2. Guardar un respaldo nuevo inmediatamente anterior al cambio, incluida la
   configuración ya instalada y GSettings completo; verificarlo y preparar
   segunda copia independiente. Usar la exclusión y condiciones del informe 022.
3. Con modo off y sin escritores concurrentes, mantener nombres, lista global y
   custom0 intactos. Sustituir solo los siete comandos, uno por uno, verificando
   cada lectura. Detenerse ante el primer error.
4. Comprobar conflictos de sistema/extensiones. Reasignar expresamente F1–F7:
   el journal suspendido conserva los comandos antiguos y rechazará una
   restauración automática tras cambiar command sin confirmar binding nuevo.
   No editar el journal para eludir esta protección. La reserva de teclas
   comienza al asignar bindings aunque el indicador siga off.
5. Validar catálogo, mismo active y fuentes existentes. Si faltan fuentes,
   detenerse; no abrir/cerrar mpv/Okular automáticamente. Liberar locks manuales
   antes de invocar las CLI de modo que los adquieren internamente.
6. Activación deliberada con `correction_mode on --notify`, verificación de
   status, siete comandos/bindings, journal y preservación de Ctrl+Alt+T.
   Preparar pruebas físicas aisladas con alcance autorizado; no insertar
   incidencias ficticias en los trabajos reales. Una activación fallida puede
   dejar recuperación parcial: verificar, no asumir reversión completa.

Recuperación futura de GNOME: conservar primero evidencia del fallo y de
cualquier dato nuevo. Con autorización de recuperación, desactivar modo y
liberar solo bindings propios; si off falla, revisar manualmente. Restaurar
únicamente las propiedades de las siete entradas desde el respaldo inmediato,
con bindings vacíos primero, sin resets globales ni tocar custom0. Restaurar
journal después de comandos/bindings y bajo su lock, conservando el fallido.
Revisar diferencias externas antes de sobrescribir. No restaurar locks,
sockets ni indicador activo de otra sesión.

Para volver al estado registrado aquí: comandos posicionales, siete bindings
vacíos, journal suspendido y modo off. **Conservar el catálogo instalado por
023**; revertir GNOME no exige retirarlo ni restaurar bases. Comprobar root,
active, hashes y atajos ajenos; no activar automáticamente al finalizar.

Recuperación específica de esta etapa: no se necesita ejecutar ninguna ahora.
Si se revoca la instalación, preservar el catálogo actual en una ruta nueva
persistente antes de retirarlo de configuración y comprobar ausencia original.
No restaurar árboles completos ni bases que siguen intactos. Cualquier retirada
o restauración posterior requiere autorización y revisión del estado de ese momento.

## 8. Veredicto final

**APTO para la configuración persistente de tipos del prompt 023.**

El catálogo queda instalado, editable y validado; las cuatro bases v1,
sus 13 incidencias, la selección y las asociaciones permanecen intactas.
La batería completa y las pruebas funcionales aisladas son correctas.

GNOME sigue pendiente de migración y activación controlada. No se declara
terminada esa integración ni se han comprobado pulsaciones físicas en esta etapa.
No se han hecho commits ni pushes. Se detiene el trabajo para revisión.
