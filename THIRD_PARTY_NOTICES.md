# Third-party runtime notices

The MIT license in this project covers LinguaPlay source code. Bundled runtime components retain their own licenses and copyrights. Copies of available distribution license files and metadata are in the portable `licenses` directory.

- Python 3.11: Python Software Foundation License; https://www.python.org/downloads/source/ and https://docs.python.org/3/license.html
- PySide6 / Shiboken6 6.12.0: the installed distribution metadata declares `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. Distributed here under LGPL v3. Source: https://code.qt.io/cgit/pyside/pyside-setup.git/ (tag v6.12.0).
- Qt 6.12 runtime libraries: LGPL v3 for the used Core, GUI, Widgets, Network and supporting LGPL modules. Qt source: https://code.qt.io/cgit/qt/qt5.git/ and https://download.qt.io/archive/qt/ ; corresponding component repositories are linked from the Qt source tree. Qt licensing information: https://www.qt.io/licensing/open-source-lgpl-obligations . No Qt libraries have been modified. DLLs remain separate in `_internal/PySide6` and may be replaced with compatible builds. Reverse engineering to debug modifications of LGPL components is permitted under their license.
- Pillow 13.0.0: HPND / Pillow license and bundled codec notices; https://github.com/python-pillow/Pillow/tree/13.0.0 .
- CTranslate2 4.8.4: MIT; https://github.com/OpenNMT/CTranslate2 . Bundled native library dependencies retain the licenses included in its distribution.
- SentencePiece 0.2.1: Apache-2.0; https://github.com/google/sentencepiece .
- NumPy 2.4.6: BSD-3-Clause and bundled native dependency notices; https://github.com/numpy/numpy . PyYAML 6.0.3: MIT; https://github.com/yaml/pyyaml .
- Helsinki-NLP OPUS-MT English to Indonesian: Apache-2.0; https://huggingface.co/Helsinki-NLP/opus-mt-en-id . Model revision and checksums are recorded in `models/opus-mt-en-id-int8/provenance.json`. We converted the original weights to CTranslate2 INT8 and copied the original SentencePiece tokenizers; no training or fine-tuning was performed. Model attribution, original model card, and Apache license accompany the converted model.
- PyWinRT / winrt-runtime 4.0.3 and Windows projections: MIT; https://github.com/pywinrt/pywinrt . Windows OCR itself is supplied by the user's Windows installation, not redistributed.
- PyInstaller bootloader: GPL with bootloader exception; https://github.com/pyinstaller/pyinstaller/tree/v6.22.3 . This exception permits distribution of frozen applications under their own license. Build tooling and other dependencies may carry additional notices collected with this package.

LinguaPlay does not restrict modification or replacement of its LGPL dependencies. All LinguaPlay source needed to rebuild the application accompanies this package; installation and build commands are in README.md. Component metadata identifies the exact runtime versions in this build.

- psutil 7.2.2: BSD-3-Clause; https://github.com/giampaolo/psutil . Used to detect running game processes before changing subtitles.
