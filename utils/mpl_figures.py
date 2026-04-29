from __future__ import annotations

import re
from typing import Iterable

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec

from utils.processing import process_spectrum


PLOT_COLORS = [
    "#2563eb",  # blue
    "#ef4444",  # red
    "#10b981",  # green
    "#8b5cf6",  # violet
    "#f59e0b",  # amber
    "#06b6d4",  # cyan
    "#ec4899",  # pink
    "#84cc16",  # lime
]


def _shorten_name(name: str, max_len: int = 12) -> str:
    match = re.search(r'_\d+p', name)
    if match:
        short = name[:match.start()] + "…"
    elif len(name) > max_len:
        short = name[:max_len] + "…"
    else:
        short = name
    return short


def make_spectrum_title(spectrum_dict: dict) -> str:
    return spectrum_dict.get("filename") or spectrum_dict.get("name") or "Spectrum"


def _apply_axis_style(ax):
    ax.set_facecolor("white")

    ax.grid(
        True,
        which="major",
        axis="both",
        color="#e5e7eb",
        linewidth=0.7,
        linestyle="-",
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#6b7280")
    ax.spines["bottom"].set_color("#6b7280")
    ax.spines["left"].set_linewidth(0.9)
    ax.spines["bottom"].set_linewidth(0.9)

    ax.tick_params(
        axis="both",
        labelsize=11,
        colors="#374151",
        width=0.8,
        length=4,
        direction="out",
    )

    return ax

def _expand_limits(x, pad_fraction: float = 0.005):
    x = np.asarray(x, dtype=float)
    if x.size < 2:
        return None

    x_min = float(np.min(x))
    x_max = float(np.max(x))
    x_range = x_max - x_min

    if x_range <= 0:
        return None

    pad = pad_fraction * x_range
    return x_min - pad, x_max + pad


def _meta_text(metadata: dict, key: str) -> str | None:
    entry = metadata.get(key)
    if not isinstance(entry, dict):
        return None

    value = entry.get("value")
    unit = entry.get("unit", "")

    if value in (None, ""):
        return None

    return f"{value} {unit}".strip()


def _format_metadata_lines(spectrum: dict) -> list[str]:
    metadata = spectrum.get("metadata", {})
    x = spectrum.get("x", [])

    lines = [
        f"Points: {len(x)}",
    ]

    if x:
        lines.append(f"Range: {x[0]:.1f} – {x[-1]:.1f} cm⁻¹")

    key_map = {
        "Laser": "Laser",
        "Grating": "Grating",
        "Filter": "Filter",
        "Acq. time": "Acq. time",
        "Accumulations": "Accum.",
        "Windows": "Windows",
        "Slit": "Slit",
        "Hole": "Hole",
        "Instrument": "Instrument",
        "Detector": "Detector",
        "Acquired": "Acquired",
    }

    for key, label in key_map.items():
        value = _meta_text(metadata, key)
        if value:
            lines.append(f"{label}: {value}")

    return lines


def _format_processing_lines(
    processing_kwargs: dict | None,
    x_shift: float | None = None,
    intensity_scale: float | None = None,
) -> list[str]:
    if not processing_kwargs:
        return []

    lines = []

    xmin = processing_kwargs.get("xmin")
    xmax = processing_kwargs.get("xmax")
    if xmin is not None and xmax is not None:
        lines.append(f"wn range: {float(xmin):.1f} – {float(xmax):.1f} cm⁻¹")

    baseline_method = processing_kwargs.get("baseline_method")
    baseline_params = processing_kwargs.get("baseline_params", {}) or {}
    if baseline_method == "arpls":
        lines.append(f"Baseline: arPLS (λ={baseline_params.get('lam', '—')})")
    elif baseline_method == "snip":
        lines.append(f"Baseline: SNIP (iter={baseline_params.get('iterations', '—')})")

    smoothing_method = processing_kwargs.get("smoothing_method")
    smoothing_params = processing_kwargs.get("smoothing_params", {}) or {}
    if smoothing_method == "whittaker":
        lines.append(f"Smoothing: Whittaker (λ={smoothing_params.get('lam', '—')})")
    elif smoothing_method == "savgol":
        lines.append(
            "Smoothing: Savitzky-Golay "
            f"(window={smoothing_params.get('window_length', '—')}, "
            f"poly={smoothing_params.get('polyorder', '—')})"
        )

    peak_prominence = processing_kwargs.get("peak_prominence")
    peak_prominence_factor = processing_kwargs.get("peak_prominence_factor")
    peak_width = processing_kwargs.get("peak_width")
    peak_distance = processing_kwargs.get("peak_distance")

    if peak_prominence is not None:
        lines.append(f"Peaks: prominence={float(peak_prominence):.3f}")
    elif peak_prominence_factor is not None:
        lines.append(f"Peaks: auto prominence factor={float(peak_prominence_factor):.3f}")

    if peak_width is not None:
        lines.append(f"Min width: {float(peak_width):.2f} cm⁻¹")

    if peak_distance is not None:
        lines.append(f"Min distance: {float(peak_distance):.2f} cm⁻¹")

    if x_shift is not None:
        lines.append(f"x shift: {float(x_shift):.2f} cm⁻¹")

    if intensity_scale is not None:
        lines.append(f"Intensity scale: {float(intensity_scale):.2f}")

    return lines


def _draw_text_block(
    ax,
    title: str,
    lines: Iterable[str],
    title_color: str = "#64748b",
    body_color: str = "#334155",
):
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    ax.text(
        0.02, 0.96,
        title,
        ha="left",
        va="top",
        fontsize=10.8,
        fontweight="bold",
        color=title_color,
    )

    y = 0.89
    for line in lines:
        ax.text(
            0.02, y,
            line,
            ha="left",
            va="top",
            fontsize=10.2,
            color=body_color,
        )
        y -= 0.062

def _annotate_peaks(
    ax,
    peak_x,
    peak_y,
    color: str,
    max_labels: int = 100,
    fontsize: float = 8,
    marker_size: float = 18,
):
    peak_x = np.asarray(peak_x, dtype=float)
    peak_y = np.asarray(peak_y, dtype=float)

    if peak_x.size == 0:
        return

    n_labels = min(peak_x.size, max_labels)
    peak_x = peak_x[:n_labels]
    peak_y = peak_y[:n_labels]

    ax.scatter(peak_x, peak_y, color=color, s=marker_size, zorder=3)

    for px, py in zip(peak_x, peak_y):
        ax.annotate(
            f"{int(round(float(px)))}",
            (px, py),
            textcoords="offset points",
            xytext=(0, 6),
            ha="center",
            va="bottom",
            fontsize=fontsize,
            color=color,
        )

def _add_footer(fig):
    fig.text(
        0.99, 0.012,
        "Generated with Advanced Raman Tool · https://github.com/radi0sus/advanced_raman_tl",
        ha="right",
        va="bottom",
        fontsize=8,
        color="#94a3b8",
    )

def create_single_summary_mpl_figure(
    spectrum: dict,
    result: dict,
    processing_kwargs: dict | None = None,
    x_shift: float = 0.0,
    intensity_scale: float = 1.0,
    show_peaks: bool = True,
    title: str | None = None,
    x_label: str = "Raman shift / cm⁻¹",
    y_label_top: str = "Intensity",
    y_label_bottom: str = "Intensity",
    show_raw: bool = True,
    show_baseline: bool = True,
    show_corrected: bool = True,
    show_smoothed: bool = True,
):
    title = title or make_spectrum_title(spectrum)

    x = np.asarray(result["x"], dtype=float)
    raw = np.asarray(result["raw"], dtype=float)
    baseline = np.asarray(result["baseline"], dtype=float)
    corrected = np.asarray(result["corrected"], dtype=float)
    smoothed = np.asarray(result["smoothed"], dtype=float)
    peaks = result.get("peaks", {})

    fig = plt.figure(figsize=(11.69, 8.27))
    gs = GridSpec(
        2, 2,
        figure=fig,
        width_ratios=[3.4, 1.35],
        height_ratios=[1.0, 1.0],
        wspace=0.16,
        hspace=0.20,
    )

    ax_top = fig.add_subplot(gs[0, 0])
    ax_bottom = fig.add_subplot(gs[1, 0], sharex=ax_top)
    ax_meta = fig.add_subplot(gs[0, 1])
    ax_proc = fig.add_subplot(gs[1, 1])

    # obere Achse
    if show_raw:
        ax_top.plot(x, raw, color="#2563eb", linewidth=1.5, alpha=0.95, label="Raw")

    if show_baseline:
        ax_top.plot(
            x,
            baseline,
            color="#ef4444",
            linewidth=1.5,
            linestyle="--",
            alpha=0.9,
            label="Baseline",
        )

    if show_corrected:
       ax_top.plot(x, corrected, color="#0f172a", linewidth=1.5, label="Corrected")

    # untere Achse
    if show_smoothed:
        ax_bottom.plot(x, smoothed, color="#10b981", linewidth=1.5, label="Smoothed")

    if show_peaks and show_smoothed:
        peak_x = np.asarray(peaks.get("x", []), dtype=float)
        if peak_x.size > 0:
            peak_y = np.interp(peak_x, x, smoothed)
            _annotate_peaks(
                ax_bottom,
                peak_x,
                peak_y,
                color="#10b981",
                fontsize=8,
                marker_size=22,
            )

    ax_top.set_title(
        "Raw Spectrum & Baseline corrected Spectrum with Baseline",
        loc="left",
        fontsize=12,
        color="#0f172a",
    )
    ax_bottom.set_title(
        "Baseline Corrected and Smoothed Spectrum",
        loc="left",
        fontsize=12,
        color="#0f172a",
    )

    ax_top.set_ylabel(y_label_top, fontsize=11, labelpad=6)
    ax_bottom.set_ylabel(y_label_bottom, fontsize=11, labelpad=6)
    ax_bottom.set_xlabel(x_label, fontsize=11)

    for ax in (ax_top, ax_bottom):
        _apply_axis_style(ax)
        ax.legend(loc="best", fontsize=10, frameon=False)

    xlim = _expand_limits(x)
    if xlim is not None:
        ax_top.set_xlim(*xlim)

    plt.setp(ax_top.get_xticklabels(), visible=False)

    metadata_lines = _format_metadata_lines(spectrum)
    processing_lines = _format_processing_lines(
        processing_kwargs=processing_kwargs,
        x_shift=x_shift,
        intensity_scale=intensity_scale,
    )

    _draw_text_block(ax_meta, "Metadata", metadata_lines)
    _draw_text_block(ax_proc, "Processing", processing_lines)

    fig.suptitle(title, x=0.5, y=0.97, ha="center", fontsize=15, color="#0f172a")
    fig.subplots_adjust(top=0.90, left=0.09, right=0.97, bottom=0.08)
    _add_footer(fig)
    return fig

def create_overlay_mpl_figure(
    spectra_dict: dict,
    processing_kwargs: dict | None = None,
    intensity_scales: dict | None = None,
    x_shifts: dict | None = None,
    title: str = "Overlay",
    x_label: str = "Raman shift / cm⁻¹",
    y_label: str = "Intensity",
    show_peaks: bool = False,
):
    processing_kwargs = processing_kwargs or {}
    intensity_scales = intensity_scales or {}
    x_shifts = x_shifts or {}

    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    all_x = []

    for i, (name, spectrum) in enumerate(spectra_dict.items()):
        color = PLOT_COLORS[i % len(PLOT_COLORS)]

        local_processing_kwargs = dict(processing_kwargs)
        local_processing_kwargs["intensity_scale"] = intensity_scales.get(name, 1.0)
        local_processing_kwargs["x_shift"] = x_shifts.get(name, 0.0)

        result = process_spectrum(
            spectrum["x"],
            spectrum["y"],
            **local_processing_kwargs,
        )

        x = np.asarray(result["x"], dtype=float)
        y = np.asarray(result["smoothed"], dtype=float)
        all_x.extend(x.tolist())

        ax.plot(
            x,
            y,
            linewidth=1.5,
            color=color,
            label=name,
        )

        if show_peaks and len(result["peaks"]["x"]) > 0:
            _annotate_peaks(
                ax,
                result["peaks"]["x"],
                result["peaks"]["y"],
                color=color,
                fontsize=7,
                marker_size=18,
            )

    ax.set_title(title, loc="left", fontsize=13, color="#0f172a")
    ax.set_xlabel(x_label, fontsize=11)
    ax.set_ylabel(y_label, fontsize=11)

    _apply_axis_style(ax)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(0.0, -0.10),
        ncol=2,
        fontsize=8.5,
        frameon=False,
        handlelength=1.8,
        handletextpad=0.5,
        labelspacing=0.3,
        columnspacing=0.8,
        borderaxespad=0.2,
    )

    xlim = _expand_limits(all_x)
    if xlim is not None:
        ax.set_xlim(*xlim)

    fig.subplots_adjust(top=0.90, left=0.08, right=0.97, bottom=0.22)
    _add_footer(fig)
    return fig


