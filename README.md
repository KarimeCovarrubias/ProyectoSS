# SistemaSS — Sistema de Gestión del Servicio Social

Aplicación web del Instituto Tecnológico de Culiacán para administrar el proceso de Servicio Social: inducción, banco de propuestas, propuestas propias, expediente de documentos, horas, cartas de terminación y constancias.

- **Backend:** Python 3.12 + Flask 3.1 (Blueprints) + SQLite 3
- **Frontend:** HTML, CSS y JavaScript sin frameworks (archivos estáticos servidos por Flask)
- **Librerías de apoyo:** `openpyxl` (Excel del Forms), `python-docx` (formatos Word), `sqlite-web` (consulta de la base)
- **Base de datos:** un solo archivo, `backend/servicio_social.db`

---

## 1. Estructura del proyecto

```text
ProyectoSS/
├── app.py                     # Punto de entrada de Flask
├── crear_bd.py                # Crea la base desde cero y el primer administrador
├── requirements.txt           # Dependencias de Python
├── README.md                  # Este documento
├── Explicacion_Conexion_BD_e_Importacion_Excel.docx / .pdf
├── backend/
│   ├── __init__.py
│   ├── db.py                  # Conexión a SQLite
│   ├── schema.sql             # Definición de tablas
│   ├── seguridad.py           # Roles y control de acceso
│   ├── validaciones.py        # Reglas de validación
│   ├── comun.py               # Utilidades compartidas
│   ├── auth_routes.py         # API de sesión
│   ├── admin_routes.py        # API del administrador
│   ├── alumno_routes.py       # API del alumno
│   ├── jefe_routes.py         # API del Jefe de Oficina de SS
│   ├── vinculacion.py         # API del Jefe de Vinculación
│   ├── perfil_routes.py       # API de datos personales del personal
│   ├── documentos_word.py     # Generación de .docx
│   ├── documentos_pdf.py      # Generación de reportes .pdf
│   ├── migrar_bd.py           # Migración de la base con respaldo
│   ├── dump_completo.sql      # Volcado SQL con datos reales (confidencial)
│   ├── servicio_social.db     # Base de datos SQLite
│   └── rutas/
│       ├── archivos.py        # Guardado seguro de archivos subidos
│       └── documentos.py      # Descarga de documentos con permisos
├── frontend/
│   ├── html/
│   ├── js/
│   └── css/
└── uploads/                   # Archivos subidos por los usuarios
```

### 1.1. Archivos de la raíz

| Archivo | Qué hace |
| --- | --- |
| `app.py` | Crea la aplicación Flask, configura la sesión y registra los módulos de rutas; redirige `/` al login. |
| `crear_bd.py` | Borra la base anterior, ejecuta `schema.sql` y da de alta al primer administrador. |
| `requirements.txt` | Lista las dependencias de Python con sus versiones. |
| `README.md` | Documentación general del proyecto. |
| `Explicacion_Conexion_BD_e_Importacion_Excel.docx` | Documento técnico sobre la conexión a la base y la importación del Excel. |
| `Explicacion_Conexion_BD_e_Importacion_Excel.pdf` | La misma explicación en PDF. |

### 1.2. Carpeta `backend/`

