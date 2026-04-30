from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt

from utils.processing import process_spectrum
from utils.figures import (
    create_single_view_figure,
    create_overlay_figure,
    create_normalized_overlay_figure,
    create_stacked_figure,
    make_spectrum_title,
)
from utils.mpl_figures import (
    create_single_summary_mpl_figure,
    create_overlay_mpl_figure,
    create_normalized_overlay_mpl_figure,
    create_stacked_mpl_figure,
)
from utils.export import (
    build_single_spectrum_csv_bytes,
    build_multi_spectra_csv_bytes,
    build_spectrum_metadata_txt_bytes,
    build_figure_html_bytes,
    build_summary_html_bytes,
    build_zip_bytes,
    build_matplotlib_png_bytes,
    build_matplotlib_pdf_bytes,
)


@dataclass
class ExportArtifacts:
    files: dict[str, bytes]
    zip_name: str

    def build_zip_bytes(self) -> bytes:
        return build_zip_bytes(self.files)


def _process_single_spectrum(
    spectrum: dict,
    processing_kwargs: dict,
    x_shift: float = 0.0,
    intensity_scale: float = 1.0,
) -> dict:
    local_processing_kwargs = dict(processing_kwargs or {})
    local_processing_kwargs["intensity_scale"] = float(intensity_scale)
    local_processing_kwargs["x_shift"] = float(x_shift)

    return process_spectrum(
        spectrum["x"],
        spectrum["y"],
        **local_processing_kwargs,
    )


def _get_original_file_bytes(
    spectrum: dict,
    original_bytes_cache: dict[str, bytes] | None = None,
) -> bytes | None:
    original_bytes_cache = original_bytes_cache or {}
    filename = spectrum.get("filename")
    if not filename:
        return None
    return original_bytes_cache.get(filename)


def build_single_export_artifacts(
    spectrum_name: str,
    spectrum: dict,
    processing_kwargs: dict,
    x_shift: float = 0.0,
    intensity_scale: float = 1.0,
    show_peaks: bool = True,
    include_csv: bool = True,
    include_metadata: bool = True,
    include_full_figure: bool = True,
    include_original_file: bool = True,
    original_bytes_cache: dict[str, bytes] | None = None,
) -> ExportArtifacts:
    result = _process_single_spectrum(
        spectrum=spectrum,
        processing_kwargs=processing_kwargs,
        x_shift=x_shift,
        intensity_scale=intensity_scale,
    )

    filename_base = Path(spectrum.get("filename", "spectrum")).stem
    files: dict[str, bytes] = {}

    if include_csv:
        files[f"{filename_base}_processed.csv"] = build_single_spectrum_csv_bytes(
            result,
            x_shift=x_shift,
            intensity_scale=intensity_scale,
        )

    if include_metadata:
        files[f"{filename_base}_metadata.txt"] = build_spectrum_metadata_txt_bytes(
            spectrum,
            processing_kwargs=processing_kwargs,
            x_shift=x_shift,
            intensity_scale=intensity_scale,
        )

    if include_full_figure:
        full_fig = create_single_view_figure(
            result,
            show_peaks=show_peaks,
            title=make_spectrum_title(spectrum),
            show_raw=True,
            show_baseline=True,
            show_corrected=True,
            show_smoothed=True,
        )
        files[f"{filename_base}_figure_full.html"] = build_figure_html_bytes(full_fig)

        mpl_fig = create_single_summary_mpl_figure(
            spectrum=spectrum,
            result=result,
            processing_kwargs=processing_kwargs,
            x_shift=x_shift,
            intensity_scale=intensity_scale,
            show_peaks=show_peaks,
            title=make_spectrum_title(spectrum),
            show_raw=True,
            show_baseline=True,
            show_corrected=True,
            show_smoothed=True,
        )
        try:
            files[f"{filename_base}_figure_full.png"] = build_matplotlib_png_bytes(mpl_fig)
        finally:
            plt.close(mpl_fig)

    if include_original_file:
        orig_bytes = _get_original_file_bytes(
            spectrum=spectrum,
            original_bytes_cache=original_bytes_cache,
        )
        if orig_bytes:
            files[spectrum["filename"]] = orig_bytes

    return ExportArtifacts(
        files=files,
        zip_name=f"{filename_base}_export.zip",
    )