def create_normalized_overlay_mpl_figure(
    spectra_dict: dict,
    processing_kwargs: dict | None = None,
    x_shifts: dict | None = None,
    title: str = "Normalized Overlay",
    x_label: str = "Raman shift / cm⁻¹",
    y_label: str = "Normalized intensity",
    show_peaks: bool = False,
):
    processing_kwargs = processing_kwargs or {}
    x_shifts = x_shifts or {}

    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    all_x = []

    for i, (name, spectrum) in enumerate(spectra_dict.items()):
        color = PLOT_COLORS[i % len(PLOT_COLORS)]

        local_processing_kwargs = dict(processing_kwargs)
        local_processing_kwargs["x_shift"] = x_shifts.get(name, 0.0)

        result = process_spectrum(
            spectrum["x"],
            spectrum["y"],
            **local_processing_kwargs,
        )

        x = np.asarray(result["x"], dtype=float)
        y = np.asarray(result["smoothed"], dtype=float)
        ymax = np.max(y) if y.size > 0 else 1.0
        y_norm = y / ymax if ymax != 0 else y

        all_x.extend(x.tolist())

        ax.plot(
            x,
            y_norm,
            linewidth=1.5,
            color=color,
            label=name,
        )

        if show_peaks and len(result["peaks"]["x"]) > 0:
            peak_x = np.asarray(result["peaks"]["x"], dtype=float)
            peak_y = np.asarray(result["peaks"]["y"], dtype=float)
            peak_y = peak_y / ymax if ymax != 0 else peak_y

            _annotate_peaks(
                ax,
                peak_x,
                peak_y,
                color=color,
                fontsize=7,
                marker_size=18,
            )

    ax.set_title(title, loc="left", fontsize=13, color="#0f172a")
    ax.set_xlabel(x_label, fontsize=11)
    ax.set_ylabel(y_label, fontsize=11)

    _apply_axis_style(ax)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(0.0, -0.10),
        ncol=2,
        fontsize=8.5,
        frameon=False,
        handlelength=1.8,
        handletextpad=0.5,
        labelspacing=0.3,
        columnspacing=0.8,
        borderaxespad=0.2,
    )

    xlim = _expand_limits(all_x)
    if xlim is not None:
        ax.set_xlim(*xlim)

    fig.subplots_adjust(top=0.90, left=0.08, right=0.97, bottom=0.22)
    _add_footer(fig)
    return fig


def create_stacked_mpl_figure(
    spectra_dict: dict,
    processing_kwargs: dict | None = None,
    x_shifts: dict | None = None,
    title: str = "Stacked Spectra",
    x_label: str = "Raman shift / cm⁻¹",
    y_label: str = "Normalized intensity",
    step: float = 0.2,
    show_peaks: bool = False,
):
    processing_kwargs = processing_kwargs or {}
    x_shifts = x_shifts or {}

    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    all_x = []

    for i, (name, spectrum) in enumerate(spectra_dict.items()):
        color = PLOT_COLORS[i % len(PLOT_COLORS)]

        local_processing_kwargs = dict(processing_kwargs)
        local_processing_kwargs["x_shift"] = x_shifts.get(name, 0.0)

        result = process_spectrum(
            spectrum["x"],
            spectrum["y"],
            **local_processing_kwargs,
        )

        x = np.asarray(result["x"], dtype=float)
        y = np.asarray(result["smoothed"], dtype=float)
        ymax = np.max(y) if y.size > 0 else 1.0
        y_norm = y / ymax if ymax != 0 else y
        y_stack = y_norm + i * step

        all_x.extend(x.tolist())

        ax.plot(
            x,
            y_stack,
            linewidth=1.5,
            color=color,
            label=name,
        )

        if show_peaks and len(result["peaks"]["x"]) > 0:
            peak_x = np.asarray(result["peaks"]["x"], dtype=float)
            peak_y = np.asarray(result["peaks"]["y"], dtype=float)
            peak_y = peak_y / ymax + i * step if ymax != 0 else peak_y + i * step

            _annotate_peaks(
                ax,
                peak_x,
                peak_y,
                color=color,
                fontsize=7,
                marker_size=18,
            )

    ax.set_title(title, loc="left", fontsize=13, color="#0f172a")
    ax.set_xlabel(x_label, fontsize=11)
    ax.set_ylabel(y_label, fontsize=11)
    ax.set_yticklabels([])

    _apply_axis_style(ax)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(0.0, -0.10),
        ncol=2,
        fontsize=8.5,
        frameon=False,
        handlelength=1.8,
        handletextpad=0.5,
        labelspacing=0.3,
        columnspacing=0.8,
        borderaxespad=0.2,
    )

    xlim = _expand_limits(all_x)
    if xlim is not None:
        ax.set_xlim(*xlim)

    fig.subplots_adjust(top=0.90, left=0.08, right=0.97, bottom=0.22)
    _add_footer(fig)
    return fig

