import sys
from PyQt6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsLineItem, QGraphicsSimpleTextItem, QGraphicsItem, QLabel
)
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter, QFont
from PyQt6.QtCore import Qt, QPointF

BG_COLOR = QColor("#16161a")
LINK_COLOR = QColor("#4a4a58")
DEAD_END_COLOR = QColor("#5a5a66")
LABEL_COLOR = QColor("#eaeaea")
AXIS_COLOR = QColor("#6c6c78")
EMPTY_DOT_COLOR = QColor("#8a8a94")
DEAD_CELL_COLOR = QColor("#ff2020")

_GRADIENT_PALETTES = [
    [(0.0, QColor("#4f7fd6")), (0.33, QColor("#7b4fd6")), (0.66, QColor("#d64f9f")), (1.0, QColor("#ff8c42"))],
    [(0.0, QColor("#3fae6b")), (0.33, QColor("#8fc93a")), (0.66, QColor("#e0d030")), (1.0, QColor("#f0a020"))],
    [(0.0, QColor("#e0463f")), (0.33, QColor("#e08a2f")), (0.66, QColor("#e8c02f")), (1.0, QColor("#f2e070"))],
    [(0.0, QColor("#2fb0c0")), (0.33, QColor("#2f7fd0")), (0.66, QColor("#5f4fd0")), (1.0, QColor("#9f4fd0"))],
    [(0.0, QColor("#d04fa0")), (0.33, QColor("#e0507a")), (0.66, QColor("#f06a4f")), (1.0, QColor("#f0994f"))],
]

# tracks pass-to-palette assignment across calls, so a new pass name
# (different from the previous render call) gets the next palette in line
_last_pass_name = object()  # sentinel, never equals a real pass name
_palette_index = -1
_color_cache = {}  # cell.id -> QColor, persists across render() calls


def reset_colors():
    """Call this before starting a fresh Gen() run so old cell-id -> color
    assignments (and the palette cycle) don't bleed into the new grid."""
    global _last_pass_name, _palette_index, _color_cache
    _last_pass_name = object()
    _palette_index = -1
    _color_cache = {}

PANEL_STYLE = """
QLabel {
    background-color: rgba(31, 31, 40, 220);
    color: #f0f0f0;
    border: 1px solid #6c4fa1;
    border-radius: 8px;
    padding: 10px 14px;
    font-family: monospace;
    font-size: 13px;
}
"""

PASS_LABEL_STYLE = """
QLabel {
    background-color: rgba(31, 31, 40, 220);
    color: #ff9f5a;
    border: 1px solid #ff9f5a;
    border-radius: 8px;
    padding: 6px 12px;
    font-family: monospace;
    font-size: 13px;
    font-weight: bold;
}
"""


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    r = c1.red() + (c2.red() - c1.red()) * t
    g = c1.green() + (c2.green() - c1.green()) * t
    b = c1.blue() + (c2.blue() - c1.blue()) * t
    return QColor(int(r), int(g), int(b))


def _gradient(t: float, palette) -> QColor:
    t = max(0.0, min(1.0, t))
    for (t0, c0), (t1, c1) in zip(palette, palette[1:]):
        if t0 <= t <= t1:
            local_t = (t - t0) / (t1 - t0) if t1 > t0 else 0
            return _lerp_color(c0, c1, local_t)
    return palette[-1][1]


def _palette_for_pass(pass_name):
    """Cycles to the next palette whenever the pass name changes from the
    previous render() call, so consecutive different passes stand out."""
    global _last_pass_name, _palette_index
    if pass_name != _last_pass_name:
        _palette_index = (_palette_index + 1) % len(_GRADIENT_PALETTES)
        _last_pass_name = pass_name
    return _GRADIENT_PALETTES[_palette_index]


class EmptyDotItem(QGraphicsEllipseItem):
    def __init__(self, x, y, radius, view):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.grid_pos = (x, y)
        self.view = view
        self.setBrush(QBrush(EMPTY_DOT_COLOR))
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setZValue(0)
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        self.view.set_panel_text(f"<i>empty</i><br>pos: {self.grid_pos}")
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.view.set_panel_text("<i>hover a cell to see its data</i>")
        super().hoverLeaveEvent(event)


class NodeItem(QGraphicsEllipseItem):
    def __init__(self, cell, radius, view):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.cell = cell
        self.view = view
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(BG_COLOR, 2))
        self.setZValue(2)

    def hoverEnterEvent(self, event):
        self.view.set_panel_text(
            f"<b style='color:#ff9f5a'>cell</b><br>"
            f"id: {self.cell.id}<br>"
            f"pos: {self.cell.pos}<br>"
            f"placed: {self.cell.placed}<br>"
            f"connections: {len(self.cell.connections)}"
        )
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.view.set_panel_text("<i>hover a cell to see its data</i>")
        super().hoverLeaveEvent(event)


class DungeonView(QGraphicsView):
    def __init__(self, scene, cell_size):
        super().__init__(scene)
        self.cell_size = cell_size
        self.empty_dots = []  # list of (item, x, y)
        self.fade_radius = cell_size * 3.5
        self.min_opacity = 0.06
        self.max_opacity = 1.0

        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(BG_COLOR))
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self._zoom = 1.0

        self.info_panel = QLabel(self)
        self.info_panel.setStyleSheet(PANEL_STYLE)
        self.info_panel.setWordWrap(True)
        self.info_panel.setFixedWidth(220)
        self.info_panel.move(14, 14)
        self.info_panel.raise_()
        self.set_panel_text("<i>hover a cell to see its data</i>")

        self.pass_label = QLabel(self)
        self.pass_label.setStyleSheet(PASS_LABEL_STYLE)
        self.pass_label.hide()

    def set_pass_name(self, name):
        if not name:
            self.pass_label.hide()
            return
        self.pass_label.setText(name)
        self.pass_label.adjustSize()
        margin = 14
        self.pass_label.move(self.viewport().width() - self.pass_label.width() - margin, margin)
        self.pass_label.raise_()
        self.pass_label.show()

    def set_panel_text(self, html):
        self.info_panel.setText(html)
        self.info_panel.adjustSize()
        self.info_panel.move(14, 14)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        new_zoom = self._zoom * factor
        if 0.15 <= new_zoom <= 10:
            self._zoom = new_zoom
            self.scale(factor, factor)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        scene_pos: QPointF = self.mapToScene(event.position().toPoint())
        mx, my = scene_pos.x(), scene_pos.y()
        if not self.empty_dots:
            return
        for item, x, y in self.empty_dots:
            dist = ((x - mx) ** 2 + (y - my) ** 2) ** 0.5
            if dist >= self.fade_radius:
                opacity = self.min_opacity
            else:
                opacity = self.min_opacity + (self.max_opacity - self.min_opacity) * (1 - dist / self.fade_radius)
            if abs(item.opacity() - opacity) > 0.01:
                item.setOpacity(opacity)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pass_label.isVisible():
            margin = 14
            self.pass_label.move(self.viewport().width() - self.pass_label.width() - margin, margin)


