# Advanced Raman Tool

> [!TIP]
> **Advanced Raman Tool** is available as a web app with interactive plots, direct HORIBA file support, export packages, and optional eLabFTW upload.  
> 👉 Try it here: https://advancedramantl-nfvgsz7dquxrmtk6xvc9hq.streamlit.app  
> 👉 Original CLI tool: https://github.com/radi0sus/raman_tl  

A web-based application for baseline correction, smoothing, processing, visualization, export, and optional eLabFTW upload of Raman spectra.

In general, the workflow and processing logic are similar to the original [`raman-tl.py`](https://github.com/radi0sus/raman_tl). For many practical questions, the original documentation is still a useful reference. The main differences are summarized below.

## Main differences compared to `raman-tl.py`

- **Graphical user interface**  
  Processing and display settings can be adjusted interactively in the browser instead of using command-line options.

- **Direct HORIBA LabSpec file support**  
  The app can read:
  - HORIBA LabSpec `.l6s`
  - HORIBA LabSpec `.xml`
  - plain text files (`wavenumber intensity`)

- **Metadata display**  
  Available metadata are shown directly in the app and included in export products where appropriate.

- **Additional baseline correction method: SNIP**  
  In addition to **arPLS**, the app also supports **SNIP** baseline correction.

- **Interactive Plotly visualization**  
  Spectra can be inspected interactively in the browser:
  - zoom and pan
  - show or hide spectra by clicking legend entries
  - isolate one spectrum by double-clicking a legend entry

- **Structured export packages**  
  Instead of writing output files directly into the working directory, the app creates ZIP-based export packages for:
  - the active spectrum
  - selected multi-spectra views
  - the full session

- **eLabFTW upload**  
  Export products can be uploaded directly to an existing **eLabFTW experiment** as attachments.

- **Session-based workflow**  
  The app is designed for interactive work:
  - upload spectra
  - inspect and compare them
  - adjust processing settings
  - export or upload results

## Typical workflow

1. Upload one or more spectra  
2. Select the active spectrum and optional overlay spectra  
3. Adjust:
   - baseline correction
   - smoothing
   - peak detection
   - spectral range
4. Inspect:
   - Single View
   - Overlay Spectra
   - Normalized Overlay
   - Stacked Spectra
5. Export results as ZIP packages  
6. Optionally upload packages to eLabFTW

## Current limitations and recommendations

- **Processing settings are global within a session**  
  Baseline correction, smoothing, peak picking, and spectral range settings currently apply to all spectra in the session.

- **Use moderate numbers of spectra for comparison**  
  It is possible to load and compare more spectra, but for practical use it is recommended to work with no more than about **5–6 spectra at a time**, especially for overlay, normalized overlay, and stacked views.

## Notes

- Manual intensity scaling and x-shifting are useful for visual comparison and alignment, but they can affect interpretation and should be used with care.
- Export and eLabFTW upload both use a two-step workflow:
  1. create the package
  2. download or upload the generated files

## References

### arPLS baseline correction
> Sung-June Baek, Aaron Park, Young-Jin Ahna, Jaebum Choo  
> **Baseline correction using asymmetrically reweighted penalized least squares smoothing**  
> *Analyst* **2015**, *140*, 250–257  
> DOI: https://doi.org/10.1039/C4AN01061B

### SNIP baseline correction
> C. G. Ryan, E. Clayton, W. L. Griffin, S. Sie, D. R. Cousens  
> **SNIP, a statistics-sensitive background treatment for the quantitative analysis of PIXE spectra in geoscience applications**  
> *Nuclear Instruments and Methods in Physics Research Section B* **1988**, *34*, 396–402  
> DOI: https://doi.org/10.1016/0168-583X(88)90063-8

### Whittaker smoothing
> Paul H. C. Eilers  
> **A perfect smoother**  
> *Anal. Chem.* **2003**, *75*, 3631–3636  
> DOI: https://doi.org/10.1021/ac034173t

based on:

> E. T. Whittaker  
> **On a new method of gradutation**  
> *Proceedings of the Edinburgh Mathematical Society* **1922**, *41*, 63–75  
> DOI: https://doi.org/10.1017/S0013091500077853