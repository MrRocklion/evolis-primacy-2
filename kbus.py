import requests
from dataclasses import dataclass
from datetime import datetime

# ── Constants ──────────────────────────────────────────────────────────────────

KBUS_URL = "https://web.sistemakbus.com/kbusweb2.0/php/Administracion/readC.php"

PROFILE_ID_TO_FARE: dict[int, str] = {
    3: "ESTUDIANTE",
    4: "TERCERA EDAD",
    5: "CAPACIDADES DIFERENTES",
}
HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer token_de_autorizacion',
}
KBUS_HEADERS = {
    "Accept":            "*/*",
    "Accept-Language":   "es-419,es;q=0.6",
    "Connection":        "keep-alive",
    "Referer":           "https://web.sistemakbus.com/kbusweb2.0/admin.php",
    "User-Agent":        (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "X-Requested-With":  "XMLHttpRequest",
    "Sec-Fetch-Dest":    "empty",
    "Sec-Fetch-Mode":    "cors",
    "Sec-Fetch-Site":    "same-origin",
    "Sec-GPC":           "1",
    "sec-ch-ua":         '"Brave";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile":  "?0",
    "sec-ch-ua-platform": '"Windows"',
}

KBUS_COOKIES = {
    "PHPSESSID":        "4pprcuia47f6qnirmnpkfikcmu",
    "ID_ADMINISTRADOR": "6565",
    "LONGITUD":         "-79.201689",
    "LATITUD":          "-3.996322",
    "USUARIO":          "j1104595671",
    "TOKEN":            "45d42cef8595ef45d8d00f7cf61493ef1c6b7d29f7af5f85f5d925c7b0f66c3d",
    "IMEI":             "843890013362090600",
    "INICIO":           "0",
    "PATH":             "admin.php",
    "MODULO":           "Accesos",
    "SISTEMA":          "1",
    "NOMBRE_SISTEMA":   "",
    "ID_PERFIL":        "2",
    "ICON_SIZE":        "0",
    "LABEL_ICON_SHOW":  "false",
    "UNIDAD_DISTANCIA": "0",
    "FORMATO_FECHA":    "0",
    "FORMATO_HORA":     "0",
    "MOSTRAR_BARRIOS":  "0",
}


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class KBusResult:
    """Normalized person data returned from the KBus API."""
    dni:        str
    first_name: str
    last_name:  str
    birth_date: str   # dd/MM/yyyy
    fare_type:  str   # ESTUDIANTE | TERCERA EDAD | CAPACIDADES DIFERENTES | GENERAL


# ── Internal: raw API call ─────────────────────────────────────────────────────

def _fetch_raw(dni: str) -> dict | None:
    """
    Perform the raw GET request to KBus API.

    Returns
    -------
    dict | None
        Parsed JSON response, or None on network/HTTP error.
    """
    params = {
        "_dc":      "1981717720096",
        "param":    dni,
        "idEstado": 1,
        "idTarjeta": "",
        "page":     1,
        "start":    0,
        "limit":    250,
    }
    try:
        response = requests.get(
            KBUS_URL,
            params=params,
            headers=KBUS_HEADERS,
            cookies=KBUS_COOKIES,
            timeout=10,
        )
        response.raise_for_status()
        
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[KBus] Request error: {e}")
        return None

def _parse_birth_date(raw_date: str) -> str:
    """
    Convert API date format to UI format.
    '1968-06-26' (YYYY-MM-DD) → '26/06/1968' (dd/MM/yyyy)
    Returns empty string if parsing fails.
    """
    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return ""
# ── Public function ────────────────────────────────────────────────────────────

def search_person(dni: str) -> KBusResult | None:
    """
    Search a person by DNI in the KBus system and return normalized data.

    Parameters
    ----------
    dni : str
        ID number to search.

    Returns
    -------
    KBusResult
        Normalized person data ready to use in the UI.
    None
        If the request failed or no records were found.
    """
    raw = _fetch_raw(dni)

    if raw is None:
        return None

    records = raw.get("incidencias", [])
    if not records:
        return None

    person     = records[0]
    profile_id = person.get("idPerfilCliente")
    fare_type  = PROFILE_ID_TO_FARE.get(profile_id, "GENERAL")

    return KBusResult(
        dni        = dni,
        first_name = person.get("nombre",     ""),
        last_name  = person.get("apellido",   ""),
        birth_date = _parse_birth_date(person.get("fNacimiento", "")),  # ← conversión aquí
        fare_type  = fare_type,
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = search_person("1101702783")
    if result:
        print(f"Nombre:    {result.first_name} {result.last_name}")
        print(f"Nacimiento:{result.birth_date}")
        print(f"Tipo:      {result.fare_type}")
    else:
        print("No encontrado o error de conexion.")