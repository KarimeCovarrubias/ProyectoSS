# SistemaSS
Proyecto Ingeniería de Software

## Como clonar y abrir el repositorio en Git Bash
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
    cd SistemaSS
```
El tercer comando es para abrirlo el VS Code:
```bash
    code .
```

## Entorno virtual
Para este proyecto se utilizará **Python 3.12**, que es una versión más estable de Python y en el que muchas versiones de las 
librerías son compatibles entre sí.
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

## Ver versión instalada de Python
```bash
python --version
```

## Ejecutar app.py para acceder al sistema
Después de instalar las librerías y estar dentro del entorno virtual, se pone el siguiente comando para ejecutar el sistema:
```bash
    python app.py
```
o
```bash
    py app.py
```

Copias el link que te da la ejecución:
    http://127.0.0.1:5000/html/login.html
A mi me aparece que se ejecuta en el puerto :5000, pero puede variar.

## Ver BD en localhost
Abres una nueva consola con Shift + Ctrl + Ñ (de preferencia sin cerrar la consola de app.py)
y te vas a meter al entorno virtual y vas a poner el siguiente comando:
```bash
    sqlite_web backend/servicio_social.db -p 8080
```
copias el link que te da, normalmente es http://127.0.0.1:8080 y lo pegas en el navegador.

## GIT IGNORE
El entorno virtual lo tiene que instalar cada persona ya que es pesado y tiene muchos archivos, los pasos están arriba.

Por cuestiones de seguridad se ocultan las siguientes cosas: 
 - La base de datos: Los datos de los usuarios NO deben ser visibles en la BD.
 - El correo y el token generado para enviar un e-mail para la recuperación de la contraseña: El token que se genera es un dato muy sensible y se tiene 
 que ocultar porque alguien más puede suplantar la identidad de nosotros, pudiendo enviar spam o un link sospechoso o peligroso.

## Subir cambios al repositorio
### Subir cambios (Commit):
 - Si hiciste o modificaste algo y tienes que subir cambios, le das a la rama que aparece en la barra de la izquierda de VS Code y le das clic.
 - Aparece un cuadro para poner qué cambios hiciste, abajo confirmación (Commit), y abajo qué archivos fueron modificados, eliminados y creados.
 - Escribes los cambios que hiciste en el cuadro.
 - Le das en Commit (confirmación).
 - Sincronizar cambios.
 - Cuando termina de cargar ya se subieron los cambios.

## Descargar cambios (Pull):
 - Si quieres descargar los cambios que hizo algun compañero, te vas a la misma rama, en la sección de Graph (son los grafos de todos los cambios hechos), hay unas flechas.
 - Le das a la segunda flecha (pones el cursor) que dice "Incorporar cambios (Pull)".
 - Cuando termine de cargar te van a aparecer todos los cambios descargados en la misma sección de Graph.

## Ejecutar crear_bd.py para crear la base de datos y el usuario del administrador
Con el entorno virtual activado, introducir el siguiente comando:
```bash
py crear_bd.py
```