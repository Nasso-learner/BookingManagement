"""Turns a report's query result into a Plotly figure spec (rendered by plotly.js in the browser).

Palette = the validated categorical order (fixed slot order, never cycled; >8 series fold into "Other").
"""
from collections import OrderedDict

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK_2, MUTED, GRID, SURFACE = "#0f172a", "#334155", "#64748b", "#e6ebf2", "#ffffff"
FONT = "Plus Jakarta Sans, system-ui, sans-serif"

CHART_TYPES = [("TABLE", "Table"), ("NUMBER", "Number (KPI)"), ("BAR", "Bar"), ("STACKED_BAR", "Stacked bar"),
               ("HBAR", "Horizontal bar"), ("LINE", "Line"), ("AREA", "Area"), ("PIE", "Donut"), ("SCATTER", "Scatter")]
SERIES_CAP = {"PIE": 6, "SCATTER": 3}  # all-pairs forms validate only for the first 3 slots


class ChartError(ValueError):
    pass


def _label(col):
    return col.replace("_", " ").capitalize()


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _columns(cfg, columns):
    x = cfg.get("x_column") or columns[0]
    ys = [c.strip() for c in (cfg.get("y_columns") or "").split(",") if c.strip()]
    ys = ys or [c for c in columns if c != x][:1] or [x]
    series = (cfg.get("series_column") or "").strip()
    missing = [c for c in (x, *ys, series) if c and c not in columns]
    if missing:
        raise ChartError(f"Column(s) not in the results: {', '.join(missing)}. Available: {', '.join(columns)}.")
    return x, ys, series


def _groups(rows, idx, x, ys, series, cap):
    """{series name: (xs, values)} in first-appearance order; extra series fold into 'Other'."""
    if not series:
        return OrderedDict((_label(y), ([r[idx[x]] for r in rows], [r[idx[y]] for r in rows])) for y in ys[:cap])
    data = OrderedDict()
    for r in rows:
        data.setdefault(str(r[idx[series]]), OrderedDict())[r[idx[x]]] = _num(r[idx[ys[0]]])
    if len(data) > cap:
        keep = sorted(data, key=lambda k: -sum(data[k].values()))[: cap - 1]
        other = OrderedDict()
        for name, points in data.items():
            if name not in keep:
                for xv, v in points.items():
                    other[xv] = other.get(xv, 0) + v
        data = OrderedDict([(k, v) for k, v in data.items() if k in keep] + [("Other", other)])
    return OrderedDict((name, (list(p.keys()), list(p.values()))) for name, p in data.items())


def build(cfg, result, chart=None):
    """Returns {"kind": "plot"|"number"|"table", ...}. Raises ChartError for bad column settings."""
    chart = chart or cfg.get("chart_type") or "TABLE"
    columns, rows = result["columns"], result["rows"]
    if chart == "TABLE" or not rows:
        return {"kind": "table"}
    idx = {c: n for n, c in enumerate(columns)}
    x, ys, series = _columns(cfg, columns)

    if chart == "NUMBER":
        return {"kind": "number", "value": rows[0][idx[ys[0]]], "label": _label(ys[0])}

    if chart == "PIE":
        groups = _groups(rows, idx, x, ys, x, SERIES_CAP["PIE"]) if len(rows) > SERIES_CAP["PIE"] else None
        labels = list(groups) if groups else [str(r[idx[x]]) for r in rows]
        values = [sum(g[1]) for g in groups.values()] if groups else [_num(r[idx[ys[0]]]) for r in rows]
        traces = [{"type": "pie", "hole": 0.6, "labels": labels, "values": values, "sort": False,
                   "marker": {"colors": PALETTE, "line": {"color": SURFACE, "width": 2}},
                   "textinfo": "percent", "textfont": {"color": SURFACE},
                   "hovertemplate": "<b>%{label}</b><br>%{value:,} (%{percent})<extra></extra>"}]
        return {"kind": "plot", "figure": {"data": traces, "layout": _layout(chart, x, ys, show_legend=True)}}

    cap = SERIES_CAP.get(chart, len(PALETTE))
    groups = _groups(rows, idx, x, ys, series, cap)
    many_points = len(rows) > 40
    traces = []
    for n, (name, (xs, vals)) in enumerate(groups.items()):
        color = PALETTE[n]
        t = {"name": name, "x": xs, "y": vals, "hovertemplate": f"<b>{name}</b>: %{{y:,}}<extra></extra>"}
        if chart in ("BAR", "STACKED_BAR", "HBAR"):
            t.update(type="bar", marker={"color": color, "line": {"color": SURFACE, "width": 2}})
            if chart == "HBAR":
                t.update(x=vals, y=xs, orientation="h", hovertemplate=f"<b>{name}</b>: %{{x:,}}<extra></extra>")
        elif chart in ("LINE", "AREA"):
            t.update(type="scatter", mode="lines" if many_points else "lines+markers",
                     line={"color": color, "width": 2}, marker={"size": 8, "color": color, "line": {"color": SURFACE, "width": 2}})
            if chart == "AREA":
                t.update(stackgroup="one", fillcolor=color + "33")
        else:  # SCATTER
            t.update(type="scatter", mode="markers",
                     marker={"size": 10, "color": color, "line": {"color": SURFACE, "width": 2}},
                     hovertemplate=f"<b>{name}</b><br>%{{x}}: %{{y:,}}<extra></extra>")
        traces.append(t)
    return {"kind": "plot", "figure": {"data": traces, "layout": _layout(chart, x, ys, show_legend=len(traces) > 1)}}


def _layout(chart, x, ys, show_legend):
    axis = {"color": MUTED, "gridcolor": GRID, "linecolor": GRID, "zeroline": False, "automargin": True,
            "tickfont": {"color": MUTED, "size": 11}, "title": {"font": {"color": INK_2, "size": 12}}}
    value_axis = {**axis, "rangemode": "tozero", "title": {**axis["title"], "text": _label(ys[0]) if len(ys) == 1 else ""}}
    cat_axis = {**axis, "showgrid": False, "title": {**axis["title"], "text": _label(x)}}
    horizontal = chart == "HBAR"
    return {
        "font": {"family": FONT, "color": INK_2, "size": 12},
        "paper_bgcolor": "rgba(0,0,0,0)", "plot_bgcolor": "rgba(0,0,0,0)",
        "margin": {"l": 8, "r": 8, "t": 40 if show_legend else 12, "b": 8},
        "colorway": PALETTE, "showlegend": show_legend,
        "legend": {"orientation": "h", "x": 0, "y": 1.02, "yanchor": "bottom", "font": {"color": INK_2}},
        "barmode": "stack" if chart == "STACKED_BAR" else "group", "bargap": 0.35, "bargroupgap": 0.08,
        "barcornerradius": 4,
        "hovermode": "x unified" if chart in ("LINE", "AREA") else "closest",
        "hoverlabel": {"bgcolor": SURFACE, "bordercolor": GRID, "font": {"color": INK, "family": FONT}},
        "xaxis": value_axis if horizontal else cat_axis,
        "yaxis": cat_axis if horizontal else value_axis,
    }
