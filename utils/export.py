from __future__ import annotations

import csv
import io
import zipfile
import json
import html
from datetime import datetime
#import plotly.graph_objects as go
from io import BytesIO
from matplotlib.backends.backend_pdf import PdfPages

def build_matplotlib_png_bytes(fig, dpi=150):
    buf = BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=dpi,
        bbox_inches="tight",
    )
    buf.seek(0)
    return buf.getvalue()

def build_matplotlib_pdf_bytes(figures):
    buf = BytesIO()

    with PdfPages(buf) as pdf:
        for fig in figures:
            pdf.savefig(fig)

    buf.seek(0)
    return buf.getvalue()

def make_safe_html_title(text: str) -> str:
    return str(text).replace("<", "").replace(">", "")

def meta_text(metadata: dict, key: str, default: str = "") -> str:
    entry = metadata.get(key)
    if not isinstance(entry, dict):
        return default

    value = entry.get("value")
    unit = entry.get("unit", "")

    if value in (None, ""):
        return default

    text = f"{value} {unit}".strip()
    return text or default

def build_single_spectrum_csv_bytes(
    result: dict,
    x_shift: float = 0.0,
    intensity_scale: float = 1.0,
) -> bytes:
    x = result["x"]
    y_raw = result["raw"]
    y_baseline = result["baseline"]
    y_corrected = result["corrected"]
    y_smoothed = result["smoothed"]

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "x",
        "x_shifted",
        "y_raw",
        "y_baseline",
        "y_corrected",
        "y_smoothed",
        "y_scaled",
    ])

    for xi, yi_raw, yi_base, yi_corr, yi_smooth in zip(
        x, y_raw, y_baseline, y_corrected, y_smoothed
    ):
        writer.writerow([
            f"{xi:.4f}",
            f"{xi + float(x_shift):.4f}",
            f"{yi_raw:.4f}",
            f"{yi_base:.4f}",
            f"{yi_corr:.4f}",
            f"{yi_smooth:.4f}",
            f"{yi_smooth * float(intensity_scale):.4f}",
        ])

    return output.getvalue().encode("utf-8")

def build_spectrum_metadata_txt_bytes(
    spectrum: dict,
    processing_kwargs: dict,
    x_shift: float = 0.0,
    intensity_scale: float = 1.0,
) -> bytes:
    metadata = spectrum.get("metadata", {})
    x = spectrum.get("x", [])

    lines = []

    filename = spectrum.get("filename")
    if filename:
        lines.append(f"Filename: {filename}")

    #if x:
    #    lines.append(f"Points: {len(x)}")
    #    lines.append(f"Original range: {float(x[0]):.1f} - {float(x[-1]):.1f} cm⁻¹")

    lines.append("")
    lines.append("Processing")
    xmin = processing_kwargs.get("xmin")
    xmax = processing_kwargs.get("xmax")
    if xmin is not None and xmax is not None:
        lines.append(f"wn range: {float(xmin):.1f} – {float(xmax):.1f} cm⁻¹")
    lines.append(f"x_shift: {float(x_shift):.4f}")
    lines.append(f"intensity_scale: {float(intensity_scale):.4f}")

    for key in [
        "baseline_method",
        "smoothing_method",
        "peak_prominence",
        "peak_prominence_factor",
        "peak_width",
        "peak_distance",
        "peak_rel_height",
    ]:
        value = processing_kwargs.get(key)
        if value is not None:
            lines.append(f"{key}: {value}")

    baseline_params = processing_kwargs.get("baseline_params")
    if baseline_params:
        for key, value in baseline_params.items():
            if value is not None:
                lines.append(f"baseline_params.{key}: {value}")

    smoothing_params = processing_kwargs.get("smoothing_params")
    if smoothing_params:
        for key, value in smoothing_params.items():
            if value is not None:
                lines.append(f"smoothing_params.{key}: {value}")

    if metadata:
        lines.append("")
        lines.append("Spectrum metadata")
        
    if x:
        lines.append(f"Points: {len(x)}")
        lines.append(f"Range: {float(x[0]):.1f} - {float(x[-1]):.1f} cm⁻¹")        

        key_order = [
            "Laser",
            "Grating",
            "Filter",
            "Acq. time",
            "Accumulations",
            "Windows",
            "Slit",
            "Hole",
            "Instrument",
            "Detector",
            "Acquired",
        ]

        for key in key_order:
            text = meta_text(metadata, key)
            if text:
                lines.append(f"{key}: {text}")

    return "\n".join(lines).encode("utf-8")