def create_session_overview_mpl_figure(
    spectra: dict,
    selected_overlay_names: list[str],
    export_time: str,
):
    fig = plt.figure(figsize=(11.69, 8.27))  # A4 quer
    ax = fig.add_subplot(111)

    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    fig.suptitle(
        "Session Overview",
        x=0.5,
        y=0.97,
        ha="center",
        fontsize=16,
        color="#0f172a",
    )

    session_lines = [
        ("Export time", export_time),
        ("Loaded spectra", str(len(spectra))),
        ("Overlay spectra", str(len(selected_overlay_names))),
        ("Overlay selection", ", ".join(selected_overlay_names) if selected_overlay_names else "—"),
    ]

    ax.text(
        0.06, 0.90,
        "Session overview",
        ha="left",
        va="top",
        fontsize=12,
        fontweight="bold",
        color="#64748b",
    )

    y = 0.82
    for label, value in session_lines:
        ax.text(
            0.06, y,
            label,
            ha="left",
            va="top",
            fontsize=11,
            color="#0f172a",
            fontweight="bold",
        )
        ax.text(
            0.28, y,
            value,
            ha="left",
            va="top",
            fontsize=11,
            color="#334155",
            wrap=True,
        )
        y -= 0.11

    fig.subplots_adjust(top=0.90, left=0.04, right=0.96, bottom=0.08)
    return fig