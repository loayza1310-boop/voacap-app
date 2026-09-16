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

    # Azimut inverso: RX -> TX
    azimut_rx_tx = (azimut + 180) % 360

    return distancia_km, azimut, azimut_rx_tx


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

    # -----------------------------------------------------
    # POTENCIA TX FIJA
    # -----------------------------------------------------
    # La aplicación utilizará siempre 25 W.
    # Ya no depende del valor enviado por App Inventor.
    potencia_w = 25.0

    # VOACAP utiliza kW
    potencia_kw = potencia_w / 1000.0

    # -----------------------------------------------------
    # CALCULAR DISTANCIA Y AZIMUT
    # -----------------------------------------------------

    distancia_km, azimut_tx_rx, azimut_rx_tx = calcular_distancia_azimut(
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

        "method": "9",
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

        "deg": "{:.0f}".format(azimut_tx_rx),
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

    session = requests.Session()

    respuesta = session.post(
        VOACAP_URL,
        data=formulario,
        headers=headers,
        timeout=60
    )

    respuesta.raise_for_status()

    return (
        session,
        respuesta.text,
        distancia_km,
        azimut_tx_rx,
        azimut_rx_tx,
        potencia_w
    )


# =========================================================
# EXTRAER RESULTADOS REALES DE VOACAP
# =========================================================

def _extraer_url_prediction(html):
    """
    Busca la URL dinámica de prediction.txt que genera VOACAP Online.
    Ejemplo:
      /hf/predictions/27381b798a2d/prediction.txt
    """
    patrones = [
        r'https?://(?:www\.)?voacap\.com/hf/predictions/[^"\'>\s]+/prediction\.txt',
        r'/hf/predictions/[^"\'>\s]+/prediction\.txt',
    ]

    for patron in patrones:
        m = re.search(patron, html, re.IGNORECASE)
        if m:
            url = m.group(0)

            if url.startswith("/"):
                url = "https://www.voacap.com" + url

            # Limpiar posibles caracteres finales
            url = url.rstrip('\'"<>')
            return url

    return None


def _numero_simple(valor):
    """Convierte un campo numérico de prediction.txt a float."""
    if valor is None:
        return None

    valor = str(valor).strip()
    valor = valor.replace("?", "").replace("*", "").replace("%", "")

    try:
        return float(valor)
    except (ValueError, TypeError):
        return None


def extraer_fot_muf_prediction(prediction_txt):
    """
    Extrae FOT y MUF directamente del prediction.txt REAL de VOACAP.

    Formato observado:

        GMT   LMT    FOT    HPF  ESMUF    MUF    LUF
        1.0  19.9   8.14  12.16   0.00  10.31  -8.78

    Columnas:
        GMT, LMT, FOT, HPF, ESMUF, MUF, LUF

    Se conservan los decimales originales de VOACAP.
    """
    resultados = []
    tabla_encontrada = False

    for linea in prediction_txt.splitlines():
        linea_limpia = linea.strip()

        if not linea_limpia:
            continue

        compacta = re.sub(r"\s+", " ", linea_limpia).upper()

        if re.search(
            r"\bGMT\b\s+\bLMT\b\s+\bFOT\b\s+\bHPF\b\s+\bESMUF\b\s+\bMUF\b\s+\bLUF\b",
            compacta
        ):
            tabla_encontrada = True
            continue

        if not tabla_encontrada:
            continue

        m = re.match(
            r"^(\d{1,2}(?:\.\d+)?)\s+"
            r"([-+]?\d+(?:\.\d+)?)\s+"
            r"([-+]?\d+(?:\.\d+)?)\s+"
            r"([-+]?\d+(?:\.\d+)?)\s+"
            r"([-+]?\d+(?:\.\d+)?)\s+"
            r"([-+]?\d+(?:\.\d+)?)\s+"
            r"([-+]?\d+(?:\.\d+)?)",
            linea_limpia
        )

        if not m:
            continue

        hora = float(m.group(1))
        fot = float(m.group(3))
        hpf = float(m.group(4))
        muf = float(m.group(6))

        utc = int(round(hora))

        if utc < 1 or utc > 24:
            continue

        resultados.append({
            "utc": utc,
            "fot": fot,
            "muf": muf,
            "hpf": hpf
        })

        if len(resultados) >= 24:
            break

    return resultados


def extraer_resultados(html, session):
    """
    Obtiene prediction.txt generado por VOACAP Online y extrae
    directamente FOT/MUF/HPF del Method 9.

    Si VOACAP no entrega el enlace prediction.txt, se informa
    claramente en vez de devolver datos incorrectos.
    """

    url_prediction = _extraer_url_prediction(html)

    if not url_prediction:
        raise RuntimeError(
            "VOACAP no devolvió el enlace dinámico a prediction.txt"
        )

    respuesta_txt = session.get(
        url_prediction,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.voacap.com/hf/"
        },
        timeout=60
    )

    respuesta_txt.raise_for_status()

    prediction_txt = respuesta_txt.text

    resultados = extraer_fot_muf_prediction(prediction_txt)

    if not resultados:
        # Guardamos una pequeña pista en el error para saber
        # si VOACAP cambió el formato.
        muestra = "\n".join(prediction_txt.splitlines()[:80])

        raise RuntimeError(
            "Se encontró prediction.txt, pero no se encontró la "
            "tabla GMT MUF FOT HPF de Method 9.\n\n"
            "Inicio de prediction.txt:\n" + muestra
        )

    return resultados


# =========================================================
# PÁGINA PRINCIPAL
# =========================================================
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
            "rxlon"
        ],

        "salidas": [
            "utc",
            "freq1",
            "freq2",
            "freq3",
            "fot",
            "muf",
            "azimut",
            "azimut_rx_tx"
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
            "rxlon"
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

        (
            session,
            html,
            distancia_km,
            azimut_tx_rx,
            azimut_rx_tx,
            potencia_w
        ) = consultar_voacap(datos)

        # -------------------------------------------------
        # EXTRAER FOT / MUF DESDE prediction.txt
        # -------------------------------------------------

        resultados = extraer_resultados(html, session)

        # -------------------------------------------------
        # RESPUESTA
        # -------------------------------------------------

        return jsonify({
            "estado": "OK",
            "distancia_km": round(distancia_km, 2),
            "azimut": round(azimut_tx_rx, 2),
            "azimut_rx_tx": round(azimut_rx_tx, 2),
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
    print("Fuente FOT/MUF: prediction.txt - tabla GMT/LMT/FOT/HPF/ESMUF/MUF/LUF")
    print("Potencia TX fija: 25 W")
    print("Potencia enviada a VOACAP: kW")
    print("----------------------------------------")
    print("")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )