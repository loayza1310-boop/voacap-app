from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import math
import re
import json

app = Flask(__name__)

VOACAP_URL = "https://www.voacap.com/hf/best_freq.html"


# =========================================================
# CALCULAR DISTANCIA Y AZIMUT
# =========================================================

def calcular_distancia_azimut(lat1, lon1, lat2, lon2):
    R = 6371.0

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    distancia_km = R * c

    y = math.sin(dlon) * math.cos(lat2_rad)

    x = (
        math.cos(lat1_rad) * math.sin(lat2_rad)
        - math.sin(lat1_rad)
        * math.cos(lat2_rad)
        * math.cos(dlon)
    )

    azimut = math.degrees(math.atan2(y, x))
    azimut = (azimut + 360) % 360

    return distancia_km, azimut


# =========================================================
# ENVIAR DATOS A VOACAP ONLINE
# =========================================================

def consultar_voacap(datos):

    # -----------------------------------------------------
    # DATOS RECIBIDOS DESDE APP INVENTOR
    # -----------------------------------------------------

    fecha = datos["date"]

    txlat = float(datos["txlat"])
    txlon = float(datos["txlon"])

    rxlat = float(datos["rxlat"])
    rxlon = float(datos["rxlon"])

    # Potencia recibida desde App Inventor en WATTS
    potencia_w = float(datos["txpower"])

    # -----------------------------------------------------
    # CONVERTIR WATTS A kW
    # -----------------------------------------------------

    potencia_kw = potencia_w / 1000.0

    # -----------------------------------------------------
    # CALCULAR DISTANCIA Y AZIMUT
    # -----------------------------------------------------

    distancia_km, azimut = calcular_distancia_azimut(
        txlat,
        txlon,
        rxlat,
        rxlon
    )

    # -----------------------------------------------------
    # DATOS PARA VOACAP ONLINE
    # -----------------------------------------------------

    formulario = {
        "date": fecha,

        "txname": "TX",
        "txlat": str(txlat),
        "txlon": str(txlon),

        # VOACAP utiliza kW
        "txpower": "{:.4f}".format(potencia_kw),

        # SSB
        "txmode": "38",

        "rxname": "RX",
        "rxlat": str(rxlat),
        "rxlon": str(rxlon),

        # -------------------------------------------------
        # PARÁMETROS DE VOACAP ONLINE
        # -------------------------------------------------

        "rxalat": "38.5826",
        "rxalon": "-121.4868",

        "rxblat": "37.5272",
        "rxblon": "-77.4426",

        "rxclat": "41.8993",
        "rxclon": "12.5079",

        "rxdlat": "55.7372",
        "rxdlon": "37.6227",

        "rxelat": "35.7076",
        "rxelon": "139.7296",

        "method": "30",
        "midpoint": "0",
        "mapengine": "voacap",
        "proj": "cyl",
        "mintoa": "3.00",
        "noise": "153",
        "path": "0",
        "ssn": "-1",
        "dynssn": "",
        "es": "0",

        # -------------------------------------------------
        # CALCULADOS AUTOMÁTICAMENTE
        # -------------------------------------------------

        "deg": "{:.0f}".format(azimut),
        "km": "{:.0f}".format(distancia_km),

        # -------------------------------------------------
        # OTROS PARÁMETROS
        # -------------------------------------------------

        "lpmplat": "0",
        "lpmplon": "0",

        "spmplat": "0",
        "spmplon": "0",

        "areatime": "20",
        "arearange": "1",
        "areaband": "14.100",

        "para": "",
        "rxset": "dxcc",
        "antset": "dipoles",
        "eaa": "Y",
        "action": "",

        # -------------------------------------------------
        # ANTENAS
        # -------------------------------------------------

        "txantenna": "d60m.ant",
        "rxantenna": "2elevert.ant",

        "txantenna2": "d60m.ant",
        "txantenna3": "d60m.ant",
        "txantenna4": "d60m.ant",
        "txantenna5": "d60m.ant",
        "txantenna6": "d60m.ant",
        "txantenna7": "d60m.ant",
        "txantenna8": "d60m.ant",
        "txantenna9": "d60m.ant",

        "rxantenna2": "2elevert.ant",
        "rxantenna3": "2elevert.ant",
        "rxantenna4": "2elevert.ant",

        "rxantenna5": "d60m.ant",
        "rxantenna6": "d60m.ant",
        "rxantenna7": "d60m.ant",
        "rxantenna8": "d60m.ant",
        "rxantenna9": "d60m.ant"
    }

    # =====================================================
    # ENCABEZADOS
    # =====================================================

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://www.voacap.com/hf/",
        "Origin": "https://www.voacap.com"
    }

    # =====================================================
    # POST A VOACAP ONLINE
    # =====================================================

    respuesta = requests.post(
        VOACAP_URL,
        data=formulario,
        headers=headers,
        timeout=60
    )

    respuesta.raise_for_status()

    return respuesta.text, distancia_km, azimut, potencia_w


# =========================================================
# EXTRAER RESULTADOS REALES DE VOACAP
# =========================================================