| Archivo | Qué hace |
| --- | --- |
| `__init__.py` | Marca `backend` como paquete de Python. |
| `db.py` | Capa única de conexión a SQLite: `conectar()`, `transaccion()` y bitácora. |
| `schema.sql` | Define las 21 tablas, llaves foráneas, restricciones e índices. |
| `seguridad.py` | Declara los roles válidos, la respuesta uniforme de error y el decorador `login_requerido`. |
| `validaciones.py` | Reglas reutilizables: nombres, control, CURP, correo, teléfono, semestre, créditos, PDF y fechas. |
| `comun.py` | Utilidades compartidas: notificaciones, horas, documentos requeridos, periodos y estatus del servicio. |
| `auth_routes.py` | API de sesión: login, logout, sesión actual y cambio de contraseña. |
| `admin_routes.py` | API del administrador: usuarios, importación del Excel y datos académicos. |
| `alumno_routes.py` | API del alumno: perfil, programa, propuestas, documentos, horas, inducción y notificaciones. |
| `jefe_routes.py` | API del Jefe de Oficina de SS: banco, programas, documentos, servicios, horas, periodos, planes, inducción y reporte PDF. |
| `vinculacion.py` | API del Jefe de Vinculación: cartas de terminación, constancias y folios. |
| `perfil_routes.py` | API de datos personales y de contacto del personal (jefes y administrador). |
| `documentos_word.py` | Genera los formatos Word editables (solicitud, carta de presentación, constancia). |
| `documentos_pdf.py` | Genera el reporte PDF de documentos faltantes sin librerías externas. |
| `migrar_bd.py` | Migra una base existente al esquema vigente y crea un respaldo antes de tocar los datos. |
| `dump_completo.sql` | Volcado SQL de apoyo con datos reales; contiene hashes de contraseñas y es confidencial. |
| `servicio_social.db` | Base de datos SQLite del sistema (en modo WAL aparecen también `-wal` y `-shm`). |
| `rutas/archivos.py` | Valida y guarda los archivos subidos con nombre generado dentro de `uploads/`. |
| `rutas/documentos.py` | Abre o descarga documentos verificando rol y propiedad, y entrega la carta de terminación del alumno. |

### 1.3. Carpeta `frontend/html/`

| Archivo | Qué hace |
| --- | --- |
| `login.html` | Pantalla de inicio de sesión. |
| `recuperar.html` | Página de “olvidé mi contraseña”; no tiene backend, el administrador restablece la contraseña. |
| `cambiar_password.html` | Formulario para cambiar la contraseña propia. |
| `admin/inicio.html` | Panel general del administrador con resumen y actividad reciente. |
| `admin/usuarios.html` | Alta de usuarios, importación del Excel del Forms y datos académicos. |
| `admin/datos_p.html` | Datos personales del administrador. |
| `alumno/inicio.html` | Inicio del alumno con sus datos y avance de horas. |
| `alumno/carga.html` | Selección del programa y resumen de la carga actual. |
| `alumno/bp.html` | Consulta del Banco de Propuestas. |
| `alumno/pp.html` | Registro y seguimiento de propuestas propias. |
| `alumno/subir.html` | Expediente y carga de documentos en PDF. |
| `alumno/datos_p.html` | Datos personales y académicos del alumno. |
| `jefeSS/inicio.html` | Panel de la Oficina de Servicio Social. |
| `jefeSS/banco.html` | Alta y administración del Banco de Propuestas. |
| `jefeSS/propuestas.html` | Validación de propuestas propias de los alumnos. |
| `jefeSS/documentos.html` | Revisión de documentos y descarga del reporte de faltantes. |
| `jefeSS/plantillas.html` | Plantillas Word y programación de fechas de entrega. |
| `jefeSS/datos_p.html` | Datos personales del Jefe de Oficina de SS. |
| `jefeVinc/inicio.html` | Panel del Jefe de Vinculación. |
| `jefeVinc/cartas.html` | Carga de cartas de terminación y validación del PDF firmado. |
| `jefeVinc/datos_p.html` | Datos personales del Jefe de Vinculación. |
| `img/TecCul.png` | Logotipo institucional usado en las páginas. |

### 1.4. Carpeta `frontend/js/`

| Archivo | Qué hace |
| --- | --- |
| `sesion.js` | Utilidades comunes: validar sesión, menú por rol, `fetch` con manejo de errores y cambio de contraseña. |
| `login.js` | Envía el formulario de inicio de sesión. |
| `cambiar_pasword.js` | Valida y envía el cambio de contraseña. |
| `admin/inicio.js` | Carga el resumen del administrador. |
| `admin/usuarios.js` | Lista y crea usuarios, importa el Excel y genera las credenciales. |
| `admin/datos_p.js` | Datos personales del administrador. |
| `alumno/inicio.js` | Datos del alumno y avance de horas. |
| `alumno/carga.js` | Muestra los programas disponibles y registra la selección. |
| `alumno/bp.js` | Llena la tabla del Banco de Propuestas. |
| `alumno/pp.js` | Alta y consulta de propuestas propias. |
| `alumno/subir.js` | Carga de documentos, descarga de plantillas y estatus del expediente. |
| `alumno/datos_p.js` | Datos personales del alumno. |
| `jefeSS/jefe_comun.js` | Catálogos, badges y modales compartidos por las páginas del Jefe de SS. |
| `jefeSS/jefe_inicio.js` | Resumen de la Oficina de SS. |
| `jefeSS/jefe_banco.js` | Alta, edición, estatus y responsable de las propuestas del banco. |
| `jefeSS/jefe_propuestas.js` | Aprueba o rechaza propuestas propias. |
| `jefeSS/jefe_documentos.js` | Valida u observa los documentos del expediente. |
| `jefeSS/jefe_plantillas.js` | Sube plantillas y define fechas de entrega. |
| `jefeSS/datos_p.js` | Datos personales del Jefe de Oficina de SS. |
| `jefeVinc/inicio.js` | Resumen del panel de Vinculación. |
| `jefeVinc/cartas.js` | Sube la carta Word, valida u observa el PDF y emite constancias. |
| `jefeVinc/datos_p.js` | Datos personales del Jefe de Vinculación. |

### 1.5. Carpeta `frontend/css/`

| Archivo | Qué hace |
| --- | --- |
| `estilo_iniciarSesion.css` | Estilos del inicio de sesión. |
| `estilo_recuperar.css` | Estilos de la página de recuperación. |
| `admin/estilo_inicio.css` | Estilos del panel del administrador y del cambio de contraseña. |
| `admin/estilo_usuarios.css` | Estilos de la gestión de usuarios. |
| `alumno/estilo_inicio.css` | Estilos del inicio del alumno. |
| `alumno/estilo_carga.css` | Estilos de la carga y selección de programa. |
| `alumno/estilo_bp.css` | Estilos del Banco de Propuestas del alumno. |
| `alumno/estilo_pp.css` | Estilos de propuestas propias. |
| `alumno/estilo_subir.css` | Estilos del expediente y la carga de documentos. |
| `alumno/estilo_datosP.css` | Estilos de los datos personales del alumno. |
| `jefeSS/estilo_jefe.css` | Estilos de todas las páginas de la Oficina de SS. |
| `jefeVinc/estilo_inicio.css` | Estilos del panel de Vinculación. |
| `jefeVinc/estilo_cartas.css` | Estilos de la página de cartas de terminación. |

### 1.6. Carpeta `uploads/`

| Ruta | Qué contiene |
| --- | --- |
| `uploads/alumnos/<id>/` | Documentos PDF que sube cada alumno y archivos del plan antiguo. |
| `uploads/plantillas/` | Plantillas Word que sube el Jefe de Oficina de SS. |
| `uploads/cartas/` | Cartas de terminación en Word que sube Vinculación. |
| `uploads/constancias/` | Constancias generadas por Vinculación (se crea al emitir la primera). |

Los archivos no se sirven como contenido público: se descargan a través de la API, que revisa la sesión y el rol.

---

## 2. Arquitectura y convenciones

1. El navegador pide una página estática (`frontend/html/...`) y su JavaScript llama a la API con `fetch`.
2. Flask atiende la ruta en el *blueprint* correspondiente (`backend/*.py`).
3. El decorador `@login_requerido(...)` valida la sesión y el rol.
4. La ruta consulta o escribe por medio de `backend/db.py` (`conectar()` para leer, `transaccion()` para escribir).
5. La respuesta viaja como JSON (o como archivo Word/PDF cuando corresponde).

Reglas fijas del proyecto:

