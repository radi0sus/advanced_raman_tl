from __future__ import annotations

import csv
import io
import zipfile


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

    if x:
        lines.append(f"Points: {len(x)}")
        lines.append(f"Original range: {float(x[0]):.4f} - {float(x[-1]):.4f} cm^-1")

    lines.append("")
    lines.append("Processing")
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
        for key, value in metadata.items():
            if value not in (None, ""):
                lines.append(f"{key}: {value}")

    return "\n".join(lines).encode("utf-8")
    
def build_figure_html_bytes(fig) -> bytes:
    return fig.to_html(full_html=True, include_plotlyjs=True).encode("utf-8")
    
def build_zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)

    return buffer.getvalue()