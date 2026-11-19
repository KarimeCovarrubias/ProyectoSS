# Generador de reportes en PDF sin librerías pesadas 






from __future__ import annotations

from datetime import datetime

ANCHO = 792.0     
ALTO = 612.0
MARGEN = 26.0

TAM_TITULO = 13
TAM_SUBTITULO = 9
TAM_TEXTO = 8.5
TAM_ENCABEZADO = 8.5
ALTO_LINEA = 10.0
PADDING = 4.0

# Limpia caracteres raros para que el texto se imprima bien dentro del PDF
def _texto_pdf(texto):

    limpio = str(texto or "").replace("\r", " ").replace("\n", " ").strip()
    return (limpio.replace("\\", "\\\\")
                   .replace("(", "\\(")
                   .replace(")", "\\)"))


def _ancho_texto(texto, tam, negrita=False):
  
    factor = 0.60 if negrita else 0.56
    return len(str(texto or "")) * tam * factor


def _partir_palabra(palabra, ancho, tam, negrita):

    partes, actual = [], ""
    for letra in palabra:
        candidato = actual + letra
        if actual and _ancho_texto(candidato, tam, negrita) > ancho:
            partes.append(actual)
            actual = letra
        else:
            actual = candidato
    if actual:
        partes.append(actual)
    return partes or [""]


def _envolver(texto, ancho, tam=TAM_TEXTO, negrita=False):

    palabras = str(texto or "").split()
    if not palabras:
        return [""]
    lineas, actual = [], ""
    for palabra in palabras:
        candidato = palabra if not actual else actual + " " + palabra
        if _ancho_texto(candidato, tam, negrita) <= ancho:
            actual = candidato
            continue
        if actual:
            lineas.append(actual)
            actual = ""
        if _ancho_texto(palabra, tam, negrita) <= ancho:
            actual = palabra
        else:
            partes = _partir_palabra(palabra, ancho, tam, negrita)
            lineas.extend(partes[:-1])
            actual = partes[-1]
    if actual:
        lineas.append(actual)
    return lineas


