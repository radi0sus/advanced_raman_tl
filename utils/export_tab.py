from __future__ import annotations

import hashlib
import json

import streamlit as st

from utils.package_creation import (
    build_single_export_artifacts,
    build_multi_export_artifacts,
    build_session_export_artifacts,
)


def apply_filename_prefix(filename: str, prefix: str | None) -> str:
    prefix = (prefix or "").strip()
    if not prefix:
        return filename

    safe_prefix = prefix.replace("/", "_").replace("\\", "_").strip()
    if not safe_prefix:
        return filename

    return f"{safe_prefix}_{filename}"


def build_single_export_signature(
    selected_spectrum_name: str,
    processing_kwargs: dict,
    show_peaks: bool,
    include_csv: bool,
    include_metadata: bool,
    include_full_figure: bool,
    include_original_file: bool,
) -> str:
    payload = {
        "selected_spectrum_name": selected_spectrum_name,
        "processing_kwargs": processing_kwargs,
        "x_shift": st.session_state.x_shifts.get(selected_spectrum_name, 0.0),
        "intensity_scale": st.session_state.intensity_scales.get(selected_spectrum_name, 1.0),
        "show_peaks": show_peaks,
        "include_csv": include_csv,
        "include_metadata": include_metadata,
        "include_full_figure": include_full_figure,
        "include_original_file": include_original_file,
    }

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def build_multi_export_signature(
    selected_overlay_names: list[str],
    processing_kwargs: dict,
    show_multi_peaks: bool,
    include_overlay_html: bool,
    include_normalized_html: bool,
    include_stacked_html: bool,
    include_overlay_csv: bool,
) -> str:
    payload = {
        "selected_overlay_names": sorted(selected_overlay_names),
        "processing_kwargs": processing_kwargs,
        "x_shifts": st.session_state.x_shifts,
        "intensity_scales": st.session_state.intensity_scales,
        "stack_step": st.session_state.get("stack_step", 1.2),
        "show_multi_peaks": show_multi_peaks,
        "include_overlay_html": include_overlay_html,
        "include_normalized_html": include_normalized_html,
        "include_stacked_html": include_stacked_html,
        "include_overlay_csv": include_overlay_csv,
    }

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def build_session_export_signature(
    spectra: dict,
    selected_overlay_names: list[str],
    processing_kwargs: dict,
    include_session_single_exports: bool,
    include_session_original_files: bool,
    include_session_overlay_csv: bool,
    include_session_summary: bool,
    show_multi_peaks: bool,
    show_peaks: bool,
) -> str:
    payload = {
        "spectrum_names": sorted(spectra.keys()),
        "selected_overlay_names": sorted(selected_overlay_names),
        "processing_kwargs": processing_kwargs,
        "x_shifts": st.session_state.x_shifts,
        "intensity_scales": st.session_state.intensity_scales,
        "stack_step": st.session_state.get("stack_step", 1.2),
        "include_session_single_exports": include_session_single_exports,
        "include_session_original_files": include_session_original_files,
        "include_session_overlay_csv": include_session_overlay_csv,
        "include_session_summary": include_session_summary,
        "show_multi_peaks": show_multi_peaks,
        "show_peaks": show_peaks,
    }

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _render_action_panel_ready(
    zip_bytes: bytes,
    zip_name: str,
    download_key: str,
):
    st.success("Export package ready for download.")

    prefixed_zip_name = apply_filename_prefix(
        zip_name,
        st.session_state.get("export_zip_filename_prefix", ""),
    )

    st.download_button(
        label=f"⬇ Download {prefixed_zip_name}",
        data=zip_bytes,
        file_name=prefixed_zip_name,
        mime="application/zip",
        key=download_key,
        width="stretch",
    )