- **`app.py` no contiene SQL.** Toda la persistencia pasa por `backend/db.py`.
- **Consultas parametrizadas:** los valores siempre van con `?`, nunca concatenados.
- **Contraseñas con hash** (`werkzeug.security`); nunca se guardan en texto plano.
- **Sesión de 15 minutos** de inactividad, cookie `HttpOnly` y `SameSite=Lax`.
- **Roles:** `ALUMNO`, `JEFE_OFICINA_SS`, `JEFE_VINCULACION`, `ADMINISTRADOR`.
- **Bitácora:** las operaciones importantes registran quién hizo qué y cuándo.

---

## 3. API

### 3.1. Convenciones

- **Base:** `http://127.0.0.1:5000` (el puerto puede variar).
- **Formato:** JSON, salvo las rutas que reciben `multipart/form-data` (archivos) o devuelven un archivo.
- **Sesión:** cookie de Flask; sin sesión, las rutas protegidas responden `401`.
- **Errores:** `{"error": {"mensaje": "...", "codigo": "..."}}` con el código HTTP correspondiente (`400`, `401`, `403`, `404`, `409`, `423`, `500`).
- **Roles:** cada ruta declara los roles permitidos; un rol distinto recibe `403`.

### 3.2. Autenticación y sesión — `backend/auth_routes.py`

| Método | Ruta | Rol | Descripción |
| --- | --- | --- | --- |
| POST | `/api/login` | Público | Valida usuario y contraseña, aplica bloqueo tras 3 intentos fallidos e inicia la sesión. |
| POST | `/api/logout` | Cualquiera con sesión | Cierra la sesión activa. |
| GET | `/api/sesion` | Cualquiera con sesión | Devuelve id, nombre y rol del usuario autenticado. |
| POST | `/api/cambiar-password` | Cualquiera con sesión | Cambia la contraseña propia (actual, nueva y confirmación). |

### 3.3. Alumno — `backend/alumno_routes.py`

| Método | Ruta | Rol | Descripción |
| --- | --- | --- | --- |
| GET | `/api/alumno/perfil` | ALUMNO | Datos del alumno, servicio actual y avance de horas. |
| PATCH | `/api/alumno/perfil` | ALUMNO | Actualiza teléfono y domicilio. |
| GET | `/api/programas/banco` | ALUMNO | Banco de propuestas disponibles más sus propuestas aprobadas. |
| GET | `/api/alumno/programas-disponibles` | ALUMNO | Programas que puede elegir según plan, cupo y estatus. |
| POST | `/api/alumno/seleccionar-programa` | ALUMNO | Asocia un programa al alumno y crea su servicio social. |
| POST | `/api/alumno/propuesta-propia` | ALUMNO | Registra una propuesta propia interna o externa para dictamen. |
| GET | `/api/alumno/mis-propuestas` | ALUMNO | Lista sus propuestas propias con el dictamen recibido. |
| GET | `/api/alumno/avance-horas` | ALUMNO | Horas acumuladas, requeridas y porcentaje de avance. |
| GET | `/api/alumno/documentos` | ALUMNO | Expediente con estatus, fechas límite y observaciones. |
| POST | `/api/alumno/documentos` | ALUMNO | Sube un PDF validando tipo, tamaño, fecha y estado del documento. |
| GET | `/api/alumno/plantillas/<tipo>/archivo` | ALUMNO | Descarga la plantilla Word del tipo de documento. |
| GET | `/api/alumno/formatos/<tipo>` | ALUMNO | Genera el formato Word prellenado con los datos del alumno. |
| GET | `/api/alumno/induccion` | ALUMNO | Curso de inducción vigente y estado de asistencia y Forms. |
| POST | `/api/alumno/induccion/qr` | ALUMNO | Registra la asistencia con el token del código QR. |
| POST | `/api/alumno/induccion/forms` | ALUMNO | Guarda las respuestas del FORMS de inducción. |
| POST | `/api/alumno/baja` | ALUMNO | Da de baja su servicio social indicando el motivo. |

