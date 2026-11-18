-- =====================================================================
-- Sistema de Gestion del Servicio Social - Script completo de la base
-- Generado desde backend/servicio_social.db
--
-- CONTIENE DATOS REALES, INCLUYENDO HASHES DE CONTRASEÑAS.
-- No compartir ni subir este archivo a Internet.
--
-- Para recrear la base desde cero, ejecute este script en una base vacia.
-- =====================================================================
PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- TABLE: usuarios
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

-- TABLE: alumnos
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

-- TABLE: recuperaciones_password
CREATE TABLE recuperaciones_password (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token      TEXT NOT NULL UNIQUE,
    expira_en  TEXT NOT NULL,
    usado      INTEGER NOT NULL DEFAULT 0 CHECK (usado IN (0, 1))
);

-- TABLE: cursos_induccion
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

-- TABLE: asistencias_induccion
CREATE TABLE asistencias_induccion (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    curso_id        INTEGER NOT NULL REFERENCES cursos_induccion(id) ON DELETE CASCADE,
    alumno_id       INTEGER NOT NULL REFERENCES alumnos(usuario_id) ON DELETE CASCADE,
    forms_completos INTEGER NOT NULL DEFAULT 0 CHECK (forms_completos IN (0, 1)),
    registrada_en   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (curso_id, alumno_id)
);

-- TABLE: forms_induccion
CREATE TABLE forms_induccion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    curso_id    INTEGER NOT NULL REFERENCES cursos_induccion(id) ON DELETE CASCADE,
    alumno_id   INTEGER NOT NULL REFERENCES alumnos(usuario_id) ON DELETE CASCADE,
    respuestas  TEXT NOT NULL,
    enviado_en  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (curso_id, alumno_id)
);

-- TABLE: empresas_receptoras
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

-- TABLE: programas
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

-- INDEX: ux_programas_banco
CREATE UNIQUE INDEX ux_programas_banco
    ON programas(nombre, empresa_id, periodo) WHERE tipo = 'BANCO';

-- TABLE: planes_servicio
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

-- TABLE: servicios_sociales
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

-- INDEX: ux_servicio_vigente
CREATE UNIQUE INDEX ux_servicio_vigente
    ON servicios_sociales(alumno_id) WHERE estatus IN ('PENDIENTE','ACTIVO');

-- TABLE: bajas
CREATE TABLE bajas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    servicio_id    INTEGER NOT NULL UNIQUE REFERENCES servicios_sociales(id),
    motivo         TEXT NOT NULL CHECK (length(trim(motivo)) > 0),
    fecha          TEXT NOT NULL DEFAULT (datetime('now')),
    registrada_por INTEGER NOT NULL REFERENCES usuarios(id)
);

-- TABLE: registro_horas
CREATE TABLE registro_horas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    servicio_id    INTEGER NOT NULL REFERENCES servicios_sociales(id) ON DELETE CASCADE,
    fecha          TEXT NOT NULL,
    horas          INTEGER NOT NULL CHECK (horas > 0),
    registrada_por INTEGER NOT NULL REFERENCES usuarios(id),
    creado_en      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- TABLE: periodos_entrega
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

-- TABLE: documentos
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

-- INDEX: ix_documentos_pendientes
CREATE INDEX ix_documentos_pendientes
    ON documentos(subido_en) WHERE estatus = 'PENDIENTE';

-- TABLE: observaciones
CREATE TABLE observaciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    autor_id     INTEGER NOT NULL REFERENCES usuarios(id),
    texto        TEXT NOT NULL CHECK (length(trim(texto)) > 0),
    creada_en    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- TABLE: plantillas_documento
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

-- TABLE: expediciones
CREATE TABLE expediciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    servicio_id  INTEGER NOT NULL REFERENCES servicios_sociales(id) ON DELETE CASCADE,
    tipo         TEXT NOT NULL,
    generada_por INTEGER NOT NULL REFERENCES usuarios(id),
    generada_en  TEXT NOT NULL DEFAULT (datetime('now')),
    ruta_archivo TEXT
);

