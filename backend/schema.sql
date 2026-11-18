-- =====================================================================
-- Base de datos del Sistema de Gestión del Servicio Social (SQLite)
-- Basada en el ERS (RF-01..RF-17, RNF-07, RNF-09, CU01..CU12).
--
-- Reglas generales:
--   * Todas las personas (usuarios y responsables de dependencias)
--     tienen nombre, apellido paterno y apellido materno obligatorios.
--   * Las llaves foráneas y las restricciones viven en la base de datos
--     (RNF-07: integridad y consistencia).
--   * La bitácora es inmutable (RNF-09).
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- USUARIOS (clase padre). El Administrador los crea (CU02 / RF-01 / RF-02).
-- ---------------------------------------------------------------------
CREATE TABLE usuarios (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    identificador         TEXT NOT NULL UNIQUE,   -- no. de control u hoja de empleado
    nombre                TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    apellido_paterno      TEXT NOT NULL CHECK (length(trim(apellido_paterno)) > 0),
    apellido_materno      TEXT NOT NULL CHECK (length(trim(apellido_materno)) > 0),
    correo                TEXT NOT NULL UNIQUE,
    password_hash         TEXT NOT NULL,          -- hash + sal, nunca texto plano (RNF-01)
    rol                   TEXT NOT NULL CHECK (rol IN
                            ('ALUMNO','JEFE_OFICINA_SS','JEFE_VINCULACION','ADMINISTRADOR')),
    activo                INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    debe_cambiar_password INTEGER NOT NULL DEFAULT 0 CHECK (debe_cambiar_password IN (0, 1)),
    intentos_fallidos     INTEGER NOT NULL DEFAULT 0 CHECK (intentos_fallidos >= 0),
    bloqueado_hasta       TEXT,
    creado_en             TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en        TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (lower(correo) LIKE '%@culiacan.tecnm.mx'),
    CHECK (rol <> 'ALUMNO' OR (length(identificador) = 8
                               AND identificador NOT GLOB '*[^0-9]*')),
    CHECK (identificador = trim(identificador))
);

-- Datos propios del alumno (RF-01 / CU04).
CREATE TABLE alumnos (
    usuario_id            INTEGER PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    curp                  TEXT NOT NULL UNIQUE CHECK (length(curp) = 18),
    carrera               TEXT NOT NULL CHECK (length(trim(carrera)) > 0),
    semestre              INTEGER NOT NULL CHECK (semestre >= 7),  -- RF-01: 7.º o más
    telefono              TEXT,
    domicilio             TEXT,
    plan_estudios         TEXT CHECK (plan_estudios IN ('NUEVO','ANTIGUO')),
    creditos              INTEGER CHECK (creditos >= 0),
    porcentaje_creditos   REAL
                          CHECK (porcentaje_creditos IS NULL
                                 OR (porcentaje_creditos >= 70 AND porcentaje_creditos <= 100)),
    foto_infantil         TEXT,
    boleta_extraescolares TEXT,
    actualizado_en        TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ((creditos IS NULL) = (porcentaje_creditos IS NULL)),
    CHECK (plan_estudios IS NULL OR plan_estudios = 'NUEVO'
           OR (foto_infantil IS NOT NULL AND boleta_extraescolares IS NOT NULL))
);

-- Recuperación de contraseña: token de un solo uso.
CREATE TABLE recuperaciones_password (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token      TEXT NOT NULL UNIQUE,
    expira_en  TEXT NOT NULL,
    usado      INTEGER NOT NULL DEFAULT 0 CHECK (usado IN (0, 1))
);

-- ---------------------------------------------------------------------
-- CURSO DE INDUCCIÓN Y ASISTENCIA (CU03). El QR se genera desde el
-- sistema y vence a los 10 segundos; los FORMS se guardan completos.
-- ---------------------------------------------------------------------
CREATE TABLE cursos_induccion (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha          TEXT NOT NULL,
    lugar          TEXT,
    periodo        TEXT NOT NULL UNIQUE,
    qr_token       TEXT,
    qr_generado_en TEXT,
    qr_expira_en   TEXT,
    activo         INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE asistencias_induccion (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    curso_id        INTEGER NOT NULL REFERENCES cursos_induccion(id) ON DELETE CASCADE,
    alumno_id       INTEGER NOT NULL REFERENCES alumnos(usuario_id) ON DELETE CASCADE,
    forms_completos INTEGER NOT NULL DEFAULT 0 CHECK (forms_completos IN (0, 1)),
    registrada_en   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (curso_id, alumno_id)
);

CREATE TABLE forms_induccion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    curso_id    INTEGER NOT NULL REFERENCES cursos_induccion(id) ON DELETE CASCADE,
    alumno_id   INTEGER NOT NULL REFERENCES alumnos(usuario_id) ON DELETE CASCADE,
    respuestas  TEXT NOT NULL,
    enviado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (curso_id, alumno_id)
);

