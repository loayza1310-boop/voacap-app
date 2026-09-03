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

    # Potencia recibida desde App Inventor en WATTS
    potencia_w = float(datos["txpower"])

    # -----------------------------------------------------
    # CONVERTIR WATTS A kW
    # -----------------------------------------------------

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

    respuesta = requests.post(
        VOACAP_URL,
        data=formulario,
        headers=headers,
        timeout=60
    )

    respuesta.raise_for_status()

    return respuesta.text, distancia_km, azimut_tx_rx, azimut_rx_tx, potencia_w


# =========================================================
# EXTRAER RESULTADOS REALES DE VOACAP
# =========================================================

def _numero_voacap(valor):
    """Convierte un campo aislado de VOACAP a número."""
    if valor is None:
        return None

    valor = str(valor).strip().replace("?", "").replace("*", "").replace("%", "")

    if valor in ("", "-", "--", "---", "."):
        return None

    if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", valor):
        return None

    try:
        return float(valor)
    except ValueError:
        return None


def _frecuencia_voacap(valor):
    """Extrae la frecuencia del SEGUNDO campo de una fila Best FREQ."""
    if valor is None:
        return None

    valor = str(valor).strip().replace("?", "").replace("*", "")

    if not re.fullmatch(r"\d+(?:\.\d+)?", valor):
        return None

    return valor


def _parsear_fila_bestfreq(linea):
    """
    Parsea UNA fila real de Best FREQ.

    Formato de VOACAP:
      UTC FREQ REL MUFday SIG10 SIG50 SIG90 dSIG
          SNR10 SNR50 SNR90 dSNR FOT MUF HPF

    Los campos SIG pueden contener '(S9+)', '(S9)', '(S0)', etc.
    Esos números de señal NO deben confundirse con FOT/MUF/HPF.
    """
    linea = linea.strip()

    # Solo aceptamos filas que comiencen con UTC 01..24.
    m = re.match(
        r"^(\d{1,2})\s+([0-9]+(?:\.[0-9]+)?[?*]?)\s+",
        linea
    )
    if not m:
        return None

    utc = int(m.group(1))
    if utc < 1 or utc > 24:
        return None

    frecuencia = _frecuencia_voacap(m.group(2))
    if frecuencia is None:
        return None

    # Eliminar los indicadores de señal entre paréntesis ANTES de
    # buscar números. Ej.: '-94 (S9+)' -> '-94'.
    sin_senales = re.sub(r"\([^)]*\)", " ", linea)

    # Tomar tokens completos, no números incrustados en texto.
    tokens = sin_senales.split()

    numeros = []
    for token in tokens[1:]:
        numero = _numero_voacap(token)
        if numero is not None:
            numeros.append(numero)

    # En una fila completa, los tres últimos campos son:
    # FOT, MUF, HPF.
    fot = None
    muf = None
    hpf = None

    if len(numeros) >= 3:
        fot = numeros[-3]
        muf = numeros[-2]
        hpf = numeros[-1]

    return {
        "utc": utc,
        "freq": frecuencia,
        "fot": fot,
        "muf": muf,
        "hpf": hpf
    }


def extraer_resultados(html):
    """
    Extrae exactamente las 3 mejores frecuencias y FOT/MUF de cada UTC.

    Regla de VOACAP Best FREQ:
      - Cada UTC aparece en 3 filas consecutivas.
      - La frecuencia es el segundo campo de cada fila.
      - La primera fila del grupo contiene FOT, MUF y HPF.
      - NO se mezclan frecuencias de otras horas.
    """
    soup = BeautifulSoup(html, "html.parser")

    pre = soup.find("pre")
    if pre:
        texto = pre.get_text("\n")
    else:
        # Fallback: algunas respuestas pueden no usar <pre>.
        texto = soup.get_text("\n")

    grupos = {}

    for linea in texto.splitlines():
        fila = _parsear_fila_bestfreq(linea)
        if not fila:
            continue

        utc = fila["utc"]

        if utc not in grupos:
            grupos[utc] = {
                "frecuencias": [],
                "fot": None,
                "muf": None,
                "hpf": None
            }

        grupo = grupos[utc]

        # Solo las TRES primeras filas de ese UTC son FREQ1/FREQ2/FREQ3.
        if len(grupo["frecuencias"]) < 3:
            grupo["frecuencias"].append(fila["freq"])

        # FOT/MUF/HPF pertenecen a la primera fila de cada UTC.
        if len(grupo["frecuencias"]) == 1 and grupo["fot"] is None:
            grupo["fot"] = fila["fot"]
            grupo["muf"] = fila["muf"]
            grupo["hpf"] = fila["hpf"]

    resultados = []

    for utc in sorted(grupos):
        grupo = grupos[utc]
        freqs = grupo["frecuencias"]

        resultados.append({
            "utc": utc,
            "freq1": freqs[0] if len(freqs) > 0 else None,
            "freq2": freqs[1] if len(freqs) > 1 else None,
            "freq3": freqs[2] if len(freqs) > 2 else None,
            "fot": grupo["fot"],
            "muf": grupo["muf"]
        })

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

        html, distancia_km, azimut_tx_rx, azimut_rx_tx, potencia_w = consultar_voacap(datos)

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
    print("Potencia recibida: W")
    print("Potencia enviada a VOACAP: kW")
    print("----------------------------------------")
    print("")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )