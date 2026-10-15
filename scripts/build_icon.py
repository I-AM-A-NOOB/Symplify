# coding: utf-8
"""Regenerate ``icon/Symplify.ico`` (and the loose PNGs) from ``icon/Symplify.svg``.

    uv run python scripts/build_icon.py

Windows asks for nine sizes — 16 (taskbar), 20/24 (title bar, alt-tab), 32/40/48
(Explorer), 64/128 (the taskbar thumbnail) and 256 (large icons) — so all nine
are produced; Windows then never has to scale one up.

**Why this packs the ICO by hand.** The rasterizer could be ImageMagick's, but
its ICO *writer* stores every entry as an uncompressed BMP/DIB whatever you feed
it — PNG input, ICO input, `-compress Zip`, all of it (upstream issues #2394 and
#8578) — so the same pixels cost 381 KB instead of 48 KB. Its ICO *reader* is
fine, so `magick identify icon/Symplify.ico` still inspects what we write, and
`magick` is a perfectly good way to look at `icons-png/` too.

The rasterizer is Qt instead of ImageMagick, for two reasons: PySide6 is already
a hard dependency of this project, where ImageMagick would be a tool to install
before the icon can be rebuilt; and it is the *same* renderer the app itself
draws this SVG with (`Icon.qml` renders it in the title bar), so the icon file
and the title bar cannot disagree about how the artwork looks. Rendering a
1024 px master once and resampling each size from it is what keeps the small
entries clean — measured against ImageMagick's own master + Lanczos pipeline,
the two agree to a normalized RMSE of 0.4-2.1%, which is antialiased edge pixels.

The entries are PNG, which every Windows since Vista reads. A BMP/DIB payload
would need a hand-laid colour bitmap *plus* a 1bpp AND mask to carry alpha
(ImageMagick's own BMP writer cannot be reused: it drops alpha and writes
`biHeight = height`, so readers take the entry for twice as tall as it is) — and
that is only for a pre-Vista reader, so it is not written.

Alpha is the point of the artwork, so the script audits it rather than assuming:
it samples the master's corners and centre and says so when the SVG turns out
to be fully opaque — an opaque-white corner is exactly what a lost alpha channel
looks like — and it re-reads the container it just wrote to prove each entry's
kind, size and offset.

Output: ``icon/Symplify.ico`` (committed — Nuitka embeds it and `main.py` loads
it) and ``icons-png/`` (git-ignored; the same nine sizes as loose PNGs, for
anything that wants a raster).
"""

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QSize, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "icon" / "Symplify.svg"
ICO = ROOT / "icon" / "Symplify.ico"
PNG_DIR = ROOT / "icons-png"

#: What Windows asks for, small to large. 256 is stored as a 0 byte in the
#: directory, so it has to keep being the largest.
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
#: The one high-resolution render every entry is resampled from.
MASTER = 1024


def _app():
    """A Qt application, on a platform plugin that needs no display."""
    app = QGuiApplication.instance()
    if app is not None:
        return app

    import os

    # The script has to run on a CI runner and over SSH, where there is no
    # screen; Qt would otherwise fail to reach a platform plugin.
    if not os.environ.get("DISPLAY") and sys.platform.startswith("linux"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QGuiApplication([])


def render_master() -> QImage:
    """The SVG, rasterized once at ``MASTER`` px on a transparent canvas."""
    image = QImage(MASTER, MASTER, QImage.Format.Format_ARGB32)
    # Transparent, not white: the artwork's rounded corners and its
    # radial-gradient fade are the reason the file carries alpha at all, and a
    # white background would be a hard-edged square wherever it is composited.
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    QSvgRenderer(str(SVG)).render(painter)
    painter.end()
    return image


def _png_bytes(image: QImage) -> bytes:
    """One image as a PNG, in memory.

    A bare ``QBuffer()``, whose byte array Qt owns: the two-argument form takes a
    ``QByteArray`` *pointer*, and handing it a temporary from Python leaves that
    temporary free to be collected while Qt still writes to it — which is a hard
    crash (exit 9), not an exception.
    """
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise SystemExit(f"Qt could not encode a {image.width()}px PNG.")
    return bytes(buffer.data())


def pack_ico(entries: list[tuple[int, bytes]]) -> bytes:
    """An ICO container: a 6-byte header, one 16-byte entry per image, payloads.

    ``entries`` is ``(size, png bytes)``, already in the order Windows should see
    them (largest first).
    """
    # ICONDIR: reserved, type (1 = icon), count.
    parts = [struct.pack("<HHH", 0, 1, len(entries))]
    offset = 6 + 16 * len(entries)
    for size, payload in entries:
        # Width and height are single bytes, so 256 has to be written as 0.
        dimensions = 0 if size >= 256 else size
        parts.append(struct.pack(
            "<BBBBHHII",
            dimensions, dimensions,
            0,     # palette colour count (0 = no palette)
            0,     # reserved
            1,     # colour planes
            32,    # bits per pixel
            len(payload),
            offset,
        ))
        offset += len(payload)
    parts.extend(payload for _size, payload in entries)
    return b"".join(parts)


def read_ico(path: Path) -> list[tuple[int, str, int, int]]:
    """``(size, kind, bytes, offset)`` per entry, read back from the file.

    Deliberately independent of ``pack_ico``: the report is evidence about what
    landed on disk, not a restatement of what was meant to be written.
    """
    data = path.read_bytes()
    if data[:4] != b"\x00\x00\x01\x00":
        raise SystemExit(f"{path} is not an ICO file.")
    count = struct.unpack_from("<H", data, 4)[0]

    entries = []
    for index in range(count):
        width, _height, _colors, _reserved, _planes, _bits, size, offset = (
            struct.unpack_from("<BBBBHHII", data, 6 + 16 * index)
        )
        payload = data[offset:offset + 4]
        kind = "PNG" if payload[:3] == b"\x89PN" else (
            "BMP/DIB" if payload[:2] == b"BM" or payload[3:4] == b"\x00" else "?")
        entries.append((width or 256, kind, size, offset))
    return entries


def main() -> int:
    if not SVG.is_file():
        raise SystemExit(f"No source SVG at {SVG}.")

    _app()

    print(f"source   : {SVG.relative_to(ROOT).as_posix()}")
    master = render_master()

    # The audit that catches the failure this file has actually had: an icon
    # that looks right in a preview and is opaque white in its corners.
    alphas = [master.pixelColor(x, y).alpha()
              for x, y in ((0, 0), (MASTER - 1, 0), (0, MASTER - 1),
                           (MASTER // 2, MASTER // 2))]
    if min(alphas) == 255:
        print("alpha    : the artwork is fully opaque - there is no transparency "
              "to preserve (that is the SVG's content, not a conversion loss)")
    else:
        print(f"alpha    : corners {alphas[:3]}, centre {alphas[3]} "
              "(0 = transparent)")

    PNG_DIR.mkdir(exist_ok=True)
    entries: list[tuple[int, bytes]] = []
    for size in SIZES:
        image = master.scaled(
            QSize(size, size),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        payload = _png_bytes(image)
        (PNG_DIR / f"{size}.png").write_bytes(payload)
        entries.append((size, payload))
        print(f"  {size:>3}px  PNG  {len(payload):>6} bytes  -> {PNG_DIR.name}/{size}.png")

    # Largest first: Windows and Electron both look at the first entry more
    # often than they should.
    entries.sort(key=lambda entry: -entry[0])
    ICO.write_bytes(pack_ico(entries))

    print(f"packed   : {ICO.relative_to(ROOT).as_posix()} "
          f"({ICO.stat().st_size} bytes)")
    written = read_ico(ICO)
    for size, kind, size_bytes, offset in written:
        print(f"  {size:>3}x{size:<3} {kind:<7} {size_bytes:>6} bytes @ {offset}")
    if len(written) != len(SIZES):
        raise SystemExit(f"Wrote {len(written)} entries, expected {len(SIZES)}.")

    # Qt is what reads this file at runtime, so ask it — a container that only
    # our own parser understands would ship broken.
    from PySide6.QtGui import QIcon

    icon = QIcon(str(ICO))
    loaded = sorted(s.width() for s in icon.availableSizes())
    if loaded != sorted(SIZES):
        raise SystemExit(f"Qt read back sizes {loaded}, expected {sorted(SIZES)}.")
    print(f"verified : QIcon loaded all {len(loaded)} sizes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