def render_export_tab(
    spectra: dict[str, dict],
    active_spectrum: dict,
    selected_spectrum_name: str,
    selected_overlay_names: list[str],
    processing_kwargs: dict,
    show_peaks: bool,
    show_multi_peaks: bool,
):
    #st.markdown("#####  Export packages")
    st.caption(
        """
        Create ZIP packages for the active spectrum, selected multi-spectra views, or the full session. 
        First create the export package, then download the generated ZIP file.
        """
    )
    

    with st.container(border=True):
        st.text_input(
            "Filename prefix (optional)",
            placeholder="Enter an optional prefix for downloaded ZIP files...",
            key="export_zip_filename_prefix",
            help="Optional prefix added to the downloaded ZIP filename only. ZIP contents are not changed.",
        )

    # ------------------------------------------------------------------
    # Single export
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown("##### Active spectrum")
        st.caption(
            "Export processed data, metadata, plot files, and optionally the original uploaded file "
            "for the currently active spectrum."
        )

        col_left, col_right = st.columns([1.7, 1.0], gap="large")

        with col_left:
            include_csv = st.checkbox(
                "Include processed data (CSV)",
                value=True,
                key="single_include_csv",
            )
            include_metadata = st.checkbox(
                "Include metadata (TXT)",
                value=True,
                key="single_include_metadata",
            )
            include_full_figure = st.checkbox(
                "Include plot (HTML / PNG)",
                value=True,
                key="single_include_figure",
            )
            include_original_file = st.checkbox(
                "Include original file (L6S / XML / TXT)",
                value=True,
                key="single_include_original",
            )

        current_single_export_signature = build_single_export_signature(
            selected_spectrum_name=selected_spectrum_name,
            processing_kwargs=processing_kwargs,
            show_peaks=show_peaks,
            include_csv=include_csv,
            include_metadata=include_metadata,
            include_full_figure=include_full_figure,
            include_original_file=include_original_file,
        )

        if st.session_state.single_export_signature != current_single_export_signature:
            st.session_state.single_export_zip_bytes = None
            st.session_state.single_export_zip_name = None
            st.session_state.single_export_signature = current_single_export_signature

        with col_right:
            st.caption(f"Active spectrum: `{selected_spectrum_name}`")

            if (
                st.session_state.single_export_zip_bytes is None
                or st.session_state.single_export_zip_name is None
            ):
                st.info("No package created yet.")

                if st.button("Create export package", 
                    key="create_single_export", 
                    width="stretch",
                    help="First create the export package, then download the generated ZIP file.",
                    ):
                    try:
                        artifacts = build_single_export_artifacts(
                            spectrum_name=selected_spectrum_name,
                            spectrum=active_spectrum,
                            processing_kwargs=processing_kwargs,
                            x_shift=st.session_state.x_shifts.get(selected_spectrum_name, 0.0),
                            intensity_scale=st.session_state.intensity_scales.get(selected_spectrum_name, 1.0),
                            show_peaks=show_peaks,
                            include_csv=include_csv,
                            include_metadata=include_metadata,
                            include_full_figure=include_full_figure,
                            include_original_file=include_original_file,
                            original_bytes_cache=st.session_state.original_bytes_cache,
                        )

                        if not artifacts.files:
                            st.warning("Please select at least one export item.")
                        else:
                            st.session_state.single_export_zip_bytes = artifacts.build_zip_bytes()
                            st.session_state.single_export_zip_name = artifacts.zip_name
                            st.session_state.single_export_signature = current_single_export_signature
                            st.success("Single spectrum export package created.")
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Export error: {exc}")
            else:
                _render_action_panel_ready(
                    zip_bytes=st.session_state.single_export_zip_bytes,
                    zip_name=st.session_state.single_export_zip_name,
                    download_key="download_single_export",
                )

    # ------------------------------------------------------------------
    # Multi export
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown("##### Multi-spectra views")
        st.caption(
            "Export overlay, normalized overlay, stacked spectra, and combined processed data "
            "for the currently selected overlay spectra."
        )

        col_left, col_right = st.columns([1.7, 1.0], gap="large")

        with col_left:
            include_overlay_html = st.checkbox(
                "Include overlay plot (HTML / PNG)",
                value=True,
                key="multi_include_overlay_html",
            )
            include_normalized_html = st.checkbox(
                "Include normalized overlay plot (HTML / PNG)",
                value=True,
                key="multi_include_normalized_html",
            )
            include_stacked_html = st.checkbox(
                "Include stacked plot (HTML / PNG)",
                value=True,
                key="multi_include_stacked_html",
            )
            include_overlay_csv = st.checkbox(
                "Include processed data (CSV)",
                value=True,
                key="multi_include_overlay_csv",
            )

        current_multi_export_signature = build_multi_export_signature(
            selected_overlay_names=selected_overlay_names,
            processing_kwargs=processing_kwargs,
            show_multi_peaks=show_multi_peaks,
            include_overlay_html=include_overlay_html,
            include_normalized_html=include_normalized_html,
            include_stacked_html=include_stacked_html,
            include_overlay_csv=include_overlay_csv,
        )

        if st.session_state.multi_export_signature != current_multi_export_signature:
            st.session_state.multi_export_zip_bytes = None
            st.session_state.multi_export_zip_name = None
            st.session_state.multi_export_signature = current_multi_export_signature

        with col_right:
            st.caption(f"Selected spectra: `{len(selected_overlay_names)}`")

            if (
                st.session_state.multi_export_zip_bytes is None
                or st.session_state.multi_export_zip_name is None
            ):
                st.info("No package created yet.")

                if st.button("Create multi-spectra export package", 
                    key="create_multi_export", 
                    width="stretch",
                    help="First create the export package, then download the generated ZIP file.",
                    ):
                    try:
                        selected_spectra = {
                            name: spectra[name]
                            for name in selected_overlay_names
                            if name in spectra
                        }

                        if not selected_spectra:
                            st.warning("Please select at least one spectrum for multi export.")
                        else:
                            artifacts = build_multi_export_artifacts(
                                selected_spectra=selected_spectra,
                                processing_kwargs=processing_kwargs,
                                intensity_scales=st.session_state.intensity_scales,
                                x_shifts=st.session_state.x_shifts,
                                stack_step=st.session_state.get("stack_step", 1.2),
                                show_multi_peaks=show_multi_peaks,
                                include_overlay_html=include_overlay_html,
                                include_normalized_html=include_normalized_html,
                                include_stacked_html=include_stacked_html,
                                include_overlay_csv=include_overlay_csv,
                            )

                            if not artifacts.files:
                                st.warning("Please select at least one multi-spectra export item.")
                            else:
                                st.session_state.multi_export_zip_bytes = artifacts.build_zip_bytes()
                                st.session_state.multi_export_zip_name = artifacts.zip_name
                                st.session_state.multi_export_signature = current_multi_export_signature
                                st.success("Multi-spectra export package created.")
                                st.rerun()
                    except Exception as exc:
                        st.error(f"Multi export error: {exc}")
            else:
                _render_action_panel_ready(
                    zip_bytes=st.session_state.multi_export_zip_bytes,
                    zip_name=st.session_state.multi_export_zip_name,
                    download_key="download_multi_export",
                )

    # ------------------------------------------------------------------
    # Session export
    # ------------------------------------------------------------------
    with st.container(border=True):
        st.markdown("##### Full session")
        st.caption(
            "Export the complete session including per-spectrum files, original files, "
            "combined overlay data, and the session summary."
        )

        col_left, col_right = st.columns([1.7, 1.0], gap="large")

        with col_left:
            include_session_single_exports = st.checkbox(
                "Include processed data and metadata (CSV / TXT)",
                value=True,
                key="session_include_single_exports",
            )
            include_session_original_files = st.checkbox(
                "Include original files (L6S / XML / TXT)",
                value=True,
                key="session_include_original_files",
            )
            include_session_overlay_csv = st.checkbox(
                "Include overlay (CSV)",
                value=True,
                key="session_include_overlay_csv",
            )
            include_session_summary = st.checkbox(
                "Include summary (HTML / PDF)",
                value=True,
                key="session_include_summary",
            )

        current_session_export_signature = build_session_export_signature(
            spectra=spectra,
            selected_overlay_names=selected_overlay_names,
            processing_kwargs=processing_kwargs,
            include_session_single_exports=include_session_single_exports,
            include_session_original_files=include_session_original_files,
            include_session_overlay_csv=include_session_overlay_csv,
            include_session_summary=include_session_summary,
            show_multi_peaks=show_multi_peaks,
            show_peaks=show_peaks,
        )

        if st.session_state.session_export_signature != current_session_export_signature:
            st.session_state.session_export_zip_bytes = None
            st.session_state.session_export_zip_name = None
            st.session_state.session_export_signature = current_session_export_signature

        with col_right:
            st.caption(f"Loaded spectra: `{len(spectra)}`")

            if (
                st.session_state.session_export_zip_bytes is None
                or st.session_state.session_export_zip_name is None
            ):
                st.info("No package created yet.")

                if st.button("Create session export package", 
                    key="create_session_export", 
                    width="stretch",
                    help="First create the export package, then download the generated ZIP file.",
                    ):
                    try:
                        if not (
                            include_session_single_exports
                            or include_session_original_files
                            or include_session_overlay_csv
                            or include_session_summary
                        ):
                            st.session_state.session_export_zip_bytes = None
                            st.session_state.session_export_zip_name = None
                            st.warning("Please select at least one export item.")
                        else:
                            artifacts = build_session_export_artifacts(
                                spectra=spectra,
                                selected_overlay_names=selected_overlay_names,
                                processing_kwargs=processing_kwargs,
                                x_shifts=st.session_state.x_shifts,
                                intensity_scales=st.session_state.intensity_scales,
                                original_bytes_cache=st.session_state.original_bytes_cache,
                                stack_step=st.session_state.get("stack_step", 1.2),
                                show_single_peaks=show_peaks,
                                show_multi_peaks=show_multi_peaks,
                                include_session_single_exports=include_session_single_exports,
                                include_session_original_files=include_session_original_files,
                                include_session_overlay_csv=include_session_overlay_csv,
                                include_session_summary=include_session_summary,
                            )

                            st.session_state.session_export_zip_bytes = artifacts.build_zip_bytes()
                            st.session_state.session_export_zip_name = artifacts.zip_name
                            st.session_state.session_export_signature = current_session_export_signature
                            st.success("Session export package created.")
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Session export error: {exc}")
            else:
                _render_action_panel_ready(
                    zip_bytes=st.session_state.session_export_zip_bytes,
                    zip_name=st.session_state.session_export_zip_name,
                    download_key="download_session_export",
                )