from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy, QSlider
)
from PySide6.QtCore import Qt, QRect, QPoint, QSize
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QImage


class CropDialog(QDialog):
    """
    Modal dialog to crop an image with a draggable/resizable selection.
    Opens the source image, lets the user drag a crop rectangle,
    and returns the cropped QPixmap on accept.
    """

    HANDLE_SIZE = 10  # px, corner handle hit area

    def __init__(self, image_path: str, crop_ratio: tuple[int, int] = (200, 260), parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recortar foto de perfil")
        self.setMinimumSize(700, 560)
        self.setModal(True)

        self._source_path  = image_path
        self._crop_ratio   = crop_ratio          # (w, h) ratio for the crop box
        self._cropped_pixmap: QPixmap | None = None

        self._origin_pixmap: QPixmap = QPixmap(image_path)
        self._scale         = 1.0                # display scale factor
        self._offset        = QPoint(0, 0)       # top-left of image in canvas

        # Crop rect in image coordinates
        self._crop_rect  = QRect()
        self._dragging   = False
        self._resizing   = False
        self._drag_start = QPoint()
        self._rect_start = QRect()

        self._setup_ui()
        self._init_crop_rect()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Canvas
        self.canvas = _CropCanvas(self)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setMinimumSize(600, 440)
        layout.addWidget(self.canvas)

        # Hint label
        hint = QLabel("Arrastra para mover la seleccion • Esquinas para redimensionar")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #64748b; font-size: 9pt;")
        layout.addWidget(hint)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setObjectName("secondary")
        self.cancel_button.setFixedWidth(120)
        self.cancel_button.clicked.connect(self.reject)

        self.save_button = QPushButton("Guardar recorte")
        self.save_button.setFixedWidth(160)
        self.save_button.clicked.connect(self._on_save)

        btn_row.addWidget(self.cancel_button)
        btn_row.addWidget(self.save_button)
        layout.addLayout(btn_row)

    # ── Init crop rect centered ────────────────────────────────────────────────

    def _init_crop_rect(self):
        """Place initial crop rect centered in the image, respecting ratio."""
        img_w = self._origin_pixmap.width()
        img_h = self._origin_pixmap.height()
        rw, rh = self._crop_ratio

        # Make crop cover ~60% of the shorter dimension
        scale  = min(img_w / rw, img_h / rh) * 0.6
        cw     = int(rw * scale)
        ch     = int(rh * scale)
        cx     = (img_w - cw) // 2
        cy     = (img_h - ch) // 2
        self._crop_rect = QRect(cx, cy, cw, ch)

    # ── Coordinate helpers ─────────────────────────────────────────────────────

    def _to_canvas(self, p: QPoint) -> QPoint:
        """Image coords → canvas coords."""
        return QPoint(
            int(p.x() * self._scale) + self._offset.x(),
            int(p.y() * self._scale) + self._offset.y(),
        )

    def _to_image(self, p: QPoint) -> QPoint:
        """Canvas coords → image coords."""
        return QPoint(
            int((p.x() - self._offset.x()) / self._scale),
            int((p.y() - self._offset.y()) / self._scale),
        )

    def _canvas_rect(self) -> QRect:
        """Crop rect in canvas coordinates."""
        tl = self._to_canvas(self._crop_rect.topLeft())
        br = self._to_canvas(self._crop_rect.bottomRight())
        return QRect(tl, br)

    def _clamp_rect(self, rect: QRect) -> QRect:
        """Keep crop rect within image bounds."""
        img_w = self._origin_pixmap.width()
        img_h = self._origin_pixmap.height()
        x = max(0, min(rect.x(), img_w - rect.width()))
        y = max(0, min(rect.y(), img_h - rect.height()))
        w = max(20, min(rect.width(),  img_w - x))
        h = max(20, min(rect.height(), img_h - y))
        return QRect(x, y, w, h)

    def _near_corner(self, canvas_pos: QPoint) -> str | None:
        """Return which corner handle is near the point, or None."""
        cr   = self._canvas_rect()
        hs   = self.HANDLE_SIZE
        corners = {
            "tl": cr.topLeft(),
            "tr": cr.topRight(),
            "bl": cr.bottomLeft(),
            "br": cr.bottomRight(),
        }
        for name, pt in corners.items():
            if abs(canvas_pos.x() - pt.x()) <= hs and abs(canvas_pos.y() - pt.y()) <= hs:
                return name
        return None

    # ── Mouse events (forwarded from canvas) ───────────────────────────────────

    def on_mouse_press(self, pos: QPoint):
        self._drag_start = pos
        self._rect_start = QRect(self._crop_rect)
        corner = self._near_corner(pos)
        if corner:
            self._resizing = corner
            self._dragging = False
        elif self._canvas_rect().contains(pos):
            self._dragging = True
            self._resizing = False

    def on_mouse_move(self, pos: QPoint):
        delta_img = QPoint(
            int((pos.x() - self._drag_start.x()) / self._scale),
            int((pos.y() - self._drag_start.y()) / self._scale),
        )
        rw, rh = self._crop_ratio

        if self._dragging:
            new_rect = QRect(
                self._rect_start.x() + delta_img.x(),
                self._rect_start.y() + delta_img.y(),
                self._rect_start.width(),
                self._rect_start.height(),
            )
            self._crop_rect = self._clamp_rect(new_rect)

        elif self._resizing:
            r    = QRect(self._rect_start)
            dx   = delta_img.x()
            dy   = delta_img.y()
            # Maintain aspect ratio: drive off the larger delta
            ratio = rw / rh
            corner = self._resizing

            if corner == "br":
                size = max(abs(dx), abs(int(dy * ratio)))
                new_w = max(40, r.width()  + size * (1 if dx >= 0 else -1))
                new_h = max(40, int(new_w / ratio))
                r.setWidth(new_w); r.setHeight(new_h)
            elif corner == "bl":
                size  = max(abs(dx), abs(int(dy * ratio)))
                new_w = max(40, r.width()  + size * (1 if dx <= 0 else -1))
                new_h = max(40, int(new_w / ratio))
                r.setLeft(r.right() - new_w); r.setHeight(new_h)
            elif corner == "tr":
                size  = max(abs(dx), abs(int(dy * ratio)))
                new_w = max(40, r.width()  + size * (1 if dx >= 0 else -1))
                new_h = max(40, int(new_w / ratio))
                r.setWidth(new_w); r.setTop(r.bottom() - new_h)
            elif corner == "tl":
                size  = max(abs(dx), abs(int(dy * ratio)))
                new_w = max(40, r.width()  + size * (1 if dx <= 0 else -1))
                new_h = max(40, int(new_w / ratio))
                r.setLeft(r.right() - new_w); r.setTop(r.bottom() - new_h)

            self._crop_rect = self._clamp_rect(r)

        # Update cursor
        corner = self._near_corner(pos)
        if corner in ("tl", "br"):
            self.canvas.setCursor(Qt.SizeFDiagCursor)
        elif corner in ("tr", "bl"):
            self.canvas.setCursor(Qt.SizeBDiagCursor)
        elif self._canvas_rect().contains(pos):
            self.canvas.setCursor(Qt.SizeAllCursor)
        else:
            self.canvas.setCursor(Qt.ArrowCursor)

        self.canvas.update()

    def on_mouse_release(self, _pos: QPoint):
        self._dragging = False
        self._resizing = False

    # ── Draw (called by canvas paintEvent) ────────────────────────────────────

    def draw(self, painter: QPainter, canvas_size: QSize):
        # Fit image into canvas
        img_w = self._origin_pixmap.width()
        img_h = self._origin_pixmap.height()
        scale_x = canvas_size.width()  / img_w
        scale_y = canvas_size.height() / img_h
        self._scale  = min(scale_x, scale_y)
        disp_w = int(img_w * self._scale)
        disp_h = int(img_h * self._scale)
        self._offset = QPoint(
            (canvas_size.width()  - disp_w) // 2,
            (canvas_size.height() - disp_h) // 2,
        )

        # Draw image
        painter.drawPixmap(self._offset.x(), self._offset.y(), disp_w, disp_h, self._origin_pixmap)

        # Dark overlay outside crop rect
        cr = self._canvas_rect()
        overlay = QColor(0, 0, 0, 140)
        painter.fillRect(self._offset.x(), self._offset.y(), disp_w, cr.top() - self._offset.y(), overlay)
        painter.fillRect(self._offset.x(), cr.bottom(), disp_w, disp_h - (cr.bottom() - self._offset.y()), overlay)
        painter.fillRect(self._offset.x(), cr.top(), cr.left() - self._offset.x(), cr.height(), overlay)
        painter.fillRect(cr.right(), cr.top(), disp_w - (cr.right() - self._offset.x()), cr.height(), overlay)

        # Crop border
        pen = QPen(QColor("#3b82f6"), 2)
        painter.setPen(pen)
        painter.drawRect(cr)

        # Corner handles
        hs = self.HANDLE_SIZE
        painter.setBrush(QColor("#3b82f6"))
        for pt in [cr.topLeft(), cr.topRight(), cr.bottomLeft(), cr.bottomRight()]:
            painter.drawRect(pt.x() - hs // 2, pt.y() - hs // 2, hs, hs)

        # Rule of thirds grid
        pen_grid = QPen(QColor(255, 255, 255, 60), 1, Qt.DashLine)
        painter.setPen(pen_grid)
        for i in (1, 2):
            x = cr.left() + cr.width()  * i // 3
            y = cr.top()  + cr.height() * i // 3
            painter.drawLine(x, cr.top(), x, cr.bottom())
            painter.drawLine(cr.left(), y, cr.right(), y)

    # ── Save ───────────────────────────────────────────────────────────────────

    def _on_save(self):
        r = self._crop_rect
        self._cropped_pixmap = self._origin_pixmap.copy(r)
        self.accept()

    def get_cropped_pixmap(self) -> QPixmap | None:
        return self._cropped_pixmap

    def get_cropped_image(self) -> QImage | None:
        if self._cropped_pixmap:
            return self._cropped_pixmap.toImage()
        return None


class _CropCanvas(QLabel):
    """Internal canvas widget that forwards paint/mouse events to CropDialog."""

    def __init__(self, dialog: "CropDialog"):
        super().__init__()
        self._dialog = dialog
        self.setMouseTracking(True)
        self.setStyleSheet("background: #1e293b;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._dialog.draw(painter, self.size())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dialog.on_mouse_press(event.position().toPoint())

    def mouseMoveEvent(self, event):
        self._dialog.on_mouse_move(event.position().toPoint())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dialog.on_mouse_release(event.position().toPoint())