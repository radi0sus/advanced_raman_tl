from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import streamlit as st

from utils.labram_parser import load
from utils.processing import process_spectrum
from utils.figures import (
    create_single_view_figure,
    create_overlay_figure,
    create_normalized_overlay_figure,
    create_stacked_figure,
)

from utils.export import (
    build_single_spectrum_csv_bytes,
    build_multi_spectra_csv_bytes,
    build_spectrum_metadata_txt_bytes,
    build_figure_html_bytes,
    build_summary_html_bytes,
    build_zip_bytes,
)

try:
    from utils.figures import make_spectrum_title
except ImportError:
    def make_spectrum_title(spectrum_dict):
        return spectrum_dict.get("filename") or "Spectrum"


st.set_page_config(
    page_title="Raman Analysis",
    layout="wide",
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

def make_file_key(uploaded_file) -> str:
    data = uploaded_file.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    return f"{uploaded_file.name}:{digest}"


def parse_uploaded_file(uploaded_file) -> dict:
    suffix = Path(uploaded_file.name).suffix.lower()
    original_bytes = uploaded_file.getvalue()  # NEU

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = Path(tmp.name)

    try:
        sp = load(tmp_path)
        return {
            "filename": uploaded_file.name,
            "name": uploaded_file.name,
            "is_blc": sp.is_blc,
            "x": list(sp.wavenumbers),
            "y": list(sp.intensities),
            "y_raw": list(sp.intensities_raw) if sp.intensities_raw is not None else None,
            "metadata": dict(sp.metadata),
            "history": list(sp.history),
            "original_bytes": original_bytes,  # NEU
        }
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

def sync_uploaded_files(uploaded_files):
    current_files = uploaded_files or []
    current_map = {make_file_key(f): f for f in current_files}
    current_keys = set(current_map.keys())

    # Dateien entfernen, die nicht mehr im Uploader sind
    removed_keys = st.session_state.uploaded_file_keys - current_keys
    for file_key in removed_keys:
        filename = st.session_state.file_key_to_name.pop(file_key, None)
        if filename is not None:
            st.session_state.spectra.pop(filename, None)
            st.session_state.intensity_scales.pop(filename, None)
            st.session_state.x_shifts.pop(filename, None)
            st.session_state.pop(f"intensity_scale_{filename}", None)
            st.session_state.pop(f"x_shift_{filename}", None)

    # Neue Dateien hinzufügen
    for file_key, uploaded_file in current_map.items():
        if file_key in st.session_state.uploaded_file_keys:
            continue

        try:
            sp = parse_uploaded_file(uploaded_file)
            st.session_state.spectra[sp["filename"]] = sp
            st.session_state.file_key_to_name[file_key] = sp["filename"]
        except Exception as exc:
            st.sidebar.error(f"Failed to parse {uploaded_file.name}: {exc}")

    # Synchronisierten Stand speichern
    st.session_state.uploaded_file_keys = current_keys
    
    # reset wn slider
    if not st.session_state.spectra:
        st.session_state.pop("wn_range", None)


def build_processing_kwargs():

    with st.sidebar.expander("Processing settings", expanded=False):
        with st.container(border=True):
            st.markdown("#### Baseline")
    
            baseline_method = st.radio(
                "Method",
                ["arpls", "snip"],
                format_func=lambda x: "arPLS" if x == "arpls" else "SNIP",
            )
    
            if baseline_method == "arpls":
                baseline_value = st.slider(
                    "arPLS lambda",
                    min_value=100,
                    max_value=10000,
                    value=1000,
                    step=100,
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
                )
                baseline_params = {
                    "iterations": int(baseline_value),
                }

        #st.divider()
        with st.container(border=True):
            st.markdown("#### Smoothing")
            smoothing_method = st.radio(
                "Method",
                ["whittaker", "savgol"],
                format_func=lambda x: "Whittaker" if x == "whittaker" else "Savitzky-Golay",
            )
    
            if smoothing_method == "whittaker":
                smoothing_lambda = st.slider(
                    "Whittaker lambda",
                    min_value=0.1,
                    max_value=50.0,
                    value=1.0,
                    step=0.1,
                )
                smoothing_params = {"lam": float(smoothing_lambda), "d": 2}
            else:
                savgol_window = st.slider(
                    "Savitzky-Golay window",
                    min_value=3,
                    max_value=51,
                    value=5,
                    step=2,
                )
                savgol_polyorder = st.slider(
                    "Savitzky-Golay polyorder",
                    min_value=1,
                    max_value=7,
                    value=3,
                    step=1,
                )
                smoothing_params = {
                    "window_length": int(savgol_window),
                    "polyorder": int(savgol_polyorder),
                }

        #st.divider()
        
        with st.container(border=True):
            st.markdown("#### Peaks")
            prominence_mode = st.radio(
                "Prominence mode",
                ["auto", "manual"],
                horizontal=True,
            )
    
            if prominence_mode == "manual":
                peak_prominence = st.slider(
                    "Prominence",
                    min_value=0.0,
                    max_value=200.0,
                    value=10.0,
                    step=1.0,
                )
            else:
                peak_prominence = None
    
            peak_prominence_factor = st.slider(
                "Auto prominence factor",
                min_value=0.001,
                max_value=0.2,
                value=0.05,
                step=0.001,
            )
    
            peak_width = st.slider(
                "Min width (cm⁻¹)",
                min_value=0.0,
                max_value=50.0,
                value=2.0,
                step=0.5,
            )
    
            peak_distance = st.slider(
                "Min distance (cm⁻¹)",
                min_value=0.0,
                max_value=100.0,
                value=8.0,
                step=1.0,
            )
    
        #st.divider()
        
#        with st.container(border=True):
#            st.markdown("#### Range")
#    
#            xmin, xmax = st.slider(
#                "X range",
#                min_value=0,
#                max_value=4000,
#                value=(100, 3200),
#                step=1,
#            )

    return {
        "xmin": float(xmin),
        "xmax": float(xmax),
        #"x_shift": float(spectrum_shift),
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
        "Laser Wavelength (nm)": "Laser",
        "Acq. time (s)": "Acq. time",
        "Accumulations": "Accum.",
        "Grating": "Grating",
        "Filter": "Filter",
        "Instrument Name": "Instrument",
        "Detector Name": "Detector",
        "Spectrum Name": "Name",
        "Acquired": "Acquired",
    }

    for key, label in key_map.items():
        value = metadata.get(key)
        if value not in (None, ""):
            lines.append(f"<b>{label}:</b> {value}")

    st.markdown(
        f"<div style='font-size: 0.95rem; line-height: 1.5;'>{'<br>'.join(lines)}</div>",
        unsafe_allow_html=True,
    )
    
    st.markdown(f"<div style='font-size: 0.95rem; line-height: 1.5;'>&nbsp</div>",unsafe_allow_html=True,)

init_session_state()

st.title("Raman Analysis")

uploaded_files = st.sidebar.file_uploader(
    "Upload Raman spectra",
    type=["txt", "xml", "l6s"],
    accept_multiple_files=True,
)

sync_uploaded_files(uploaded_files)

spectra = st.session_state.spectra

if not spectra:
    st.info("Upload one or more spectra to begin.")
    st.stop()

with st.sidebar.expander("Spectrum selection", expanded=True):
    spectrum_names = list(spectra.keys())

    selected_spectrum_name = st.selectbox(
        "Active spectrum",
        options=spectrum_names,
    )
    
    #st.markdown(f"**Active spectrum:** {selected_spectrum_name}")
    
    selected_overlay_names = st.multiselect(
        "Overlay spectra",
        options=spectrum_names,
        default=spectrum_names,
    )
    
    slider_key = f"intensity_scale_{selected_spectrum_name}"

    if slider_key not in st.session_state:
        st.session_state[slider_key] = float(
            st.session_state.intensity_scales.get(selected_spectrum_name, 1.0)
        )
        
    with st.container(border=True):    
    
        st.markdown(
            f"""
            <span style='font-size: 0.9rem; line-height: 1.5; font-weight: 500; 
            color: red'>
            ⚠️ Significant data manipulation possible!
            </span>""", 
            unsafe_allow_html=True,
        )
        
        st.markdown(
            f"""
            <div style='font-size: 0.6rem; border-radius: 6px; color: red; 
            font-weight: 500; 
            background-color: None;'>{selected_spectrum_name}<br><br></div>
            """,
            unsafe_allow_html=True,
        )

        active_intensity_scale = st.slider(
            f"Intensity scale (active spectrum):",
            min_value=0.1,
            max_value=20.0,
            step=0.1,
            key=slider_key,
        )
       
        st.session_state.intensity_scales[selected_spectrum_name] = float(active_intensity_scale)    
        
        shift_key = f"x_shift_{selected_spectrum_name}"
        
        if shift_key not in st.session_state:
            st.session_state[shift_key] = float(
                st.session_state.x_shifts.get(selected_spectrum_name, 0.0)
            )
        
        active_x_shift = st.slider(
            f"Spectrum shift (active spectrum):",
            min_value=-50.0,
            max_value=50.0,
            step=0.1,
            key=shift_key,
        )
           
        st.session_state.x_shifts[selected_spectrum_name] = float(active_x_shift)    
    
with st.sidebar.expander("Display options", expanded=False):
    show_peaks = st.checkbox("Show peaks (single spectrum)", value=True, key="single_show_peaks")
    show_multi_peaks = st.checkbox("Show peaks (overlay & stacked)", value=True, key="multi_show_peaks")
    xmin, xmax = st.slider(
                    "wn range (cm⁻¹)",
                    min_value=0,
                    max_value=4000,
                    value=(100, 3200),
                    step=1,
                    key="wn_range",
                )

processing_kwargs = build_processing_kwargs()

active_spectrum = spectra.get(selected_spectrum_name)
if active_spectrum is None:
    st.stop()
    
with st.sidebar.expander("Spectrum Info", expanded=False):
    show_metadata(active_spectrum)

tabs = st.tabs(["Single View", "Overlay Spectra", "Normalized Overlay", "Stacked Spectra", "Export"])

with tabs[0]:
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
        
        result = process_spectrum(
            active_spectrum["x"],
            active_spectrum["y"],
            **single_processing_kwargs,
        )
        
        fig = create_single_view_figure(
            result,
            show_peaks=show_peaks,
            title=make_spectrum_title(active_spectrum),
        )
        st.plotly_chart(fig, width="stretch")
    except Exception as exc:
        st.error(f"Processing error: {exc}")

with tabs[1]:
    try:
        selected_spectra = {
            name: spectra[name]
            for name in selected_overlay_names
            if name in spectra
        }

        if not selected_spectra:
            st.warning("Please select at least one spectrum for overlay.")
        else:
            fig = create_overlay_figure(
                selected_spectra,
                processing_kwargs=processing_kwargs,
                intensity_scales=st.session_state.intensity_scales,
                x_shifts=st.session_state.x_shifts,
                title="Overlay",
                show_peaks=show_multi_peaks,
            )
            st.plotly_chart(fig, width="stretch")
    except Exception as exc:
        st.error(f"Overlay error: {exc}")

with tabs[2]:
    try:
        selected_spectra = {
            name: spectra[name]
            for name in selected_overlay_names
            if name in spectra
        }

        if not selected_spectra:
            st.warning("Please select at least one spectrum for normalized overlay.")
        else:
            fig = create_normalized_overlay_figure(
                selected_spectra,
                processing_kwargs=processing_kwargs,
                x_shifts=st.session_state.x_shifts,
                title="Normalized Overlay",
                show_peaks=show_multi_peaks,
            )
            st.plotly_chart(fig, width="stretch")
    except Exception as exc:
        st.error(f"Normalized overlay error: {exc}")

with tabs[3]:
    try:
        selected_spectra = {
            name: spectra[name]
            for name in selected_overlay_names
            if name in spectra
        }

        if not selected_spectra:
            st.warning("Please select at least one spectrum for stacked view.")
        else:
            stack_step = st.slider(
                "Stack spacing",
                min_value=0.0,
                max_value=2.0,
                value=1.2,
                step=0.001,
                key="stack_step",
            )

            fig = create_stacked_figure(
                selected_spectra,
                processing_kwargs=processing_kwargs,
                x_shifts=st.session_state.x_shifts,
                title="Stacked Spectra",
                show_peaks=show_multi_peaks,
                step=stack_step,
            )
            st.plotly_chart(fig, width="stretch")
    except Exception as exc:
        st.error(f"Stacked figure error: {exc}")

with tabs[4]:
    st.markdown("### Export active spectrum")

    include_csv = st.checkbox("Include processed (CSV)", value=True, key="single_include_csv")
    include_metadata = st.checkbox("Include metadata (TXT)", value=True, key="single_include_metadata")
    include_full_figure = st.checkbox("Include figure (HTML)", value=True, key="single_include_figure")
    include_original_file = st.checkbox(
        "Include original file (L6S / XML / TXT)",
        value=True,
        key="single_include_original",
    )

    if (
        st.session_state.single_export_zip_bytes is None
        or st.session_state.single_export_zip_name is None
    ):
        if st.button("Create export package", key="create_single_export"):
            try:
                export_processing_kwargs = dict(processing_kwargs)
                export_processing_kwargs["intensity_scale"] = st.session_state.intensity_scales.get(
                    selected_spectrum_name,
                    1.0,
                )
                export_processing_kwargs["x_shift"] = st.session_state.x_shifts.get(
                    selected_spectrum_name,
                    0.0,
                )

                export_result = process_spectrum(
                    active_spectrum["x"],
                    active_spectrum["y"],
                    **export_processing_kwargs,
                )

                filename_base = Path(active_spectrum.get("filename", "spectrum")).stem
                files = {}

                if include_csv:
                    files[f"{filename_base}_processed.csv"] = build_single_spectrum_csv_bytes(
                        export_result,
                        x_shift=st.session_state.x_shifts.get(selected_spectrum_name, 0.0),
                        intensity_scale=st.session_state.intensity_scales.get(selected_spectrum_name, 1.0),
                    )

                if include_metadata:
                    files[f"{filename_base}_metadata.txt"] = build_spectrum_metadata_txt_bytes(
                        active_spectrum,
                        processing_kwargs=processing_kwargs,
                        x_shift=st.session_state.x_shifts.get(selected_spectrum_name, 0.0),
                        intensity_scale=st.session_state.intensity_scales.get(selected_spectrum_name, 1.0),
                    )

                if include_full_figure:
                    full_fig = create_single_view_figure(
                        export_result,
                        show_peaks=show_peaks,
                        title=make_spectrum_title(active_spectrum),
                        show_raw=True,
                        show_baseline=True,
                        show_corrected=True,
                        show_smoothed=True,
                    )
                    files[f"{filename_base}_figure_full.html"] = build_figure_html_bytes(full_fig)

                if include_original_file:
                    orig_bytes = active_spectrum.get("original_bytes")
                    if orig_bytes:
                        files[active_spectrum["filename"]] = orig_bytes

                if not files:
                    st.warning("Please select at least one export item.")
                else:
                    st.session_state.single_export_zip_bytes = build_zip_bytes(files)
                    st.session_state.single_export_zip_name = f"{filename_base}_export.zip"
                    st.success("Single spectrum export package created.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Export error: {exc}")
    else:
        st.success("Export package ready for download.")
        st.download_button(
            label=f"⬇ Download {st.session_state.single_export_zip_name}",
            data=st.session_state.single_export_zip_bytes,
            file_name=st.session_state.single_export_zip_name,
            mime="application/zip",
            key="download_single_export",
        )

    st.markdown("### Export selected multi-spectra views")

    include_overlay_html = st.checkbox("Include overlay plot (HTML)", value=True, key="multi_include_overlay_html")
    include_normalized_html = st.checkbox(
        "Include normalized overlay plot (HTML)",
        value=True,
        key="multi_include_normalized_html",
    )
    include_stacked_html = st.checkbox("Include stacked plot (HTML)", value=True, key="multi_include_stacked_html")
    include_overlay_csv = st.checkbox(
        "Include overlay CSV (shared shifted x-axis, visible smoothed spectra)",
        value=True,
        key="multi_include_overlay_csv",
    )

    if (
        st.session_state.multi_export_zip_bytes is None
        or st.session_state.multi_export_zip_name is None
    ):
        if st.button("Create multi-spectra export package", key="create_multi_export"):
            try:
                selected_spectra = {
                    name: spectra[name]
                    for name in selected_overlay_names
                    if name in spectra
                }

                if not selected_spectra:
                    st.warning("Please select at least one spectrum for multi export.")
                else:
                    files = {}
                    processed_results = {}

                    for name, spectrum in selected_spectra.items():
                        local_processing_kwargs = dict(processing_kwargs)
                        local_processing_kwargs["intensity_scale"] = st.session_state.intensity_scales.get(name, 1.0)
                        local_processing_kwargs["x_shift"] = st.session_state.x_shifts.get(name, 0.0)

                        processed_results[name] = process_spectrum(
                            spectrum["x"],
                            spectrum["y"],
                            **local_processing_kwargs,
                        )

                    if include_overlay_html:
                        overlay_fig = create_overlay_figure(
                            selected_spectra,
                            processing_kwargs=processing_kwargs,
                            intensity_scales=st.session_state.intensity_scales,
                            x_shifts=st.session_state.x_shifts,
                            title="Overlay",
                            show_peaks=show_multi_peaks,
                        )
                        files["overlay/overlay_plot.html"] = build_figure_html_bytes(overlay_fig)

                    if include_normalized_html:
                        normalized_fig = create_normalized_overlay_figure(
                            selected_spectra,
                            processing_kwargs=processing_kwargs,
                            x_shifts=st.session_state.x_shifts,
                            title="Normalized Overlay",
                            show_peaks=show_multi_peaks,
                        )
                        files["overlay/normalized_overlay_plot.html"] = build_figure_html_bytes(normalized_fig)

                    if include_stacked_html:
                        stacked_fig = create_stacked_figure(
                            selected_spectra,
                            processing_kwargs=processing_kwargs,
                            x_shifts=st.session_state.x_shifts,
                            title="Stacked Spectra",
                            show_peaks=show_multi_peaks,
                            step=st.session_state.get("stack_step", 1.2),
                        )
                        files["overlay/stacked_plot.html"] = build_figure_html_bytes(stacked_fig)

                    if include_overlay_csv:
                        files["overlay/overlay_processed.csv"] = build_multi_spectra_csv_bytes(
                            processed_results
                        )

                    if not files:
                        st.warning("Please select at least one multi-spectra export item.")
                    else:
                        st.session_state.multi_export_zip_bytes = build_zip_bytes(files)
                        st.session_state.multi_export_zip_name = "multi_spectra_export.zip"
                        st.success("Multi-spectra export package created.")
                        st.rerun()
            except Exception as exc:
                st.error(f"Multi export error: {exc}")
    else:
        st.success("Multi-spectra export package ready for download.")
        st.download_button(
            label=f"⬇ Download {st.session_state.multi_export_zip_name}",
            data=st.session_state.multi_export_zip_bytes,
            file_name=st.session_state.multi_export_zip_name,
            mime="application/zip",
            key="download_multi_export",
        )

    st.markdown("### Export full session")

    include_session_original_files = st.checkbox(
        "Include original files in session export",
        value=True,
        key="session_include_original_files",
    )
    include_session_overlay_csv = st.checkbox(
        "Include overlay CSV in session export",
        value=True,
        key="session_include_overlay_csv",
    )

    if (
        st.session_state.session_export_zip_bytes is None
        or st.session_state.session_export_zip_name is None
    ):
        if st.button("Create session export package", key="create_session_export"):
            try:
                files = {}

                single_results = {}
                for name, spectrum in spectra.items():
                    local_processing_kwargs = dict(processing_kwargs)
                    local_processing_kwargs["intensity_scale"] = st.session_state.intensity_scales.get(name, 1.0)
                    local_processing_kwargs["x_shift"] = st.session_state.x_shifts.get(name, 0.0)

                    result = process_spectrum(
                        spectrum["x"],
                        spectrum["y"],
                        **local_processing_kwargs,
                    )
                    single_results[name] = result

                    filename_base = Path(spectrum.get("filename", name)).stem

                    files[f"{name}/{filename_base}_processed.csv"] = build_single_spectrum_csv_bytes(
                        result,
                        x_shift=st.session_state.x_shifts.get(name, 0.0),
                        intensity_scale=st.session_state.intensity_scales.get(name, 1.0),
                    )

                    files[f"{name}/{filename_base}_metadata.txt"] = build_spectrum_metadata_txt_bytes(
                        spectrum,
                        processing_kwargs=processing_kwargs,
                        x_shift=st.session_state.x_shifts.get(name, 0.0),
                        intensity_scale=st.session_state.intensity_scales.get(name, 1.0),
                    )

                    if include_session_original_files:
                        orig_bytes = spectrum.get("original_bytes")
                        if orig_bytes:
                            files[f"{name}/{spectrum['filename']}"] = orig_bytes

                selected_spectra = {
                    name: spectra[name]
                    for name in selected_overlay_names
                    if name in spectra
                }

                overlay_processed_results = {}
                for name, spectrum in selected_spectra.items():
                    local_processing_kwargs = dict(processing_kwargs)
                    local_processing_kwargs["intensity_scale"] = st.session_state.intensity_scales.get(name, 1.0)
                    local_processing_kwargs["x_shift"] = st.session_state.x_shifts.get(name, 0.0)

                    overlay_processed_results[name] = process_spectrum(
                        spectrum["x"],
                        spectrum["y"],
                        **local_processing_kwargs,
                    )

                overlay_fig = create_overlay_figure(
                    selected_spectra,
                    processing_kwargs=processing_kwargs,
                    intensity_scales=st.session_state.intensity_scales,
                    x_shifts=st.session_state.x_shifts,
                    title="Overlay",
                    show_peaks=show_multi_peaks,
                )

                normalized_fig = create_normalized_overlay_figure(
                    selected_spectra,
                    processing_kwargs=processing_kwargs,
                    x_shifts=st.session_state.x_shifts,
                    title="Normalized Overlay",
                    show_peaks=show_multi_peaks,
                )

                stacked_fig = create_stacked_figure(
                    selected_spectra,
                    processing_kwargs=processing_kwargs,
                    x_shifts=st.session_state.x_shifts,
                    title="Stacked Spectra",
                    show_peaks=show_multi_peaks,
                    step=st.session_state.get("stack_step", 1.2),
                )

                overlay_csv_path = None
                if include_session_overlay_csv and overlay_processed_results:
                    overlay_csv_path = "overlay/overlay_processed.csv"
                    files[overlay_csv_path] = build_multi_spectra_csv_bytes(
                        overlay_processed_results
                    )

                summary_bytes = build_summary_html_bytes(
                    spectra=spectra,
                    single_results=single_results,
                    overlay_names=list(selected_spectra.keys()),
                    overlay_fig=overlay_fig,
                    normalized_overlay_fig=normalized_fig,
                    stacked_fig=stacked_fig,
                    processing_kwargs=processing_kwargs,
                    x_shifts=st.session_state.x_shifts,
                    intensity_scales=st.session_state.intensity_scales,
                    include_original_file_links=include_session_original_files,
                    overlay_csv_path=overlay_csv_path,
                )

                files["summary.html"] = summary_bytes

                st.session_state.session_export_zip_bytes = build_zip_bytes(files)
                st.session_state.session_export_zip_name = "session_export.zip"
                st.success("Session export package created.")
                st.rerun()
            except Exception as exc:
                st.error(f"Session export error: {exc}")
    else:
        st.success("Session export package ready for download.")
        st.download_button(
            label=f"⬇ Download {st.session_state.session_export_zip_name}",
            data=st.session_state.session_export_zip_bytes,
            file_name=st.session_state.session_export_zip_name,
            mime="application/zip",
            key="download_session_export",
        )