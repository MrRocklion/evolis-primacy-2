from PIL import Image, ImageDraw, ImageFont
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path


# ── Enums ──────────────────────────────────────────────────────────────────────


# ── Constants ──────────────────────────────────────────────────────────────────

CARD_WIDTH   = 1016
CARD_HEIGHT  = 648

DECO_HEIGHT  = 60
AREA_PADDING = 20

PHOTO_WIDTH  = 200
PHOTO_HEIGHT = 260
LOGO_WIDTH   = 200
LOGO_HEIGHT  = 120

MARGIN       = 40
GAP          = 30
LABEL_WIDTH  = 155
LINE_HEIGHT  = 48

COLOR_WHITE  = (255, 255, 255)
COLOR_LABEL  = (0, 0, 204)
COLOR_VALUE  = (0,  0,  0)



# ── Dataclass ──────────────────────────────────────────────────────────────────

@dataclass
class CardData:
    id_number:      str
    first_name:     str
    last_name:      str
    birth_date:     str
    expiry_date:    str
    fare_type:      str
    photo_path:     str = "profil.jpeg"
    logo_path:      str = "assets/logo.jpeg"
    output_path:    str = "front.bmp"


# ── Helpers ────────────────────────────────────────────────────────────────────

    # En _load_fonts cambia el try/except:
def _load_fonts(sizes: dict[str, int]) -> dict[str, ImageFont.FreeTypeFont]:
    font_map = {
        "deco":       ("arial.ttf",  sizes["deco"]),
        "label":      ("arial.ttf",  sizes["label"]),
        "label_bold": ("arialbd.ttf", sizes["label_bold"]),  # arialbd = Arial Bold
        "value":      ("arial.ttf",  sizes["value"]),
    }
    try:
        return {key: ImageFont.truetype(path, size) for key, (path, size) in font_map.items()}
    except OSError:
        default = ImageFont.load_default()
        return {key: default for key in font_map}


def _paste_image(canvas: Image.Image, path: str, size: tuple[int, int], position: tuple[int, int]) -> None:
    """Open, resize and paste an image onto the canvas."""
    source = Image.open(path).convert("RGB").resize(size)
    canvas.paste(source, position)


def _center_y(area_start: int, area_height: int, element_height: int) -> int:
    """Return the Y coordinate to vertically center an element in an area."""
    return area_start + (area_height - element_height) // 2


# ── Main function ──────────────────────────────────────────────────────────────

def generate_card(data: CardData) -> Path:
    """
    Generate an ID card image in BMP format (1016x648 px, CR80 at 300 dpi).

    Parameters
    ----------
    data : CardData
        Dataclass containing all the fields required to build the card.

    Returns
    -------
    Path
        Path to the generated BMP file.

    Raises
    ------
    FileNotFoundError
        If photo or logo files are not found.
    """
    # ── Validate input files ───────────────────────────────────────
    for file_path in (data.photo_path, data.logo_path):
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")

    # ── Layout calculations ────────────────────────────────────────
    area_y_start = DECO_HEIGHT + AREA_PADDING
    area_y_end   = CARD_HEIGHT - DECO_HEIGHT - AREA_PADDING
    area_height  = area_y_end - area_y_start

    text_area_width = CARD_WIDTH - (MARGIN + PHOTO_WIDTH + GAP + GAP + LOGO_WIDTH + MARGIN)

    photo_x = MARGIN
    text_x  = photo_x + PHOTO_WIDTH + GAP
    logo_x  = text_x  + text_area_width + GAP

    photo_y = _center_y(area_y_start, area_height, PHOTO_HEIGHT)

    # ── Canvas ─────────────────────────────────────────────────────
    canvas = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), color=COLOR_WHITE)
    draw   = ImageDraw.Draw(canvas)



    # ── Fonts ──────────────────────────────────────────────────────
    fonts = _load_fonts({
        "deco":        26,
        "label":       24,
        "label_bold":  26,   # mismo tamaño, distinto archivo
        "value":       28,
    })

    

    # ── Fare label on bottom band ──────────────────────────────────
    draw.text(
        (CARD_WIDTH // 2, CARD_HEIGHT - DECO_HEIGHT // 2),
        data.fare_type.upper(),
        fill=COLOR_WHITE,
        font=fonts["deco"],
        anchor="mm",
    )

    # ── Photo and logo ─────────────────────────────────────────────
    _paste_image(canvas, data.photo_path, (PHOTO_WIDTH, PHOTO_HEIGHT), (photo_x, photo_y))
    _paste_image(canvas, data.logo_path,  (LOGO_WIDTH,  LOGO_HEIGHT),  (logo_x,  320))

    # ── Text fields ────────────────────────────────────────────────
    # if self.fare_type  === FareType.no
    if data.fare_type == 'ESTUDIANTE':
        fields = [
            ("Cedula:",           data.id_number),
            ("Apellidos:",    data.last_name.upper()),
            ("Nombres:",   data.first_name.upper()),
            ("F. nacimiento:",   data.birth_date),
            ("Vencimiento:",  data.expiry_date),
            ("Tipo de tarifa:",  data.fare_type),

        ]
    else:
        fields = [
            ("Cedula: ",           data.id_number),
            ("Apellidos: ",    data.last_name.upper()),
            ("Nombres: ",   data.first_name.upper()),
            ("F. nacimiento: ",   data.birth_date),
            ("Vencimiento: ",  'SIN CADUCIDAD'),
            ("Tipo de tarifa:",  data.fare_type),
        ]


    total_text_height = LINE_HEIGHT * len(fields)
    text_start_y      = _center_y(area_y_start, area_height, total_text_height)

    for index, (label, value) in enumerate(fields):
        y = text_start_y + index * LINE_HEIGHT + LINE_HEIGHT // 2
        if label=='Tipo de tarifa:':
            draw.text((text_x,               y), label, fill=COLOR_LABEL, font=fonts["label_bold"], anchor="lm")
            draw.text((text_x +40+ LABEL_WIDTH, y), value, fill=COLOR_LABEL, font=fonts["label_bold"], anchor="lm")
        else:
            draw.text((text_x,               y), label, fill=COLOR_LABEL, font=fonts["label_bold"], anchor="lm")
            draw.text((text_x +20+ LABEL_WIDTH, y), value, fill=COLOR_VALUE, font=fonts["label_bold"], anchor="lm")

    # ── Save ───────────────────────────────────────────────────────
    output = Path(data.output_path)
    canvas.save(output)
    return output