def build_multi_spectra_csv_bytes(
    processed_results: dict[str, dict],
) -> bytes:
    """
    Build a CSV for multiple processed spectra with a shared x-axis.

    Assumes:
    - result["x"] already includes any applied x_shift
    - result["smoothed"] already matches the visible plotted y values
      (including intensity scaling if applied in process_spectrum)

    Missing y values are filled with 0.0000.
    All numeric values are written with 4 decimal places.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Gemeinsame x-Achse = Vereinigung aller vorhandenen x-Werte
    all_x = set()
    for result in processed_results.values():
        for xi in result["x"]:
            all_x.add(round(float(xi), 10))

    x_common = sorted(all_x)

    # Header
    header = ["x"] + [f"y_{name}" for name in processed_results.keys()]
    writer.writerow(header)

    # Mapping je Spektrum: x -> y
    y_maps = {}
    for name, result in processed_results.items():
        y_maps[name] = {
            round(float(xi), 10): float(yi)
            for xi, yi in zip(result["x"], result["smoothed"])
        }

    # Datenzeilen
    for xi in x_common:
        row = [f"{xi:.4f}"]
        for name in processed_results.keys():
            yi = y_maps[name].get(xi, 0.0)
            row.append(f"{yi:.4f}")
        writer.writerow(row)

    return output.getvalue().encode("utf-8")
    
#def build_figure_html_bytes(fig) -> bytes:
#    return fig.to_html(full_html=True, include_plotlyjs=True).encode("utf-8")

def build_figure_html_bytes(fig) -> bytes:
    html_doc = fig.to_html(full_html=True, include_plotlyjs="cdn")

    footer = """
    <div style="margin: 1.5rem 2rem 1rem 2rem; padding-top: 1rem; border-top: 1px solid #e5e7eb; font-size: 0.9rem; color: #64748b; font-family: Arial, sans-serif;">
      Generated with Advanced Raman Tool ·
      <a href="https://github.com/radi0sus/advanced_raman_tl" target="_blank" rel="noopener noreferrer">
        https://github.com/radi0sus/advanced_raman_tl
      </a>
    </div>
    """

    if "</body>" in html_doc:
        html_doc = html_doc.replace("</body>", footer + "\n</body>")
    else:
        html_doc += footer

    return html_doc.encode("utf-8")    
    
def build_zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)

    return buffer.getvalue()
    
def build_summary_html_bytes(
    spectra: dict[str, dict],
    single_results: dict[str, dict],
    overlay_names: list[str],
    overlay_fig,
    normalized_overlay_fig,
    stacked_fig,
    processing_kwargs: dict,
    x_shifts: dict[str, float] | None = None,
    intensity_scales: dict[str, float] | None = None,
    include_single_file_links: bool = True,
    include_original_file_links: bool = True,
    overlay_csv_path: str | None = "overlay/overlay_processed.csv",
) -> bytes:
    x_shifts = x_shifts or {}
    intensity_scales = intensity_scales or {}

    export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def fmt_pretty(value):
        if value is None:
            return ""

        if isinstance(value, bool):
            return "Yes" if value else "No"

        if isinstance(value, int):
            return str(value)

        if isinstance(value, float):
            if value == 0:
                return "0"
            if float(value).is_integer():
                return str(int(value))
            if abs(value) < 1e-3 or abs(value) >= 1e4:
                return f"{value:.3g}"
            return f"{value:.6f}".rstrip("0").rstrip(".")

        return str(value)

    def metadata_to_html(spectrum: dict) -> str:
        metadata = spectrum.get("metadata", {})
        x = spectrum.get("x", [])

        items = []
        filename = spectrum.get("filename", "")
        if filename:
            items.append(("Filename", filename))

        if x:
            items.append(("Points", len(x)))
            items.append(("Range", f"{float(x[0]):.1f} – {float(x[-1]):.1f} cm⁻¹"))

        key_map = {
            "Laser": "Laser",
            "Acq. time": "Acq. time",
            "Accumulations": "Accumulations",
            "Windows": "Windows",
            "Grating": "Grating",
            "Filter": "Filter",
            "Slit": "Slit",
            "Hole": "Hole",
            "Instrument": "Instrument",
            "Detector": "Detector",
            "Acquired": "Acquired",
        }

        for key, label in key_map.items():
            value = meta_text(metadata, key)
            if value:
                items.append((label, value))

        return "".join(
            f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
            for k, v in items
        )
        
    def processing_to_html() -> str:
        sections = []

        xmin = processing_kwargs.get("xmin")
        xmax = processing_kwargs.get("xmax")
        if xmin is not None or xmax is not None:
            rows = []
            if xmin is not None:
                rows.append(("Wavenumber min", f"{fmt_pretty(xmin)} cm⁻¹"))
            if xmax is not None:
                rows.append(("Wavenumber max", f"{fmt_pretty(xmax)} cm⁻¹"))

            sections.append(("Spectral range", rows))

        baseline_method = processing_kwargs.get("baseline_method")
        baseline_params = processing_kwargs.get("baseline_params", {})
        if baseline_method:
            rows = [("Method", "arPLS" if baseline_method == "arpls" else "SNIP")]

            if baseline_method == "arpls":
                if baseline_params.get("lam") is not None:
                    rows.append(("Lambda", fmt_pretty(baseline_params.get("lam"))))
                if baseline_params.get("ratio") is not None:
                    rows.append(("Ratio", fmt_pretty(baseline_params.get("ratio"))))
                if baseline_params.get("max_iter") is not None:
                    rows.append(("Maximum iterations", fmt_pretty(baseline_params.get("max_iter"))))

            elif baseline_method == "snip":
                if baseline_params.get("iterations") is not None:
                    rows.append(("Iterations", fmt_pretty(baseline_params.get("iterations"))))

            sections.append(("Baseline correction", rows))

        smoothing_method = processing_kwargs.get("smoothing_method")
        smoothing_params = processing_kwargs.get("smoothing_params", {})
        if smoothing_method:
            rows = [(
                "Method",
                "Whittaker" if smoothing_method == "whittaker" else "Savitzky–Golay"
            )]

            if smoothing_method == "whittaker":
                if smoothing_params.get("lam") is not None:
                    rows.append(("Lambda", fmt_pretty(smoothing_params.get("lam"))))
                if smoothing_params.get("d") is not None:
                    rows.append(("Order", fmt_pretty(smoothing_params.get("d"))))

            elif smoothing_method == "savgol":
                if smoothing_params.get("window_length") is not None:
                    rows.append(("Window length", fmt_pretty(smoothing_params.get("window_length"))))
                if smoothing_params.get("polyorder") is not None:
                    rows.append(("Polynomial order", fmt_pretty(smoothing_params.get("polyorder"))))

            sections.append(("Smoothing", rows))

        rows = []

        peak_prominence = processing_kwargs.get("peak_prominence")
        peak_prominence_factor = processing_kwargs.get("peak_prominence_factor")
        peak_width = processing_kwargs.get("peak_width")
        peak_distance = processing_kwargs.get("peak_distance")
        peak_height = processing_kwargs.get("peak_height")
        peak_rel_height = processing_kwargs.get("peak_rel_height")

        if peak_prominence is not None:
            rows.append(("Prominence", fmt_pretty(peak_prominence)))
        elif peak_prominence_factor is not None:
            rows.append(("Auto prominence factor", fmt_pretty(peak_prominence_factor)))

        if peak_width is not None:
            rows.append(("Minimum width", f"{fmt_pretty(peak_width)} cm⁻¹"))

        if peak_distance is not None:
            rows.append(("Minimum distance", f"{fmt_pretty(peak_distance)} cm⁻¹"))

        if peak_height is not None:
            rows.append(("Minimum height", fmt_pretty(peak_height)))

        if peak_rel_height is not None:
            rows.append(("Relative height", fmt_pretty(peak_rel_height)))

        if rows:
            sections.append(("Peak detection", rows))

        html_sections = []
        for section_title, rows in sections:
            rows_html = "".join(
                f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>"
                for k, v in rows
            )
            html_sections.append(f"""
                <div class="settings-block">
                    <h3>{html.escape(section_title)}</h3>
                    <table class="meta">
                        {rows_html}
                    </table>
                </div>
            """)

        return "".join(html_sections)

    plot_divs = []
    plot_scripts = []

    def add_plot(fig, div_id: str):
        fig_json = fig.to_plotly_json()
        plot_divs.append(f'<div id="{div_id}" class="plot"></div>')
        plot_scripts.append(
            f"Plotly.newPlot('{div_id}', {json.dumps(fig_json['data'])}, {json.dumps(fig_json['layout'])}, {{responsive: true}});"
        )

    body_parts = []

    body_parts.append(f"""
    <h1>Raman Analysis Session Export</h1>
    <div id="nav-overview" class="section summary-overview-section">
      <h2>Session overview</h2>
      <table class="meta">
        <tr><th>Export time</th><td>{html.escape(export_time)}</td></tr>
        <tr><th>Loaded spectra</th><td>{len(spectra)}</td></tr>
        <tr><th>Overlay spectra</th><td>{len(overlay_names)}</td></tr>
        <tr><th>Overlay selection</th><td>{html.escape(', '.join(overlay_names) if overlay_names else 'None')}</td></tr>
      </table>
    </div>
    """)

    body_parts.append(f"""
    <div id="nav-processing" class="section summary-processing-section">
      <h2>Processing settings</h2>
      {processing_to_html()}
    </div>
    """)

    body_parts.append('<div id="nav-spectra" class="section"><h2>Individual spectra</h2></div>')

    spectrum_nav_links = []

    for i, (name, spectrum) in enumerate(spectra.items(), start=1):
        result = single_results[name]
        filename_base = spectrum.get("filename", name)
        stem = filename_base.rsplit(".", 1)[0]

        section_id = f"spectrum-{i}"
        spectrum_nav_links.append(
            f'<a href="#{section_id}" title="{html.escape(name)}">{i}</a>'
        )

        links = []

        if include_single_file_links:
            links.extend([
                f'<a href="{html.escape(name)}/{html.escape(stem)}_processed.csv">Processed CSV</a>',
                f'<a href="{html.escape(name)}/{html.escape(stem)}_metadata.txt">Metadata TXT</a>',
            ])

        if include_original_file_links and spectrum.get("filename"):
            links.append(
                f'<a href="{html.escape(name)}/{html.escape(spectrum.get("filename", name))}">Original file</a>'
            )

        from utils.figures import create_single_view_figure
        fig = create_single_view_figure(
            result,
            show_peaks=True,
            title=name,
        )

        div_id = f"single_plot_{i}"
        add_plot(fig, div_id)

        links_html = f'<div class="links">{" | ".join(links)}</div>' if links else ""

        body_parts.append(f"""
        <div id="{section_id}" class="section spectrum-section summary-single-spectrum">
          <h3>{html.escape(name)}</h3>
          {links_html}
          <table class="meta">
            {metadata_to_html(spectrum)}
            <tr><th>Wavenumber shift</th><td>{html.escape(fmt_pretty(float(x_shifts.get(name, 0.0))))} cm⁻¹</td></tr>
            <tr><th>Intensity scale</th><td>{html.escape(fmt_pretty(float(intensity_scales.get(name, 1.0))))}×</td></tr>
          </table>
          {plot_divs[-1]}
        </div>
        """)

    body_parts.append('<div id="nav-overlay" class="section"><h2>Overlay views</h2></div>')

    overlay_links = []
    if overlay_csv_path:
        overlay_links.append(f'<a href="{html.escape(overlay_csv_path)}">Overlay CSV</a>')

    overlay_links_html = f'<div class="links">{" | ".join(overlay_links)}</div>' if overlay_links else ""

    body_parts.append(f"""
    <div class="section spectrum-section summary-overlay-info">
      <h3>Selected spectra in overlays</h3>
      <div>{html.escape(', '.join(overlay_names) if overlay_names else 'None')}</div>
      {overlay_links_html}
    </div>
    """)

    add_plot(overlay_fig, "overlay_plot")
    body_parts.append("""
    <div class="section spectrum-section summary-overlay-view">
      <h3>Overlay</h3>
      {plot}
    </div>
    """.replace("{plot}", plot_divs[-1]))

    add_plot(normalized_overlay_fig, "normalized_overlay_plot")
    body_parts.append("""
    <div class="section spectrum-section summary-overlay-view">
      <h3>Normalized Overlay</h3>
      {plot}
    </div>
    """.replace("{plot}", plot_divs[-1]))

    add_plot(stacked_fig, "stacked_plot")
    body_parts.append("""
    <div class="section spectrum-section summary-overlay-view">
      <h3>Stacked Spectra</h3>
      {plot}
    </div>
    """.replace("{plot}", plot_divs[-1]))
    

    html_doc = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>
      <title>Raman Analysis Session Export</title>
      <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
      <style>
        #raman-navbar {{
          position: sticky;
          top: 0;
          z-index: 1000;
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 0.75rem;
          background: white;
          border-bottom: 1px solid #cbd5e1;
          padding: 0.75rem 0;
          margin-bottom: 1.5rem;
        }}

        #raman-navbar .nav-title {{
          font-weight: 700;
          color: #334155;
          margin-right: 0.5rem;
        }}

        #raman-navbar a {{
          color: #2563eb;
          text-decoration: none;
          font-size: 0.95rem;
        }}

        #raman-navbar a:hover {{
          text-decoration: underline;
        }}

        #raman-navbar .nav-subtitle {{
          color: #475569;
          font-size: 0.9rem;
          margin-left: 0.5rem;
        }}

        #raman-navbar .nav-divider {{
          color: #94a3b8;
          margin: 0 0.25rem;
        }}
        
        #raman-navbar .nav-print-button {{
          border: 1px solid #cbd5e1;
          background: #f8fafc;
          color: #0f172a;
          border-radius: 6px;
          padding: 0.35rem 0.7rem;
          font-size: 0.9rem;
          cursor: pointer;
        }}
        
        #raman-navbar .nav-print-button:hover {{
          background: #e2e8f0;
        }}
        
        #raman-navbar .nav-footer {{
          color: #64748b;
          font-size: 0.9rem;
        }}
        
        #raman-navbar .nav-footer a {{
          color: #2563eb;
          text-decoration: none;
        }}
        
        #raman-navbar .nav-footer a:hover {{
          text-decoration: underline;
        }}
        
        #nav-overview,
        #nav-processing,
        #nav-spectra,
        #nav-overlay {{
          scroll-margin-top: 4.5rem;
        }}

        @media print {{
          @page {{
            size: auto;
            margin: 12mm;
          }}
        
          #raman-navbar {{
            display: none !important;
          }}
        
          body {{
            margin: 0;
            color: black;
            background: white;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }}
        
          .summary-single-spectrum,
          .summary-overlay-view,
          .summary-overlay-info,
          .settings-block,
          .meta,
          .plot {{
            break-inside: avoid;
            page-break-inside: avoid;
          }}
        
          .summary-single-spectrum,
          .summary-overlay-view,
          .summary-overlay-info {{
            break-before: page;
            page-break-before: always;
          }}
        
          .summary-single-spectrum:first-of-type,
          .summary-overlay-view:first-of-type,
          .summary-overlay-info:first-of-type {{
            break-before: auto;
            page-break-before: auto;
          }}
        
          .plot {{
            height: 420px !important;
          }}
        
          .links {{
            display: none !important;
          }}
        
          h1, h2, h3 {{
            break-after: avoid;
            page-break-after: avoid;
          }}
        }}

        body {{
          font-family: Arial, sans-serif;
          margin: 24px;
          color: #0f172a;
          background: white;
        }}
        h1 {{
          margin-bottom: 0.2rem;
        }}
        h2 {{
          margin-top: 2rem;
          border-bottom: 1px solid #cbd5e1;
          padding-bottom: 0.25rem;
        }}
        h3 {{
          margin-bottom: 0.5rem;
        }}
        .section {{
          margin-bottom: 2rem;
        }}
        .spectrum-section {{
          padding: 1rem 0;
          border-bottom: 1px solid rgba(148, 163, 184, 0.35);
        }}
        .meta {{
          border-collapse: collapse;
          margin: 0.5rem 0 0.8rem 0;
          width: 100%;
          max-width: 900px;
          font-size: 0.9rem;
          line-height: 1.3;
        }}
        
        .meta th {{
          text-align: left;
          vertical-align: top;
          padding: 0.18rem 0.6rem 0.18rem 0;
          width: 180px;
          color: #64748b;
          font-weight: 600;
        }}
        
        .meta td {{
          padding: 0.18rem 0;
          color: #0f172a;
        }}
        .links {{
          margin: 0.5rem 0 1rem 0;
        }}
        .links a {{
          color: #2563eb;
          text-decoration: none;
          margin-right: 1rem;
        }}
        .links a:hover {{
          text-decoration: underline;
        }}
        .plot {{
          width: 100%;
          height: 900px;
        }}
        .settings-block {{
          margin-bottom: 1.25rem;
        }}
        .settings-block h3 {{
          margin-bottom: 0.4rem;
          color: #1e293b;
        }}
        .summary-single-spectrum {{
          scroll-margin-top: 4.5rem;
        }}
      </style>
    </head>
    <body>
      <nav id="raman-navbar">
        <span class="nav-title">Raman Export</span>
        <a href="#nav-overview">Overview</a>
        <a href="#nav-processing">Processing</a>
        <a href="#nav-spectra">Spectra</a>
        <a href="#nav-overlay">Overlays</a>
        <button type="button" class="nav-print-button" onclick="window.print()">🖨 Print / PDF</button>
        <span class="nav-divider">|</span>
        <span class="nav-subtitle">Singles:</span>
        {''.join(spectrum_nav_links)}
        <span class="nav-divider">|</span>
        <span class="nav-footer">
          Generated with Advanced Raman Tool ·
          <a href="https://github.com/radi0sus/advanced_raman_tl" target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
        </span>
</nav>
      {''.join(body_parts)}
      <script>
        {''.join(plot_scripts)}
      </script>
    </body>
    </html>
    """

    return html_doc.encode("utf-8")