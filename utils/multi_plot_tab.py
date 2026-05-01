from __future__ import annotations

import json

import streamlit as st

from utils.figures import create_stacked_figure


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
            tuple(sorted((k, _val_to_hashable(v)) for k, v in sp.items())),
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
def _cached_normalized_multi_figure(
    spectra_hashable,
    kwargs_json,
    x_shifts_json,
    title,
    show_peaks,
    step,
):
    return create_stacked_figure(
        _hashable_to_spectra(spectra_hashable),
        processing_kwargs=json.loads(kwargs_json),
        x_shifts=json.loads(x_shifts_json),
        title=title,
        show_peaks=show_peaks,
        step=float(step),
    )


def _render_multi_plot_tab(
    spectra: dict,
    selected_overlay_names: list[str],
    processing_kwargs: dict,
    show_multi_peaks: bool,
    title: str,
    step: float,
    empty_warning_text: str,
):
    try:
        selected_spectra = {
            name: spectra[name]
            for name in selected_overlay_names
            if name in spectra
        }

        if not selected_spectra:
            st.warning(empty_warning_text)
            return

        fig = _cached_normalized_multi_figure(
            _spectra_to_hashable(selected_spectra),
            json.dumps(processing_kwargs, sort_keys=True),
            json.dumps(dict(sorted(st.session_state.x_shifts.items()))),
            title,
            show_multi_peaks,
            float(step),
        )
        st.plotly_chart(fig, width="stretch")
    except Exception as exc:
        st.error(f"{title} error: {exc}")


def render_normalized_overlay_tab(
    spectra: dict,
    selected_overlay_names: list[str],
    processing_kwargs: dict,
    show_multi_peaks: bool,
):
    _render_multi_plot_tab(
        spectra=spectra,
        selected_overlay_names=selected_overlay_names,
        processing_kwargs=processing_kwargs,
        show_multi_peaks=show_multi_peaks,
        title="Normalized Overlay",
        step=0.0,
        empty_warning_text="Please select at least one spectrum for normalized overlay.",
    )


def render_stacked_spectra_tab(
    spectra: dict,
    selected_overlay_names: list[str],
    processing_kwargs: dict,
    show_multi_peaks: bool,
):
    _render_multi_plot_tab(
        spectra=spectra,
        selected_overlay_names=selected_overlay_names,
        processing_kwargs=processing_kwargs,
        show_multi_peaks=show_multi_peaks,
        title="Stacked Spectra",
        step=float(st.session_state.get("stack_step", 1.2)),
        empty_warning_text="Please select at least one spectrum for stacked view.",
    )