# Preparación segura de la integración real — prompt 022

Fecha: 30 de octubre de 2026. Código auditado: `407765f`, rama `master`.

**Propuesta para revisión. No se ha ejecutado la integración.** Los comandos de
este informe son instrucciones futuras. El único archivo añadido al repositorio
es este informe: no se ha cambiado código ni hecho commit/push.

## 1. Diagnóstico del estado actual

### Hechos comprobados

- Árbol inicialmente limpio; HEAD coincide con la referencia local origin/master.
  No se hizo fetch: no se certifica el estado remoto actual.
- Ubuntu 22.04.5; sesión declarada X11, DISPLAY `:0`, runtime `/run/user/1000`.
  GNOME 42.9 procede de la confirmación del usuario/documentación anterior;
  no se volvió a consultar su versión.
- `.venv/bin/python` importa el paquete desde el `src/` de este repositorio.
- **696 tests superados en esta auditoría (28,43 s)**. Ruff lint, Ruff format
  (60 archivos) y git diff --check correctos. Los tests aíslan XDG/SQLite y
  sustituyen las fuentes de escritorio; no prueban pulsaciones físicas reales.
- Los 17 bloques Bash del procedimiento y sus fragmentos Python pasan análisis
  de sintaxis sin ejecutarse. La copia, restauración y activación propuestas
  quedan pendientes de ensayo operativo; la sintaxis no certifica su ejecución.
- XDG_CONFIG_HOME y XDG_STATE_HOME están ausentes en el proceso de auditoría.

| Elemento | Ubicación o estado observado |
| --- | --- |
| Configuración | `/home/jon/.config/audiobook-qc/` |
| Registro de trabajos | `jobs.json`, versión 1 |
| Raíz | `/home/jon/Documentos/correcciones/bocachica/audiobook-qc/trabajos` |
| Activo | `23acd96a-54d9-4b07-9c6b-961a943bf703` (PRUEBA_A) |
| Catálogo nuevo | `incident_types.json` **ausente** |
| Descripciones adicionales | `descriptions.json`, una frase provisional PRON |
| Estado persistente | `/home/jon/.local/state/audiobook-qc/gnome-bindings.json` |
| Indicador para :0 | `/run/user/1000/audiobook-qc/correction-19e89348f2a9d5f3.active`, **ausente** |

Hay cuatro trabajos. Sus nombres de prueba no autorizan a descartarlos.

| UUID | Nombre | Esquema observado | Incidencias observadas |
| --- | --- | --- | --- |
| `01f8269a-faf8-4a86-a360-e98afee62839` | PRUEBA_B | 1 | 1 |
| `23acd96a-54d9-4b07-9c6b-961a943bf703` | PRUEBA_A | 1 | 3 |
| `7de5955d-63a0-4a21-874c-b6ae7cfe52ba` | Prueba_trabajo_B | 1 | 4 |
| `a0a0b054-c2a1-4ca2-a845-0068ed557731` | Espinas_en_el_aire_PRUEBA | 1 | 5 |

Las lecturas SQLite usaron `mode=ro&immutable=1`, sin creación de journals ni
recuperación. No había sidecars WAL/SHM/journal en el inventario. Los recuentos
son **observaciones provisionales**: no se bloquearon escritores, por lo que no
son una instantánea transaccional certificada. La validación definitiva debe
hacerse sobre copias tomadas durante una ventana sin escrituras.

Los dos primeros trabajos tienen sources.json y mpv.log; los otros dos no
tienen asociación persistente de fuentes. No debe creársela como efecto
secundario de esta integración.

Permisos observados: configuración/estado y carpetas de cada trabajo 0700;
raíz de trabajos 0775; bases 0644; jobs.json, job.json, sources.json y journal
0600; descriptions.json y locks 0664. Las carpetas privadas limitan el acceso
a los archivos interiores. No se cambió ningún permiso.

La consulta de GNOME fuera del sandbox, autorizada, confirmó:

- Siete entradas `audiobook-qc-{text,pron,dicc,ruid,resp,inter,otro}`.
- Comandos `.../.venv/bin/python -m audiobook_qc.capture_save_probe --desktop
  TIPO`, con **tipo posicional**. Todos tienen binding vacío.
- Journal con F1–F7 en el orden solicitado, suspended=true y los mismos
  comandos posicionales. Es coherente con las entradas suspendidas.
- custom0 conserva `gnome-terminal --window --maximize` y `<Primary><Alt>t`.
- Hay mpv (`--force-window=yes ./`) y Okular abiertos. No se inició, cerró,
  pausó ni controló ninguno. Un proceso abierto o un socket presente no
  demuestran que esté disponible el socket por UUID del trabajo activo.

### Funcionamiento del código y archivos anteriores

[jobs.py](src/audiobook_qc/jobs.py) determina la ubicación desde jobs.json,
con root absoluto y active UUID/null. No existe raíz de trabajos predeterminada.
Cada trabajo contiene job.json e incidencias.sqlite3. `configure` con otra raíz
borra la selección y no mueve datos; select/clear escriben active.