def build_multi_export_artifacts(
    selected_spectra: dict[str, dict],
    processing_kwargs: dict,
    intensity_scales: dict[str, float] | None = None,
    x_shifts: dict[str, float] | None = None,
    stack_step: float = 1.2,
    show_multi_peaks: bool = True,
    include_overlay_html: bool = True,
    include_normalized_html: bool = True,
    include_stacked_html: bool = True,
    include_overlay_csv: bool = True,
) -> ExportArtifacts:
    intensity_scales = intensity_scales or {}
    x_shifts = x_shifts or {}

    files: dict[str, bytes] = {}
    processed_results: dict[str, dict] = {}

    if include_overlay_csv:
        for name, spectrum in selected_spectra.items():
            processed_results[name] = _process_single_spectrum(
                spectrum=spectrum,
                processing_kwargs=processing_kwargs,
                x_shift=x_shifts.get(name, 0.0),
                intensity_scale=intensity_scales.get(name, 1.0),
            )

    if include_overlay_html:
        overlay_fig = create_overlay_figure(
            selected_spectra,
            processing_kwargs=processing_kwargs,
            intensity_scales=intensity_scales,
            x_shifts=x_shifts,
            title="Overlay",
            show_peaks=show_multi_peaks,
        )
        files["overlay/overlay_plot.html"] = build_figure_html_bytes(overlay_fig)

        overlay_mpl_fig = create_overlay_mpl_figure(
            selected_spectra,
            processing_kwargs=processing_kwargs,
            intensity_scales=intensity_scales,
            x_shifts=x_shifts,
            title="Overlay",
            show_peaks=show_multi_peaks,
        )
        try:
            files["overlay/overlay_plot.png"] = build_matplotlib_png_bytes(overlay_mpl_fig)
        finally:
            plt.close(overlay_mpl_fig)

    if include_normalized_html:
        normalized_fig = create_normalized_overlay_figure(
            selected_spectra,
            processing_kwargs=processing_kwargs,
            x_shifts=x_shifts,
            title="Normalized Overlay",
            show_peaks=show_multi_peaks,
        )
        files["overlay/normalized_overlay_plot.html"] = build_figure_html_bytes(normalized_fig)

        normalized_mpl_fig = create_normalized_overlay_mpl_figure(
            selected_spectra,
            processing_kwargs=processing_kwargs,
            x_shifts=x_shifts,
            title="Normalized Overlay",
            show_peaks=show_multi_peaks,
        )
        try:
            files["overlay/normalized_overlay_plot.png"] = build_matplotlib_png_bytes(normalized_mpl_fig)
        finally:
            plt.close(normalized_mpl_fig)

    if include_stacked_html:
        stacked_fig = create_stacked_figure(
            selected_spectra,
            processing_kwargs=processing_kwargs,
            x_shifts=x_shifts,
            title="Stacked Spectra",
            show_peaks=show_multi_peaks,
            step=stack_step,
        )
        files["overlay/stacked_plot.html"] = build_figure_html_bytes(stacked_fig)

        stacked_mpl_fig = create_stacked_mpl_figure(
            selected_spectra,
            processing_kwargs=processing_kwargs,
            x_shifts=x_shifts,
            title="Stacked Spectra",
            show_peaks=show_multi_peaks,
            step=stack_step,
        )
        try:
            files["overlay/stacked_plot.png"] = build_matplotlib_png_bytes(stacked_mpl_fig)
        finally:
            plt.close(stacked_mpl_fig)

    if include_overlay_csv and processed_results:
        files["overlay/overlay_processed.csv"] = build_multi_spectra_csv_bytes(processed_results)

    return ExportArtifacts(
        files=files,
        zip_name="multi_spectra_export.zip",
    )