-- ---------------------------------------------------------------------
-- EMPRESA / DEPENDENCIA RECEPTORA (RF-05, CU08).
-- El responsable (titular) tiene nombre y los dos apellidos obligatorios.
-- Cada propuesta (banco o propia) guarda su propia fila: el responsable de
-- una propuesta NO se comparte con las demás, aunque la dependencia se llame
-- igual. Por eso no hay UNIQUE(nombre, domicilio).
-- ---------------------------------------------------------------------
CREATE TABLE empresas_receptoras (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre                    TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    titular_nombre            TEXT NOT NULL CHECK (length(trim(titular_nombre)) > 0),
    titular_apellido_paterno  TEXT NOT NULL CHECK (length(trim(titular_apellido_paterno)) > 0),
    titular_apellido_materno  TEXT NOT NULL CHECK (length(trim(titular_apellido_materno)) > 0),
    titular                   TEXT NOT NULL CHECK (length(trim(titular)) > 0),  -- nombre completo
    domicilio                 TEXT NOT NULL CHECK (length(trim(domicilio)) > 0),
    telefono                  TEXT NOT NULL CHECK (length(trim(telefono)) > 0),
    creado_en                 TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en            TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- PROGRAMAS DE SERVICIO SOCIAL (RF-04, RF-12, RF-17, CU08, CU09)
--   BANCO  = Banco de Propuestas (lo captura el Jefe de Oficina de SS).
--   PROPIA = Propuesta Propia del alumno, interna o externa; queda
--            PENDIENTE hasta que el Jefe de Oficina la valida.
-- ---------------------------------------------------------------------
CREATE TABLE programas (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo              TEXT NOT NULL CHECK (tipo IN ('BANCO','PROPIA')),
    origen            TEXT NOT NULL CHECK (origen IN ('INTERNA','EXTERNA')),
    nombre            TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    empresa_id        INTEGER NOT NULL REFERENCES empresas_receptoras(id),
    area_responsable  TEXT,
    objetivo          TEXT,
    actividades       TEXT NOT NULL CHECK (length(trim(actividades)) > 0),
    horas             INTEGER NOT NULL CHECK (horas > 0),
    cupo              INTEGER NOT NULL CHECK (cupo > 0),
    cupo_disponible   INTEGER NOT NULL
                      CHECK (cupo_disponible >= 0 AND cupo_disponible <= cupo),
    periodo           TEXT NOT NULL CHECK (length(trim(periodo)) > 0),
    plan_estudios     TEXT NOT NULL DEFAULT 'AMBOS'
                      CHECK (plan_estudios IN ('NUEVO','ANTIGUO','AMBOS')),
    estatus           TEXT NOT NULL CHECK (estatus IN
                        ('DISPONIBLE','INACTIVO','PENDIENTE','APROBADA','RECHAZADA')),
    creado_por        INTEGER REFERENCES usuarios(id),
    propuesto_por     INTEGER REFERENCES alumnos(usuario_id),
    motivo_rechazo    TEXT,
    validado_por      INTEGER REFERENCES usuarios(id),
    validado_en       TEXT,
    creado_en         TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (tipo <> 'PROPIA' OR propuesto_por IS NOT NULL),
    CHECK (tipo <> 'BANCO' OR estatus IN ('DISPONIBLE','INACTIVO')),
    CHECK (tipo <> 'PROPIA' OR estatus IN ('PENDIENTE','APROBADA','RECHAZADA'))
);
-- CU08: no se repite una propuesta del banco en el mismo periodo.
CREATE UNIQUE INDEX ux_programas_banco
    ON programas(nombre, empresa_id, periodo) WHERE tipo = 'BANCO';

-- ---------------------------------------------------------------------
-- PLANES DE SERVICIO SOCIAL (RF-13). No se elimina un plan en uso.
-- ---------------------------------------------------------------------
CREATE TABLE planes_servicio (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT NOT NULL UNIQUE CHECK (length(trim(nombre)) > 0),
    actividades       TEXT NOT NULL CHECK (length(trim(actividades)) > 0),
    cronograma        TEXT NOT NULL CHECK (length(trim(cronograma)) > 0),
    horas_por_periodo INTEGER NOT NULL CHECK (horas_por_periodo > 0),
    activo            INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_por        INTEGER REFERENCES usuarios(id),
    creado_en         TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- SERVICIO SOCIAL: PENDIENTE -> ACTIVO -> CONCLUIDO -> LIBERADO, o BAJA.
-- ---------------------------------------------------------------------
CREATE TABLE servicios_sociales (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id        INTEGER NOT NULL REFERENCES alumnos(usuario_id),
    programa_id      INTEGER NOT NULL REFERENCES programas(id),
    plan_id          INTEGER REFERENCES planes_servicio(id),
    estatus          TEXT NOT NULL DEFAULT 'PENDIENTE'
                     CHECK (estatus IN ('PENDIENTE','ACTIVO','CONCLUIDO','LIBERADO','BAJA')),
    fecha_inicio     TEXT,
    fecha_fin        TEXT,
    horas_requeridas INTEGER NOT NULL DEFAULT 480 CHECK (horas_requeridas > 0),
    creado_en        TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en   TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (fecha_inicio IS NULL OR fecha_fin IS NULL OR fecha_inicio <= fecha_fin)
);
-- RF-05: un alumno no puede tener otro servicio vigente.
CREATE UNIQUE INDEX ux_servicio_vigente
    ON servicios_sociales(alumno_id) WHERE estatus IN ('PENDIENTE','ACTIVO');

-- Baja o cancelación (RF-16).
CREATE TABLE bajas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    servicio_id    INTEGER NOT NULL UNIQUE REFERENCES servicios_sociales(id),
    motivo         TEXT NOT NULL CHECK (length(trim(motivo)) > 0),
    fecha          TEXT NOT NULL DEFAULT (datetime('now')),
    registrada_por INTEGER NOT NULL REFERENCES usuarios(id)
);

-- Horas acumuladas (RF-08).
CREATE TABLE registro_horas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    servicio_id    INTEGER NOT NULL REFERENCES servicios_sociales(id) ON DELETE CASCADE,
    fecha          TEXT NOT NULL,
    horas          INTEGER NOT NULL CHECK (horas > 0),
    registrada_por INTEGER NOT NULL REFERENCES usuarios(id),
    creado_en      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Periodo (ventana) de entrega de CADA documento (RF-09).
-- La fecha la define el Jefe de Oficina de SS UNA VEZ y aplica a TODOS los
-- alumnos por igual. Fuera de esa ventana la subida se rechaza.
--   * Los reportes bimestrales usan numero_reporte 1..3.
--   * Los demás documentos usan numero_reporte = 0.
CREATE TABLE periodos_entrega (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo           TEXT NOT NULL CHECK (tipo IN
                     ('CARTA_PRESENTACION','SOLICITUD','CARTA_ACEPTACION',
                      'REPORTE_BIMESTRAL','MEMORIA_FINAL','CARTA_TERMINACION')),
    numero_reporte INTEGER NOT NULL DEFAULT 0 CHECK (numero_reporte BETWEEN 0 AND 3),
    fecha_inicio   TEXT NOT NULL,
    fecha_fin      TEXT NOT NULL,
    definido_por   INTEGER REFERENCES usuarios(id),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (tipo, numero_reporte),
    CHECK (fecha_inicio <= fecha_fin),
    CHECK ((tipo = 'REPORTE_BIMESTRAL' AND numero_reporte BETWEEN 1 AND 3)
           OR (tipo <> 'REPORTE_BIMESTRAL' AND numero_reporte = 0))
);

-- ---------------------------------------------------------------------
-- DOCUMENTOS (PDF, máx. 5 MB) que sube el alumno (RF-07, CU07, CU10).
-- ---------------------------------------------------------------------
CREATE TABLE documentos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    servicio_id     INTEGER NOT NULL REFERENCES servicios_sociales(id) ON DELETE CASCADE,
    tipo            TEXT NOT NULL CHECK (tipo IN
                      ('CARTA_PRESENTACION','SOLICITUD','CARTA_ACEPTACION',
                       'REPORTE_BIMESTRAL','MEMORIA_FINAL','CARTA_TERMINACION')),
    numero_reporte  INTEGER NOT NULL DEFAULT 0,
    version         INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    estatus         TEXT NOT NULL DEFAULT 'PENDIENTE'
                    CHECK (estatus IN ('PENDIENTE','VALIDADO','OBSERVADO','REEMPLAZADO')),
    nombre_original TEXT NOT NULL,
    ruta_archivo    TEXT NOT NULL,
    tamano_bytes    INTEGER NOT NULL CHECK (tamano_bytes > 0 AND tamano_bytes <= 5242880),
    subido_por      INTEGER REFERENCES usuarios(id),   -- alumno o Jefe de Vinculación (carta firmada)
    subido_en       TEXT NOT NULL DEFAULT (datetime('now')),
    revisado_por    INTEGER REFERENCES usuarios(id),
    revisado_en     TEXT,
    CHECK ((tipo = 'REPORTE_BIMESTRAL' AND numero_reporte BETWEEN 1 AND 3)
           OR (tipo <> 'REPORTE_BIMESTRAL' AND numero_reporte = 0)),
    UNIQUE (servicio_id, tipo, numero_reporte, version)
);
CREATE INDEX ix_documentos_pendientes
    ON documentos(subido_en) WHERE estatus = 'PENDIENTE';