`JobStore.destination()` mantiene jobs.lock desde resolución hasta commit.
Abre una base existente con mode=rw, verifica acceso/columnas/versión y no
recrea una base desaparecida. Incluso consultas jobs_cli config/list/get/active
e incidents_cli list/get toman locks que pueden crear archivos/directorios.
`correction_mode status` también toma el lock del journal. No se usaron estas
CLI como auditoría estrictamente pasiva.

[type_config.py](src/audiobook_qc/type_config.py) lee un JSON versionado estricto
en XDG_CONFIG_HOME/audiobook-qc/incident_types.json, fallback a ~/.config con
variable ausente/vacía. Rechaza XDG relativo. `types_cli init` publica el recurso
completo mediante enlace exclusivo, con archivo privado y sin sobrescribir
archivo o symlink existente. Archivo ausente/corrupto impide capturar incluso
con tipo posicional; no existe catálogo de respaldo implícito.

[capture_save_probe.py](src/audiobook_qc/capture_save_probe.py) resuelve
`--hotkey F1` a F7 una vez desde la configuración. Hotkey y tipo posicional son
excluyentes. Escritorio requiere modo activo, foco mpv/Okular, trabajo válido y
fuentes coherentes. Rechaza overrides de socket/servicio y un --db diferente
del trabajo seleccionado. Captura usa jobs.lock y el lock por base.

[gnome_shortcuts.py](src/audiobook_qc/integrations/gnome_shortcuts.py) reconoce
como propias órdenes que comienzan con intérprete Python, `-m`, módulo de
captura y contienen --desktop; wrappers/env/scripts pueden no reconocerse.
Solo escribe binding: **no registra entradas ni cambia comandos, nombres o
lista global**. Esas operaciones son manuales o GSettings explícito.

[shortcut_mode.py](src/audiobook_qc/shortcut_mode.py): off retira primero el
indicador, guarda combinaciones y libera bindings propios. On restaura y
verifica antes de activar. Cambiar un comando suspendido exige reasignar su
binding deliberadamente; no se debe editar el journal para eludirlo.
El journal no es un backup completo: no guarda nombres ni la lista global.
[correction_mode.py](src/audiobook_qc/correction_mode.py) valida además fuentes
antes de on y no abre mpv/Okular automáticamente.

Orden de locks compatible con mantenimiento: gnome-bindings.lock → jobs.lock →
locks de captura. Son flock exclusivos no bloqueantes. No protegen frente a
editores JSON, GSettings externo, SQLite técnico o programas que los eludan.
No borrar/reemplazar locks: procesos abiertos podrían bloquear distintos inodos.

`incident_probe --db`, `capture_save_probe --db` sin --desktop, probes de
mpv/Okular/selección y *.capture.lock siguen siendo herramientas/archivos válidos,
no residuos para eliminar. Escritores técnicos pueden evitar jobs.lock.
Ejemplos /tmp, socket común y servicios Okular con PID del README son históricos
o diagnósticos; no son rutas de producción. La fixture tests/fixtures/incidents_v1.sql
nunca debe usarse para reconstruir bases reales.

README/STEPS conservan pendientes históricos que el usuario confirma validados
posteriormente (teclas físicas, limpieza de ensayos). Se respeta esa evidencia,
sin presentarla como prueba repetida de los comandos reales aún sin adaptar.

## 2. Compatibilidad de la versión nueva con el entorno anterior

### Catálogo, fórmulas y teclas

El recurso distribuido coincide exactamente con lo solicitado. Todos los tipos
iniciales están habilitados; ID, etiqueta, habilitación y fórmula son explícitos.
Se puede editar etiquetas/estado/fórmulas y añadir tipos según el alcance ya
implementado; el historial conserva el ID estable.

| Tecla lógica | ID | Etiqueta | Fórmula inicial |
| --- | --- | --- | --- |
| F1 | TEXT | Texto | null (sin fórmula) |
| F2 | PRON | Pronunciación | Revisar pronunciación. |
| F3 | DICC | Dicción | Revisar dicción. |
| F4 | RUID | Ruido | Ruido. |
| F5 | RESP | Respiración | Respiración. |
| F6 | INTER | Entonación | Revisar entonación. |
| F7 | OTRO | Otro | null (sin fórmula) |

Capturar deja la genérica vacía; aplicar fórmula requiere edición explícita
`--default-description`. Reformular/instalar catálogos no altera textos previos.
descriptions.json es adicional y opcional, no requiere conversión ni sustitución.

El historial sigue legible con tipos deshabilitados o retirados, usando el ID
si ya no hay definición. Con catálogo ausente/corrupto, lectura/edición manual
degradan con aviso. Seleccionar un tipo diferente exige que esté habilitado.
Deshabilitarlo requiere desasignar sus hotkeys. No se infiere procedencia de
una descripción histórica por igualdad de texto.

