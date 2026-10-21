"""Esportazione dei disegni vettoriali del PDF in DXF (AutoCAD e compatibili).

Linee, polilinee e curve diventano LINE/LWPOLYLINE/SPLINE (i cerchi CIRCLE), i
riempimenti HATCH e il testo TEXT. I layer del PDF (OCG, spesso creati dai
programmi CAD) vengono mantenuti; in loro assenza si raggruppa per colore.
Le coordinate sono in millimetri, moltiplicate per la scala del disegno.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field

import ezdxf
import pymupdf
from ezdxf import colors as dxf_colors
from ezdxf import path as dxf_path
from ezdxf.lldxf.const import VALID_DXF_LINEWEIGHTS

PT_TO_MM = 25.4 / 72
UNITS = {"mm": (1.0, 4), "cm": (10.0, 5), "m": (1000.0, 6)}  # divisore, codice $INSUNITS


@dataclass
class DxfOptions:
    scale: float = 1.0            # 100 = disegno in scala 1:100
    units: str = "mm"             # unità del DXF: mm, cm, m
    include_text: bool = True
    include_fills: bool = True
    skip_white_fills: bool = True
    include_annotations: bool = True
    detect_circles: bool = True
    layers_by_color: bool = True  # se il PDF non ha layer propri


@dataclass
class DxfReport:
    path: str
    lines: int = 0
    curves: int = 0
    circles: int = 0
    hatches: int = 0
    texts: int = 0
    layers: set = field(default_factory=set)
    raster_only: bool = False

    @property
    def vector_entities(self) -> int:
        return self.lines + self.curves + self.circles + self.hatches


def page_vector_stats(page: pymupdf.Page) -> tuple[int, int]:
    """(numero di tracciati vettoriali, numero di immagini) di una pagina."""
    return len(page.get_drawings()), len(page.get_images())


def _layer_name(name: str) -> str:
    name = re.sub(r'[<>/\\":;?*|=`,]', "_", name.strip())
    return name[:200] or "0"


def _rgb(c) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(round(v * 255)))) for v in c[:3]) if c else (0, 0, 0)


def _color_attribs(rgb) -> dict:
    """Il nero diventa il colore CAD 7 (bianco/nero secondo lo sfondo), altrimenti colore reale."""
    if max(rgb) <= 20:
        return {"color": 7}
    return {"true_color": dxf_colors.rgb2int(rgb)}


def _lineweight(width_pt: float) -> int:
    target = width_pt * PT_TO_MM * 100  # centesimi di mm
    valid = [w for w in VALID_DXF_LINEWEIGHTS if w >= 0]
    return min(valid, key=lambda w: abs(w - target))


class _Writer:
    def __init__(self, page: pymupdf.Page, opts: DxfOptions):
        self.page = page
        self.opts = opts
        divisor, insunits = UNITS[opts.units]
        self.k = PT_TO_MM * opts.scale / divisor
        self.doc = ezdxf.new("R2010", setup=True)
        self.doc.units = insunits
        self.doc.header["$MEASUREMENT"] = 1  # metrico
        self.msp = self.doc.modelspace()
        self.matrix = page.rotation_matrix   # spazio non ruotato → pagina come visualizzata
        self.height = page.rect.height
        self.linetypes: dict[str, str] = {}

    # Coordinate PDF (y verso il basso) → DXF (y verso l'alto), in unità di disegno
    def pt(self, p) -> tuple[float, float]:
        q = pymupdf.Point(p) * self.matrix
        return (q.x * self.k, (self.height - q.y) * self.k)

    def layer(self, name: str, rgb) -> str:
        name = _layer_name(name)
        if name not in self.doc.layers:
            lay = self.doc.layers.add(name)
            if max(rgb) <= 20:
                lay.color = 7
            else:
                lay.rgb = rgb
        return name

    def linetype(self, dashes: str) -> str | None:
        nums = [float(x) for x in re.findall(r"[\d.]+", dashes.split("]")[0])] if dashes else []
        nums = [n for n in nums if n > 0]
        if not nums:
            return None
        if len(nums) % 2:
            nums = nums * 2
        key = " ".join(f"{n:g}" for n in nums)
        if key not in self.linetypes:
            name = f"PDF_TRATTEGGIO_{len(self.linetypes) + 1}"
            elems = [n * self.k * (1 if i % 2 == 0 else -1) for i, n in enumerate(nums)]
            self.doc.linetypes.add(name, pattern=[sum(abs(e) for e in elems)] + elems,
                                   description=f"Tratteggio PDF [{key}]")
            self.linetypes[key] = name
        return self.linetypes[key]

    def _attribs(self, layer: str, rgb, width: float | None, dashes: str | None) -> dict:
        a = {"layer": layer, **_color_attribs(rgb)}
        if width is not None:
            a["lineweight"] = _lineweight(width)
        lt = self.linetype(dashes) if dashes else None
        if lt:
            a["linetype"] = lt
        return a

    # ------------------------------------------------------------------ disegni
    def _paths(self, items) -> list[dxf_path.Path]:
        paths: list[dxf_path.Path] = []
        cur: dxf_path.Path | None = None
        last = None
        for it in items:
            kind = it[0]
            if kind == "re":
                r = it[1]
                pts = [self.pt(r.tl), self.pt(r.tr), self.pt(r.br), self.pt(r.bl)]
                p = dxf_path.Path(pts[0])
                for q in pts[1:]:
                    p.line_to(q)
                p.close()
                paths.append(p)
                cur, last = None, None
                continue
            if kind == "qu":
                q = it[1]
                pts = [self.pt(q.ul), self.pt(q.ur), self.pt(q.lr), self.pt(q.ll)]
                p = dxf_path.Path(pts[0])
                for v in pts[1:]:
                    p.line_to(v)
                p.close()
                paths.append(p)
                cur, last = None, None
                continue
            start = self.pt(it[1])
            if cur is None or last is None or math.dist(start, last) > 1e-6:
                cur = dxf_path.Path(start)
                paths.append(cur)
            if kind == "l":
                end = self.pt(it[2])
                cur.line_to(end)
            elif kind == "c":
                end = self.pt(it[4])
                cur.curve4_to(end, self.pt(it[2]), self.pt(it[3]))
            else:
                continue
            last = end
        return paths

    def _circle(self, d: dict) -> tuple[tuple[float, float], float] | None:
        """Riconosce i cerchi (4 curve di Bézier con riquadro quadrato)."""
        items = d["items"]
        if len(items) != 4 or any(i[0] != "c" for i in items):
            return None
        r = d["rect"]
        if r.width <= 0 or abs(r.width - r.height) > max(0.5, 0.01 * r.width):
            return None
        if pymupdf.Point(items[0][1]) != pymupdf.Point(items[-1][4]) and \
                abs(items[0][1] - items[-1][4]) > 0.5:
            return None
        center = self.pt(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
        return center, r.width / 2 * self.k

    def drawings(self, report: DxfReport) -> None:
        opts = self.opts
        for d in self.page.get_drawings():
            stroke = d.get("color")
            fill = d.get("fill")
            kind = d.get("type", "s")
            ocg = d.get("layer") or ""
            base_rgb = _rgb(stroke if stroke is not None else fill)
            if ocg:
                layer = self.layer(ocg, base_rgb)
            elif opts.layers_by_color:
                layer = self.layer("PDF_%02X%02X%02X" % base_rgb, base_rgb)
            else:
                layer = self.layer("PDF_DISEGNO", (0, 0, 0))
            report.layers.add(layer)
            circle = self._circle(d) if opts.detect_circles else None
            paths = None if circle else self._paths(d["items"])

            # Riempimento
            if fill is not None and "f" in kind and opts.include_fills:
                frgb = _rgb(fill)
                if not (opts.skip_white_fills and min(frgb) >= 250):
                    if circle:
                        hatch = self.msp.add_hatch(dxfattribs={"layer": layer,
                                                               "true_color": dxf_colors.rgb2int(frgb)})
                        hatch.set_solid_fill(rgb=frgb)
                        ep = hatch.paths.add_edge_path()
                        ep.add_arc(circle[0], circle[1], 0, 360)
                        report.hatches += 1
                    else:
                        closed = [p for p in paths if len(p)]
                        if closed:
                            for h in dxf_path.render_hatches(
                                    self.msp, closed, edge_path=True,
                                    dxfattribs={"layer": layer, "true_color": dxf_colors.rgb2int(frgb)}):
                                h.set_solid_fill(rgb=frgb)
                                report.hatches += 1
            # Contorno
            if stroke is None or "s" not in kind:
                continue
            attrs = self._attribs(layer, _rgb(stroke), d.get("width") or 0, d.get("dashes"))
            if circle:
                self.msp.add_circle(circle[0], circle[1], dxfattribs=attrs)
                report.circles += 1
                continue
            for p in paths:
                if not len(p):
                    continue
                if d.get("closePath") and not p.is_closed:
                    p.close()
                if p.has_curves:
                    dxf_path.render_splines_and_polylines(self.msp, [p], dxfattribs=attrs)
                    report.curves += 1
                elif len(p) == 1 and not p.is_closed:
                    self.msp.add_line(p.start, p.end, dxfattribs=attrs)
                    report.lines += 1
                else:
                    pts = [v for v in p.flattening(0.01)]
                    poly = self.msp.add_lwpolyline([(v.x, v.y) for v in pts], dxfattribs=attrs)
                    if p.is_closed:
                        poly.closed = True
                    report.lines += 1

    # -------------------------------------------------------------------- testo
    def texts(self, report: DxfReport) -> None:
        rot = self.page.rotation
        for t in self.page.get_texttrace():
            if t.get("type") == 3 or not t["chars"]:  # testo invisibile (es. strato OCR)
                continue
            txt = "".join(chr(c[0]) for c in t["chars"] if c[0] > 0)
            if not txt.strip():
                continue
            rgb = _rgb(t.get("color"))
            layer = self.layer(t["layer"] or "TESTO", rgb if t["layer"] else (0, 0, 0))
            report.layers.add(layer)
            dx, dy = t["dir"]
            angle = (-math.degrees(math.atan2(dy, dx)) - rot) % 360
            # In DXF l'altezza del testo è circa l'altezza delle maiuscole
            h = t["size"] * 0.72 * self.k
            self.msp.add_text(txt.rstrip(), height=max(h, 1e-6), rotation=angle, dxfattribs={
                "layer": layer, **_color_attribs(rgb), "insert": self.pt(t["chars"][0][2])})
            report.texts += 1


def export_page(doc: pymupdf.Document, index: int, out_path: str, opts: DxfOptions | None = None) -> DxfReport:
    opts = opts or DxfOptions()
    work = doc
    if not opts.include_annotations and doc[index].first_annot is not None:
        # I commenti fanno parte dei disegni della pagina: si tolgono da una copia
        work = pymupdf.open()
        work.insert_pdf(doc, from_page=index, to_page=index, annots=False)
        index = 0
    page = work[index]
    report = DxfReport(out_path)
    w = _Writer(page, opts)
    w.drawings(report)
    if opts.include_text:
        w.texts(report)
    report.raster_only = report.vector_entities == 0 and bool(page.get_images())
    w.doc.saveas(out_path)
    if work is not doc:
        work.close()
    return report


def export(doc: pymupdf.Document, pages: list[int], out_path: str, opts: DxfOptions | None = None) -> list[DxfReport]:
    """Una pagina → out_path; più pagine → out_path con suffisso _p001, _p002…"""
    if len(pages) == 1:
        return [export_page(doc, pages[0], out_path, opts)]
    base, ext = os.path.splitext(out_path)
    return [export_page(doc, p, f"{base}_p{p + 1:03d}{ext or '.dxf'}", opts) for p in pages]
