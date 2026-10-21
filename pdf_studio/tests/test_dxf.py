import math
from collections import Counter

import ezdxf
import pymupdf
import pytest

from pdfstudio import dxf_export as X


@pytest.fixture
def plan():
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    muri = doc.add_ocg("MURI")
    quote = doc.add_ocg("QUOTE")
    page.draw_rect(pymupdf.Rect(100, 100, 600, 110), color=(0, 0, 0), fill=(0.6, 0.6, 0.6), oc=muri)
    page.draw_circle((220, 250), 40, color=(0.6, 0.3, 0), width=0.7)
    page.draw_sector((350, 300), (410, 300), 90, color=(0, 0, 0), width=0.3)
    page.draw_line((100, 440), (600, 440), color=(1, 0, 0), width=0.25, dashes="[4 2] 0", oc=quote)
    page.insert_text((320, 435), "10.00 m", fontsize=10, color=(1, 0, 0), oc=quote)
    page.insert_text((620, 300), "Scala 1:50", fontsize=8, rotate=90)
    return doc


def read(path):
    d = ezdxf.readfile(path)
    return d, d.modelspace()


def test_geometry_scale_and_layers(plan, tmp_path):
    out = str(tmp_path / "p.dxf")
    rep = X.export_page(plan, 0, out, X.DxfOptions(scale=50, units="m"))
    d, msp = read(out)
    assert d.units == 6  # metri
    kinds = Counter(e.dxftype() for e in msp)
    assert kinds["CIRCLE"] == 1 and kinds["HATCH"] == 1 and kinds["TEXT"] == 2
    circle = msp.query("CIRCLE").first
    assert circle.dxf.radius == pytest.approx(40 * 25.4 / 72 * 50 / 1000, rel=1e-3)
    wall = next(e for e in msp.query("LWPOLYLINE") if e.dxf.layer == "MURI")
    xs = [p[0] for p in wall.get_points("xy")]
    assert max(xs) - min(xs) == pytest.approx(500 * 25.4 / 72 * 50 / 1000, rel=1e-3)  # 8,82 m
    assert {"MURI", "QUOTE"} <= rep.layers
    texts = {e.dxf.text: e for e in msp.query("TEXT")}
    assert texts["10.00 m"].dxf.layer == "QUOTE"
    assert texts["Scala 1:50"].dxf.rotation == pytest.approx(90)
    dashed = next(e for e in msp if e.dxf.layer == "QUOTE" and e.dxftype() in ("LINE", "LWPOLYLINE"))
    assert dashed.dxf.linetype.startswith("PDF_TRATTEGGIO")


def test_y_axis_flipped(plan, tmp_path):
    out = str(tmp_path / "p.dxf")
    X.export_page(plan, 0, out, X.DxfOptions())
    _d, msp = read(out)
    c = msp.query("CIRCLE").first.dxf.center
    assert c.x == pytest.approx(220 * 25.4 / 72, rel=1e-3)
    assert c.y == pytest.approx((595 - 250) * 25.4 / 72, rel=1e-3)


def test_black_uses_cad_color_7(plan, tmp_path):
    out = str(tmp_path / "p.dxf")
    X.export_page(plan, 0, out, X.DxfOptions())
    _d, msp = read(out)
    scala = next(e for e in msp.query("TEXT") if e.dxf.text == "Scala 1:50")
    assert scala.dxf.color == 7


def test_options_and_multipage(plan, tmp_path):
    plan.new_page().draw_line((10, 10), (100, 10))
    out = str(tmp_path / "tav.dxf")
    reps = X.export(plan, [0, 1], out, X.DxfOptions(include_text=False, include_fills=False,
                                                   detect_circles=False))
    assert [r.path for r in reps] == [str(tmp_path / "tav_p001.dxf"), str(tmp_path / "tav_p002.dxf")]
    _d, msp = read(reps[0].path)
    kinds = Counter(e.dxftype() for e in msp)
    assert kinds["TEXT"] == 0 and kinds["HATCH"] == 0 and kinds["CIRCLE"] == 0 and kinds["SPLINE"] >= 1


def test_annotations_included(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.add_ink_annot([[(10, 10), (50, 60), (90, 20)]])
    out = str(tmp_path / "a.dxf")
    rep = X.export_page(doc, 0, out, X.DxfOptions())
    assert rep.vector_entities >= 1
    rep = X.export_page(doc, 0, out, X.DxfOptions(include_annotations=False))
    assert rep.vector_entities == 0


def test_raster_page_detected(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 50, 50), False)
    pix.clear_with(100)
    page.insert_image(pymupdf.Rect(0, 0, 200, 200), pixmap=pix)
    rep = X.export_page(doc, 0, str(tmp_path / "r.dxf"), X.DxfOptions())
    assert rep.raster_only


def test_rotated_page(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.draw_line((100, 100), (200, 100))
    page.set_rotation(90)
    out = str(tmp_path / "rot.dxf")
    X.export_page(doc, 0, out, X.DxfOptions())
    _d, msp = read(out)
    e = next(iter(msp))
    pts = [e.dxf.start, e.dxf.end] if e.dxftype() == "LINE" else [p for p in e.get_points("xy")]
    # Una linea orizzontale su pagina ruotata di 90° diventa verticale nel disegno
    assert math.isclose(pts[0][0], pts[1][0], abs_tol=1e-6)