Los comandos GNOME observados mantienen el tipo inicial, pero **no siguen una
reasignación del JSON**: deben cambiarse a --desktop --hotkey Fn. Actualmente
también fallarían por catálogo ausente. On no valida ese catálogo: que on termine
correctamente no demuestra que una captura sea posible.

### SQLite

[sqlite_repository.py](src/audiobook_qc/sqlite_repository.py) admite v1 y v2.
V1 tiene CHECK enumerado de los siete IDs; v2 valida sintaxis
`[A-Z][A-Z0-9_]*`, sin FK al catálogo. Las bases nuevas son v2.
Abrir, leer o inicializar una v1 existente no la migra.

**No hace falta migrar las cuatro bases para los siete IDs iniciales.**
Esta es la ruta recomendada. Usar IDs adicionales en v1 falla con instrucción
de migración explícita.

`jobs_cli migrate-types UUID` reconstruye la tabla dentro de la misma base
en una transacción BEGIN IMMEDIATE; no elimina/recrea el archivo ni convierte
tipos. Copia todas las columnas y conserva IDs, fechas, selección, comentarios,
genérica, posiciones REAL, audio, documentos/páginas, exported y sqlite_sequence
(también si todas las filas fueron borradas). Tests cubren conservación,
rollback, idempotencia, secuencia y exclusión con JobStore.

Rechaza columnas/objetos SQL adicionales. No compara formalmente todas las
restricciones/tipos de cualquier esquema externo: revisar sqlite_master y
ensayar cada copia sigue siendo necesario. No hay downgrade automático;
versiones antiguas que solo admiten v1 rechazan v2. Cambiar user_version a 1
no constituye una recuperación válida.

## 3. Riesgos detectados, clasificados por gravedad

| Gravedad | Riesgo | Control |
| --- | --- | --- |
| Crítica | Restaurar backup tras capturas nuevas pierde datos posteriores | Preservar estado fallido y conciliar antes de restaurar |
| Crítica | Copiar SQLite vivo sin WAL/journal produce respaldo incoherente | Ventana sin escritores, revisar sidecars, validar copias |
| Alta | Catálogo nuevo ausente: fallan capturas | Init explícito y validación antes de activar |
| Alta | Comandos posicionales ignoran reasignación lógica | Adaptar las siete entradas y confirmar bindings |
| Alta | Comando suspendido cambiado: journal no restaura | Reasignar binding, no editar journal para sortear control |
| Alta | configure/select/clear alteran raíz o destino | Conservar jobs.json y comparar hash/UUID |
| Alta | Escritores externos no respetan locks | Mantenimiento entre sesiones y detectar diferencias |
| Alta | Migración innecesaria rompe compatibilidad hacia atrás | Conservar v1; v2 con autorización aparte |
| Alta | mpv abierto no corresponde al socket por UUID | Verificar fuentes sin abrir/cerrar procesos |
| Media | Teclas reservadas aunque indicador siga off | Reasignación breve supervisada |
| Media | Conflictos de sistema/extensiones no cubiertos por comparación literal | Inspección y pruebas físicas |
| Media | XDG distinto o JSON parcial | Entorno coherente y publicación atómica |
| Media | Backup en el mismo disco | Segunda copia persistente independiente |
| Media | PRIMARY puede ser antiguo; captura no atómica | Selección fresca, pausa manual y revisión |

No se detecta incompatibilidad imprescindible que requiera cambiar código.
No hay modo de mantenimiento global capaz de detener todos los escritores externos.

## 4. Procedimiento de integración recomendado

**Todos los comandos siguientes son futuros y requieren autorización de la
integración.** Ejecutar por etapas en Bash, desde la sesión X11 del usuario,
sin sudo. Detener al primer error o diferencia inesperada; no ejecutar todo
como un instalador automático.

### A. Auditoría previa de solo lectura

Precondición: identificar código, entorno y datos. Preparar variables de tarea:

```bash
cd /home/jon/prog/python/audiobook-qc
AQ_PY=/home/jon/prog/python/audiobook-qc/.venv/bin/python
AQ_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/audiobook-qc"
# STATE vacío es error en esta versión, no fallback.
AQ_STATE="${XDG_STATE_HOME-$HOME/.local/state}/audiobook-qc"
export AQ_PY AQ_CONFIG AQ_STATE
git status --short
git log -1 --oneline
cat "$AQ_CONFIG/jobs.json"
cat "$AQ_STATE/gnome-bindings.json"
gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings
ps -C mpv,okular,gnome-shell -o pid,comm,args
"$AQ_PY" - <<'PY'
import json, os
from pathlib import Path
from audiobook_qc.correction_mode import is_active, state_path
assert os.environ.get('XDG_STATE_HOME') != ''
for name in ('AQ_CONFIG', 'AQ_STATE'):
    assert Path(os.environ[name]).is_absolute()
p = Path(os.environ['AQ_CONFIG'])
data = json.loads((p/'jobs.json').read_text())
assert data['version'] == 1 and Path(data['root']).is_absolute()
print('ROOT', data['root'], 'ACTIVE', data['active'])
print('MODE', state_path(), is_active())
for name in ('jobs.json', 'incident_types.json', 'descriptions.json'):
    f = p/name
    print(f, 'exists', f.exists(), 'symlink', f.is_symlink())
PY
AQ_ROOT=$("$AQ_PY" -c 'import json,os; from pathlib import Path; print(json.loads((Path(os.environ["AQ_CONFIG"])/"jobs.json").read_text())["root"])')
export AQ_ROOT
find "$AQ_CONFIG" "$AQ_STATE" "$AQ_ROOT" -printf '%y %m %u:%g %s %p -> %l\n'
find "$AQ_ROOT" -type f \( -name '*-wal' -o -name '*-shm' -o -name '*-journal' \) -print
df -h "$AQ_ROOT" "$HOME"
```