class _Pagina:
    def __init__(self):
        self.operaciones: list[str] = []

    def texto(self, x, y, texto, tam=TAM_TEXTO, negrita=False,
              alineacion="izq", ancho=None, color=(0, 0, 0)):
        fuente = "F2" if negrita else "F1"
        cadena = str(texto or "")
        if alineacion in ("centro", "derecha"):
            medida = _ancho_texto(cadena, tam, negrita)
            x -= medida / 2 if alineacion == "centro" else medida
        r, g, b = color
        self.operaciones.append(
            f"{r:.3f} {g:.3f} {b:.3f} rg BT /{fuente} {tam:.2f} Tf "
            f"{x:.2f} {y:.2f} Td ({_texto_pdf(cadena)}) Tj ET")

    def rectangulo(self, x, y, ancho, alto, color):
        r, g, b = color
        self.operaciones.append(
            f"{r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {y:.2f} {ancho:.2f} {alto:.2f} re f")

    def linea(self, x1, y1, x2, y2, gris=0.75, grosor=0.5):
        self.operaciones.append(
            f"{gris:.3f} {gris:.3f} {gris:.3f} RG {grosor:.2f} w "
            f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")


class Reporte:


    def __init__(self, titulo, subtitulo="", resumen=None, nota=""):
        self.titulo = titulo
        self.subtitulo = subtitulo
        self.resumen = list(resumen or [])
        self.nota = nota
        self.paginas: list[_Pagina] = []
        self.pagina = None
        self.y = 0.0
        self.generado_en = datetime.now()

       
    # Control de hojas y saltos de página
    def _nueva_pagina(self, primera=False):
        pagina = _Pagina()
        self.paginas.append(pagina)
        self.pagina = pagina
        self.y = ALTO - MARGEN

        if primera:
            pagina.texto(ANCHO / 2, self.y - 14,
                         "INSTITUTO TECNOLÓGICO DE CULIACÁN",
                         tam=TAM_TITULO, negrita=True, alineacion="centro",
                         ancho=ANCHO)
            self.y -= 24
            pagina.texto(ANCHO / 2, self.y,
                         "Departamento de Gestión Tecnológica y Vinculación · "
                         "Oficina de Servicio Social y Desarrollo Comunitario",
                         tam=TAM_SUBTITULO, alineacion="centro", ancho=ANCHO,
                         color=(0.25, 0.25, 0.25))
            self.y -= 24
            pagina.texto(ANCHO / 2, self.y, self.titulo,
                         tam=11.5, negrita=True, alineacion="centro", ancho=ANCHO)
            self.y -= 15
            if self.subtitulo:
                pagina.texto(ANCHO / 2, self.y, self.subtitulo,
                             tam=TAM_SUBTITULO, alineacion="centro", ancho=ANCHO,
                             color=(0.25, 0.25, 0.25))
                self.y -= 14

            pagina.linea(MARGEN, self.y, ANCHO - MARGEN, self.y, gris=0.55)
            self.y -= 16

            fecha = self.generado_en.strftime("%d/%m/%Y %H:%M")
            pagina.texto(MARGEN, self.y, f"Generado el: {fecha}", tam=8,
                         color=(0.35, 0.35, 0.35))
            self.y -= 13
            for linea in self.resumen:
                pagina.texto(MARGEN, self.y, linea, tam=8.5)
                self.y -= 12
            if self.resumen:
                self.y -= 3
        else:
            pagina.texto(MARGEN, self.y, self.titulo + " (continuación)",
                         tam=10, negrita=True)
            self.y -= 16

    def _salto(self):
        self._nueva_pagina()

    # Dibujo de la tabla con renglones alternados
    def tabla(self, columnas, filas):
     
        x0 = MARGEN
        ancho_total = sum(c[1] for c in columnas)
        alto_encabezado = 20.0

        def dibujar_encabezado():
            self.pagina.rectangulo(x0, self.y - alto_encabezado, ancho_total,
                                   alto_encabezado, (0.13, 0.30, 0.55))
            x = x0
            for titulo, ancho, _ in columnas:
                self.pagina.texto(x + PADDING, self.y - 13, titulo,
                                  tam=TAM_ENCABEZADO, negrita=True,
                                  color=(1, 1, 1))
                x += ancho
            self.y -= alto_encabezado

        def borde_inferior(alto):
            self.pagina.linea(x0, self.y, x0 + ancho_total, self.y, gris=0.80)
            self.y -= alto
            self.pagina.linea(x0, self.y, x0 + ancho_total, self.y, gris=0.80)

        def lineas_verticales():
            x = x0
            for _, ancho, _ in columnas:
                self.pagina.linea(x, self.y_alto, x, self.y, gris=0.85)
                x += ancho
            self.pagina.linea(x0 + ancho_total, self.y_alto,
                              x0 + ancho_total, self.y, gris=0.85)

        dibujar_encabezado()
        self.y_alto = self.y
        if not filas:
            self.pagina.texto(ANCHO / 2, self.y - 26,
                              "No hay registros para este reporte.",
                              tam=10, alineacion="centro", ancho=ANCHO,
                              color=(0.35, 0.35, 0.35))
            self.y -= 42
            return

        for indice, fila in enumerate(filas):
            celdas = []
            for _, ancho, clave in columnas:
                celdas.append(_envolver(fila.get(clave, ""), ancho - 2 * PADDING,
                                        TAM_TEXTO))
            alto = max(18.0, max(len(c) for c in celdas) * ALTO_LINEA + 6)

            if self.y - alto < MARGEN + 12:
                lineas_verticales()
                borde_inferior(0)
                self._salto()
                dibujar_encabezado()
                self.y_alto = self.y

            if indice % 2 == 1:
                self.pagina.rectangulo(x0, self.y - alto, ancho_total, alto,
                                       (0.96, 0.96, 0.97))

            x = x0
            for (_, ancho, _), renglones in zip(columnas, celdas):
                for numero, renglon in enumerate(renglones):
                    self.pagina.texto(x + PADDING,
                                      self.y - 12 - numero * ALTO_LINEA,
                                      renglon, tam=TAM_TEXTO)
                x += ancho

            lineas_verticales()
            borde_inferior(alto)

        if self.nota:
            self.y -= 10
            for renglon in _envolver(self.nota, ancho_total, 8):
                self.pagina.texto(x0, self.y, renglon, tam=8,
                                  color=(0.35, 0.35, 0.35))
                self.y -= 11

    # Genera la estructura en bytes del PDF listo para descargarse
    def guardar(self):
       
        if not self.paginas:
            self._nueva_pagina(primera=True)

        total = len(self.paginas)
        for numero, pagina in enumerate(self.paginas, start=1):
            pagina.linea(MARGEN, MARGEN - 4, ANCHO - MARGEN, MARGEN - 4,
                         gris=0.75)
            pagina.texto(MARGEN, MARGEN - 15,
                         "Sistema de Servicio Social · Reporte generado "
                         "automáticamente", tam=7.5, color=(0.4, 0.4, 0.4))
            pagina.texto(ANCHO - MARGEN, MARGEN - 15, f"Página {numero} de {total}",
                         tam=7.5, alineacion="derecha", ancho=0,
                         color=(0.4, 0.4, 0.4))

        objetos: list[bytes] = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"",  # se completa después con las páginas
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
            b"/Encoding /WinAnsiEncoding >>",
        ]
        hijos = []
        for pagina in self.paginas:
            contenido = "\n".join(pagina.operaciones).encode("cp1252", "replace")
            numero_pagina = len(objetos) + 1
            numero_contenido = numero_pagina + 1
            hijos.append(f"{numero_pagina} 0 R")
            objetos.append(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ANCHO:.0f} {ALTO:.0f}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                f"/Contents {numero_contenido} 0 R >>".encode("ascii"))
            objetos.append(
                b"<< /Length " + str(len(contenido)).encode("ascii") + b" >>\n"
                b"stream\n" + contenido + b"\nendstream")
        objetos[1] = (
            f"<< /Type /Pages /Kids [{' '.join(hijos)}] /Count {len(hijos)} >>"
            .encode("ascii"))

        salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        posiciones = []
        for numero, objeto in enumerate(objetos, start=1):
            posiciones.append(len(salida))
            salida += f"{numero} 0 obj\n".encode("ascii") + objeto + b"\nendobj\n"

        inicio_xref = len(salida)
        salida += f"xref\n0 {len(objetos) + 1}\n".encode("ascii")
        salida += b"0000000000 65535 f \n"
        for posicion in posiciones:
            salida += f"{posicion:010d} 00000 n \n".encode("ascii")
        salida += (
            f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
            f"startxref\n{inicio_xref}\n%%EOF\n").encode("ascii")
        return bytes(salida)


def generar_pdf_tabla(titulo, subtitulo, columnas, filas, resumen=None, nota=""):

    reporte = Reporte(titulo, subtitulo, resumen=resumen, nota=nota)
    reporte._nueva_pagina(primera=True)
    reporte.tabla(columnas, filas)
    return reporte.guardar()