### 3.4. Jefe de Oficina de SS — `backend/jefe_routes.py`

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/api/jefe/resumen` | Contadores del panel: servicios activos, documentos pendientes, propuestas. |
| GET | `/api/jefe/plantillas` | Lista las plantillas Word disponibles por tipo. |
| POST | `/api/jefe/plantillas` | Sube o reemplaza una plantilla Word. |
| GET | `/api/jefe/plantillas/<tipo>/archivo` | Descarga una plantilla Word. |
| GET | `/api/jefe/programas` | Lista las propuestas del banco (visibles y ocultas) y las propias aprobadas. |
| POST | `/api/jefe/programas` | Crea una propuesta en el banco. |
| PATCH | `/api/jefe/programas/<id>` | Edita nombre, objetivo, actividades, horas y cupo. |
| PATCH | `/api/jefe/programas/<id>/estatus` | Oculta o vuelve a publicar una propuesta. |
| PATCH | `/api/jefe/programas/<id>/responsable` | Corrige la dependencia y el responsable. |
| GET | `/api/jefe/propuestas-propias` | Lista las propuestas propias pendientes y dictaminadas. |
| POST | `/api/jefe/propuestas-propias/<id>/validar` | Aprueba (y publica) o rechaza con motivo una propuesta propia. |
| GET | `/api/jefe/documentos` | Lista documentos de alumnos con filtros por estatus. |
| GET | `/api/jefe/documentos/<id>/archivo` | Abre un documento para revisión. |
| POST | `/api/jefe/documentos/<id>/revisar` | Marca el documento como `VALIDADO` u `OBSERVADO`. |
| GET | `/api/jefe/servicios` | Lista servicios sociales con su avance. |
| PATCH | `/api/jefe/servicios/<id>` | Registra fechas oficiales, activa o asigna plan al servicio. |
| POST | `/api/jefe/servicios/<id>/baja` | Da de baja un servicio con motivo y libera el cupo. |
| GET | `/api/jefe/servicios/<id>/horas` | Consulta las horas acumuladas del servicio. |
| POST | `/api/jefe/servicios/<id>/horas` | Registro manual de horas (obsoleto: se calculan por reporte validado). |
| GET | `/api/jefe/periodos` | Consulta las fechas de entrega por tipo de documento. |
| POST | `/api/jefe/periodos` | Define la fecha única de entrega para un documento. |
| POST | `/api/jefe/periodos/semana` | Programa una semana completa para los documentos sin fecha. |
| GET | `/api/jefe/reportes-faltantes` | Datos de alumnos con documentos vencidos sin validar. |
| GET | `/api/jefe/reportes-faltantes/pdf` | Descarga el reporte PDF de documentos faltantes. |
| GET | `/api/jefe/planes` | Lista los planes de servicio social. |
| POST | `/api/jefe/planes` | Crea un plan con actividades, cronograma y horas. |
| PATCH | `/api/jefe/planes/<id>` | Edita un plan existente. |
| DELETE | `/api/jefe/planes/<id>` | Elimina un plan que no esté en uso. |
| GET | `/api/jefe/induccion` | Lista los cursos de inducción. |
| POST | `/api/jefe/induccion` | Crea un curso de inducción. |
| POST | `/api/jefe/induccion/<id>/qr` | Genera el token del código QR (vigente 10 segundos). |
| GET | `/api/jefe/induccion/<id>/asistencias` | Consulta la asistencia y el FORMS de cada alumno. |

Todas las rutas de esta sección requieren el rol `JEFE_OFICINA_SS`.

### 3.5. Jefe de Vinculación — `backend/vinculacion.py`

Prefijo del módulo: `/api/vinculacion`. Todas las rutas requieren `JEFE_VINCULACION`.

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/resumen` | Contadores de expedientes por revisar, observados y liberados. |
| GET | `/servicios` | Servicios concluidos con búsqueda, filtro por estado y paginación. |
| POST | `/servicios/<id>/carta` | Sube o reemplaza la carta de terminación editable en Word. |
| POST | `/servicios/<id>/carta/revisar` | Valida u observa el PDF firmado que subió el alumno; solo la validación libera el servicio. |
| GET | `/servicios/<id>/constancia` | Verifica si la constancia ya puede emitirse y qué falta. |
| POST | `/servicios/<id>/constancia` | Genera la constancia en Word y registra el folio único. |
| GET | `/constancias` | Historial de constancias emitidas. |
| GET | `/constancias/<id>/archivo` | Descarga una constancia emitida. |

### 3.6. Administrador — `backend/admin_routes.py`

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/api/admin/resumen` | Totales de usuarios por rol y actividad reciente de la bitácora. |
| GET | `/api/admin/usuarios` | Lista usuarios con búsqueda y filtro por rol. |
| POST | `/api/admin/usuarios` | Crea una cuenta de alumno o de personal con su rol. |
| POST | `/api/admin/alumnos/importar` | Importa el Excel del Forms (`.xlsx`, máximo 5 MB) y genera credenciales. |
| POST | `/api/admin/alumnos/<id>/academicos` | Captura plan de estudios, créditos y documentos del plan antiguo. |
| PATCH | `/api/admin/usuarios/<id>/estado` | Activa o desactiva una cuenta. |
| POST | `/api/admin/usuarios/<id>/restablecer-password` | Restablece la contraseña (CURP del alumno o temporal para el personal). |

Todas las rutas requieren `ADMINISTRADOR`.

### 3.7. Documentos, notificaciones y perfil

| Método | Ruta | Rol | Descripción |
| --- | --- | --- | --- |
| GET | `/api/documentos/<id>/archivo` | Todos | Abre el documento en el navegador o lo descarga con `?descargar=1`, validando permisos. |
| GET | `/api/mi-carta-terminacion` | ALUMNO | Indica si ya puede descargar su carta de terminación y la entrega. |
| GET | `/api/notificaciones` | Cualquiera con sesión | Lista las notificaciones del usuario. |
| POST | `/api/notificaciones/leer` | Cualquiera con sesión | Marca notificaciones como leídas. |
| GET | `/api/personal/perfil` | Jefes y administrador | Datos personales del usuario de personal. |
| PATCH | `/api/personal/perfil` | Jefes y administrador | Actualiza sus datos de contacto. |

**Total: 73 endpoints** (4 de sesión, 16 de alumno, 2 de notificaciones, 32 del Jefe de SS, 8 de Vinculación, 7 de administrador, 2 de documentos y 2 de perfil).

---

## 4. Base de datos

- **Archivo:** `backend/servicio_social.db` (SQLite, modo WAL).
- **Esquema:** `backend/schema.sql`.
- **Conexión:** `backend/db.py` (`conectar()` para lecturas y `transaccion()` para escrituras).
- **Tablas (21):** `usuarios`, `alumnos`, `recuperaciones_password`, `cursos_induccion`, `asistencias_induccion`, `forms_induccion`, `empresas_receptoras`, `programas`, `planes_servicio`, `servicios_sociales`, `bajas`, `registro_horas`, `periodos_entrega`, `documentos`, `observaciones`, `plantillas_documento`, `expediciones`, `constancias`, `notificaciones`, `bitacora`, `contacto_personal`.

Para recrearla: `python crear_bd.py`. Para migrarla conservando datos: `python -m backend.migrar_bd`.

---

## 5. Cómo clonar y abrir el repositorio en Git Bash

Si no has instalado Git Bash, descárgalo de:
https://git-scm.com/install/windows

Sigue los siguientes pasos para instalarlo:
https://share.gemini.google/rQZEBV8rzEvi

Si ya lo tienes instalado, tienes que poner solo 3 comandos en la consola de Git Bash.

El primer comando es para clonarlo en tu computadora localmente:
```bash
    git clone https://github.com/KarimeCovarrubias/ProyectoSS.git
```
El segundo comando es para moverte al repositorio:
```bash
    cd ProyectoSS
```
El tercer comando es para abrirlo en VS Code:
```bash
    code .