Validar root/active, cuatro job.json, catálogo, journal y claves name/command/binding
de todas las rutas GSettings. Revisar lanzadores y scripts conocidos que apunten
a otras bases; no suponer que jobs.json inventaría todas las bases históricas.
Confirmar mantenimiento sin escritores en todas las terminales/sesiones. La
lista de procesos es orientativa, no demuestra ausencia de escritores.

Cambio esperado: ninguno. Detener ante modo activo, sidecars, symlinks, raíz
distinta, falta de espacio o actividad desconocida. Aquí se aprovecha el estado
off observado. Si estuviera on, guardar primero el estado original y acordar
su suspensión; no ejecutar off antes de respaldar por seguir esta receta.
Reversión: ninguna.

### B. Exclusión y copias verificables

Precondición: modo off, sin escritores externos ni edición de GSettings.
No cerrar mpv/Okular. Si modifican mpv.log durante la copia, detenerse y acordar
una ventana segura. No matarlos para obtener el respaldo.

En la misma terminal, tomar locks existentes, sin crearlos ni truncarlos:

```bash
exec 8<"$AQ_STATE/gnome-bindings.lock"
flock -xn 8
exec 9<"$AQ_CONFIG/jobs.lock"
flock -xn 9
aq_capture_fds=()
for aq_lock in "$AQ_ROOT"/*/incidencias.sqlite3.capture.lock; do
    test -f "$aq_lock" || break
    exec {aq_fd}<"$aq_lock"
    flock -xn "$aq_fd" || break
    aq_capture_fds+=("$aq_fd")
done
```

**Comprobar éxito de cada apertura y flock, y cuatro locks de captura adquiridos.**
Ante fallo, detenerse y liberar lo adquirido; no pasar al backup. El break solo
detiene el bucle, no autoriza continuar. En Linux local, flock exclusivo admite
descriptor de lectura. Mantener estos descriptores hasta terminar E. No invocar
CLI que necesiten los mismos locks mientras los conserva esta terminal.

Elegir ubicación persistente nueva, fuera de los árboles originales y de /tmp/runtime:

```bash
umask 077
AQ_BACKUP="$HOME/Respaldos/audiobook-qc/$(date +%Y%m%d-%H%M%S)-preintegracion"
export AQ_BACKUP
mkdir -p "$HOME/Respaldos/audiobook-qc"
mkdir "$AQ_BACKUP"
```

Inventariar permisos/propietarios/fechas/hashes, copiar y comparar originales
antes/después y copias. Guardar también estado GNOME y ausencia del catálogo:

```bash
"$AQ_PY" - <<'PY'
import hashlib, json, os, stat, subprocess
from pathlib import Path
from audiobook_qc.correction_mode import is_active, state_path
from audiobook_qc.integrations.gnome_shortcuts import GSettingsShortcuts
b = Path(os.environ['AQ_BACKUP'])
trees = {k: Path(os.environ[v]) for k,v in (
    ('config','AQ_CONFIG'), ('state','AQ_STATE'), ('jobs','AQ_ROOT'))}
def inventory(root):
    result = {}
    for p in [root, *sorted(root.rglob('*'))]:
        s = p.lstat()
        if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):
            raise RuntimeError(f'Enlace u objeto especial: {p}')
        row = dict(mode=stat.S_IMODE(s.st_mode), uid=s.st_uid,
                   gid=s.st_gid, mtime_ns=s.st_mtime_ns)
        if p.is_file():
            row.update(size=s.st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        result[str(p.relative_to(root))] = row
    return result
def desktop():
    g = GSettingsShortcuts()
    return [vars(g.read(p)) for p in g.paths()]
assert not is_active(), 'Modo activo'
before = {k: inventory(p) for k,p in trees.items()}
gnome = desktop()
for root in trees.values():
    for p in root.rglob('*'):
        assert not p.name.endswith(('-wal','-shm','-journal')), p
for k,p in trees.items():
    subprocess.run(['cp','-a','--',str(p),str(b/k)], check=True)
    assert inventory(b/k) == before[k], f'Copia diferente: {k}'
assert before == {k: inventory(p) for k,p in trees.items()}, 'Cambio concurrente'
assert desktop() == gnome and not is_active(), 'Cambio GNOME/modo'
manifest = dict(paths={k:str(p) for k,p in trees.items()}, inventory=before,
                desktop=gnome, mode=dict(path=str(state_path()), active=False,
                existed=state_path().exists()),
                incident_types_existed=(trees['config']/'incident_types.json').exists())
(b/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
(b/'git-head.txt').write_text(subprocess.check_output(['git','rev-parse','HEAD'],text=True))
print('Copia y originales coincidentes:', b)
PY
```

