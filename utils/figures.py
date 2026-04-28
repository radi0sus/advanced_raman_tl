import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re

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

def _shorten_name(name, max_len=12):
    match = re.search(r'_\d+p', name)
    if match:
        short = name[:match.start()] + "…"
    elif len(name) > max_len:
        short = name[:max_len] + "…"
    else:
        short = name  # wirklich kurzer Name, kein …
    return short

def _axis_style(fig):
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(148, 163, 184, 0.18)",
        zeroline=False,
        linecolor="rgba(100, 116, 139, 0.45)",
        mirror=False,
        automargin=True,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(148, 163, 184, 0.18)",
        zeroline=False,
        linecolor="rgba(100, 116, 139, 0.45)",
        mirror=False,
        automargin=True,
    )
    fig.update_layout(
        #template="plotly_white",
        #paper_bgcolor="white",
        #plot_bgcolor="white",
        showlegend=True,
        font=dict(size=13),
        title=dict(
            x=0.0,
            xanchor="left",
            y=0.98,
            yanchor="top",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.22,
            xanchor="left",
            x=0.0,
            bgcolor="rgba(0,0,0,0.03)",
            bordercolor="Black",
            borderwidth=0,
        ),
    )
    return fig

def make_spectrum_title(spectrum_dict):
    return spectrum_dict.get("filename") or spectrum_dict.get("name") or "Spectrum"

def _expand_xaxis(fig, x, pad_fraction=0.005):
    x = np.asarray(x, dtype=float)
    if len(x) < 2:
        return fig

    x_min = float(np.min(x))
    x_max = float(np.max(x))
    x_range = x_max - x_min

    if x_range <= 0:
        return fig

    pad = pad_fraction * x_range
    fig.update_xaxes(range=[x_min - pad, x_max + pad])
    return fig

def _add_peak_annotations(
    fig,
    peaks,
    row=None,
    col=None,
    max_labels=100,
    marker_color="#8b5cf6",
    marker_size=6,
    legendgroup=None,
    trace_name="Peak",
    showlegend=False,
):
    peak_x = np.asarray(peaks.get("x", np.array([])), dtype=float)
    peak_y = np.asarray(peaks.get("y", np.array([])), dtype=float)

    if len(peak_x) == 0:
        return fig

    n_labels = min(len(peak_x), max_labels)
    peak_x = peak_x[:n_labels]
    peak_y = peak_y[:n_labels]
    peak_labels = [str(int(round(float(v)))) for v in peak_x]

    fig.add_trace(
        go.Scatter(
            x=peak_x,
            y=peak_y,
            mode="markers+text",
            text=peak_labels,
            textposition="top center",
            textfont=dict(size=10, color=marker_color),
            marker=dict(
                color=marker_color,
                size=marker_size,
                line=dict(color="white", width=1),
            ),
            name=trace_name,
            showlegend=showlegend,
            legendgroup=legendgroup,
        ),
        row=row,
        col=col,
    )

    return fig

from plotly.subplots import make_subplots

def create_single_view_figure(
    result,
    show_peaks=True,
    title="Processed Spectrum",
    x_label="Raman shift / cm⁻¹",
    y_label_top="Intensity",
    y_label_bottom="Intensity",
    show_raw=True,
    show_baseline=True,
    show_corrected=True,
    show_smoothed=True,
):
    x = result["x"]
    raw = result["raw"]
    baseline = result["baseline"]
    corrected = result["corrected"]
    smoothed = result["smoothed"]
    peaks = result["peaks"]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            "Raw Spectrum & Baseline corrected Spectrum with Baseline",
            "Baseline Corrected and Smoothed Spectrum",
        ),
    )

    # oben
    if show_raw:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=raw,
                mode="lines",
                name="Raw",
                line=dict(color="#2563eb", width=2),
            ),
            row=1,
            col=1,
        )

    if show_baseline:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=baseline,
                mode="lines",
                name="Baseline",
                line=dict(color="#ef4444", width=2, dash="dash"),
            ),
            row=1,
            col=1,
        )

    if show_corrected:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=corrected,
                mode="lines",
                name="Corrected",
                line=dict(color="#0f172a", width=2),
            ),
            row=1,
            col=1,
        )

    # unten
    if show_smoothed:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=smoothed,
                mode="lines",
                name="Smoothed",
                line=dict(color="#10b981", width=2.5),
                legendgroup="smoothed",
            ),
            row=2,
            col=1,
        )

    if show_peaks and show_smoothed:
        peak_x = np.asarray(peaks.get("x", np.array([])), dtype=float)

        if len(peak_x) > 0:
            peak_y = np.interp(
                peak_x,
                np.asarray(x, dtype=float),
                np.asarray(smoothed, dtype=float),
            )

            peak_result = {
                "x": peak_x,
                "y": peak_y,
            }

            _add_peak_annotations(
                fig,
                peak_result,
                row=2,
                col=1,
                marker_color="#10b981",
                marker_size=8,
                legendgroup="smoothed",
                trace_name="Peak",
                showlegend=False,
            )

    fig.update_layout(
        title=title,
        height=800,
    )

    fig.update_yaxes(title_text=y_label_top, row=1, col=1)
    fig.update_yaxes(title_text=y_label_bottom, row=2, col=1)
    fig.update_xaxes(title_text=x_label, row=2, col=1)

    _expand_xaxis(fig, x)
    return _axis_style(fig)

