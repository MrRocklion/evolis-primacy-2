import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit,
    QComboBox, QVBoxLayout, QHBoxLayout, QFrame, QStackedWidget,
    QMessageBox, QFileDialog, QSizePolicy,QDialog
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QPixmap, QFont

from bmp_card import generate_card, CardData
from evolis_print import print_card
from kbus import search_person, KBusResult
from crop import CropDialog
# ── Constants ──────────────────────────────────────────────────────────────────

USER_TYPE_TO_FARE: dict[str, str] = {
    "Estudiante":   "ESTUDIANTE",
    "Discapacidad": "CAPACIDADES DIFERENTES",
    "Tercera Edad": "TERCERA EDAD",
}

DATE_FORMAT    = "dd/MM/yyyy"
DATE_EXAMPLE   = "ej: 31/12/2025"
INPUT_HEIGHT   = 42
BUTTON_HEIGHT  = 44

STYLE_SHEET = """
    QWidget {
        background-color: #f8fafc;
        color: #1e293b;
    }
    QLineEdit, QComboBox {
        background-color: #ffffff;
        border: 1.5px solid #cbd5e1;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 11pt;
        min-height: 42px;
    }
    QLineEdit:focus, QComboBox:focus {
        border-color: #3b82f6;
    }
    QLineEdit:disabled, QComboBox:disabled {
        background-color: #f1f5f9;
        color: #94a3b8;
        border-color: #e2e8f0;
    }
    QLineEdit[invalid="true"] {
        border-color: #ef4444;
        background-color: #fff5f5;
    }
    QPushButton {
        background-color: #3b82f6;
        color: white;
        border: none;
        border-radius: 6px;
        font-size: 11pt;
        font-weight: 600;
        min-height: 44px;
        padding: 0 16px;
    }
    QPushButton:hover    { background-color: #2563eb; }
    QPushButton:pressed  { background-color: #1d4ed8; }
    QPushButton:disabled { background-color: #93c5fd; color: #e0f2fe; }
    QPushButton#secondary {
        background-color: #e2e8f0;
        color: #475569;
    }
    QPushButton#secondary:hover   { background-color: #cbd5e1; }
    QPushButton#secondary:pressed { background-color: #94a3b8; }
    QPushButton#secondary:disabled { background-color: #f1f5f9; color: #cbd5e1; }
    QPushButton#save {
        background-color: #16a34a;
        min-height: 48px;
        font-size: 12pt;
    }
    QPushButton#save:hover    { background-color: #15803d; }
    QPushButton#save:pressed  { background-color: #166534; }
    QPushButton#save:disabled { background-color: #86efac; color: #f0fdf4; }
    QFrame#card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
    }
    QLabel#section_title {
        font-size: 13pt;
        font-weight: bold;
        color: #0f172a;
    }
    QLabel#field_label {
        font-size: 10pt;
        color: #64748b;
    }
    QLabel#status_ok   { color: #16a34a; font-size: 10pt; font-weight: 600; }
    QLabel#status_warn { color: #d97706; font-size: 10pt; font-weight: 600; }
    QLabel#status_info { color: #64748b; font-size: 10pt; font-style: italic; }
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_date(text: str) -> tuple[int, int, int] | None:
    """
    Parse dd/MM/yyyy text input.
    Returns (day, month, year) tuple or None if invalid.
    """
    try:
        parts = text.strip().split("/")
        if len(parts) != 3:
            return None
        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        # Basic range validation
        if not (1 <= d <= 31 and 1 <= m <= 12 and 1900 <= y <= 2100):
            return None
        return d, m, y
    except ValueError:
        return None


def make_label(text: str, object_name: str = "field_label") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(object_name)
    return lbl


def make_input(placeholder: str = "") -> QLineEdit:
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    w.setMinimumHeight(INPUT_HEIGHT)
    return w


def make_date_input() -> QLineEdit:
    """Plain text input for dates in dd/MM/yyyy format."""
    w = make_input(DATE_EXAMPLE)
    w.setMaxLength(10)
    # Auto-insert slashes as user types
    w.textChanged.connect(lambda text, widget=w: _auto_format_date(widget, text))
    return w


def _auto_format_date(widget: QLineEdit, text: str):
    """Auto-insert '/' separators at positions 2 and 5."""
    # Strip existing slashes to work with raw digits
    digits = text.replace("/", "")
    if not digits.isdigit() and digits != "":
        # Remove non-digit, non-slash characters
        clean = "".join(c for c in text if c.isdigit())
        widget.blockSignals(True)
        widget.setText(clean)
        widget.blockSignals(False)
        return

    formatted = digits
    if len(digits) >= 3:
        formatted = digits[:2] + "/" + digits[2:]
    if len(digits) >= 5:
        formatted = digits[:2] + "/" + digits[2:4] + "/" + digits[4:8]

    if formatted != text:
        widget.blockSignals(True)
        cursor = widget.cursorPosition()
        widget.setText(formatted)
        # Adjust cursor after auto-insert
        widget.setCursorPosition(min(cursor + 1, len(formatted)))
        widget.blockSignals(False)


def make_combo(items: list[str]) -> QComboBox:
    w = QComboBox()
    w.addItems(items)
    w.setMinimumHeight(INPUT_HEIGHT)
    return w


def field_row(label: str, widget: QWidget) -> QVBoxLayout:
    """Label stacked above input widget."""
    layout = QVBoxLayout()
    layout.setSpacing(4)
    layout.addWidget(make_label(label))
    layout.addWidget(widget)
    return layout


def set_status(label: QLabel, text: str, kind: str = "info"):
    """Update status label text and style. kind: 'ok' | 'warn' | 'info'"""
    label.setObjectName(f"status_{kind}")
    label.setText(text)
    label.style().unpolish(label)
    label.style().polish(label)


def set_input_invalid(widget: QLineEdit, invalid: bool):
    """Toggle red border on invalid date inputs."""
    widget.setProperty("invalid", "true" if invalid else "false")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


# ── Main Window ────────────────────────────────────────────────────────────────

class UserRegistration(QWidget):

    def __init__(self):
        super().__init__()
        self._photo_path: str   = "profil.jpeg"
        self._form_locked: bool = True

        self.sample_data = [
            {
                "dni":"1158895671",
                "first_name":        "Juan",
                "last_name":         "Perez",
                "birth_date":        "15/05/2000",
                "disability_type":   "Fisica",
                "disability_degree": "Ligera",
                "type":"CAPACIDADES DIFERENTES"
            },
            {
                "dni":"1104595671",
                "first_name":        "JOAN DAVID",
                "last_name":         "ENCARNACION DIAZ",
                "birth_date":        "15/07/19999",
                "type":"ESTUDIANTE"
            },
            {
                "dni":"1109876543",
                "first_name":        "Maria",
                "last_name":         "Gonzalez",
                "birth_date":        "20/11/1998",
                "type":"TERCERA EDAD"
            }
        ]

        self._setup_ui()
        # BUG FIX: _lock_form called AFTER _setup_ui so all widgets exist
        self._lock_form(locked=True)

    # ── UI Setup ───────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setWindowTitle("Registro de Usuarios — CTUCL")
        self.setMinimumSize(1000, 640)
        self.setStyleSheet(STYLE_SHEET)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)
        root.addLayout(self._build_left_panel(),  2)
        root.addLayout(self._build_right_panel(), 3)

    # ── Left panel ─────────────────────────────────────────────────────────────

    def _build_left_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(12)

        photo_card = QFrame()
        photo_card.setObjectName("card")
        photo_layout = QVBoxLayout(photo_card)
        photo_layout.setContentsMargins(16, 16, 16, 16)
        photo_layout.setSpacing(12)
        photo_layout.addWidget(make_label("Foto de perfil", "section_title"))

        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumSize(220, 280)
        self.image_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_preview.setStyleSheet(
            "background:#f1f5f9; border:2px dashed #cbd5e1;"
            "border-radius:8px; color:#94a3b8; font-size:10pt;"
        )
        self.image_preview.setText("Sin imagen")

        self.load_image_button = QPushButton("Cargar imagen")
        self.load_image_button.setObjectName("secondary")
        self.load_image_button.clicked.connect(self._on_load_image)

        self.take_photo_button = QPushButton("Tomar foto")
        self.take_photo_button.setObjectName("secondary")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.load_image_button)
        btn_row.addWidget(self.take_photo_button)

        photo_layout.addWidget(self.image_preview)
        photo_layout.addLayout(btn_row)
        layout.addWidget(photo_card)
        layout.addStretch()
        return layout

    # ── Right panel ────────────────────────────────────────────────────────────

    def _build_right_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(16)

        # Search card
        search_card = QFrame()
        search_card.setObjectName("card")
        search_layout = QVBoxLayout(search_card)
        search_layout.setContentsMargins(16, 16, 16, 16)
        search_layout.setSpacing(10)
        search_layout.addWidget(make_label("Buscar beneficiario", "section_title"))

        search_row = QHBoxLayout()
        self.document_input = make_input("Ingrese numero de cedula")
        self.document_input.returnPressed.connect(self._on_search)
        self.document_input.setMinimumHeight(46)
        self.search_button = QPushButton("Buscar")
        self.search_button.setFixedWidth(130)
        self.search_button.clicked.connect(self._on_search)
        search_row.addWidget(self.document_input)
        search_row.addWidget(self.search_button)

    
        self.status_label = QLabel("Busque una cedula para continuar.")
        self.status_label.setObjectName("status_info")

        search_layout.addLayout(search_row)
        search_layout.addWidget(self.status_label)
        layout.addWidget(search_card)

        # Form card
        self.form_card = QFrame()
        self.form_card.setObjectName("card")
        form_layout = QVBoxLayout(self.form_card)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(12)

        type_row = QHBoxLayout()
        type_row.addWidget(make_label("Tipo de usuario:", "section_title"))
        self.user_type_combo = make_combo(list(USER_TYPE_TO_FARE.keys()))
        self.user_type_combo.setFixedWidth(220)
        self.user_type_combo.currentIndexChanged.connect(
            lambda i: self.stacked_widget.setCurrentIndex(i)
        )
        type_row.addWidget(self.user_type_combo)
        type_row.addStretch()

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self._build_student_page())
        self.stacked_widget.addWidget(self._build_disability_page())
        self.stacked_widget.addWidget(self._build_half_fare_page())

        form_layout.addLayout(type_row)
        form_layout.addWidget(self.stacked_widget)
        layout.addWidget(self.form_card)

        self.save_button = QPushButton("Guardar y generar tarjeta")
        self.save_button.setObjectName("save")
        self.save_button.clicked.connect(self._on_save)
        layout.addWidget(self.save_button)

        return layout

    # ── Pages ──────────────────────────────────────────────────────────────────

    def _build_student_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        self.student_first_name  = make_input("Nombres")
        self.student_last_name   = make_input("Apellidos")
        self.student_birth_date  = make_date_input()
        self.student_expiry_date = make_date_input()

        row1 = QHBoxLayout()
        row1.addLayout(field_row("Nombres",   self.student_first_name))
        row1.addLayout(field_row("Apellidos", self.student_last_name))

        row2 = QHBoxLayout()
        row2.addLayout(field_row("Fecha de nacimiento  (dd/MM/yyyy)",  self.student_birth_date))
        row2.addLayout(field_row("Fecha de vencimiento (dd/MM/yyyy)",  self.student_expiry_date))

        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addStretch()
        return widget

    def _build_disability_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        self.disability_first_name   = make_input("Nombres")
        self.disability_last_name    = make_input("Apellidos")
        self.disability_birth_date   = make_date_input()
        self.disability_type_combo   = make_combo(["Ninguna", "Fisica"])
        self.disability_degree_combo = make_combo(["Ninguna", "Ligera", "Moderada", "Grave", "Muy Grave", "Completa"])

        row1 = QHBoxLayout()
        row1.addLayout(field_row("Nombres",   self.disability_first_name))
        row1.addLayout(field_row("Apellidos", self.disability_last_name))

        row2 = QHBoxLayout()
        row2.addLayout(field_row("Fecha de nacimiento (dd/MM/yyyy)", self.disability_birth_date))

        row3 = QHBoxLayout()
        row3.addLayout(field_row("Tipo de discapacidad",  self.disability_type_combo))
        row3.addLayout(field_row("Grado de discapacidad", self.disability_degree_combo))

        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addLayout(row3)
        layout.addStretch()
        return widget

    def _build_half_fare_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        self.half_fare_first_name = make_input("Nombres")
        self.half_fare_last_name  = make_input("Apellidos")
        self.half_fare_birth_date = make_date_input()

        row1 = QHBoxLayout()
        row1.addLayout(field_row("Nombres",   self.half_fare_first_name))
        row1.addLayout(field_row("Apellidos", self.half_fare_last_name))

        row2 = QHBoxLayout()
        row2.addLayout(field_row("Fecha de nacimiento (dd/MM/yyyy)", self.half_fare_birth_date))

        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addStretch()
        return widget
    # ── Lock / unlock ──────────────────────────────────────────────────────────

    def _lock_form(self, locked: bool):
        """
        BUG FIX: Qt does not propagate setEnabled to children of QFrame
        when the frame itself is disabled. Each child widget must be
        disabled individually.
        """
        self._form_locked = locked
        for w in self._lockable_widgets():
            w.setEnabled(not locked)

    def _lockable_widgets(self) -> list[QWidget]:
        return [
            self.save_button,
            self.user_type_combo,
            self.student_first_name,     self.student_last_name,
            self.student_birth_date,     self.student_expiry_date,
            self.disability_first_name,  self.disability_last_name,
            self.disability_birth_date,
            self.disability_type_combo,  self.disability_degree_combo,
            self.half_fare_first_name,   self.half_fare_last_name,
            self.half_fare_birth_date,
            self.load_image_button,      self.take_photo_button,
        ]

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar foto de perfil", "",
            "Images (*.jpeg *.jpg *.png)"
        )
        if not path:
            return

        dialog = CropDialog(
            image_path = path,
            crop_ratio = (200, 260),   # misma proporcion que FOTO_W x FOTO_H en bmp_card
            parent     = self,
        )

        if dialog.exec() != QDialog.Accepted:
            return  # usuario canceló

        cropped = dialog.get_cropped_pixmap()
        if not cropped:
            return

        # Guardar en disco para pasarle a generate_card
        self._photo_path = f"profiles/{self.document_input.text().strip() or 'user'}.jpg"
        cropped.save(self._photo_path, "JPEG")

        # Mostrar preview en panel izquierdo
        self.image_preview.setPixmap(
            cropped.scaled(
                self.image_preview.width(),
                self.image_preview.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        self.image_preview.setText("")

    def _on_search(self):
        document = self.document_input.text().strip()
        if not document:
            QMessageBox.warning(self, "Validacion", "Ingrese un numero de cedula.")
            return

        self._clear_fields()

        # ── Llamada al API KBus ────────────────────────────────────────
        set_status(self.status_label, "Buscando...", "info")
        QApplication.processEvents()  # refresca la UI antes del request
        print(document)
        person: KBusResult | None = search_person(document)

        if person is None:
            self._lock_form(locked=False)
            self.user_type_combo.setEnabled(True)
            set_status(self.status_label, "Usuario no encontrado — complete el formulario manualmente.", "warn")
            return

        # ── Mapear fare_type → índice del combo ───────────────────────
        FARE_TO_INDEX: dict[str, int] = {
            "ESTUDIANTE":            0,
            "CAPACIDADES DIFERENTES": 1,
            "TERCERA EDAD":          2,
        }
        combo_index = FARE_TO_INDEX.get(person.fare_type, 0)

        self.user_type_combo.setCurrentIndex(combo_index)
        self.stacked_widget.setCurrentIndex(combo_index)

        # ── Autocompletar página activa ───────────────────────────────
        match combo_index:
            case 0:  # Estudiante
                self.student_first_name.setText(person.first_name)
                self.student_last_name.setText(person.last_name)
                self.student_birth_date.setText(person.birth_date)

            case 1:  # Discapacidad
                self.disability_first_name.setText(person.first_name)
                self.disability_last_name.setText(person.last_name)
                self.disability_birth_date.setText(person.birth_date)
                self._set_combo(self.disability_type_combo,   "Ninguna")
                self._set_combo(self.disability_degree_combo, "Ninguna")

            case 2:  # Tercera edad
                self.half_fare_first_name.setText(person.first_name)
                self.half_fare_last_name.setText(person.last_name)
                self.half_fare_birth_date.setText(person.birth_date)
                self._set_combo(self.half_fare_type_combo,   "Ninguna")
                self._set_combo(self.half_fare_degree_combo, "Ninguna")

        self._lock_form(locked=False)
        self.user_type_combo.setEnabled(False)
        set_status(
            self.status_label,
            f"Usuario encontrado: {person.first_name} {person.last_name} — {person.fare_type}",
            "ok",
        )
    def _on_save(self):
        index     = self.stacked_widget.currentIndex()
        user_type = self.user_type_combo.currentText()
        id_number = self.document_input.text().strip()

        # Estudiante: valida expiry. Discapacidad y Tercera Edad: sin expiry
        expiry_text  = None
        exp_widget   = None

        match index:
            case 0:  # Estudiante
                first_name   = self.student_first_name.text().strip()
                last_name    = self.student_last_name.text().strip()
                birth_text   = self.student_birth_date.text().strip()
                expiry_text  = self.student_expiry_date.text().strip()
                birth_widget = self.student_birth_date
                exp_widget   = self.student_expiry_date
            case 1:  # Discapacidad
                first_name   = self.disability_first_name.text().strip()
                last_name    = self.disability_last_name.text().strip()
                birth_text   = self.disability_birth_date.text().strip()
                birth_widget = self.disability_birth_date
            case 2:  # Tercera edad
                first_name   = self.half_fare_first_name.text().strip()
                last_name    = self.half_fare_last_name.text().strip()
                birth_text   = self.half_fare_birth_date.text().strip()
                birth_widget = self.half_fare_birth_date

        # ── Validation ────────────────────────────────────────────────
        errors = []

        if not id_number:
            errors.append("Ingrese el numero de documento.")
        if not first_name or not last_name:
            errors.append("Nombres y apellidos son obligatorios.")

        birth_parsed = parse_date(birth_text)
        set_input_invalid(birth_widget, birth_parsed is None)
        if birth_parsed is None:
            errors.append("Fecha de nacimiento invalida. Use dd/MM/yyyy.")

        # Vencimiento solo para Estudiante
        expiry_parsed = None
        if exp_widget is not None:
            expiry_parsed = parse_date(expiry_text)
            set_input_invalid(exp_widget, expiry_parsed is None)
            if expiry_parsed is None:
                errors.append("Fecha de vencimiento invalida. Use dd/MM/yyyy.")

        if errors:
            QMessageBox.warning(self, "Validacion", "\n".join(errors))
            return

        # ── Build date strings ─────────────────────────────────────────
        d, m, y  = birth_parsed
        birth_str = f"{d:02d}/{m:02d}/{y}"
        expiry_str = f"{expiry_parsed[0]:02d}/{expiry_parsed[1]:02d}/{expiry_parsed[2]}" \
                    if expiry_parsed else "SIN CADUCIDAD"

        try:
            output_path = f"cards/{id_number}.bmp"
            output = generate_card(CardData(
                id_number   = id_number,
                first_name  = first_name,
                last_name   = last_name,
                birth_date  = birth_str,
                expiry_date = expiry_str,
                fare_type   = USER_TYPE_TO_FARE[user_type],
                photo_path  = self._photo_path,
                output_path = output_path,
            ))
            QMessageBox.information(self, "Exito", f"Tarjeta generada:\n{Path(output).resolve()}")
        except FileNotFoundError as e:
            QMessageBox.critical(self, "Archivo no encontrado", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo generar la tarjeta:\n{e}")
    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _set_combo(combo: QComboBox, value: str):
        idx = combo.findText(value, Qt.MatchFixedString)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _clear_fields(self):
        # Estudiante — tiene expiry
        for w in (self.student_first_name, self.student_last_name):
            w.clear()
        self.student_birth_date.clear();  set_input_invalid(self.student_birth_date,  False)
        self.student_expiry_date.clear(); set_input_invalid(self.student_expiry_date, False)

        # Discapacidad — sin expiry
        for w in (self.disability_first_name, self.disability_last_name):
            w.clear()
        self.disability_birth_date.clear(); set_input_invalid(self.disability_birth_date, False)
        self.disability_type_combo.setCurrentIndex(0)
        self.disability_degree_combo.setCurrentIndex(0)

        # Tercera edad — sin expiry, sin combos
        for w in (self.half_fare_first_name, self.half_fare_last_name):
            w.clear()
        self.half_fare_birth_date.clear(); set_input_invalid(self.half_fare_birth_date, False)

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = UserRegistration()
    window.show()
    sys.exit(app.exec())