cp -a preserva metadatos; cualquier error impide aceptar la copia. El manifiesto
verifica bytes/permisos básicos, no ACL/xattrs: si existen, compararlos además
con getfacl/getfattr antes de aceptar el respaldo, sin instalar herramientas
automáticamente. Registrar también permisos de directorios antecesores.

Comprobar legibilidad e integridad sobre las copias sin sidecars:

```bash
"$AQ_PY" - <<'PY'
import os, sqlite3
from pathlib import Path
for p in sorted((Path(os.environ['AQ_BACKUP'])/'jobs').glob('*/incidencias.sqlite3')):
    c = sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1', uri=True)
    assert c.execute('PRAGMA integrity_check').fetchall() == [('ok',)], p
    print(p.parent.name, c.execute('PRAGMA user_version').fetchone(),
          c.execute('SELECT count(*) FROM incidents').fetchone(),
          c.execute('SELECT * FROM sqlite_sequence').fetchall())
    print(c.execute('SELECT type,name,sql FROM sqlite_master').fetchall())
    c.close()
PY
```

Comparar trabajos y revisar esquemas; hacer segunda copia en soporte persistente
independiente y comprobar los mismos hashes. No proceder ante diferencias.
Ventana sin escritores es precondición: hashes no detectan todo cambio transitorio
que un escritor externo deshaga. Si hay WAL/journal o no puede garantizarse quietud,
se necesita un plan específico de snapshot/backup SQLite consistente. No borrar
sidecars, ejecutar checkpoints ni recuperar journals en el original.

Cambio esperado: solo backups nuevos. Reversión: no tocar originales; conservar
copias fallidas como evidencia, sin tratarlas como respaldo válido.

### C. Ensayo aislado

Precondición: B validada. Mantener el backup maestro intacto. Para ensayar una
migración, copiar cada base a un directorio persistente distinto y ejecutar el
repositorio directamente sobre la copia, sin JobStore real:

```bash
mkdir "$AQ_BACKUP/ensayo"
cp -a "$AQ_BACKUP/jobs/23acd96a-54d9-4b07-9c6b-961a943bf703/incidencias.sqlite3" "$AQ_BACKUP/ensayo/v1.sqlite3"
"$AQ_PY" - <<'PY'
import os, sqlite3
from pathlib import Path
from audiobook_qc.sqlite_repository import SQLiteIncidentRepository
p = Path(os.environ['AQ_BACKUP'])/'ensayo/v1.sqlite3'
def contents():
    with sqlite3.connect(p) as c:
        return (c.execute('SELECT * FROM incidents ORDER BY id').fetchall(),
                c.execute('SELECT * FROM sqlite_sequence').fetchall())
before = contents()
with SQLiteIncidentRepository(p, existing=True) as r:
    assert r.migrate_types()
    assert not r.migrate_types()
assert contents() == before
with sqlite3.connect(p) as c:
    assert c.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
print('Preservación de todas las columnas y secuencia verificada')
PY
```

Opcional para integrar solo siete tipos; obligatorio por cada base si se plantea
v2. Si se ensayan CLI/configuración, aislar XDG_CONFIG_HOME, XDG_STATE_HOME y
XDG_RUNTIME_DIR y modificar **solo jobs.json copiado** para apuntar a trabajos
copiados. Copiar jobs.json sin cambiar root seguiría apuntando a producción.
XDG no aísla GSettings ni el bus: no ejecutar on ni GSettings real desde el ensayo.

Validación: igualdad de todas las filas/columnas y secuencia; integridad correcta.
Detener ante diferencias. Cambios/reversión limitados al ensayo.

### D. Preparación de configuración persistente

Precondición: backup validado, locks retenidos, modo off, catálogo aún ausente
(incluido symlink). Cada test debe terminar correctamente antes de init:

```bash
test ! -e "$AQ_CONFIG/incident_types.json"
test ! -L "$AQ_CONFIG/incident_types.json"
"$AQ_PY" -m audiobook_qc.types_cli init --json
"$AQ_PY" -m audiobook_qc.types_cli validate --json
"$AQ_PY" -m audiobook_qc.types_cli list --json
"$AQ_PY" -m audiobook_qc.types_cli hotkeys --json
"$AQ_PY" -m audiobook_qc.descriptions_cli validate --json
```

Revisar tabla de sección 2 (null, puntos finales, enabled y mapa). No sobrescribir
un archivo que haya aparecido. Conservar descriptions.json, jobs.json, fuentes
y bases byte a byte. Estas CLI de catálogos no necesitan locks de trabajos.
Cambio esperado: solo incident_types.json privado. Detener si hay otros cambios.
Reversión: trasladar archivo nuevo a evidencia para recuperar ausencia original.

