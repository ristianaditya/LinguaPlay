# Offline Game Translation Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LinguaPlay a reliable offline-first launcher that detects supported game subtitle files, translates them before play, preserves originals, and falls back to configurable OCR when file patching is unavailable.

**Architecture:** Extend the existing library, adapter, patch, translation, OCR, and overlay modules instead of introducing a second runtime. Each game has a persisted profile containing detection results, translation settings, glossary/memory, patch state, and overlay settings. A staged pre-translation job produces reviewable output before an atomic install; unsupported formats remain OCR-only.

**Tech Stack:** Python 3.11, PySide6, existing CTranslate2 OPUS-MT runtime, Pillow/PyWinRT Windows OCR, JSON persistence, pytest, PyInstaller portable build.

**Spec:** `PRODUCT.md`, `DESIGN.md`, and `docs/adapters.md`.

## Global Constraints

- Translation must work offline with the bundled OPUS-MT model and must not require Qwen, Ollama, or an API key.
- Patch operations must preserve originals, use atomic writes, verify hashes, and support rollback.
- The application targets Windows 10/11 x64 and must continue to run as a portable folder.
- Unknown proprietary archives must be reported as unsupported; the application must not decrypt, inject, or modify them automatically.
- OCR must remain a fallback mode and must not read game memory or inject into the game process.
- The rejected generated forest background must not be reintroduced.

## Review Focus

- A game with repeated dialog text must reuse translation memory and avoid duplicate model work.
- A translation job interrupted halfway must resume without corrupting staged or installed files.
- A subtitle file changed by another program must be refused by the patcher and reported clearly.
- A game with an unknown archive format must remain usable through OCR without being falsely marked fully supported.
- A user switching between Original and Translated must get the correct file hashes and an explicit launch mode.

### Task 1: Persisted per-game translation profile

**Files:**
- Modify: `linguaplay/library.py`
- Modify: `linguaplay/library_ui.py`
- Modify: `linguaplay/ui.py`
- Test: `tests/test_game_profiles.py`

**Interfaces:**
- Produces `GameTranslationProfile` fields: `source_language`, `target_language`, `adapter_id`, `support_level`, `glossary_path`, `memory_path`, `overlay_profile_id`, and `last_scan`.
- Produces `LibraryStore.get_profile(game_id) -> GameTranslationProfile` and `LibraryStore.save_profile(profile) -> None`.

- [ ] Write tests for profile creation, migration of existing library JSON, and per-game isolation.
- [ ] Implement profile serialization with backward-compatible defaults and atomic JSON persistence.
- [ ] Add profile controls to the game detail page without changing the existing launch modes.
- [ ] Run `pytest tests/test_game_profiles.py -v` and confirm all profile tests pass.

### Task 2: Adapter scan and compatibility report

**Files:**
- Modify: `linguaplay/adapters.py`
- Modify: `linguaplay/library.py`
- Modify: `linguaplay/library_ui.py`
- Test: `tests/test_compatibility_scan.py`

**Interfaces:**
- Produces `CompatibilityReport` with `support_level`, `candidates`, `adapter_id`, `warnings`, and `scan_hash`.
- Produces `scan_game_root(root: Path) -> CompatibilityReport`.

- [ ] Write tests for supported SRT/WebVTT/JSON, unknown archive candidates, and an empty game root.
- [ ] Implement deterministic scan scoring using content validation and adapter confidence, not filename alone.
- [ ] Persist the report in the game profile and display Supported, Patch available, OCR only, or Unsupported.
- [ ] Run `pytest tests/test_compatibility_scan.py -v` and confirm unsupported files are never selected for patching.

### Task 3: Resumable offline pre-translation job

**Files:**
- Create: `linguaplay/translation_jobs.py`
- Modify: `linguaplay/translation.py`
- Modify: `linguaplay/library_ui.py`
- Test: `tests/test_translation_jobs.py`

**Interfaces:**
- Produces `TranslationJob.start()`, `pause()`, `cancel()`, `resume()`, and `status()`.
- Produces `TranslationJobStatus` with `job_id`, `total_units`, `completed_units`, `failed_units`, `state`, and `staged_files`.

- [ ] Write tests for duplicate text reuse, cancellation, resume, and the offline model path.
- [ ] Implement a durable job manifest and staged output directory per game/profile.
- [ ] Route every text unit through glossary lookup, translation memory lookup, then OPUS-MT inference.
- [ ] Run `pytest tests/test_translation_jobs.py -v` and verify no network socket is required.