```

## 6. Entorno virtual

Para este proyecto se utilizará **Python 3.12**, que es una versión más estable de Python y en el que muchas versiones de las librerías son compatibles entre sí.

Python 3.12 se puede descargar de la Microsoft Store:
https://apps.microsoft.com/detail/9NCVDN91XZQP?hl=neutral&gl=MX&ocid=pdpshare

### Instalación del entorno virtual
```bash
python -3.12 -m venv .venv
```
o
```bash
py -3.12 -m venv .venv
```

### Acceder al entorno virtual en Windows
```bash
.venv\Scripts\activate.bat
```
o
```bash
.venv\Scripts\Activate.ps1
```

### Acceder al entorno virtual en Mac o Linux
```bash
source .venv/bin/activate
```

### Instalar las librerías necesarias (requirements.txt)
```bash
pip install -r requirements.txt
```

#### Verificar qué se instaló
```bash
pip list
```

### Desactivar el entorno
```bash
deactivate
```

## 7. Ver versión instalada de Python
```bash
python --version
```

## 8. Ejecutar app.py para acceder al sistema

Después de instalar las librerías y estar dentro del entorno virtual, se pone el siguiente comando para ejecutar el sistema:
```bash
    python app.py
```
o
```bash
    py app.py
```

Copia el enlace que te da la ejecución:
```text
    http://127.0.0.1:5000/html/login.html
```
En este equipo aparece en el puerto `5000`, pero puede variar.

## 9. Ver la base de datos en localhost

Abre una nueva consola con `Shift + Ctrl + Ñ` (de preferencia sin cerrar la consola de `app.py`), entra al entorno virtual y ejecuta:
```bash
    sqlite_web backend/servicio_social.db -p 8080
```
Copia el enlace que te da, normalmente `http://127.0.0.1:8080`, y pégalo en el navegador.

## 10. Ejecutar crear_bd.py para crear la base de datos y el usuario administrador

Con el entorno virtual activado:
```bash
    py crear_bd.py
```

## 11. GIT IGNORE

El entorno virtual lo tiene que instalar cada persona, ya que es pesado y tiene muchos archivos; los pasos están arriba.

Por cuestiones de seguridad se ocultan las siguientes cosas:

- **La base de datos:** los datos de los usuarios no deben ser visibles en el repositorio.
- **El correo y el token de recuperación de contraseña:** son datos sensibles que permitirían suplantar identidades o enviar enlaces peligrosos.

## 12. Subir cambios al repositorio

### Subir cambios (Commit)
- Si hiciste o modificaste algo y tienes que subir cambios, da clic en la rama que aparece en la barra de la izquierda de VS Code.
- Aparece un cuadro para escribir qué cambios hiciste, abajo la confirmación (Commit) y la lista de archivos modificados, eliminados y creados.
- Escribe los cambios en el cuadro.
- Da clic en Commit.
- Sincroniza los cambios.
- Cuando termina de cargar, los cambios ya se subieron.

### Descargar cambios (Pull)
- Si quieres descargar los cambios que hizo otro compañero, ve a la misma rama y entra a la sección Graph (los grafos de todos los cambios hechos).
- Da clic en la segunda flecha (“Incorporar cambios / Pull”).
- Cuando termine de cargar aparecerán todos los cambios descargados en la misma sección.

## 13. Notas y pendientes conocidos

- `frontend/html/recuperar.html` no tiene backend ni JavaScript: la recuperación real se hace desde el panel del administrador con “Restablecer contraseña”.
- Los endpoints `/api/notificaciones` y `/api/notificaciones/leer` existen y el sistema genera avisos, pero ninguna pantalla los muestra todavía; solo se contabilizan los no leídos en el perfil del alumno.
- La importación del Excel crea la cuenta, los datos del alumno y la asistencia a inducción; **no** crea el servicio social ni captura plan y créditos.
- Las horas no se capturan a mano: se acumulan 160 horas por cada reporte bimestral validado (máximo 3 reportes).
- La carta de terminación la genera Vinculación en Word; el alumno la firma, sube el PDF y Vinculación lo valida para liberar el servicio.
- `backend/dump_completo.sql` contiene datos reales y hashes de contraseñas: no debe compartirse ni publicarse.
