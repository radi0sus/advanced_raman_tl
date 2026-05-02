from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import streamlit as st

from utils.labram_parser import load
from utils.processing import process_spectrum
from utils.figures import (
    create_single_view_figure,
    create_overlay_figure,
)

from utils.multi_plot_tab import (
    render_normalized_overlay_tab,
    render_stacked_spectra_tab,
)

from utils.export_tab import render_export_tab
from utils.elabftw_tab import render_elabftw_single_upload_section

try:
    from utils.figures import make_spectrum_title
except ImportError:
    def make_spectrum_title(spectrum_dict):
        return spectrum_dict.get("filename") or "Spectrum"


st.set_page_config(
    page_title="Advanced Raman Tool",
    layout="wide",
)

st.markdown(
    """
    <style>
    .github-corner-link {
        position: fixed;
        left: 60%;
        transform: translateX(-50%);
        bottom: 12px;
        z-index: 9999;
        font-size: 0.82rem;
        color: #64748b;
        opacity: 0.8;
    }

    .github-corner-link a {
        color: #2563eb;
        text-decoration: none;
    }

    .github-corner-link a:hover {
        text-decoration: underline;
    }
    </style>

    <div class="github-corner-link">
        <a href="https://github.com/radi0sus/advanced_raman_tl" target="_blank">
            Advanced Raman Tool · GitHub ↗
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)


def init_session_state():
    if "spectra" not in st.session_state:
        st.session_state.spectra = {}

    if "uploaded_file_keys" not in st.session_state:
        st.session_state.uploaded_file_keys = set()

    if "file_key_to_name" not in st.session_state:
        st.session_state.file_key_to_name = {}

    if "intensity_scales" not in st.session_state:
        st.session_state.intensity_scales = {}

    if "x_shifts" not in st.session_state:
        st.session_state.x_shifts = {}

    # Bytes separat vom spectra-Dict, damit der Session State klein bleibt
    if "original_bytes_cache" not in st.session_state:
        st.session_state.original_bytes_cache = {}

    if "single_export_zip_bytes" not in st.session_state:
        st.session_state.single_export_zip_bytes = None

    if "single_export_zip_name" not in st.session_state:
        st.session_state.single_export_zip_name = None

    if "multi_export_zip_bytes" not in st.session_state:
        st.session_state.multi_export_zip_bytes = None

    if "multi_export_zip_name" not in st.session_state:
        st.session_state.multi_export_zip_name = None

    if "session_export_zip_bytes" not in st.session_state:
        st.session_state.session_export_zip_bytes = None

    if "session_export_zip_name" not in st.session_state:
        st.session_state.session_export_zip_name = None

    if "single_export_signature" not in st.session_state:
        st.session_state.single_export_signature = None

    if "multi_export_signature" not in st.session_state:
        st.session_state.multi_export_signature = None

    if "session_export_signature" not in st.session_state:
        st.session_state.session_export_signature = None

    if "stack_step" not in st.session_state:
        st.session_state.stack_step = 1.2


def make_file_key(uploaded_file) -> str:
    data = uploaded_file.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    return f"{uploaded_file.name}:{digest}"


def parse_uploaded_file(uploaded_file) -> dict:
    suffix = Path(uploaded_file.name).suffix.lower()
    original_bytes = uploaded_file.getvalue()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = Path(tmp.name)

    try:
        sp = load(tmp_path)
        result = {
            "filename": uploaded_file.name,
            "name": uploaded_file.name,
            "is_blc": sp.is_blc,
            "x": list(sp.wavenumbers),
            "y": list(sp.intensities),
            "y_raw": list(sp.intensities_raw) if sp.intensities_raw is not None else None,
            "metadata": dict(sp.metadata),
            "history": list(sp.history),
            # original_bytes wird NICHT hier gespeichert, sondern separat in
            # original_bytes_cache, damit der Session State klein bleibt.
        }
        # Bytes direkt in den separaten Cache schreiben
        st.session_state.original_bytes_cache[uploaded_file.name] = original_bytes
        return result
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def sync_uploaded_files(uploaded_files):
    current_files = uploaded_files or []
    current_map = {make_file_key(f): f for f in current_files}
    current_keys = set(current_map.keys())

    had_changes = False

    # Dateien entfernen, die nicht mehr im Uploader sind
    removed_keys = st.session_state.uploaded_file_keys - current_keys
    for file_key in removed_keys:
        filename = st.session_state.file_key_to_name.pop(file_key, None)
        if filename is not None:
            st.session_state.spectra.pop(filename, None)
            st.session_state.intensity_scales.pop(filename, None)
            st.session_state.x_shifts.pop(filename, None)
            st.session_state.original_bytes_cache.pop(filename, None)
            st.session_state.pop(f"intensity_scale_{filename}", None)
            st.session_state.pop(f"x_shift_{filename}", None)
            had_changes = True

    # Neue Dateien hinzufügen
    for file_key, uploaded_file in current_map.items():
        if file_key in st.session_state.uploaded_file_keys:
            continue

        try:
            sp = parse_uploaded_file(uploaded_file)
            st.session_state.spectra[sp["filename"]] = sp
            st.session_state.file_key_to_name[file_key] = sp["filename"]
            had_changes = True
        except Exception as exc:
            st.sidebar.error(f"Failed to parse {uploaded_file.name}: {exc}")

    # Synchronisierten Stand speichern
    st.session_state.uploaded_file_keys = current_keys

    # Exportzustände invalidieren, wenn sich Uploads geändert haben
    if had_changes:
        st.session_state.single_export_zip_bytes = None
        st.session_state.single_export_zip_name = None

        st.session_state.multi_export_zip_bytes = None
        st.session_state.multi_export_zip_name = None

        st.session_state.session_export_zip_bytes = None
        st.session_state.session_export_zip_name = None

        st.session_state.session_export_signature = None
        st.session_state.single_export_signature = None
        st.session_state.multi_export_signature = None

    # reset wn slider
    if not st.session_state.spectra:
        st.session_state.pop("wn_range", None)
        st.session_state.pop("stack_step", None)


def build_processing_kwargs():
    with st.sidebar.expander("Processing settings", expanded=False):
        with st.container(border=True):
            st.markdown("#### Baseline")

            baseline_method = st.radio(
                "Method",
                ["arpls", "snip"],
                format_func=lambda x: "arPLS" if x == "arpls" else "SNIP",
                #help="Choose the baseline correction method applied before smoothing and peak detection.",
            )

            if baseline_method == "arpls":
                baseline_value = st.slider(
                    "arPLS lambda",
                    min_value=100,
                    max_value=10000,
                    value=1000,
                    step=100,
                    help="Smoothness parameter for arPLS baseline correction. Higher values usually produce a smoother baseline.",
                )
                baseline_params = {
                    "lam": float(baseline_value),
                    "ratio": 1e-6,
                    "max_iter": 200,
                }
            else:
                baseline_value = st.slider(
                    "SNIP iterations",
                    min_value=10,
                    max_value=200,
                    value=60,
                    step=1,
                    help="Number of iterations used by the SNIP baseline algorithm.",
                )
                baseline_params = {
                    "iterations": int(baseline_value),
                }

        with st.container(border=True):
            st.markdown("#### Smoothing")
            smoothing_method = st.radio(
                "Method",
                ["whittaker", "savgol"],
                format_func=lambda x: "Whittaker" if x == "whittaker" else "Savitzky-Golay",
                #help="Choose the smoothing method applied after baseline correction.",
            )

            if smoothing_method == "whittaker":
                smoothing_lambda = st.slider(
                    "Whittaker lambda",
                    min_value=0.1,
                    max_value=50.0,
                    value=1.0,
                    step=0.1,
                    help="Smoothness parameter for Whittaker smoothing. Higher values usually increase smoothing.",
                )
                smoothing_params = {"lam": float(smoothing_lambda), "d": 2}
            else:
                savgol_window = st.slider(
                    "Savitzky-Golay window",
                    min_value=3,
                    max_value=51,
                    value=5,
                    step=2,
                    help="Window length for Savitzky-Golay smoothing. Must be an odd number.",
                )
                savgol_polyorder = st.slider(
                    "Savitzky-Golay polyorder",
                    min_value=1,
                    max_value=7,
                    value=3,
                    step=1,
                    help="Polynomial order used for Savitzky-Golay smoothing.",
                )
                smoothing_params = {
                    "window_length": int(savgol_window),
                    "polyorder": int(savgol_polyorder),
                }

        with st.container(border=True):
            st.markdown("#### Peaks")
            prominence_mode = st.radio(
                "Prominence mode",
                ["auto", "manual"],
                horizontal=True,
                #help="Use automatic peak prominence estimation or define a fixed manual prominence threshold.",
            )

            if prominence_mode == "manual":
                peak_prominence = st.slider(
                    "Prominence",
                    min_value=0.0,
                    max_value=200.0,
                    value=10.0,
                    step=1.0,
                    help="Minimum prominence required for a peak to be detected in manual mode.",
                )
            else:
                peak_prominence = None

            peak_prominence_factor = st.slider(
                "Auto prominence factor",
                min_value=0.001,
                max_value=0.2,
                value=0.05,
                step=0.001,
                help="Scaling factor used to estimate peak prominence automatically from the processed spectrum.",
            )

            peak_width = st.slider(
                "Min width (cm⁻¹)",
                min_value=0.0,
                max_value=50.0,
                value=2.0,
                step=0.5,
                help="Minimum peak width required for detected peaks.",
            )

            peak_distance = st.slider(
                "Min distance (cm⁻¹)",
                min_value=0.0,
                max_value=100.0,
                value=8.0,
                step=1.0,
                help="Minimum distance between detected peaks.",
            )

    return {
        "xmin": float(xmin),
        "xmax": float(xmax),
        "baseline_method": baseline_method,
        "baseline_params": baseline_params,
        "smoothing_method": smoothing_method,
        "smoothing_params": smoothing_params,
        "peak_prominence": peak_prominence,
        "peak_prominence_factor": float(peak_prominence_factor),
        "peak_width": float(peak_width) if peak_width > 0 else None,
        "peak_distance": float(peak_distance) if peak_distance > 0 else None,
        "peak_height": None,
        "peak_rel_height": 0.5,
    }


def _meta_text(metadata: dict, key: str) -> str | None:
    entry = metadata.get(key)
    if not isinstance(entry, dict):
        return None

    value = entry.get("value")
    unit = entry.get("unit", "")

    if value in (None, ""):
        return None

    return f"{value} {unit}".strip()


def show_metadata(spectrum: dict):
    metadata = spectrum.get("metadata", {})
    x = spectrum.get("x", [])

    lines = [
        f"<b>File:</b> {spectrum.get('filename', '')}",
        f"<b>Points:</b> {len(x)}",
    ]

    if x:
        lines.append(f"<b>Range:</b> {x[0]:.1f} – {x[-1]:.1f} cm⁻¹")

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
            lines.append(f"<b>{label}:</b> {value}")

    st.markdown(
        f"<div style='font-size: 0.95rem; line-height: 1.5;'>{'<br>'.join(lines)}</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='font-size: 0.95rem; line-height: 1.5;'>&nbsp</div>",
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def cached_process_spectrum(x_tuple, y_tuple, kwargs_json):
    kwargs = json.loads(kwargs_json)
    return process_spectrum(list(x_tuple), list(y_tuple), **kwargs)


def run_processed(x, y, kwargs):
    return cached_process_spectrum(
        tuple(x),
        tuple(y),
        json.dumps(kwargs, sort_keys=True),
    )


def _spectra_to_hashable(spectra_dict: dict) -> tuple:
    def _val_to_hashable(v):
        if isinstance(v, list):
            return tuple(v)
        if isinstance(v, dict):
            return tuple(sorted((k, _val_to_hashable(w)) for k, w in v.items()))
        return v

    return tuple(
        (
            name,
            tuple(sorted(
                (k, _val_to_hashable(v))
                for k, v in sp.items()
            )),
        )
        for name, sp in sorted(spectra_dict.items())
    )


def _hashable_to_spectra(spectra_hashable: tuple) -> dict:
    def _val_from_hashable(v):
        if isinstance(v, tuple) and v and isinstance(v[0], tuple) and len(v[0]) == 2:
            try:
                return {k: _val_from_hashable(w) for k, w in v}
            except (TypeError, ValueError):
                return list(v)
        if isinstance(v, tuple):
            return list(v)
        return v

    result = {}
    for name, fields in spectra_hashable:
        result[name] = {k: _val_from_hashable(v) for k, v in fields}
    return result


@st.cache_data(show_spinner=False)
def cached_overlay_figure(spectra_hashable, kwargs_json, intensity_scales_json, x_shifts_json, title, show_peaks):
    return create_overlay_figure(
        _hashable_to_spectra(spectra_hashable),
        processing_kwargs=json.loads(kwargs_json),
        intensity_scales=json.loads(intensity_scales_json),
        x_shifts=json.loads(x_shifts_json),
        title=title,
        show_peaks=show_peaks,
    )


init_session_state()

st.title(":blue[Advanced Raman Tool]")

uploaded_files = st.sidebar.file_uploader(
    "Upload Raman spectra",
    type=["txt", "xml", "l6s"],
    accept_multiple_files=True,
    help=(
        "Upload one or more Raman spectra in TXT, XML, or L6S format. "
        "TXT files should contain two columns without header: wavenumber and intensity. "
        "Files containing more than one spectrum are currently not supported."
    ),
)

sync_uploaded_files(uploaded_files)

spectra = st.session_state.spectra

if not spectra:
    st.info(
        """
        Upload one or more spectra to begin.

        **Supported formats**
        - **TXT**: plain text, no header, two columns (`wavenumber intensity`)
        - **XML**: HORIBA LabSpec XML
        - **L6S**: HORIBA LabSpec L6S

        Files containing more than one spectrum are currently not supported.
        """
    )
    
    st.divider()
    
    col_left, col_center, col_right = st.columns([1, 4, 1])
    with col_center:
        st.video(
            "https://raw.githubusercontent.com/radi0sus/media/main/advanced_raman_tl/demo_d.mp4",
            format="video/mp4",
            autoplay=False,
            muted=True,
            loop=True,
        )
    
    st.stop()

with st.sidebar.expander("Spectrum selection", expanded=True):
    spectrum_names = list(spectra.keys())

    selected_spectrum_name = st.selectbox(
        "Active spectrum",
        options=spectrum_names,
        help=(
            "Select the spectrum used for the single view, manual spectrum adjustments, "
            "metadata display, single-spectrum export, and single-spectrum upload."
        ),
    )

    st.session_state.selected_spectrum_name = selected_spectrum_name

    selected_overlay_names = st.multiselect(
        "Overlay spectra",
        options=spectrum_names,
        default=spectrum_names,
        help=(
            "Select one or more spectra for overlay, normalized overlay, stacked view, "
            "multi-spectrum export, and multi-spectrum upload."
        ),
    )

    st.session_state.selected_overlay_names = selected_overlay_names

with st.sidebar.expander("Display options", expanded=False):
    show_peaks = st.checkbox(
        "Show peaks (single spectrum)",
        value=True,
        key="single_show_peaks",
        #help="Display detected peak positions in the single-spectrum view.",
    )
    show_multi_peaks = st.checkbox(
        "Show peaks (overlay & stacked)",
        value=True,
        key="multi_show_peaks",
        # help="Display detected peak positions in overlay, normalized overlay, and stacked views.",
    )

    xmin, xmax = st.slider(
        "wn range (cm⁻¹)",
        min_value=0,
        max_value=4000,
        value=(100, 3200),
        step=1,
        key="wn_range",
        help=(
            "Restrict the processed spectral range used for visualization, baseline correction, "
            "smoothing, and peak detection."
        ),
    )

    st.slider(
        "Stack spacing",
        min_value=0.0,
        max_value=2.0,
        step=0.01,
        key="stack_step",
        help="Vertical offset between normalized spectra in the stacked view.",
    )

processing_kwargs = build_processing_kwargs()
st.session_state.processing_kwargs = processing_kwargs

with st.sidebar.expander("Manual spectrum adjustments", expanded=False):
    st.warning("⚠️ Significant data manipulation is possible.")
    st.caption(
        "These adjustments are intended for visual comparison and manual alignment of spectra."
    )

    slider_key = f"intensity_scale_{selected_spectrum_name}"
    if slider_key not in st.session_state:
        st.session_state[slider_key] = float(
            st.session_state.intensity_scales.get(selected_spectrum_name, 1.0)
        )

    active_intensity_scale = st.slider(
        "Intensity scale (active spectrum):",
        min_value=0.1,
        max_value=20.0,
        step=0.1,
        key=slider_key,
        help="Multiply the intensity of the active spectrum for visual comparison and relevant exports.",
    )
    st.session_state.intensity_scales[selected_spectrum_name] = float(active_intensity_scale)

    shift_key = f"x_shift_{selected_spectrum_name}"
    if shift_key not in st.session_state:
        st.session_state[shift_key] = float(
            st.session_state.x_shifts.get(selected_spectrum_name, 0.0)
        )

    active_x_shift = st.slider(
        "Spectrum shift (active spectrum):",
        min_value=-50.0,
        max_value=50.0,
        step=0.1,
        key=shift_key,
        help="Apply a horizontal shift in cm⁻¹ to the active spectrum for manual spectral alignment.",
    )
    st.session_state.x_shifts[selected_spectrum_name] = float(active_x_shift)

active_spectrum = spectra.get(selected_spectrum_name)
if active_spectrum is None:
    st.stop()

with st.sidebar.expander("Spectrum Info", expanded=False):
    show_metadata(active_spectrum)

tabs = st.tabs(["Single View", "Overlay Spectra", "Normalized Overlay", "Stacked Spectra", "Export", "eLabFTW"])

with tabs[0]:
    st.caption(
        "Display the processed active spectrum with baseline, smoothing, and peak annotations."
    )
    try:
        single_processing_kwargs = dict(processing_kwargs)
        single_processing_kwargs["intensity_scale"] = st.session_state.intensity_scales.get(
            selected_spectrum_name,
            1.0,
        )

        single_processing_kwargs["x_shift"] = st.session_state.x_shifts.get(
            selected_spectrum_name,
            0.0,
        )

        result = run_processed(
            active_spectrum["x"],
            active_spectrum["y"],
            single_processing_kwargs,
        )

        fig = create_single_view_figure(
            result,
            show_peaks=show_peaks,
            title=make_spectrum_title(active_spectrum),
        )
        st.plotly_chart(fig, width="stretch")
    except Exception as exc:
        st.error(f"Processing error: {exc}")
        
    st.caption(
        "Click legend entries to show or hide individual spectra."
    )

with tabs[1]:
    st.caption(
        "Display the selected processed spectra in a shared overlay for direct comparison of absolute intensities and peak positions."
    )
    try:
        selected_spectra = {
            name: spectra[name]
            for name in selected_overlay_names
            if name in spectra
        }

        if not selected_spectra:
            st.warning("Please select at least one spectrum for overlay.")
        else:
            fig = cached_overlay_figure(
                _spectra_to_hashable(selected_spectra),
                json.dumps(processing_kwargs, sort_keys=True),
                json.dumps(dict(sorted(st.session_state.intensity_scales.items()))),
                json.dumps(dict(sorted(st.session_state.x_shifts.items()))),
                "Overlay",
                show_multi_peaks,
            )
            st.plotly_chart(fig, width="stretch")
    except Exception as exc:
        st.error(f"Overlay error: {exc}")
    
    st.caption(
        "Click legend entries to show or hide individual spectra."
    )    

with tabs[2]:
    st.caption(
        "Display the selected spectra after normalization for comparison of relative spectral features."
    )
    render_normalized_overlay_tab(
        spectra=spectra,
        selected_overlay_names=selected_overlay_names,
        processing_kwargs=processing_kwargs,
        show_multi_peaks=show_multi_peaks,
    )
    
    st.caption(
        "Click legend entries to show or hide individual spectra."
    )
    
with tabs[3]:
    st.caption(
        """
        Display the selected normalized spectra with adjustable vertical spacing 
        (Display options) for clearer comparison of overlapping features.
        """
    )
    render_stacked_spectra_tab(
        spectra=spectra,
        selected_overlay_names=selected_overlay_names,
        processing_kwargs=processing_kwargs,
        show_multi_peaks=show_multi_peaks,
    )

    st.caption(
        "Click legend entries to show or hide individual spectra."
        )

with tabs[4]:
    render_export_tab(
        spectra=spectra,
        active_spectrum=active_spectrum,
        selected_spectrum_name=selected_spectrum_name,
        selected_overlay_names=selected_overlay_names,
        processing_kwargs=processing_kwargs,
        show_peaks=show_peaks,
        show_multi_peaks=show_multi_peaks,
    )

with tabs[5]:
    render_elabftw_single_upload_section()