-- Observaciones del Jefe de Oficina cuando observa un documento (RF-15).
CREATE TABLE observaciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    autor_id     INTEGER NOT NULL REFERENCES usuarios(id),
    texto        TEXT NOT NULL CHECK (length(trim(texto)) > 0),
    creada_en    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- PLANTILLAS WORD que sube el Jefe de Oficina de SS (RF-06).
-- ---------------------------------------------------------------------
CREATE TABLE plantillas_documento (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo           TEXT NOT NULL UNIQUE CHECK (tipo IN
                     ('CARTA_PRESENTACION','SOLICITUD','CARTA_ACEPTACION',
                      'REPORTE_BIMESTRAL','MEMORIA_FINAL','CARTA_TERMINACION')),
    nombre_original TEXT NOT NULL,
    ruta_archivo   TEXT NOT NULL,
    subido_por     INTEGER NOT NULL REFERENCES usuarios(id),
    subido_en      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- EXPEDICIÓN de formatos en Word (RF-06). Cada generación queda registrada.
-- ---------------------------------------------------------------------
CREATE TABLE expediciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    servicio_id  INTEGER NOT NULL REFERENCES servicios_sociales(id) ON DELETE CASCADE,
    tipo         TEXT NOT NULL,
    generada_por INTEGER NOT NULL REFERENCES usuarios(id),
    generada_en  TEXT NOT NULL DEFAULT (datetime('now')),
    ruta_archivo TEXT
);

