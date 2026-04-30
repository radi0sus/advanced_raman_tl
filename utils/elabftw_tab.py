from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
import streamlit as st

from utils.package_creation import (
    build_single_export_artifacts,
    build_multi_export_artifacts,
)


RECENT_EXPERIMENTS_LIMIT = 50


# -----------------------------
# Session state helpers
# -----------------------------

def init_elabftw_session_state():
    defaults = {
        "elabftw_base_url": "",
        "elabftw_api_key": "",
        "elabftw_recent_experiments": [],
        "elabftw_selected_experiment_id": None,
        "elabftw_selected_experiment_label": None,
        "elabftw_selected_dropdown_label": "Select an experiment...",
        "elabftw_connection_ok": False,
        "elabftw_only_mine": True,
        "elabftw_only_mine_checkbox": True,
        "elabftw_last_loaded_only_mine": None,
        "elabftw_single_upload_zip_bytes": None,
        "elabftw_single_upload_zip_name": None,
        "elabftw_single_upload_png_bytes": None,
        "elabftw_single_upload_png_name": None,
        "elabftw_single_upload_signature": None,
        "elabftw_multi_upload_zip_bytes": None,
        "elabftw_multi_upload_zip_name": None,
        "elabftw_multi_upload_png_bytes": None,
        "elabftw_multi_upload_png_name": None,
        "elabftw_multi_upload_signature": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# -----------------------------
# Connection / API helpers
# -----------------------------

@dataclass
class ElabConnection:
    base_url: str
    api_key: str

    @property
    def api_base(self) -> str:
        return self.base_url.rstrip("/") + "/api/v2"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": self.api_key,
            "Accept": "application/json",
        }


def normalize_base_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def make_connection(base_url: str, api_key: str) -> ElabConnection:
    return ElabConnection(
        base_url=normalize_base_url(base_url),
        api_key=(api_key or "").strip(),
    )


def _safe_get(d: dict[str, Any], *keys, default=None):
    for key in keys:
        if key in d and d[key] not in (None, ""):
            return d[key]
    return default


def _format_datetime_for_label(value: str | None) -> str:
    if not value:
        return "—"

    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


def make_experiment_option_label(exp: dict[str, Any]) -> str:
    title = str(_safe_get(exp, "title", default="Untitled experiment"))
    exp_id = str(_safe_get(exp, "id", default="—"))
    owner = str(_safe_get(exp, "fullname", default="—"))
    modified = _safe_get(exp, "modified_at", "created_at")
    modified_label = _format_datetime_for_label(modified)

    return f"{title} · ID {exp_id} · {owner} · {modified_label}"


def test_connection(conn: ElabConnection) -> tuple[bool, str]:
    if not conn.base_url or not conn.api_key:
        return False, "Please provide both eLabFTW server URL and API key."

    try:
        response = requests.get(
            f"{conn.api_base}/experiments",
            headers=conn.headers,
            params={"limit": 1},
            timeout=20,
        )
        if response.ok:
            return True, "Connection successful."
        return False, f"Connection failed: {response.status_code} {response.text}"
    except Exception as exc:
        return False, f"Connection failed: {exc}"