-- TABLE: constancias
CREATE TABLE constancias (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    servicio_id INTEGER NOT NULL UNIQUE REFERENCES servicios_sociales(id),
    folio       TEXT NOT NULL UNIQUE,
    ruta_archivo TEXT,
    emitida_por INTEGER NOT NULL REFERENCES usuarios(id),
    emitida_en  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- TABLE: notificaciones
CREATE TABLE notificaciones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    mensaje    TEXT NOT NULL,
    leida      INTEGER NOT NULL DEFAULT 0 CHECK (leida IN (0, 1)),
    creada_en  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- INDEX: ix_notificaciones_usuario
CREATE INDEX ix_notificaciones_usuario ON notificaciones(usuario_id, leida);

-- TABLE: bitacora
CREATE TABLE bitacora (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER REFERENCES usuarios(id),
    accion     TEXT NOT NULL,
    detalle    TEXT,
    fecha      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- TRIGGER: bitacora_sin_update
CREATE TRIGGER bitacora_sin_update BEFORE UPDATE ON bitacora
BEGIN SELECT RAISE(ABORT, 'La bitácora no se puede modificar'); END;

-- TRIGGER: bitacora_sin_delete
CREATE TRIGGER bitacora_sin_delete BEFORE DELETE ON bitacora
BEGIN SELECT RAISE(ABORT, 'La bitácora no se puede borrar'); END;

-- TABLE: contacto_personal
CREATE TABLE contacto_personal (
    usuario_id     INTEGER PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    telefono       TEXT,
    domicilio      TEXT,
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================ DATOS ============================

-- usuarios: 6 fila(s)
INSERT INTO usuarios ("id", "identificador", "nombre", "apellido_paterno", "apellido_materno", "correo", "password_hash", "rol", "activo", "debe_cambiar_password", "intentos_fallidos", "bloqueado_hasta", "creado_en", "actualizado_en") VALUES (1, 'EMP001', 'JUAN', 'PÉREZ', 'LÓPEZ', 'emp001@culiacan.tecnm.mx', 'scrypt:32768:8:1$pKqnrF0kfyKmPLvG$3f074593e13b048459d29c2290c7f1eb60591585b9e3a7e58b2b08954f413f538ec950feeff62407bec816669334ed4196b76db5903a994c7cde7cee9e0ad7e6', 'ADMINISTRADOR', 1, 0, 0, NULL, '2026-11-15 20:23:03', '2026-11-18 00:18:32');
INSERT INTO usuarios ("id", "identificador", "nombre", "apellido_paterno", "apellido_materno", "correo", "password_hash", "rol", "activo", "debe_cambiar_password", "intentos_fallidos", "bloqueado_hasta", "creado_en", "actualizado_en") VALUES (2, 'EMP002', 'MARÍA', 'CUÉN', 'RIVAS', 'emp002@culiacan.tecnm.mx', 'scrypt:32768:8:1$dwVKvwjy7JgIpcvY$07583a0b262911ffe35f00ea8b7e9ef0d37a8d04f649132bf039cbb11b9b5dd58a3890e136eebdf57a5d5e4c50a5c8fafeb8366e9b1c96d45a8bd63562662854', 'JEFE_OFICINA_SS', 1, 0, 0, NULL, '2026-11-15 20:24:55', '2026-11-18 00:18:32');
INSERT INTO usuarios ("id", "identificador", "nombre", "apellido_paterno", "apellido_materno", "correo", "password_hash", "rol", "activo", "debe_cambiar_password", "intentos_fallidos", "bloqueado_hasta", "creado_en", "actualizado_en") VALUES (3, '23170270', 'Juan Carlos', 'Pérez', 'López', '23170270@culiacan.tecnm.mx', 'scrypt:32768:8:1$lTADDyPGIcVcuT7Z$d98c45bb8c5fe4a3d3fb2ae3981c6a2ed8c82862dd510d6f8573067aebb33d2a6a21be59eed4bf960e2258f8201d8b0cdec7d8e54c2f160f001a6147c837ac99', 'ALUMNO', 1, 0, 0, NULL, '2026-11-15 20:26:52', '2026-11-18 00:18:32');
INSERT INTO usuarios ("id", "identificador", "nombre", "apellido_paterno", "apellido_materno", "correo", "password_hash", "rol", "activo", "debe_cambiar_password", "intentos_fallidos", "bloqueado_hasta", "creado_en", "actualizado_en") VALUES (4, '23170271', 'María Fernanda', 'García', 'NO REGISTRADO', '23170271@culiacan.tecnm.mx', 'scrypt:32768:8:1$RWBIBNEtazk4igoW$2332364e5c529dba5cf1468ba8476a6d54996474152acfa245f6c938b0de8c4c7fe8e6c0cbbdf4ab4ba38a89dfd0fca86cd62b19cedcb245c8b6a3bb10ef9a94', 'ALUMNO', 1, 1, 0, NULL, '2026-11-15 20:26:52', '2026-11-18 00:18:32');
INSERT INTO usuarios ("id", "identificador", "nombre", "apellido_paterno", "apellido_materno", "correo", "password_hash", "rol", "activo", "debe_cambiar_password", "intentos_fallidos", "bloqueado_hasta", "creado_en", "actualizado_en") VALUES (5, '23170272', 'Luis', 'Ramírez', 'Soto', '23170272@culiacan.tecnm.mx', 'scrypt:32768:8:1$B0KAiDh5hxm57myR$c2914a4de4dac7a2a5174388df91939e94967598b4191526547db1d4070741a9151ef55af631ea7b07beeb1b6f24341a679b5a8c1b702daafc65ba05af280f55', 'ALUMNO', 1, 1, 0, NULL, '2026-11-15 20:26:52', '2026-11-18 00:18:32');
INSERT INTO usuarios ("id", "identificador", "nombre", "apellido_paterno", "apellido_materno", "correo", "password_hash", "rol", "activo", "debe_cambiar_password", "intentos_fallidos", "bloqueado_hasta", "creado_en", "actualizado_en") VALUES (6, 'EMP003', 'DANIEL ARMANDO', 'FERNÁNDEZ', 'BONILLA', 'emp003@culiacan.tecnm.mx', 'scrypt:32768:8:1$Pne7S4XdOQxIO5to$649f447f2ecedb178c4d3b61a2989bfd4076cc5ce9bf0f28f13e64f823ee66341daf72f33462d686e99a7f82c84809eb293f77247ae84b91f80dfbae647c81d7', 'JEFE_VINCULACION', 1, 0, 0, NULL, '2026-11-15 20:33:35', '2026-11-18 00:18:32');

-- alumnos: 3 fila(s)
INSERT INTO alumnos ("usuario_id", "curp", "carrera", "semestre", "telefono", "domicilio", "plan_estudios", "creditos", "porcentaje_creditos", "foto_infantil", "boleta_extraescolares", "actualizado_en") VALUES (3, 'PELJ000101HSLRPN09', 'Ingeniería en Sistemas Computacionales', 7, '6671234567', 'Col. Centro, Culiacán, Sin.', 'NUEVO', 200, 76.92, NULL, NULL, '2026-11-18 00:18:32');
INSERT INTO alumnos ("usuario_id", "curp", "carrera", "semestre", "telefono", "domicilio", "plan_estudios", "creditos", "porcentaje_creditos", "foto_infantil", "boleta_extraescolares", "actualizado_en") VALUES (4, 'GAXM000202MSLRXR05', 'Arquitectura', 8, '6679876543', 'Col. Rosales, Culiacán, Sin.', NULL, NULL, NULL, NULL, NULL, '2026-11-18 00:18:32');
INSERT INTO alumnos ("usuario_id", "curp", "carrera", "semestre", "telefono", "domicilio", "plan_estudios", "creditos", "porcentaje_creditos", "foto_infantil", "boleta_extraescolares", "actualizado_en") VALUES (5, 'RASL010303HSLMTS02', 'Ingeniería Industrial', 9, '6671112233', 'Fracc. Las Quintas, Culiacán', NULL, NULL, NULL, NULL, NULL, '2026-11-18 00:18:32');

-- recuperaciones_password: sin datos

-- cursos_induccion: 1 fila(s)
INSERT INTO cursos_induccion ("id", "fecha", "lugar", "periodo", "qr_token", "qr_generado_en", "qr_expira_en", "activo") VALUES (1, '2026-05-27', NULL, '2026-2', NULL, NULL, NULL, 1);

-- asistencias_induccion: 3 fila(s)
INSERT INTO asistencias_induccion ("id", "curso_id", "alumno_id", "forms_completos", "registrada_en") VALUES (1, 1, 3, 1, '2026-11-15 20:26:52');
INSERT INTO asistencias_induccion ("id", "curso_id", "alumno_id", "forms_completos", "registrada_en") VALUES (2, 1, 4, 1, '2026-11-15 20:26:52');
INSERT INTO asistencias_induccion ("id", "curso_id", "alumno_id", "forms_completos", "registrada_en") VALUES (3, 1, 5, 1, '2026-11-15 20:26:52');

-- forms_induccion: sin datos

-- empresas_receptoras: 5 fila(s)
INSERT INTO empresas_receptoras ("id", "nombre", "titular_nombre", "titular_apellido_paterno", "titular_apellido_materno", "titular", "domicilio", "telefono", "creado_en", "actualizado_en") VALUES (1, 'ITC', 'Guadalupe', 'Cárdenas', 'Machado', 'Guadalupe Cárdenas Machado', 'ITC', '1234567890', '2026-11-18 00:18:32', '2026-11-18 00:18:32');
INSERT INTO empresas_receptoras ("id", "nombre", "titular_nombre", "titular_apellido_paterno", "titular_apellido_materno", "titular", "domicilio", "telefono", "creado_en", "actualizado_en") VALUES (2, 'ITC', 'Guadalupe', 'Cárdenas', 'Machado', 'Guadalupe Cárdenas Machado', 'ITC', '1234567890', '2026-11-18 00:18:32', '2026-11-18 00:18:32');
INSERT INTO empresas_receptoras ("id", "nombre", "titular_nombre", "titular_apellido_paterno", "titular_apellido_materno", "titular", "domicilio", "telefono", "creado_en", "actualizado_en") VALUES (3, 'ITC', 'Guadalupe', 'Cárdenas', 'Machado', 'Guadalupe Cárdenas Machado', 'ITC', '1234567890', '2026-11-18 00:18:32', '2026-11-18 00:18:32');
INSERT INTO empresas_receptoras ("id", "nombre", "titular_nombre", "titular_apellido_paterno", "titular_apellido_materno", "titular", "domicilio", "telefono", "creado_en", "actualizado_en") VALUES (4, 'ITC', 'Guadalupe', 'Cárdenas', 'Machado', 'Guadalupe Cárdenas Machado', 'ITC', '1234567890', '2026-11-18 00:18:32', '2026-11-18 00:18:32');
INSERT INTO empresas_receptoras ("id", "nombre", "titular_nombre", "titular_apellido_paterno", "titular_apellido_materno", "titular", "domicilio", "telefono", "creado_en", "actualizado_en") VALUES (5, 'ITC', 'Isaac', 'López', 'Sámano', 'Isaac López Sámano', 'ITC', '1234567890', '2026-11-18 00:18:32', '2026-11-18 00:18:32');

-- programas: 5 fila(s)
INSERT INTO programas ("id", "tipo", "origen", "nombre", "empresa_id", "area_responsable", "objetivo", "actividades", "horas", "cupo", "cupo_disponible", "periodo", "plan_estudios", "estatus", "creado_por", "propuesto_por", "motivo_rechazo", "validado_por", "validado_en", "creado_en", "actualizado_en") VALUES (1, 'BANCO', 'INTERNA', 'Soporte', 1, 'Victor', 'BLA', 'BLA', 480, 3, 3, '2026-2', 'NUEVO', 'DISPONIBLE', 2, NULL, NULL, NULL, NULL, '2026-11-17 19:22:20', '2026-11-18 00:18:32');
INSERT INTO programas ("id", "tipo", "origen", "nombre", "empresa_id", "area_responsable", "objetivo", "actividades", "horas", "cupo", "cupo_disponible", "periodo", "plan_estudios", "estatus", "creado_por", "propuesto_por", "motivo_rechazo", "validado_por", "validado_en", "creado_en", "actualizado_en") VALUES (2, 'PROPIA', 'INTERNA', 'Soporte de la plataforma de Ambar', 2, NULL, NULL, 'BLAB', 480, 1, 1, '2026-2', 'NUEVO', 'RECHAZADA', NULL, 3, 'blabla', 2, '2026-11-17 22:32:09', '2026-11-17 22:26:41', '2026-11-18 00:18:32');
INSERT INTO programas ("id", "tipo", "origen", "nombre", "empresa_id", "area_responsable", "objetivo", "actividades", "horas", "cupo", "cupo_disponible", "periodo", "plan_estudios", "estatus", "creado_por", "propuesto_por", "motivo_rechazo", "validado_por", "validado_en", "creado_en", "actualizado_en") VALUES (3, 'PROPIA', 'INTERNA', 'Soporte de la plataforma moodle', 3, 'Soporte digital', 'blabla', 'blabl', 480, 1, 0, '2026-2', 'AMBOS', 'APROBADA', NULL, 3, NULL, 2, '2026-11-17 22:36:58', '2026-11-17 22:36:29', '2026-11-18 00:18:32');
INSERT INTO programas ("id", "tipo", "origen", "nombre", "empresa_id", "area_responsable", "objetivo", "actividades", "horas", "cupo", "cupo_disponible", "periodo", "plan_estudios", "estatus", "creado_por", "propuesto_por", "motivo_rechazo", "validado_por", "validado_en", "creado_en", "actualizado_en") VALUES (4, 'BANCO', 'INTERNA', 'Soporte técnico', 4, 'CC', 'JADJAD', 'JDQJWD', 480, 6, 6, '2026-2', 'AMBOS', 'DISPONIBLE', 2, NULL, NULL, NULL, NULL, '2026-11-17 22:45:36', '2026-11-18 00:18:32');
INSERT INTO programas ("id", "tipo", "origen", "nombre", "empresa_id", "area_responsable", "objetivo", "actividades", "horas", "cupo", "cupo_disponible", "periodo", "plan_estudios", "estatus", "creado_por", "propuesto_por", "motivo_rechazo", "validado_por", "validado_en", "creado_en", "actualizado_en") VALUES (5, 'BANCO', 'INTERNA', 'Autimatización industrial', 5, 'IND', 'ADJAD', 'ADJDJ', 480, 5, 5, '2026-2', 'AMBOS', 'DISPONIBLE', 2, NULL, NULL, NULL, NULL, '2026-11-17 23:19:18', '2026-11-18 00:18:32');

-- planes_servicio: sin datos

-- servicios_sociales: 2 fila(s)
INSERT INTO servicios_sociales ("id", "alumno_id", "programa_id", "plan_id", "estatus", "fecha_inicio", "fecha_fin", "horas_requeridas", "creado_en", "actualizado_en") VALUES (1, 3, 2, NULL, 'BAJA', NULL, NULL, 480, '2026-11-17 22:26:41', '2026-11-18 00:18:32');
INSERT INTO servicios_sociales ("id", "alumno_id", "programa_id", "plan_id", "estatus", "fecha_inicio", "fecha_fin", "horas_requeridas", "creado_en", "actualizado_en") VALUES (2, 3, 3, NULL, 'PENDIENTE', NULL, NULL, 480, '2026-11-17 22:36:29', '2026-11-18 00:18:32');

-- bajas: 1 fila(s)
INSERT INTO bajas ("id", "servicio_id", "motivo", "fecha", "registrada_por") VALUES (1, 1, 'Propuesta propia rechazada: blabla', '2026-11-17 22:32:09', 2);

-- registro_horas: sin datos

-- periodos_entrega: sin datos

-- documentos: 3 fila(s)
INSERT INTO documentos ("id", "servicio_id", "tipo", "numero_reporte", "version", "estatus", "nombre_original", "ruta_archivo", "tamano_bytes", "subido_por", "subido_en", "revisado_por", "revisado_en") VALUES (1, 2, 'SOLICITUD', 0, 1, 'REEMPLAZADO', 'Practica_flexbox.pdf', 'alumnos/3/5e8ecc0350354d5d897412b60643a09b.pdf', 188697, 3, '2026-11-17 23:33:48', 2, '2026-11-17 23:34:34');
INSERT INTO documentos ("id", "servicio_id", "tipo", "numero_reporte", "version", "estatus", "nombre_original", "ruta_archivo", "tamano_bytes", "subido_por", "subido_en", "revisado_por", "revisado_en") VALUES (2, 2, 'SOLICITUD', 0, 2, 'VALIDADO', 'Practica_directivas_VUE.pdf', 'alumnos/3/0f835e45c45545528d7582ffc86489c3.pdf', 88419, 3, '2026-11-17 23:34:58', 2, '2026-11-17 23:35:19');
INSERT INTO documentos ("id", "servicio_id", "tipo", "numero_reporte", "version", "estatus", "nombre_original", "ruta_archivo", "tamano_bytes", "subido_por", "subido_en", "revisado_por", "revisado_en") VALUES (3, 2, 'CARTA_ACEPTACION', 0, 1, 'VALIDADO', 'Practica_directivas_VUE.pdf', 'alumnos/3/089e7466d2d94eddbf25cbb8966ac991.pdf', 88419, 3, '2026-11-17 23:38:30', 2, '2026-11-17 23:39:14');

-- observaciones: 1 fila(s)
INSERT INTO observaciones ("id", "documento_id", "autor_id", "texto", "creada_en") VALUES (1, 1, 2, 'No es el documento solicitado', '2026-11-17 23:34:34');

-- plantillas_documento: 2 fila(s)
INSERT INTO plantillas_documento ("id", "tipo", "nombre_original", "ruta_archivo", "subido_por", "subido_en") VALUES (1, 'CARTA_PRESENTACION', 'Restore de Full.docx', 'plantillas/518ad2a9b56b4f76a6055b102e4f6009.docx', 2, '2026-11-17 23:39:29');
INSERT INTO plantillas_documento ("id", "tipo", "nombre_original", "ruta_archivo", "subido_por", "subido_en") VALUES (2, 'REPORTE_BIMESTRAL', 'Restore de Full.docx', 'plantillas/25be70c51c8c4e899d23960a6468ba46.docx', 2, '2026-11-17 23:39:50');

-- expediciones: sin datos

-- constancias: sin datos

-- notificaciones: 26 fila(s)
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (1, 3, 'Se publicó un nuevo programa en el banco: Soporte', 0, '2026-11-17 19:22:20');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (2, 4, 'Se publicó un nuevo programa en el banco: Soporte', 0, '2026-11-17 19:22:20');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (3, 5, 'Se publicó un nuevo programa en el banco: Soporte', 0, '2026-11-17 19:22:20');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (4, 3, 'Su propuesta propia "Soporte de la plataforma de Ambar" quedó pendiente de validación por la Oficina de Servicio Social.', 0, '2026-11-17 22:26:41');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (5, 2, 'El alumno Juan Carlos Pérez López registró la propuesta propia "Soporte de la plataforma de Ambar" (programa 2).', 0, '2026-11-17 22:26:41');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (6, 3, 'Su propuesta propia "Soporte de la plataforma de Ambar" fue rechazada: blabla. Ya puede elegir otro programa.', 0, '2026-11-17 22:32:09');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (7, 3, 'Su propuesta propia "Soporte de la plataforma moodle" quedó pendiente de validación por la Oficina de Servicio Social.', 0, '2026-11-17 22:36:29');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (8, 2, 'El alumno Juan Carlos Pérez López registró la propuesta propia "Soporte de la plataforma moodle" (programa 3).', 0, '2026-11-17 22:36:29');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (9, 3, 'Su propuesta propia "Soporte de la plataforma moodle" fue aprobada y publicada en el banco.', 0, '2026-11-17 22:36:58');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (10, 3, 'Se publicó un nuevo programa en el banco: Soporte técnico', 0, '2026-11-17 22:45:36');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (11, 4, 'Se publicó un nuevo programa en el banco: Soporte técnico', 0, '2026-11-17 22:45:36');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (12, 5, 'Se publicó un nuevo programa en el banco: Soporte técnico', 0, '2026-11-17 22:45:36');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (13, 3, 'Se publicó un nuevo programa en el banco: Autimatización industrial', 0, '2026-11-17 23:19:18');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (14, 4, 'Se publicó un nuevo programa en el banco: Autimatización industrial', 0, '2026-11-17 23:19:18');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (15, 5, 'Se publicó un nuevo programa en el banco: Autimatización industrial', 0, '2026-11-17 23:19:18');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (16, 2, 'El alumno Juan Carlos Pérez López subió Solicitud de servicio social (servicio 2, versión 1).', 0, '2026-11-17 23:33:48');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (17, 6, 'El alumno Juan Carlos Pérez López subió Solicitud de servicio social (servicio 2, versión 1).', 0, '2026-11-17 23:33:48');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (18, 3, 'Su documento "Solicitud de servicio social" tiene observaciones: No es el documento solicitado', 0, '2026-11-17 23:34:34');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (19, 2, 'El alumno Juan Carlos Pérez López subió Solicitud de servicio social (servicio 2, versión 2).', 0, '2026-11-17 23:34:58');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (20, 6, 'El alumno Juan Carlos Pérez López subió Solicitud de servicio social (servicio 2, versión 2).', 0, '2026-11-17 23:34:58');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (21, 3, 'Su documento "Solicitud de servicio social" fue validado', 0, '2026-11-17 23:35:19');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (22, 2, 'El alumno Juan Carlos Pérez López subió Carta de aceptación (servicio 2, versión 1).', 0, '2026-11-17 23:38:30');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (23, 6, 'El alumno Juan Carlos Pérez López subió Carta de aceptación (servicio 2, versión 1).', 0, '2026-11-17 23:38:30');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (24, 3, 'Su documento "Carta de aceptación" fue validado', 0, '2026-11-17 23:39:14');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (25, 3, 'Se definió el periodo para subir Reporte bimestral #1: 2026-11-17 a 2026-11-23.', 0, '2026-11-18 00:14:01');
INSERT INTO notificaciones ("id", "usuario_id", "mensaje", "leida", "creada_en") VALUES (26, 3, 'Se programó una semana (2026-11-17 a 2026-11-23) para subir sus documentos.', 0, '2026-11-18 00:14:21');

-- bitacora: 180 fila(s)
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (1, 1, 'LOGIN', NULL, '2026-11-15 20:23:16');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (2, 1, 'LOGOUT', NULL, '2026-11-15 20:23:48');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (3, 1, 'LOGIN', NULL, '2026-11-15 20:23:51');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (4, 1, 'ALTA_USUARIO', 'Usuario creado: EMP002 (JEFE_OFICINA_SS)', '2026-11-15 20:24:55');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (5, 1, 'IMPORTAR_ALUMNOS', 'Periodo 2026-2: 3 creados, 1 omitidos', '2026-11-15 20:26:52');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (6, 1, 'LOGOUT', NULL, '2026-11-15 20:31:13');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (7, 1, 'LOGIN', NULL, '2026-11-15 20:31:26');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (8, 1, 'IMPORTAR_ALUMNOS', 'Periodo 2026-2: 0 creados, 4 omitidos', '2026-11-15 20:31:53');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (9, 1, 'ALTA_USUARIO', 'Usuario creado: EMP003 (JEFE_VINCULACION)', '2026-11-15 20:33:35');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (10, 1, 'LOGOUT', NULL, '2026-11-15 20:35:02');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (11, 3, 'LOGIN', NULL, '2026-11-15 20:35:36');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (12, 1, 'LOGIN', NULL, '2026-11-15 22:37:13');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (13, 1, 'LOGOUT', NULL, '2026-11-15 22:37:17');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (14, 1, 'LOGIN', NULL, '2026-11-15 22:37:31');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (15, 1, 'LOGOUT', NULL, '2026-11-15 22:37:39');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (16, 3, 'LOGIN', NULL, '2026-11-15 22:37:52');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (17, 3, 'CAMBIO_PASSWORD', 'Actualizó su contraseña', '2026-11-15 22:38:26');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (18, 3, 'LOGOUT', NULL, '2026-11-15 22:38:34');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (19, 3, 'LOGIN', NULL, '2026-11-15 22:38:45');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (20, 3, 'LOGOUT', NULL, '2026-11-15 22:41:55');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (21, 3, 'LOGIN', NULL, '2026-11-15 22:41:57');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (22, 3, 'LOGOUT', NULL, '2026-11-15 22:42:19');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (23, 1, 'LOGIN', NULL, '2026-11-15 22:44:05');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (24, 1, 'LOGOUT', NULL, '2026-11-15 22:46:13');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (25, 1, 'LOGIN', NULL, '2026-11-15 23:04:25');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (26, 1, 'LOGOUT', NULL, '2026-11-15 23:04:46');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (27, 2, 'LOGIN', NULL, '2026-11-15 23:04:51');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (28, 6, 'LOGIN', NULL, '2026-11-15 23:04:56');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (29, 2, 'LOGIN', NULL, '2026-11-15 23:05:01');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (30, 2, 'LOGIN', NULL, '2026-11-15 23:05:40');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (31, 2, 'LOGIN', NULL, '2026-11-15 23:05:54');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (32, 1, 'LOGIN', NULL, '2026-11-15 23:23:29');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (33, 1, 'LOGOUT', NULL, '2026-11-15 23:23:37');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (34, 2, 'LOGIN', NULL, '2026-11-15 23:23:44');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (35, 3, 'LOGIN', NULL, '2026-11-16 00:30:35');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (36, 3, 'LOGOUT', NULL, '2026-11-16 00:30:39');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (37, 3, 'LOGIN', NULL, '2026-11-16 00:31:25');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (38, 3, 'LOGOUT', NULL, '2026-11-16 00:31:26');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (39, 1, 'LOGIN', NULL, '2026-11-16 00:31:30');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (40, 1, 'LOGOUT', NULL, '2026-11-16 00:31:31');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (41, 2, 'LOGIN', NULL, '2026-11-16 00:31:34');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (42, 2, 'LOGOUT', NULL, '2026-11-16 00:42:03');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (43, 2, 'LOGIN', NULL, '2026-11-16 01:15:10');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (44, 1, 'LOGIN', NULL, '2026-11-16 01:15:16');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (45, 1, 'LOGOUT', NULL, '2026-11-16 01:15:29');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (46, 6, 'LOGIN', NULL, '2026-11-16 01:15:35');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (47, 6, 'LOGOUT', NULL, '2026-11-16 01:17:17');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (48, 2, 'LOGIN', NULL, '2026-11-16 01:17:21');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (49, 1, 'LOGIN', NULL, '2026-11-16 01:17:31');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (50, 1, 'LOGOUT', NULL, '2026-11-16 01:23:17');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (51, 1, 'LOGIN', NULL, '2026-11-16 01:23:20');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (52, 1, 'LOGOUT', NULL, '2026-11-16 01:23:23');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (53, 2, 'LOGIN', NULL, '2026-11-16 01:23:27');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (54, 2, 'LOGIN', NULL, '2026-11-16 01:23:36');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (55, 1, 'LOGIN', NULL, '2026-11-16 01:23:42');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (56, 1, 'LOGOUT', NULL, '2026-11-16 01:24:36');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (57, 2, 'LOGIN', NULL, '2026-11-16 01:24:41');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (58, 1, 'LOGIN', NULL, '2026-11-16 01:24:48');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (59, 1, 'LOGOUT', NULL, '2026-11-16 01:24:50');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (60, 2, 'LOGIN', NULL, '2026-11-16 01:24:54');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (61, 6, 'LOGIN', NULL, '2026-11-16 01:24:58');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (62, 6, 'LOGOUT', NULL, '2026-11-16 01:25:35');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (63, 3, 'LOGIN', NULL, '2026-11-16 01:25:55');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (64, 3, 'LOGOUT', NULL, '2026-11-16 01:25:59');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (65, 2, 'LOGIN', NULL, '2026-11-16 01:26:03');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (66, 1, 'LOGIN', NULL, '2026-11-16 01:26:26');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (67, 1, 'LOGOUT', NULL, '2026-11-16 01:26:29');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (68, 2, 'LOGIN', NULL, '2026-11-16 01:26:33');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (69, 2, 'LOGOUT', NULL, '2026-11-16 02:03:51');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (70, 1, 'LOGIN', NULL, '2026-11-16 02:03:54');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (71, 1, 'LOGOUT', NULL, '2026-11-16 02:03:56');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (72, 6, 'LOGIN', NULL, '2026-11-16 02:04:04');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (73, 6, 'LOGOUT', NULL, '2026-11-16 02:06:11');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (74, 2, 'LOGIN', NULL, '2026-11-16 02:06:14');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (75, 2, 'LOGOUT', NULL, '2026-11-16 02:16:51');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (76, 1, 'LOGIN', NULL, '2026-11-16 02:16:54');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (77, 1, 'LOGOUT', NULL, '2026-11-16 02:17:00');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (78, 6, 'LOGIN', NULL, '2026-11-16 02:17:03');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (79, 6, 'LOGOUT', NULL, '2026-11-16 02:22:38');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (80, 2, 'LOGIN', NULL, '2026-11-16 02:22:42');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (81, 2, 'LOGOUT', NULL, '2026-11-16 02:22:45');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (82, 1, 'LOGIN', NULL, '2026-11-16 02:22:51');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (83, 1, 'LOGOUT', NULL, '2026-11-16 02:22:55');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (84, 3, 'LOGIN', NULL, '2026-11-16 02:23:01');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (85, 3, 'LOGOUT', NULL, '2026-11-16 02:23:04');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (86, 3, 'LOGIN', NULL, '2026-11-16 02:23:38');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (87, 3, 'LOGOUT', NULL, '2026-11-16 02:25:56');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (88, 1, 'LOGIN', NULL, '2026-11-16 02:25:59');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (89, 1, 'LOGOUT', NULL, '2026-11-16 02:26:11');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (90, 2, 'LOGIN', NULL, '2026-11-16 02:26:14');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (91, 2, 'LOGOUT', NULL, '2026-11-16 02:26:21');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (92, 6, 'LOGIN', NULL, '2026-11-16 02:26:24');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (93, 6, 'LOGOUT', NULL, '2026-11-16 02:27:24');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (94, 1, 'LOGIN', NULL, '2026-11-17 17:56:01');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (95, 1, 'LOGOUT', NULL, '2026-11-17 17:57:03');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (96, 2, 'LOGIN', NULL, '2026-11-17 17:57:07');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (97, 2, 'LOGOUT', NULL, '2026-11-17 18:00:17');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (98, 3, 'LOGIN', NULL, '2026-11-17 18:00:23');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (99, 3, 'LOGOUT', NULL, '2026-11-17 18:01:22');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (100, 2, 'LOGIN', NULL, '2026-11-17 18:01:27');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (101, 2, 'LOGOUT', NULL, '2026-11-17 18:05:26');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (102, 2, 'LOGIN', NULL, '2026-11-17 19:19:36');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (103, 2, 'CAMBIO_PASSWORD', 'Actualizó su contraseña', '2026-11-17 19:20:20');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (104, 2, 'LOGIN', NULL, '2026-11-17 19:20:27');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (105, 2, 'ALTA_PROGRAMA', 'Programa ID 1: Soporte', '2026-11-17 19:22:20');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (106, 2, 'LOGOUT', NULL, '2026-11-17 19:22:42');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (107, 3, 'LOGIN', NULL, '2026-11-17 19:22:47');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (108, 3, 'LOGOUT', NULL, '2026-11-17 19:23:25');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (109, 1, 'LOGIN', NULL, '2026-11-17 19:23:29');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (110, 1, 'LOGOUT', NULL, '2026-11-17 19:23:51');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (111, 2, 'LOGIN', NULL, '2026-11-17 19:23:55');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (112, 2, 'LOGOUT', NULL, '2026-11-17 19:24:15');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (113, 6, 'LOGIN', NULL, '2026-11-17 19:24:19');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (114, 6, 'CAMBIO_PASSWORD', 'Actualizó su contraseña', '2026-11-17 19:24:39');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (115, 6, 'LOGIN', NULL, '2026-11-17 19:24:44');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (116, 6, 'LOGOUT', NULL, '2026-11-17 19:25:09');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (117, 6, 'LOGIN', NULL, '2026-11-17 22:21:56');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (118, 6, 'LOGOUT', NULL, '2026-11-17 22:22:07');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (119, 3, 'LOGIN', NULL, '2026-11-17 22:22:14');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (120, 3, 'LOGOUT', NULL, '2026-11-17 22:24:38');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (121, 1, 'LOGIN', NULL, '2026-11-17 22:24:43');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (122, 1, 'DATOS_ACADEMICOS', 'Alumno ID 3: plan NUEVO, 200 créditos', '2026-11-17 22:25:58');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (123, 1, 'LOGOUT', NULL, '2026-11-17 22:26:02');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (124, 3, 'LOGIN', NULL, '2026-11-17 22:26:10');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (125, 3, 'PROPUESTA_PROPIA', 'Propuesta propia registrada: Soporte de la plataforma de Ambar (programa 2)', '2026-11-17 22:26:41');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (126, 3, 'LOGOUT', NULL, '2026-11-17 22:29:58');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (127, 2, 'LOGIN', NULL, '2026-11-17 22:30:02');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (128, 2, 'RECHAZAR_PROPUESTA', 'Programa ID 2: blabla', '2026-11-17 22:32:09');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (129, 2, 'LOGOUT', NULL, '2026-11-17 22:32:14');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (130, 3, 'LOGIN', NULL, '2026-11-17 22:32:20');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (131, 3, 'PROPUESTA_PROPIA', 'Propuesta propia registrada: Soporte de la plataforma moodle (programa 3)', '2026-11-17 22:36:29');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (132, 3, 'LOGOUT', NULL, '2026-11-17 22:36:34');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (133, 2, 'LOGIN', NULL, '2026-11-17 22:36:39');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (134, 2, 'APROBAR_PROPUESTA', 'Programa ID 3, servicio 2', '2026-11-17 22:36:58');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (135, 2, 'LOGOUT', NULL, '2026-11-17 22:37:01');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (136, 3, 'LOGIN', NULL, '2026-11-17 22:37:09');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (137, 3, 'LOGOUT', NULL, '2026-11-17 22:43:50');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (138, 6, 'LOGIN', NULL, '2026-11-17 22:43:54');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (139, 6, 'LOGOUT', NULL, '2026-11-17 22:44:00');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (140, 2, 'LOGIN', NULL, '2026-11-17 22:44:05');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (141, 2, 'ALTA_PROGRAMA', 'Programa ID 4: Soporte técnico', '2026-11-17 22:45:36');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (142, 2, 'LOGOUT', NULL, '2026-11-17 22:45:55');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (143, 6, 'LOGIN', NULL, '2026-11-17 22:46:00');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (144, 6, 'LOGOUT', NULL, '2026-11-17 22:46:05');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (145, 3, 'LOGIN', NULL, '2026-11-17 22:46:27');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (146, 3, 'LOGOUT', NULL, '2026-11-17 23:06:15');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (147, 3, 'LOGIN', NULL, '2026-11-17 23:18:15');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (148, 3, 'LOGOUT', NULL, '2026-11-17 23:18:28');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (149, 2, 'LOGIN', NULL, '2026-11-17 23:18:33');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (150, 2, 'ALTA_PROGRAMA', 'Programa ID 5: Autimatización industrial', '2026-11-17 23:19:18');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (151, 2, 'LOGOUT', NULL, '2026-11-17 23:19:38');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (152, 3, 'LOGIN', NULL, '2026-11-17 23:19:46');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (153, 3, 'LOGOUT', NULL, '2026-11-17 23:27:29');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (154, 3, 'LOGIN', NULL, '2026-11-17 23:32:34');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (155, 3, 'SUBIR_DOCUMENTO', 'SOLICITUD #0 v1 (servicio 2)', '2026-11-17 23:33:48');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (156, 3, 'LOGOUT', NULL, '2026-11-17 23:33:59');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (157, 2, 'LOGIN', NULL, '2026-11-17 23:34:04');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (158, 2, 'REVISAR_DOCUMENTO', 'Documento ID 1: OBSERVADO', '2026-11-17 23:34:34');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (159, 2, 'LOGOUT', NULL, '2026-11-17 23:34:40');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (160, 3, 'LOGIN', NULL, '2026-11-17 23:34:44');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (161, 3, 'SUBIR_DOCUMENTO', 'SOLICITUD #0 v2 (servicio 2)', '2026-11-17 23:34:58');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (162, 3, 'LOGOUT', NULL, '2026-11-17 23:35:01');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (163, 2, 'LOGIN', NULL, '2026-11-17 23:35:06');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (164, 2, 'REVISAR_DOCUMENTO', 'Documento ID 2: VALIDADO', '2026-11-17 23:35:19');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (165, 2, 'LOGOUT', NULL, '2026-11-17 23:35:23');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (166, 3, 'LOGIN', NULL, '2026-11-17 23:35:30');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (167, 3, 'SUBIR_DOCUMENTO', 'CARTA_ACEPTACION #0 v1 (servicio 2)', '2026-11-17 23:38:30');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (168, 3, 'LOGOUT', NULL, '2026-11-17 23:38:58');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (169, 2, 'LOGIN', NULL, '2026-11-17 23:39:07');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (170, 2, 'REVISAR_DOCUMENTO', 'Documento ID 3: VALIDADO', '2026-11-17 23:39:14');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (171, 2, 'SUBIR_PLANTILLA', 'Plantilla: CARTA_PRESENTACION', '2026-11-17 23:39:29');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (172, 2, 'SUBIR_PLANTILLA', 'Plantilla: REPORTE_BIMESTRAL', '2026-11-17 23:39:50');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (173, 2, 'LOGOUT', NULL, '2026-11-17 23:39:56');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (174, 3, 'LOGIN', NULL, '2026-11-17 23:40:07');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (175, 3, 'LOGIN', NULL, '2026-11-18 00:13:11');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (176, 3, 'LOGOUT', NULL, '2026-11-18 00:13:25');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (177, 2, 'LOGIN', NULL, '2026-11-18 00:13:30');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (178, 2, 'DEFINIR_PERIODO', 'Servicio 2, REPORTE_BIMESTRAL #1: 2026-11-17 a 2026-11-23', '2026-11-18 00:14:01');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (179, 2, 'DEFINIR_SEMANA', 'Servicio 2: 2026-11-17 a 2026-11-23 (6 documentos)', '2026-11-18 00:14:21');
INSERT INTO bitacora ("id", "usuario_id", "accion", "detalle", "fecha") VALUES (180, 2, 'LOGOUT', NULL, '2026-11-18 00:15:55');

-- contacto_personal: sin datos

COMMIT;
PRAGMA foreign_keys = ON;