def extraer_resultados(html):

    soup = BeautifulSoup(html, "html.parser")
    resultados = []

    # VOACAP coloca normalmente el detalle en un bloque PRE
    pre = soup.find("pre")

    if not pre:
        return resultados

    texto = pre.get_text("\n")
    lineas = texto.splitlines()

    frecuencias = {}
    parametros = {}

    for linea in lineas:

        linea = linea.strip()

        if not linea:
            continue

        partes = linea.split()

        # -------------------------------------------------
        # PRIMER ELEMENTO = UTC
        # -------------------------------------------------

        try:
            utc = int(partes[0])
        except (ValueError, IndexError):
            continue

        if utc < 1 or utc > 24:
            continue

        # -------------------------------------------------
        # SEGUNDO ELEMENTO = FRECUENCIA
        # -------------------------------------------------

        if len(partes) >= 2:

            frecuencia = partes[1]
            frecuencia_limpia = frecuencia.replace("?", "")

            try:
                float(frecuencia_limpia)

                if utc not in frecuencias:
                    frecuencias[utc] = []

                if len(frecuencias[utc]) < 3:
                    frecuencias[utc].append(frecuencia_limpia)

            except ValueError:
                pass

        # -------------------------------------------------
        # BUSCAR FOT Y MUF
        # -------------------------------------------------

        if utc not in parametros:

            numeros = []

            for valor in partes[1:]:

                valor = valor.replace("%", "")
                valor = valor.replace("?", "")
                valor = valor.replace("*", "")

                valor = re.sub(
                    r"[^0-9.\-+]",
                    "",
                    valor
                )

                if valor in ("", "-", ".", "+"):
                    continue

                try:
                    numeros.append(float(valor))
                except ValueError:
                    pass

            # Los últimos tres números se interpretan como:
            # FOT, MUF, HPF

            if len(numeros) >= 15:

                parametros[utc] = {
                    "fot": numeros[-3],
                    "muf": numeros[-2]
                }

    # =====================================================
    # CONSTRUIR RESULTADO FINAL
    # =====================================================

    for utc in sorted(frecuencias.keys()):

        lista = frecuencias[utc]

        datos_hora = parametros.get(utc, {})

        resultado = {
            "utc": utc,

            "freq1":
                lista[0]
                if len(lista) > 0
                else None,

            "freq2":
                lista[1]
                if len(lista) > 1
                else None,

            "freq3":
                lista[2]
                if len(lista) > 2
                else None,

            "fot":
                datos_hora.get("fot"),

            "muf":
                datos_hora.get("muf")
        }

        resultados.append(resultado)

    return resultados


# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

@app.route("/", methods=["GET"])
def inicio():

    return jsonify({
        "servidor": "VOACAP Online API",
        "estado": "funcionando",
        "modo": "SSB",

        "entradas": [
            "date",
            "txlat",
            "txlon",
            "rxlat",
            "rxlon",
            "txpower"
        ],

        "salidas": [
            "utc",
            "freq1",
            "freq2",
            "freq3",
            "fot",
            "muf"
        ]
    })


# =========================================================
# API PRINCIPAL
# =========================================================

@app.route("/voacap", methods=["POST"])
def voacap():

    try:

        datos = request.get_json(silent=True)

        if datos is None:

            cuerpo = request.get_data(as_text=True)

            if not cuerpo.strip():
                return jsonify({
                    "estado": "ERROR",
                    "mensaje": "No se recibieron datos"
                }), 400

            datos = json.loads(cuerpo)

        # -------------------------------------------------
        # VERIFICAR DATOS
        # -------------------------------------------------

        if not datos:

            return jsonify({
                "estado": "ERROR",
                "mensaje": "No se recibieron datos"
            }), 400

        campos_requeridos = [
            "date",
            "txlat",
            "txlon",
            "rxlat",
            "rxlon",
            "txpower"
        ]

        faltantes = []

        for campo in campos_requeridos:

            if campo not in datos:
                faltantes.append(campo)

        if faltantes:

            return jsonify({
                "estado": "ERROR",
                "mensaje": "Faltan parámetros",
                "faltantes": faltantes
            }), 400

        # -------------------------------------------------
        # CONSULTAR VOACAP
        # -------------------------------------------------

        html, distancia_km, azimut, potencia_w = consultar_voacap(datos)

        # -------------------------------------------------
        # EXTRAER RESULTADOS
        # -------------------------------------------------

        resultados = extraer_resultados(html)

        # -------------------------------------------------
        # RESPUESTA
        # -------------------------------------------------

        return jsonify({
            "estado": "OK",
            "distancia_km": round(distancia_km, 2),
            "azimut": round(azimut, 2),
            "potencia_w": round(potencia_w, 2),
            "resultados": resultados
        })

    except requests.exceptions.RequestException as e:

        return jsonify({
            "estado": "ERROR",
            "mensaje": "Error comunicando con VOACAP Online",
            "detalle": str(e)
        }), 502

    except (ValueError, TypeError, json.JSONDecodeError) as e:

        return jsonify({
            "estado": "ERROR",
            "mensaje": "Datos recibidos no válidos",
            "detalle": str(e)
        }), 400

    except Exception as e:

        return jsonify({
            "estado": "ERROR",
            "mensaje": "Error interno del servidor",
            "detalle": str(e)
        }), 500


# =========================================================
# INICIAR SERVIDOR
# =========================================================

if __name__ == "__main__":

    print("")
    print("----------------------------------------")
    print("       SERVIDOR VOACAP")
    print("----------------------------------------")
    print("Servidor iniciado")
    print("")
    print("URL local:")
    print("http://127.0.0.1:5000")
    print("")
    print("Modo: SSB")
    print("Potencia recibida: W")
    print("Potencia enviada a VOACAP: kW")
    print("----------------------------------------")
    print("")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