def build_session_export_artifacts(
    spectra: dict[str, dict],
    selected_overlay_names: list[str],
    processing_kwargs: dict,
    x_shifts: dict[str, float] | None = None,
    intensity_scales: dict[str, float] | None = None,
    original_bytes_cache: dict[str, bytes] | None = None,
    stack_step: float = 1.2,
    show_single_peaks: bool = True,
    show_multi_peaks: bool = True,
    include_session_single_exports: bool = True,
    include_session_original_files: bool = True,
    include_session_overlay_csv: bool = True,
    include_session_summary: bool = True,
) -> ExportArtifacts:
    x_shifts = x_shifts or {}
    intensity_scales = intensity_scales or {}
    original_bytes_cache = original_bytes_cache or {}

    files: dict[str, bytes] = {}
    single_results: dict[str, dict] = {}

    for name, spectrum in spectra.items():
        result = _process_single_spectrum(
            spectrum=spectrum,
            processing_kwargs=processing_kwargs,
            x_shift=x_shifts.get(name, 0.0),
            intensity_scale=intensity_scales.get(name, 1.0),
        )
        single_results[name] = result

        if include_session_single_exports:
            filename_base = Path(spectrum.get("filename", name)).stem

            files[f"{name}/{filename_base}_processed.csv"] = build_single_spectrum_csv_bytes(
                result,
                x_shift=x_shifts.get(name, 0.0),
                intensity_scale=intensity_scales.get(name, 1.0),
            )

            files[f"{name}/{filename_base}_metadata.txt"] = build_spectrum_metadata_txt_bytes(
                spectrum,
                processing_kwargs=processing_kwargs,
                x_shift=x_shifts.get(name, 0.0),
                intensity_scale=intensity_scales.get(name, 1.0),
            )

        if include_session_original_files:
            orig_bytes = _get_original_file_bytes(
                spectrum=spectrum,
                original_bytes_cache=original_bytes_cache,
            )
            if orig_bytes:
                files[f"{name}/{spectrum['filename']}"] = orig_bytes

    selected_spectra = {
        name: spectra[name]
        for name in selected_overlay_names
        if name in spectra
    }

    overlay_processed_results: dict[str, dict] = {}
    if include_session_overlay_csv:
        for name, spectrum in selected_spectra.items():
            overlay_processed_results[name] = _process_single_spectrum(
                spectrum=spectrum,
                processing_kwargs=processing_kwargs,
                x_shift=x_shifts.get(name, 0.0),
                intensity_scale=intensity_scales.get(name, 1.0),
            )

    overlay_fig = None
    normalized_fig = None
    stacked_fig = None

    if include_session_summary:
        overlay_fig = create_overlay_figure(
            selected_spectra,
            processing_kwargs=processing_kwargs,
            intensity_scales=intensity_scales,
            x_shifts=x_shifts,
            title="Overlay",
            show_peaks=show_multi_peaks,
        )

        normalized_fig = create_normalized_overlay_figure(
            selected_spectra,
            processing_kwargs=processing_kwargs,
            x_shifts=x_shifts,
            title="Normalized Overlay",
            show_peaks=show_multi_peaks,
        )

        stacked_fig = create_stacked_figure(
            selected_spectra,
            processing_kwargs=processing_kwargs,
            x_shifts=x_shifts,
            title="Stacked Spectra",
            show_peaks=show_multi_peaks,
            step=stack_step,
        )

    overlay_csv_path = None
    if include_session_overlay_csv and overlay_processed_results:
        overlay_csv_path = "overlay/overlay_processed.csv"
        files[overlay_csv_path] = build_multi_spectra_csv_bytes(overlay_processed_results)

    if include_session_summary:
        files["summary.html"] = build_summary_html_bytes(
            spectra=spectra,
            single_results=single_results,
            overlay_names=list(selected_spectra.keys()),
            overlay_fig=overlay_fig,
            normalized_overlay_fig=normalized_fig,
            stacked_fig=stacked_fig,
            processing_kwargs=processing_kwargs,
            x_shifts=x_shifts,
            intensity_scales=intensity_scales,
            include_single_file_links=include_session_single_exports,
            include_original_file_links=include_session_original_files,
            overlay_csv_path=overlay_csv_path,
        )

        pdf_figures = []

        for name, spectrum in spectra.items():
            result = single_results[name]

            single_summary_fig = create_single_summary_mpl_figure(
                spectrum=spectrum,
                result=result,
                processing_kwargs=processing_kwargs,
                x_shift=x_shifts.get(name, 0.0),
                intensity_scale=intensity_scales.get(name, 1.0),
                show_peaks=show_single_peaks,
                title=make_spectrum_title(spectrum),
                show_raw=True,
                show_baseline=True,
                show_corrected=True,
                show_smoothed=True,
            )
            pdf_figures.append(single_summary_fig)

        if selected_spectra:
            overlay_pdf_fig = create_overlay_mpl_figure(
                selected_spectra,
                processing_kwargs=processing_kwargs,
                intensity_scales=intensity_scales,
                x_shifts=x_shifts,
                title="Overlay",
                show_peaks=show_multi_peaks,
            )
            pdf_figures.append(overlay_pdf_fig)

            normalized_pdf_fig = create_normalized_overlay_mpl_figure(
                selected_spectra,
                processing_kwargs=processing_kwargs,
                x_shifts=x_shifts,
                title="Normalized Overlay",
                show_peaks=show_multi_peaks,
            )
            pdf_figures.append(normalized_pdf_fig)

            stacked_pdf_fig = create_stacked_mpl_figure(
                selected_spectra,
                processing_kwargs=processing_kwargs,
                x_shifts=x_shifts,
                title="Stacked Spectra",
                show_peaks=show_multi_peaks,
                step=stack_step,
            )
            pdf_figures.append(stacked_pdf_fig)

        try:
            files["summary.pdf"] = build_matplotlib_pdf_bytes(pdf_figures)
        finally:
            for fig in pdf_figures:
                plt.close(fig)

    return ExportArtifacts(
        files=files,
        zip_name="session_export.zip",
    )