def render_graph(grid, size, cell_size=60, node_radius_ratio=0.32, dead_list=None, pass_name=None):
    """
    Static graph view with pan (drag) / zoom (scroll). Row/column numbers
    are drawn along the top and left like a grid ruler. Hovering a cell or
    empty slot shows its data in the top-left panel. Empty-cell dots fade
    in near the cursor and fade out with distance. Pass name (if given)
    shows in the window title and a small top-right label.
    """
    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication(sys.argv)

    scene = QGraphicsScene()
    placed = [c for row in grid for c in row if c.placed]
    max_id = max((c.id for c in placed if c.id != -1), default=1) or 1
    radius = cell_size * node_radius_ratio

    view = DungeonView(scene, cell_size)

    # empty-cell dots
    dot_radius = cell_size * 0.12
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c.placed:
                continue
            dot = EmptyDotItem(x, y, dot_radius, view)
            dot.setPos(x * cell_size, y * cell_size)
            dot.setOpacity(view.min_opacity)
            scene.addItem(dot)
            view.empty_dots.append((dot, x * cell_size, y * cell_size))

    # links
    seen_links = set()
    for c in placed:
        x, y = c.pos
        for conn in c.connections:
            key = tuple(sorted([c.pos, conn.pos]))
            if key in seen_links:
                continue
            seen_links.add(key)
            cx, cy = conn.pos
            line = QGraphicsLineItem(x * cell_size, y * cell_size, cx * cell_size, cy * cell_size)
            pen = QPen(LINK_COLOR, 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            line.setPen(pen)
            line.setZValue(1)
            scene.addItem(line)

    # nodes
    palette = _palette_for_pass(pass_name)
    label_font = QFont("monospace", 8)
    for c in placed:
        x, y = c.pos
        if c.id == -1:
            color = DEAD_END_COLOR
        elif c.id in _color_cache:
            color = _color_cache[c.id]
        else:
            color = _gradient(c.id / max_id, palette)
            _color_cache[c.id] = color
        node = NodeItem(c, radius, view)
        node.setPos(x * cell_size, y * cell_size)
        node.setBrush(QBrush(color))
        scene.addItem(node)

        label = QGraphicsSimpleTextItem(str(c.id))
        label.setFont(label_font)
        label.setBrush(QBrush(LABEL_COLOR))
        label.setZValue(3)
        br = label.boundingRect()
        label.setPos(x * cell_size - br.width() / 2, y * cell_size - br.height() / 2)
        scene.addItem(label)

    # dead cells
    if dead_list:
        dead_radius = cell_size * (node_radius_ratio + 0.06)
        for (dx, dy) in dead_list:
            marker = QGraphicsEllipseItem(-dead_radius, -dead_radius, dead_radius * 2, dead_radius * 2)
            marker.setBrush(QBrush(DEAD_CELL_COLOR))
            marker.setPen(QPen(QColor("#ffffff"), 2))
            marker.setZValue(4)
            marker.setPos(dx * cell_size, dy * cell_size)
            scene.addItem(marker)

    # chess-style ruler: column numbers along top, row numbers along left
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    axis_font = QFont("monospace", 8)
    for x in range(cols):
        lbl = QGraphicsSimpleTextItem(str(x))
        lbl.setFont(axis_font)
        lbl.setBrush(QBrush(AXIS_COLOR))
        br = lbl.boundingRect()
        lbl.setPos(x * cell_size - br.width() / 2, -cell_size * 0.7 - br.height() / 2)
        scene.addItem(lbl)
    for y in range(rows):
        lbl = QGraphicsSimpleTextItem(str(y))
        lbl.setFont(axis_font)
        lbl.setBrush(QBrush(AXIS_COLOR))
        br = lbl.boundingRect()
        lbl.setPos(-cell_size * 0.7 - br.width() / 2, y * cell_size - br.height() / 2)
        scene.addItem(lbl)

    title = f"Dungeon Graph - {pass_name}" if pass_name else "Dungeon Graph"
    view.setWindowTitle(title)
    view.set_pass_name(pass_name)
    view.resize(1000, 800)
    view.setSceneRect(scene.itemsBoundingRect().adjusted(-100, -100, 100, 100))
    view.show()
    view.fitInView(scene.itemsBoundingRect().adjusted(-50, -50, 50, 50), Qt.AspectRatioMode.KeepAspectRatio)

    if owns_app:
        app.exec()

    return view


def render(grid, size, dead_list=None, pass_name=None, **kwargs):
    return render_graph(grid, size, dead_list=dead_list, pass_name=pass_name, **kwargs)