### E. Adaptación de comandos GNOME

Precondición: D válida; mismos paths, nombres y comandos del manifest; siete
bindings aún vacíos; sin conflictos. Mantener modo off y locks. No cambiar
custom0, nombres ni lista global. Las rutas siguientes son las observadas:

```bash
aq_base=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings
aq_schema=org.gnome.settings-daemon.plugins.media-keys.custom-keybinding
aq_ids=(text pron dicc ruid resp inter otro)
for aq_i in "${!aq_ids[@]}"; do
    aq_path="$aq_base/audiobook-qc-${aq_ids[$aq_i]}/"
    aq_n=$((aq_i + 1))
    gsettings set "$aq_schema:$aq_path" command "'$AQ_PY -m audiobook_qc.capture_save_probe --desktop --hotkey F$aq_n'" || break
    gsettings get "$aq_schema:$aq_path" command || break
done
```

Revisar siete salidas antes de seguir. Ruta de intérprete actual sin espacios;
si cambia, regenerar quoting correctamente. Asignar combinaciones expresamente:

```bash
for aq_i in "${!aq_ids[@]}"; do
    aq_path="$aq_base/audiobook-qc-${aq_ids[$aq_i]}/"
    aq_n=$((aq_i + 1))
    gsettings set "$aq_schema:$aq_path" binding "'F$aq_n'" || break
    gsettings get "$aq_schema:$aq_path" binding || break
done
```

Un break por fallo obliga a detener etapa; no continuar a activación. Releer
lista global y name/command/binding de todas las entradas. Solo deben cambiar
command/binding de las siete propias. F física y lógica quedan F1→F1, etc.
No editar journal a mano. GNOME reserva teclas desde la asignación aunque
el indicador siga off; mantener este intervalo breve y supervisado.

Cambios esperados: siete comandos y bindings. Detener ante conflicto, cambio
de identidad o concurrencia. Reversión selectiva desde manifest (sección 5).

### F. Esquemas SQLite

**Omitir migración en la ruta recomendada**: mantener cuatro bases v1 y hashes
iguales al backup. No ejecutar init/create/configure/migrate-types sobre ellas.

Si se autoriza v2 aparte: ensayar cada copia, tomar nuevo backup inmediato y
liberar los locks manuales antes de ejecutar por cada UUID aprobado:

```bash
# Solo con autorización específica para ese UUID:
"$AQ_PY" -m audiobook_qc.jobs_cli migrate-types UUID_COMPLETO
```

La CLI toma jobs.lock y la transacción SQLite: no puede ejecutarse mientras
esta terminal lo retiene. Mantener modo off y ausencia de escritores durante
la cesión de locks. Validar todas las filas/columnas, secuencia, integridad,
versión y jobs.json tras cada base. No hay atomicidad conjunta entre trabajos.
Detener ante el primer fallo. Reversión de v2 según sección 5.

### G. Activación controlada

Precondición: inventario idéntico al backup salvo catálogo y siete entradas
GNOME. Confirmar fuentes presentes; liberar locks manuales en la misma terminal:

```bash
for aq_fd in "${aq_capture_fds[@]}"; do
    exec {aq_fd}<&-
done
exec 9<&-
exec 8<&-
"$AQ_PY" -m audiobook_qc.jobs_cli active
"$AQ_PY" -m audiobook_qc.jobs_cli sources 23acd96a-54d9-4b07-9c6b-961a943bf703
"$AQ_PY" -m audiobook_qc.types_cli validate --json
"$AQ_PY" -m audiobook_qc.correction_mode on --notify
"$AQ_PY" -m audiobook_qc.correction_mode status
```

Ahora estas CLI pertenecen a una etapa que admite escrituras de estado/locks.
active debe seguir siendo PRUEBA_A. sources informa asociación, no garantiza
conectividad. On valida fuentes existentes, journal y bindings. Si faltan fuentes,
detenerse sin launch-mpv/launch-okular; decidir aparte su preparación.

Cambios esperados: indicador runtime y journal sincronizado; ninguna incidencia.
Status correcto no prueba los siete bindings ni todos los conflictos: contrastar
manualmente. On fallido intenta off pero puede dejar recuperación parcial;
revisar salida y GNOME. Reversión: off y recuperación selectiva, sin reactivar
automáticamente. No cambiar trabajo activo para conseguir que on funcione.

### H. Pruebas posteriores y comprobaciones finales

Precondición: G válida. Consultar historial de cada UUID, sin editar:

```bash
"$AQ_PY" -m audiobook_qc.incidents_cli list --job 23acd96a-54d9-4b07-9c6b-961a943bf703 --json
"$AQ_PY" -m audiobook_qc.types_cli hotkeys --json
"$AQ_PY" -m audiobook_qc.correction_mode status
```