-- ---------------------------------------------------------------------
-- CONSTANCIA DE TERMINACIÓN (RF-10, CU12). Folio único CST-AAAA-NNNN.
-- ---------------------------------------------------------------------
CREATE TABLE constancias (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    servicio_id INTEGER NOT NULL UNIQUE REFERENCES servicios_sociales(id),
    folio       TEXT NOT NULL UNIQUE,
    ruta_archivo TEXT,
    emitida_por INTEGER NOT NULL REFERENCES usuarios(id),
    emitida_en  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------
-- NOTIFICACIONES (RF-05, RF-07, RF-11, RF-14, RF-15, RF-16).
-- ---------------------------------------------------------------------
CREATE TABLE notificaciones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    mensaje    TEXT NOT NULL,
    leida      INTEGER NOT NULL DEFAULT 0 CHECK (leida IN (0, 1)),
    creada_en  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX ix_notificaciones_usuario ON notificaciones(usuario_id, leida);

-- ---------------------------------------------------------------------
-- BITÁCORA (RNF-09). Inmutable: los triggers impiden editar o borrar.
-- ---------------------------------------------------------------------
CREATE TABLE bitacora (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER REFERENCES usuarios(id),
    accion     TEXT NOT NULL,
    detalle    TEXT,
    fecha      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TRIGGER bitacora_sin_update BEFORE UPDATE ON bitacora
BEGIN SELECT RAISE(ABORT, 'La bitácora no se puede modificar'); END;

CREATE TRIGGER bitacora_sin_delete BEFORE DELETE ON bitacora
BEGIN SELECT RAISE(ABORT, 'La bitácora no se puede borrar'); END;

-- ---------------------------------------------------------------------
-- Datos de contacto del personal (el alumno los guarda en alumnos).
-- ---------------------------------------------------------------------
CREATE TABLE contacto_personal (
    usuario_id     INTEGER PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    telefono       TEXT,
    domicilio      TEXT,
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now'))
);