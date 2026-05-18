from __future__ import annotations

from pathlib import Path

from PIL import Image
from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..models.fields_config import FieldConfig, ViewConfig, ViewMode
from ..services.image_loader import (
    load_first_page_image,
    pil_to_qimage,
    placeholder_image,
)


class ImagePanel(QWidget):
    """Right panel: image view, ground-truth text, fit controls, rectangle selection."""

    view_config_changed = pyqtSignal(int)  # field column
    rectangle_drawn = pyqtSignal(int, object)  # column, [x,y,w,h] normalized

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_column = 1
        self._field_config: FieldConfig | None = None
        self._source_image: Image.Image | None = None
        self._batch_dir: Path | None = None
        self._current_path: Path | None = None
        self._drawing = False
        self._draw_start: QPoint | None = None
        self._rubber_band: QGraphicsRectItem | None = None

        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self._gt_label = QLabel("Ground truth:")
        self._gt_text = QTextEdit()
        self._gt_text.setReadOnly(True)
        self._gt_text.setMaximumHeight(72)

        self._btn_auto = QPushButton("Autofit")
        self._btn_width = QPushButton("Width")
        self._btn_height = QPushButton("Height")
        self._fit_group = QButtonGroup(self)
        for btn in (self._btn_auto, self._btn_width, self._btn_height):
            self._fit_group.addButton(btn)
        self._btn_auto.setCheckable(True)
        self._btn_width.setCheckable(True)
        self._btn_height.setCheckable(True)
        self._btn_auto.setChecked(True)

        hint = QLabel("Ctrl+drag to draw a zoom rectangle for this field")
        hint.setStyleSheet("color: gray; font-size: 11px;")

        fit_row = QHBoxLayout()
        fit_row.addWidget(self._btn_auto)
        fit_row.addWidget(self._btn_width)
        fit_row.addWidget(self._btn_height)
        fit_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self._view, stretch=1)
        layout.addLayout(fit_row)
        layout.addWidget(hint)
        layout.addWidget(self._gt_label)
        layout.addWidget(self._gt_text)

        self._btn_auto.clicked.connect(lambda: self._set_fit_mode(ViewMode.AUTO))
        self._btn_width.clicked.connect(lambda: self._set_fit_mode(ViewMode.WIDTH))
        self._btn_height.clicked.connect(lambda: self._set_fit_mode(ViewMode.HEIGHT))

        self._view.viewport().installEventFilter(self)

    def set_current_field_column(self, column: int) -> None:
        self._current_column = column

    def set_field_config(self, field: FieldConfig | None) -> None:
        self._field_config = field
        if field:
            self._apply_fit_buttons(field.view.mode)

    def set_batch_dir(self, batch_dir: Path | None) -> None:
        self._batch_dir = batch_dir

    def show_document(
        self,
        relative_or_absolute: str | Path,
        *,
        ground_truth: str = "",
        field: FieldConfig | None = None,
    ) -> None:
        if field is not None:
            self._field_config = field
            self._apply_fit_buttons(field.view.mode)

        raw = str(relative_or_absolute)
        path = Path(relative_or_absolute)
        if not path.is_absolute() and self._batch_dir:
            path = self._batch_dir / path
        self._current_path = path

        try:
            image = load_first_page_image(path)
        except Exception as exc:
            image = placeholder_image(
                f"Cannot decode:\n{path.name}\n\n{type(exc).__name__}: {exc}"
            )
        else:
            if image is None:
                image = placeholder_image(
                    "File not found.\n"
                    f"Raw entry: {raw!r}\n"
                    f"Resolved : {path}"
                )
        self._source_image = image
        self._display_image()
        self._gt_text.setPlainText(ground_truth)

    def _display_image(self) -> None:
        if self._source_image is None:
            return
        pixmap = QPixmap.fromImage(pil_to_qimage(self._source_image))
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self._apply_view_transform()

    def _apply_fit_buttons(self, mode: ViewMode) -> None:
        self._btn_auto.setChecked(mode == ViewMode.AUTO)
        self._btn_width.setChecked(mode == ViewMode.WIDTH)
        self._btn_height.setChecked(mode == ViewMode.HEIGHT)

    def _set_fit_mode(self, mode: ViewMode) -> None:
        if not self._field_config:
            return
        self._field_config.view.mode = mode
        self._apply_view_transform()
        self.view_config_changed.emit(self._field_config.column)

    def _apply_view_transform(self) -> None:
        if self._pixmap_item.pixmap().isNull():
            return
        self._view.resetTransform()
        view_rect = self._view.viewport().rect()
        pix = self._pixmap_item.pixmap()
        pw, ph = pix.width(), pix.height()
        if pw <= 0 or ph <= 0:
            return

        mode = ViewMode.AUTO
        rect_norm = None
        if self._field_config:
            mode = self._field_config.view.mode
            rect_norm = self._field_config.view.rectangle

        if mode == ViewMode.RECTANGLE and rect_norm:
            x, y, w, h = rect_norm
            src = QRectF(x * pw, y * ph, w * pw, h * ph)
            self._view.fitInView(src, Qt.AspectRatioMode.KeepAspectRatio)
            return

        if mode == ViewMode.WIDTH:
            scale = view_rect.width() / pw
        elif mode == ViewMode.HEIGHT:
            scale = view_rect.height() / ph
        else:
            scale = min(view_rect.width() / pw, view_rect.height() / ph)
        self._view.scale(scale, scale)
        self._view.centerOn(self._pixmap_item)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_view_transform()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._view.viewport():
            et = event.type()
            if et == event.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    self._drawing = True
                    self._draw_start = event.position().toPoint()
                    if self._rubber_band:
                        self._scene.removeItem(self._rubber_band)
                    self._rubber_band = QGraphicsRectItem()
                    self._rubber_band.setPen(QPen(QColor(0, 120, 215), 2, Qt.PenStyle.DashLine))
                    self._scene.addItem(self._rubber_band)
                    return True
            elif et == event.Type.MouseMove and self._drawing and self._draw_start:
                end = event.position().toPoint()
                scene_start = self._view.mapToScene(self._draw_start)
                scene_end = self._view.mapToScene(end)
                rect = QRectF(scene_start, scene_end).normalized()
                self._rubber_band.setRect(rect)
                return True
            elif et == event.Type.MouseButtonRelease and self._drawing:
                self._drawing = False
                if self._rubber_band and self._field_config:
                    rect = self._rubber_band.sceneBoundingRect()
                    self._scene.removeItem(self._rubber_band)
                    self._rubber_band = None
                    pix = self._pixmap_item.pixmap()
                    if pix.width() > 0 and pix.height() > 0:
                        norm = [
                            rect.x() / pix.width(),
                            rect.y() / pix.height(),
                            rect.width() / pix.width(),
                            rect.height() / pix.height(),
                        ]
                        self._field_config.view.rectangle = norm
                        self._field_config.view.mode = ViewMode.RECTANGLE
                        self._apply_view_transform()
                        self.rectangle_drawn.emit(self._field_config.column, norm)
                return True
        return super().eventFilter(obj, event)