Repetir list para los otros tres trabajos. Comparar todas las filas/columnas,
incluidos IDs, tipos, textos exactos, tiempos, rutas, páginas, fechas y exported.
Antes de capturar, los hashes de las cuatro bases deben seguir iguales al backup
en la ruta sin migración. Confirmar jobs.json intacto y atajos ajenos idénticos.

**No agregar incidencias ficticias a trabajos reales por defecto.** Para probar
F1–F7 físicamente, reasignación F2 PRON→DICC solo por JSON, RESP off/on, historial,
edición y fórmula sin alterar comentario/exported, usar un trabajo persistente
de ensayo aprobado con fuentes dedicadas. Cambiar selección o abrir esas fuentes
requiere autorización separada; el plan base conserva trabajo y ventanas.
Sin esa autorización, marcar esas pruebas físicas posteriores como pendientes.
No presentar los tests automáticos ni pruebas previas como sustituto de ellas.

Primera captura editorial real autorizada: audio pausado manualmente, selección
fresca y documento/página verificados; comprobar ID nuevo, tipo, timestamp, texto
y notificación con nombre del trabajo. Las demás bases deben seguir intactas.
No repetir una captura por fallo de notificación si el commit ya se confirmó.

En el alcance de prueba autorizado, comprobar rechazo con modo off o foco ajeno
y liberación/restauración de F1–F7 sin afectar Ctrl+Alt+T. Al terminar dejar modo
off, salvo autorización para continuar trabajando. Conservar backups/resultados.
Las filas nuevas son datos a conservar: no eliminarlas para recuperar hashes.

## 5. Procedimiento de recuperación

### Condiciones comunes de seguridad

Detener capturas y ediciones; registrar fallo, etapa, versión y diferencias.
Guardar una segunda copia del estado fallido en otra carpeta persistente, con
GSettings y sidecars si existen, sin sustituir el backup original. Una copia
forense de una base viva con WAL no equivale a backup restaurable.

Antes de recuperar, identificar trabajo nuevo desde el backup. **Si existe,
no restaurar a ciegas**: conciliarlo primero. Nunca hacer reset global de dconf,
reconstruir bases, borrar sidecars ni cambiar user_version como downgrade.

Con evidencia guardada, sin locks manuales y journal legible:

```bash
"$AQ_PY" -m audiobook_qc.correction_mode off --notify
```

Puede modificar journal y dejar errores parciales: revisar. Si falla, liberar
selectivamente las siete combinaciones desde GNOME dentro de la autorización
de recuperación; indicador corrupto/desactivación parcial exige revisión manual.
No cerrar mpv/Okular. Reobtener locks journal → jobs → captura antes de restaurar.
No reemplazar/restaurar *.lock, sockets, PIDs o indicador runtime antiguo.

### Fallo sin cambios de SQLite

Comparar hashes; no restaurar bases ni jobs.json que siguen intactos. Como el
catálogo era inexistente, trasladar el nuevo a evidencia (AQ_RECOVERY debe ser
una carpeta persistente nueva, fuera de configuración):

```bash
mv -n -- "$AQ_CONFIG/incident_types.json" "$AQ_RECOVERY/incident_types.after.json"
```

Verificar origen ausente y evidencia legible: mv -n puede omitir sin fallo.
Si en otro entorno existía catálogo previo, restaurar solo su copia validada
mediante temporal libre y reemplazo atómico, conservando antes la versión fallida.
No tocar descriptions.json si no cambió.

Restaurar selectivamente GNOME desde manifest, con bindings vacíos primero.
Este bloque exige lista/identidades originales y ausencia de cambios externos:

```bash
"$AQ_PY" - <<'PY'
import json, os, subprocess
from pathlib import Path
from audiobook_qc.integrations.gnome_shortcuts import GSettingsShortcuts, CUSTOM_SCHEMA
m = json.loads((Path(os.environ['AQ_BACKUP'])/'manifest.json').read_text())
g = GSettingsShortcuts()
old = {e['path']:e for e in m['desktop']}
ids = ('text','pron','dicc','ruid','resp','inter','otro')
paths = ['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/'
         f'audiobook-qc-{i}/' for i in ids]
assert g.paths() == list(old), 'Lista cambiada: conciliar manualmente'
for p in paths:
    assert g.read(p).name == old[p]['name'], 'Identidad cambiada'
for p in paths:
    subprocess.run(['gsettings','set',CUSTOM_SCHEMA+p,'binding',repr('')],check=True)
for p in paths:
    for key in ('name','command','binding'):
        subprocess.run(['gsettings','set',CUSTOM_SCHEMA+p,key,repr(old[p][key])],check=True)
assert [vars(g.read(p)) for p in g.paths()] == m['desktop']
PY
```

Si otra intervención cambió comando/identidad, conciliar antes de sobrescribir:
el bloque es para revertir únicamente los cambios previstos. En este backup
los siete bindings originales están vacíos. Si fuesen activos, mantenerlos
suspendidos hasta activación deliberada en vez de restaurarlos inmediatamente.

Recuperar journal después de comandos/bindings, con modo off y lock retenido.
Exigir ruta temporal libre; preservar primero el journal fallido:

```bash
test ! -e "$AQ_STATE/gnome-bindings.restore.json"
cp -a -- "$AQ_BACKUP/state/gnome-bindings.json" "$AQ_STATE/gnome-bindings.restore.json"
mv -T -- "$AQ_STATE/gnome-bindings.restore.json" "$AQ_STATE/gnome-bindings.json"
cmp -- "$AQ_BACKUP/state/gnome-bindings.json" "$AQ_STATE/gnome-bindings.json"
```

Comparar también permisos/uid/gid, liberar locks y comprobar status. Estado
original observado: off, bindings vacíos, comandos posicionales, journal
suspendido, mismo active. Ese estado conserva los datos, pero el código nuevo
no capturará sin catálogo; no hacer downgrade de código automáticamente.

### Fallo de v2, si se autorizó aparte

Un fallo transaccional revierte esa base; verificar versión, integridad y filas.
Otras bases ya confirmadas no se revierten juntas. Para volver de v2 confirmada
a v1, recuperar copia exacta v1, preservando primero v2 y sus datos posteriores.

Solo si no hay datos nuevos por rescatar, conexiones SQLite abiertas ni sidecars,
y se mantiene exclusión completa, publicar una copia en el UUID revisado:

```bash
# AQ_UUID es el UUID concreto revisado; la ruta temporal debe estar libre.
test ! -e "$AQ_ROOT/$AQ_UUID/incidencias.restore.sqlite3"
cp -a -- "$AQ_BACKUP/jobs/$AQ_UUID/incidencias.sqlite3" "$AQ_ROOT/$AQ_UUID/incidencias.restore.sqlite3"
cmp -- "$AQ_BACKUP/jobs/$AQ_UUID/incidencias.sqlite3" "$AQ_ROOT/$AQ_UUID/incidencias.restore.sqlite3"
mv -T -- "$AQ_ROOT/$AQ_UUID/incidencias.restore.sqlite3" "$AQ_ROOT/$AQ_UUID/incidencias.sqlite3"
```

Nunca reemplazar base con conexión abierta: podría seguir escribiendo el inodo
anterior. Si hay WAL/journal o datos nuevos, detener y diseñar recuperación
específica, sin borrar archivos. No restaurar carpeta completa ni locks sobre
una sesión viva. Si metadatos/fuentes/jobs.json cambiaron inesperadamente,
preservar diferencias y restaurar solo los afectados; configure/select no
sustituyen una recuperación exacta.

Validación final: hashes/metadatos, integridad, filas completas y secuencia,
root/active originales, GNOME ajeno intacto, journal coherente y modo off.
Solo declarar recuperación sin pérdidas tras conciliar cualquier trabajo nuevo.

## 6. Comprobaciones manuales antes de autorizar

1. Confirmar que cuatro trabajos y 13 incidencias son el conjunto previsto.
   Revisar bases fuera de la raíz mediante lanzadores/rutas conocidos: no se
   recorrió todo home/discos para afirmar que no existan más bases antiguas.
2. Confirmar mismo HOME/XDG/intérprete en terminal y GNOME; revisar wrappers,
   servicios o lanzadores con configuración alternativa.
3. Acordar ventana sin escritores en todas las sesiones/displays, incluidos
   editores técnicos y logs; documentar quién controla esa ventana.
4. Elegir respaldo persistente y segunda copia independiente; comprobar
   espacio, permisos, ACL/xattrs y lectura de ambas.
5. Aprobar conservar active y **omitir v1→v2**. IDs nuevos/migración requieren
   autorización aparte y ensayo de cada copia.
6. Revisar catálogo inicial y mantener descriptions.json provisional sin
   adoptarlo como catálogo editorial definitivo.
7. Revisar conflictos F1–F7, atajos de sistema/extensiones y Ctrl+Alt+T.
8. Confirmar socket vivo por UUID y PDF asociado sin asumirlo por procesos o
   nombres de socket. Si faltan fuentes, decidir su preparación aparte.
9. Acordar alcance de pruebas posteriores que agreguen filas, cambien selección
   o creen fuentes/trabajos de ensayo. Sin ello, pruebas físicas pendientes.
10. Revisar recuperación: conservar trabajo posterior, no restaurar locks ni
    runtime antiguo, no sobrescribir cambios externos sin conciliarlos.

## 7. Veredicto

**APTO CON CONDICIONES** para una integración posterior de catálogo y comandos
GNOME, manteniendo las cuatro bases v1. Código y tests respaldan compatibilidad;
faltan backups certificados, ventana de mantenimiento y verificación de fuentes
y activación real. No se certifica una integración ni migración ya completada.

No se han modificado configuración real, selección, bases, permisos, bindings
ni procesos mpv/Okular. La auditoría termina aquí; no se inicia la integración.
Al finalizar, las cuatro bases conservan los hashes SHA-256 obtenidos durante
la inspección, la selección sigue siendo PRUEBA_A y el catálogo continúa ausente.