### Task 4: Glossary and translation memory

**Files:**
- Create: `linguaplay/translation_memory.py`
- Modify: `linguaplay/translation.py`
- Modify: `linguaplay/library_ui.py`
- Test: `tests/test_translation_memory.py`

**Interfaces:**
- Produces `Glossary.get(source_text) -> str | None`, `Glossary.set(source_text, target_text) -> None`.
- Produces `TranslationMemory.lookup(source_text, source_lang, target_lang) -> str | None` and `.store(...) -> None`.

- [ ] Write tests for exact matches, case-preserving glossary tokens, language-pair isolation, and corrupted memory recovery.
- [ ] Implement atomic local JSON storage under the existing LinguaPlay data directory.
- [ ] Apply glossary substitutions around protected tags and validate that placeholders survive translation.
- [ ] Run `pytest tests/test_translation_memory.py -v` and verify repeated lines are served from memory.

### Task 5: Reviewable patch staging and rollback UX

**Files:**
- Modify: `linguaplay/patches.py`
- Modify: `linguaplay/library_ui.py`
- Modify: `linguaplay/ui.py`
- Test: `tests/test_patch_review.py`

**Interfaces:**
- Produces `PatchReview` with original path, staged path, original hash, staged hash, changed unit count, and warnings.
- Produces `PatchManager.apply_review(review) -> PatchResult` while retaining existing restore/verify behavior.

- [ ] Write tests for preview diff, process guard refusal, external modification refusal, and rollback after a partial write.
- [ ] Add a review screen showing file list, changed counts, warnings, and Apply/Cancel actions.
- [ ] Keep staged files outside the game root until explicit Apply.
- [ ] Run `pytest tests/test_patch_review.py -v` and the existing patch integrity suite.

### Task 6: OCR fallback profiles

**Files:**
- Modify: `linguaplay/ocr.py`
- Modify: `linguaplay/overlay_settings.py`
- Modify: `linguaplay/library_ui.py`
- Test: `tests/test_ocr_profiles.py`

**Interfaces:**
- Produces `OcrProfile` with capture rectangle, source language, polling interval, confidence threshold, and overlay profile id.
- Produces `OcrSession.start(profile)`, `.pause()`, and `.stop()`.

- [ ] Write tests for profile persistence, pause while settings are open, and OCR-only compatibility reports.
- [ ] Add per-game OCR profile selection and a calibration preview for the capture rectangle.
- [ ] Reuse the same glossary, memory, and offline translator pipeline as file patching.
- [ ] Run `pytest tests/test_ocr_profiles.py -v` and the existing Windows OCR fixture tests.

### Task 7: Adapter package format and validation

**Files:**
- Create: `linguaplay/adapter_packages.py`
- Modify: `linguaplay/adapters.py`
- Modify: `linguaplay/library_ui.py`
- Test: `tests/test_adapter_packages.py`

**Interfaces:**
- Produces `AdapterPackageManifest` with adapter id, game identifiers, version constraints, supported formats, and validation checksum.
- Produces `AdapterPackageValidator.validate(path, game_root) -> ValidationResult`.

- [ ] Write tests for valid packages, mismatched game versions, unsafe paths, and malformed manifests.
- [ ] Implement a signed-by-manifest-style integrity check and sandbox validation using temporary copies.
- [ ] Add import/export controls and mark imported adapters as user-provided.
- [ ] Run `pytest tests/test_adapter_packages.py -v` and confirm invalid packages cannot reach the patcher.

### Task 8: Release verification and portable packaging

**Files:**
- Modify: `README.md`
- Modify: `docs/verification.md`
- Modify: `build.ps1`
- Test: `tests/test_release_smoke.py`

**Interfaces:**
- Produces a portable build containing the application, OPUS-MT model, adapter metadata, and license notices.

- [ ] Write a smoke test covering library launch, pre-translate fixture, rollback, OCR fallback, and overlay settings.
- [ ] Build the clean PyInstaller package and verify it from a working directory outside the source tree.
- [ ] Run the full pytest suite, frozen diagnostic, ZIP CRC check, and SHA256 generation.
- [ ] Update README with the support matrix, offline behavior, rollback limits, and offline-game safety guidance.