def fetch_recent_experiments(
    conn: ElabConnection,
    limit: int = RECENT_EXPERIMENTS_LIMIT,
    only_mine: bool = True,
) -> list[dict[str, Any]]:
    params = {
        "limit": limit,
        "offset": 0,
        "state": "1",
        "order": "lastchange",
        "sort": "desc",
        "scope": 1 if only_mine else 3,
    }

    response = requests.get(
        f"{conn.api_base}/experiments",
        headers=conn.headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    return data if isinstance(data, list) else []


def upload_attachment_to_experiment(
    conn: ElabConnection,
    experiment_id: int,
    filename: str,
    content: bytes,
    mime_type: str = "application/octet-stream",
) -> dict[str, Any]:
    files = {
        "file": (filename, content, mime_type),
    }

    response = requests.post(
        f"{conn.api_base}/experiments/{experiment_id}/uploads",
        headers={
            "Authorization": conn.api_key,
            "Accept": "application/json",
        },
        files=files,
        timeout=120,
    )
    response.raise_for_status()

    try:
        return response.json()
    except Exception:
        return {"status": "ok"}


# -----------------------------
# Upload plan: single
# -----------------------------

def upload_single_export_to_experiment(
    conn: ElabConnection,
    experiment_id: int,
    zip_name: str,
    zip_bytes: bytes,
    png_name: str | None,
    png_bytes: bytes | None,
) -> list[str]:
    uploaded = []

    upload_attachment_to_experiment(
        conn,
        experiment_id,
        filename=zip_name,
        content=zip_bytes,
        mime_type="application/zip",
    )
    uploaded.append(zip_name)

    if png_name and png_bytes:
        upload_attachment_to_experiment(
            conn,
            experiment_id,
            filename=png_name,
            content=png_bytes,
            mime_type="image/png",
        )
        uploaded.append(png_name)

    return uploaded


# -----------------------------
# Internal state actions
# -----------------------------

def _reset_selected_experiment():
    st.session_state.elabftw_selected_experiment_id = None
    st.session_state.elabftw_selected_experiment_label = None
    st.session_state.elabftw_selected_dropdown_label = "Select an experiment..."


def _reset_elabftw_single_upload_package():
    st.session_state.elabftw_single_upload_zip_bytes = None
    st.session_state.elabftw_single_upload_zip_name = None
    st.session_state.elabftw_single_upload_png_bytes = None
    st.session_state.elabftw_single_upload_png_name = None
    st.session_state.elabftw_single_upload_signature = None

def _reset_elabftw_multi_upload_package():
    st.session_state.elabftw_multi_upload_zip_bytes = None
    st.session_state.elabftw_multi_upload_zip_name = None
    st.session_state.elabftw_multi_upload_png_bytes = None
    st.session_state.elabftw_multi_upload_png_name = None
    st.session_state.elabftw_multi_upload_signature = None

def _load_recent_experiments_into_session():
    conn = make_connection(
        st.session_state.elabftw_base_url,
        st.session_state.elabftw_api_key,
    )
    recent = fetch_recent_experiments(
        conn=conn,
        limit=RECENT_EXPERIMENTS_LIMIT,
        only_mine=st.session_state.elabftw_only_mine,
    )
    st.session_state.elabftw_recent_experiments = recent
    st.session_state.elabftw_last_loaded_only_mine = st.session_state.elabftw_only_mine


def build_elabftw_single_upload_signature(
    selected_spectrum_name: str,
    processing_kwargs: dict,
    show_peaks: bool,
) -> str:
    payload = {
        "selected_spectrum_name": selected_spectrum_name,
        "processing_kwargs": processing_kwargs,
        "x_shift": st.session_state.x_shifts.get(selected_spectrum_name, 0.0),
        "intensity_scale": st.session_state.intensity_scales.get(selected_spectrum_name, 1.0),
        "show_peaks": show_peaks,
        "include_csv": True,
        "include_metadata": True,
        "include_full_figure": True,
        "include_original_file": True,
    }

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

def build_elabftw_multi_upload_signature(
    selected_overlay_names: list[str],
    processing_kwargs: dict,
    show_multi_peaks: bool,
    stack_step: float,
) -> str:
    payload = {
        "selected_overlay_names": sorted(selected_overlay_names),
        "processing_kwargs": processing_kwargs,
        "x_shifts": st.session_state.x_shifts,
        "intensity_scales": st.session_state.intensity_scales,
        "show_multi_peaks": show_multi_peaks,
        "stack_step": stack_step,
        "include_overlay_html": True,
        "include_normalized_html": True,
        "include_stacked_html": True,
        "include_overlay_csv": True,
        "direct_png_for_upload": "stacked_plot.png",
    }

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

# -----------------------------
# UI 
# -----------------------------
# Single

def render_elabftw_single_upload_section():
    init_elabftw_session_state()

    st.markdown("### Upload single export to eLabFTW")
    st.caption(
        "Uploads are attached to an existing eLabFTW experiment. "
        "Credentials are stored only for the current session."
    )

    with st.container(border=True):
        base_url = st.text_input(
            "eLabFTW server URL",
            placeholder="https://your-elabftw.example.org",
            key="elabftw_base_url_input",
        )

        api_key = st.text_input(
            "API key",
            type="password",
            key="elabftw_api_key_input",
        )

        if st.button("Connect to eLabFTW", key="elabftw_connect_btn"):
            st.session_state.elabftw_base_url = normalize_base_url(
                st.session_state.get("elabftw_base_url_input", "")
            )
            st.session_state.elabftw_api_key = (
                st.session_state.get("elabftw_api_key_input", "").strip()
            )

            if not st.session_state.elabftw_base_url or not st.session_state.elabftw_api_key:
                st.session_state.elabftw_connection_ok = False
                st.error("Please provide both eLabFTW server URL and API key.")
                return

            conn = make_connection(
                st.session_state.elabftw_base_url,
                st.session_state.elabftw_api_key,
            )

            ok, msg = test_connection(conn)
            st.session_state.elabftw_connection_ok = ok

            if ok:
                try:
                    st.session_state.elabftw_only_mine = True
                    st.session_state.elabftw_only_mine_checkbox = True
                    _load_recent_experiments_into_session()
                    _reset_selected_experiment()
                    _reset_elabftw_single_upload_package()
                    _reset_elabftw_multi_upload_package()
                    st.success(msg)
                except Exception as exc:
                    st.session_state.elabftw_recent_experiments = []
                    st.warning(f"Connected, but could not load experiments: {exc}")
            else:
                st.error(msg)

    if not st.session_state.elabftw_connection_ok:
        st.info("Connect to eLabFTW to select an experiment and upload files.")
        return

    st.markdown("#### Target experiment")

    current_only_mine = st.checkbox(
        "Only my experiments",
        key="elabftw_only_mine_checkbox",
    )
    st.session_state.elabftw_only_mine = current_only_mine

    if st.session_state.elabftw_last_loaded_only_mine != current_only_mine:
        try:
            _load_recent_experiments_into_session()
            _reset_selected_experiment()
            _reset_elabftw_single_upload_package()
            _reset_elabftw_multi_upload_package()
        except Exception as exc:
            st.error(f"Failed to reload experiments: {exc}")

    recent = st.session_state.get("elabftw_recent_experiments", []) or []

    experiment_options = ["Select an experiment..."]
    label_to_experiment: dict[str, dict[str, Any]] = {}

    for exp in recent:
        label = make_experiment_option_label(exp)
        experiment_options.append(label)
        label_to_experiment[label] = exp

    current_label = st.session_state.get(
        "elabftw_selected_dropdown_label",
        "Select an experiment...",
    )
    if current_label not in experiment_options:
        current_label = "Select an experiment..."

    selected_label = st.selectbox(
        "Experiments",
        options=experiment_options,
        index=experiment_options.index(current_label),
        key="elabftw_experiments_selectbox",
    )

    st.session_state.elabftw_selected_dropdown_label = selected_label

    if selected_label != "Select an experiment...":
        exp = label_to_experiment[selected_label]
        new_selected_id = int(exp["id"])

        if st.session_state.elabftw_selected_experiment_id != new_selected_id:
            _reset_elabftw_single_upload_package()
            _reset_elabftw_multi_upload_package()

        st.session_state.elabftw_selected_experiment_id = new_selected_id
        st.session_state.elabftw_selected_experiment_label = selected_label

    selected_id = st.session_state.get("elabftw_selected_experiment_id")
    selected_label = st.session_state.get("elabftw_selected_experiment_label")

    if selected_id:
        st.success(f"Selected target: {selected_label}")
    else:
        st.info("Select a target experiment from the list above.")

    st.markdown("#### Upload single export")

    spectra = st.session_state.get("spectra", {})
    selected_spectrum_name = st.session_state.get("selected_spectrum_name")
    processing_kwargs = st.session_state.get("processing_kwargs")

    if not spectra:
        st.warning("No spectra loaded.")
        return

    if not selected_spectrum_name or selected_spectrum_name not in spectra:
        st.warning("No active spectrum selected.")
        return

    if not processing_kwargs:
        st.warning("Processing settings are not available.")
        return

    active_spectrum = spectra[selected_spectrum_name]
    st.write(f"Active spectrum: `{selected_spectrum_name}`")

    current_upload_signature = build_elabftw_single_upload_signature(
        selected_spectrum_name=selected_spectrum_name,
        processing_kwargs=processing_kwargs,
        show_peaks=bool(st.session_state.get("single_show_peaks", True)),
    )

    if st.session_state.elabftw_single_upload_signature != current_upload_signature:
        _reset_elabftw_single_upload_package()
        st.session_state.elabftw_single_upload_signature = current_upload_signature

    if (
        st.session_state.elabftw_single_upload_zip_bytes is None
        or st.session_state.elabftw_single_upload_zip_name is None
    ):
        if st.button("Create upload package", key="create_elabftw_single_upload_package"):
            try:
                artifacts = build_single_export_artifacts(
                    spectrum_name=selected_spectrum_name,
                    spectrum=active_spectrum,
                    processing_kwargs=processing_kwargs,
                    x_shift=st.session_state.x_shifts.get(selected_spectrum_name, 0.0),
                    intensity_scale=st.session_state.intensity_scales.get(selected_spectrum_name, 1.0),
                    show_peaks=bool(st.session_state.get("single_show_peaks", True)),
                    include_csv=True,
                    include_metadata=True,
                    include_full_figure=True,
                    include_original_file=True,
                    original_bytes_cache=st.session_state.get("original_bytes_cache", {}),
                )

                if not artifacts.files:
                    st.error("Failed to create export artifacts.")
                    return

                st.session_state.elabftw_single_upload_zip_bytes = artifacts.build_zip_bytes()
                st.session_state.elabftw_single_upload_zip_name = artifacts.zip_name
                st.session_state.elabftw_single_upload_png_name = next(
                    (name.split("/")[-1] for name in artifacts.files.keys() if name.lower().endswith(".png")),
                    None,
                )
                st.session_state.elabftw_single_upload_png_bytes = next(
                    (content for name, content in artifacts.files.items() if name.lower().endswith(".png")),
                    None,
                )
                st.session_state.elabftw_single_upload_signature = current_upload_signature

                st.success("Upload package created.")
                st.rerun()

            except Exception as exc:
                st.error(f"Package creation failed: {exc}")
    else:
        st.success("Upload package ready.")
        st.write(f"ZIP package: `{st.session_state.elabftw_single_upload_zip_name}`")

        if st.session_state.elabftw_single_upload_png_name:
            st.write(f"PNG preview: `{st.session_state.elabftw_single_upload_png_name}`")
        else:
            st.caption("No PNG found in upload package.")

        if st.button("⬆ Upload to eLabFTW", key="upload_single_to_elab_btn"):
            if not selected_id:
                st.error("Please select a target experiment first.")
                return

            try:
                conn = make_connection(
                    st.session_state.elabftw_base_url,
                    st.session_state.elabftw_api_key,
                )

                uploaded = upload_single_export_to_experiment(
                    conn=conn,
                    experiment_id=int(selected_id),
                    zip_name=st.session_state.elabftw_single_upload_zip_name,
                    zip_bytes=st.session_state.elabftw_single_upload_zip_bytes,
                    png_name=st.session_state.elabftw_single_upload_png_name,
                    png_bytes=st.session_state.elabftw_single_upload_png_bytes,
                )

                st.success("Upload completed.")
                for name in uploaded:
                    st.write(f"Uploaded: `{name}`")

            except Exception as exc:
                st.error(f"Upload failed: {exc}")
                
    # -----------------------------
    # UI 
    # -----------------------------
    # Overlays
    st.markdown("#### Upload overlay export")

    selected_overlay_names = st.session_state.get("selected_overlay_names", [])
    show_multi_peaks = bool(st.session_state.get("multi_show_peaks", True))
    stack_step = float(st.session_state.get("stack_step", 1.2))

    selected_spectra = {
        name: spectra[name]
        for name in selected_overlay_names
        if name in spectra
    }

    if not selected_spectra:
        st.warning("No overlay spectra selected.")
        return

    #st.write(f"Selected overlay spectra: {', '.join(selected_spectra.keys())}")

    current_multi_upload_signature = build_elabftw_multi_upload_signature(
        selected_overlay_names=list(selected_spectra.keys()),
        processing_kwargs=processing_kwargs,
        show_multi_peaks=show_multi_peaks,
        stack_step=stack_step,
    )

    if st.session_state.elabftw_multi_upload_signature != current_multi_upload_signature:
        _reset_elabftw_multi_upload_package()
        st.session_state.elabftw_multi_upload_signature = current_multi_upload_signature

    if (
        st.session_state.elabftw_multi_upload_zip_bytes is None
        or st.session_state.elabftw_multi_upload_zip_name is None
    ):
        if st.button("Create overlay upload package", key="create_elabftw_multi_upload_package"):
            try:
                artifacts = build_multi_export_artifacts(
                    selected_spectra=selected_spectra,
                    processing_kwargs=processing_kwargs,
                    intensity_scales=st.session_state.intensity_scales,
                    x_shifts=st.session_state.x_shifts,
                    stack_step=stack_step,
                    show_multi_peaks=show_multi_peaks,
                    include_overlay_html=True,
                    include_normalized_html=True,
                    include_stacked_html=True,
                    include_overlay_csv=True,
                )

                if not artifacts.files:
                    st.error("Failed to create overlay export artifacts.")
                    return

                st.session_state.elabftw_multi_upload_zip_bytes = artifacts.build_zip_bytes()
                st.session_state.elabftw_multi_upload_zip_name = artifacts.zip_name
                st.session_state.elabftw_multi_upload_png_name = next(
                    (
                        name.split("/")[-1]
                        for name in artifacts.files.keys()
                        if name.lower().endswith("stacked_plot.png")
                    ),
                    None,
                )
                st.session_state.elabftw_multi_upload_png_bytes = next(
                    (
                        content
                        for name, content in artifacts.files.items()
                        if name.lower().endswith("stacked_plot.png")
                    ),
                    None,
                )
                st.session_state.elabftw_multi_upload_signature = current_multi_upload_signature

                st.success("Overlay upload package created.")
                st.rerun()

            except Exception as exc:
                st.error(f"Overlay package creation failed: {exc}")
    else:
        st.success("Overlay upload package ready.")
        st.write(f"ZIP package: `{st.session_state.elabftw_multi_upload_zip_name}`")

        if st.session_state.elabftw_multi_upload_png_name:
            st.write(f"Stacked PNG: `{st.session_state.elabftw_multi_upload_png_name}`")
        else:
            st.caption("No stacked PNG found in overlay upload package.")

        if st.button("⬆ Upload overlay to eLabFTW", key="upload_multi_to_elab_btn"):
            if not selected_id:
                st.error("Please select a target experiment first.")
                return

            try:
                conn = make_connection(
                    st.session_state.elabftw_base_url,
                    st.session_state.elabftw_api_key,
                )

                uploaded = []

                upload_attachment_to_experiment(
                    conn,
                    int(selected_id),
                    filename=st.session_state.elabftw_multi_upload_zip_name,
                    content=st.session_state.elabftw_multi_upload_zip_bytes,
                    mime_type="application/zip",
                )
                uploaded.append(st.session_state.elabftw_multi_upload_zip_name)

                if (
                    st.session_state.elabftw_multi_upload_png_name
                    and st.session_state.elabftw_multi_upload_png_bytes
                ):
                    upload_attachment_to_experiment(
                        conn,
                        int(selected_id),
                        filename=st.session_state.elabftw_multi_upload_png_name,
                        content=st.session_state.elabftw_multi_upload_png_bytes,
                        mime_type="image/png",
                    )
                    uploaded.append(st.session_state.elabftw_multi_upload_png_name)

                st.success("Overlay upload completed.")
                for name in uploaded:
                    st.write(f"Uploaded: `{name}`")

            except Exception as exc:
                st.error(f"Overlay upload failed: {exc}")