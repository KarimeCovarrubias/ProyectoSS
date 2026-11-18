"""Sistema de Gestión del Servicio Social - aplicación Flask.

Uso (desde la carpeta SistemaSS):
    python crear_bd.py      (solo la primera vez)
    python app.py           -> abre http://localhost:5000
"""
import os
from datetime import timedelta
from flask import Flask, redirect

from backend.auth_routes import auth_bp
from backend.admin_routes import admin_bp
from backend.alumno_routes import alumno_bp
from backend.jefe_routes import jefe_bp
from backend.perfil_routes import perfil_bp
from backend.vinculacion import bp as vinculacion_bp
from backend.rutas.documentos import bp as documentos_bp

app = Flask(__name__, static_folder="frontend", static_url_path="")
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "clave-solo-para-desarrollo-cambiala"),
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=15),   # RNF-02: 15 min de inactividad
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# Registrar los Blueprints (módulos de rutas)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(alumno_bp)
app.register_blueprint(jefe_bp)
app.register_blueprint(perfil_bp)
app.register_blueprint(vinculacion_bp)
app.register_blueprint(documentos_bp)


@app.get("/")
def inicio():
    return redirect("/html/login.html")


if __name__ == "__main__":
    app.run(debug=True)