def create_overlay_figure(
    spectra_dict,
    processing_kwargs=None,
    intensity_scales=None,
    x_shifts=None, 
    title="Overlay",
    x_label="Raman shift / cm⁻¹",
    y_label="Intensity",
    show_peaks=False,
):
    all_x = []
    
    processing_kwargs = processing_kwargs or {}
    intensity_scales = intensity_scales or {}
    x_shifts = x_shifts or {}
    
    fig = go.Figure()

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
        
        all_x.extend(result["x"])
        
        fig.add_trace(
            go.Scatter(
                x=result["x"],
                y=result["smoothed"],
                mode="lines",
                name=_shorten_name(name),
                customdata=[name] * len(result["x"]),
                hovertemplate=(
                    f"<span style='color:{color}'><b>%{{customdata}}</b></span><br>"
                    "x: %{x:.1f}<br>y: %{y:.1f}<extra></extra>"
                ),
                legendgroup=name,
                line=dict(width=2, color=color),
            )
        )

        if show_peaks and len(result["peaks"]["x"]) > 0:
            _add_peak_annotations(
                fig,
                result["peaks"],
                marker_color=color,
                marker_size=6,
                legendgroup=name,
                trace_name="Peak",
                showlegend=False,
            )

    fig.update_layout(
        title=title,
        height=800,
        xaxis_title=x_label,
        yaxis_title=y_label,
    )

    _expand_xaxis(fig, all_x)
    return _axis_style(fig)


def create_normalized_overlay_figure(
    spectra_dict,
    processing_kwargs=None,
    x_shifts=None, 
    title="Normalized Overlay",
    x_label="Raman shift / cm⁻¹",
    y_label="Normalized intensity",
    show_peaks=False,
):

    all_x = []
    
    processing_kwargs = processing_kwargs or {}
    x_shifts = x_shifts or {}
    fig = go.Figure()

    for i, (name, spectrum) in enumerate(spectra_dict.items()):
        color = PLOT_COLORS[i % len(PLOT_COLORS)]

        local_processing_kwargs = dict(processing_kwargs)
        local_processing_kwargs["x_shift"] = x_shifts.get(name, 0.0)

        result = process_spectrum(
            spectrum["x"],
            spectrum["y"],
            **local_processing_kwargs,
        )
        
        all_x.extend(result["x"])
        
        y = np.asarray(result["smoothed"], dtype=float)
        ymax = np.max(y) if y.size > 0 else 1.0
        y_norm = y / ymax if ymax != 0 else y

        fig.add_trace(
            go.Scatter(
                x=result["x"],
                y=y_norm,
                mode="lines",
                name=_shorten_name(name),
                customdata=[name] * len(result["x"]),
                hovertemplate=(
                    f"<span style='color:{color}'><b>%{{customdata}}</b></span><br>"
                    "x: %{x:.1f}<br>y: %{y:.1f}<extra></extra>"
                ),
                legendgroup=name,
                line=dict(width=2, color=color),
            )
        )

        if show_peaks and len(result["peaks"]["x"]) > 0:
            peak_x = result["peaks"]["x"]
            peak_y = result["peaks"]["y"] / ymax if ymax != 0 else result["peaks"]["y"]

            peak_result_norm = {
                "x": peak_x,
                "y": peak_y,
            }

            _add_peak_annotations(
                fig,
                peak_result_norm,
                marker_color=color,
                marker_size=6,
                legendgroup=name,
                trace_name="Peak",
                showlegend=False,
            )

    fig.update_layout(
        title=title,
        height=800,
        xaxis_title=x_label,
        yaxis_title=y_label,
    )
    
    _expand_xaxis(fig, all_x)
    return _axis_style(fig)


def create_stacked_figure(
    spectra_dict,
    processing_kwargs=None,
    x_shifts=None,
    title="Stacked Spectra",
    x_label="Raman shift / cm⁻¹",
    y_label="Normalized intensity",
    step=0.2,
    show_peaks=False,
):

    all_x = []
    
    processing_kwargs = processing_kwargs or {}
    x_shifts = x_shifts or {}
    fig = go.Figure()

    for i, (name, spectrum) in enumerate(spectra_dict.items()):
        color = PLOT_COLORS[i % len(PLOT_COLORS)]

        local_processing_kwargs = dict(processing_kwargs)
        local_processing_kwargs["x_shift"] = x_shifts.get(name, 0.0)

        result = process_spectrum(
            spectrum["x"],
            spectrum["y"],
             **local_processing_kwargs,
        )

        all_x.extend(result["x"])

        y = np.asarray(result["smoothed"], dtype=float)
        ymax = np.max(y) if y.size > 0 else 1.0
        y_norm = y / ymax if ymax != 0 else y
        y_stack = y_norm + i * step

        fig.add_trace(
            go.Scatter(
                x=result["x"],
                y=y_stack,
                mode="lines",
                name=_shorten_name(name),
                customdata=[name] * len(result["x"]),
                hovertemplate=(
                    f"<span style='color:{color}'><b>%{{customdata}}</b></span><br>"
                    "x: %{x:.1f}<br>y: %{y:.1f}<extra></extra>"
                ),
                legendgroup=name,
                line=dict(width=2, color=color),
            )
        )

        if show_peaks and len(result["peaks"]["x"]) > 0:
            peak_x = result["peaks"]["x"]
            peak_y_raw = result["peaks"]["y"]
            peak_y = peak_y_raw / ymax + i * step if ymax != 0 else peak_y_raw + i * step

            peak_result_stacked = {
                "x": peak_x,
                "y": peak_y,
            }

            _add_peak_annotations(
                fig,
                peak_result_stacked,
                marker_color=color,
                marker_size=6,
                legendgroup=name,
                trace_name="Peak",
                showlegend=False,
            )

    fig.update_layout(
        title=title,
        height=800,
        xaxis_title=x_label,
        yaxis_title=y_label,
    )

    fig.update_yaxes(showticklabels=False)
    
    _expand_xaxis(fig, all_x)
    return _axis_style(fig)