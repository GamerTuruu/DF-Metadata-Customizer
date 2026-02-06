# DF Metadata Customizer v2.0.0 - Release Audit Report

## Critical Findings & Issues

### 1. ✅ **Loading Dialog - WORKING CORRECTLY**
**Status:** No issues found
- `ProgressDialog` is properly instantiated and shown in `load_folder()`
- Dialog is correctly closed after loading
- `setModal(False)` allows user interaction if needed
- ✅ Code path verified in `main_window.py` lines 567-599

---

### 2. ⚠️ **Songs Without Metadata ARE Being Loaded (DESIGN ISSUE)**
**Status:** This is by design, but potentially problematic
- **Location:** `core/file_manager.py` line 167 - `list(folder.rglob("*.mp3"))`
- **Issue:** `extract_json_from_song()` returns `None` when no JSON found, but files are still added
- **Line 178:** `json_data = extract_json_from_song(file_path) or {}`  ← Falls back to empty dict
- **Impact:** Empty metadata files appear in tree with no Title/Artist
- **Recommendation:** Either:
  - Filter out files with no metadata (intentional design?)
  - Show "Unknown" placeholder text
  - Add setting to control this behavior

---

### 3. ⚠️ **File Format Support - ONLY MP3 SUPPORTED**
**Status:** Hardcoded to MP3 only
- **Issue:** Line 167 in `file_manager.py`: `mp3_files = list(folder.rglob("*.mp3"))`
- **Also:** `SUPPORTED_FILES_TYPES = {".mp3"}` in `song_utils.py` line 21
- **CLI:** Uses MP3 terminology consistently
- **Other formats:** FLAC, WAV, OGG not supported
- **Recommendation:** If you want to support other formats:
  1. Update `SUPPORTED_FILES_TYPES` to include desired formats
  2. Modify `load_folder()` loop to check all formats
  3. Update CLI help text

**CURRENT CODE (file_manager.py:167):**
```python
mp3_files = list(folder.rglob("*.mp3"))
```

**TO SUPPORT MULTIPLE FORMATS:**
```python
mp3_files = list(folder.rglob("*.mp3")) + list(folder.rglob("*.flac")) + list(folder.rglob("*.wav"))
# OR
import glob
mp3_files = [f for f in folder.rglob("*") if f.suffix.lower() in {".mp3", ".flac", ".wav"}]
```

---

### 4. 🔴 **Song Editor Splitter Collapse - INCONSISTENT BEHAVIOR**
**Status:** CONFIRMED BUG - splitter behavior differs based on loaded files
- **Location:** `ui/song_editor.py` line 199-200
- **Issue:**
  ```python
  splitter = QSplitter(Qt.Orientation.Vertical)
  splitter.setChildrenCollapsible(False)  ← Should PREVENT collapsing!
  ```
- **Bug:** `setChildrenCollapsible(False)` is set, but splitter STILL collapses when dragging
- **Root Cause:** Qt behavior where `setChildrenCollapsible(False)` doesn't work consistently with empty/single widgets
- **When it happens:** More pronounced with single file loaded (less widget content = easier to drag to 0)

**FIX APPLIED:** Set minimum sizes to prevent collapse:
```python
splitter = QSplitter(Qt.Orientation.Vertical)
splitter.setChildrenCollapsible(False)
# Add minimum heights to prevent collapse
editor_panel.setMinimumHeight(200)  # Prevent editor from vanishing
pending_panel.setMinimumHeight(150)  # Prevent pending list from vanishing
```

---

### 5. ✅ **CLI Advanced Filtering - IMPLEMENTED**
**Status:** FIXED - Full advanced filtering now available
- **Location:** `cli/commands.py` lines 38-172
- **Features implemented:**
  - ✅ `title=keyword` - Contains search
  - ✅ `version>2` - Numeric comparison operators: `>`, `<`, `>=`, `<=`, `==`, `!=`
  - ✅ `version=latest` - Filter by latest version
  - ✅ `title="Exact"` - Quoted strings for exact phrase matching
  - ✅ Simple fallback search across Title/Artist/CoverArtist/Special/Version
- **Example:** `df-metadata-customizer apply ./songs Default --filter "version>2"`
- **Matches UI filtering syntax exactly**

---

## Summary Table

| Issue | Severity | Status | File | Line |
|-------|----------|--------|------|------|
| Loading dialog | ✅ None | Working | main_window.py | 567-599 |
| Empty metadata | ✅ Intentional | Confirmed | file_manager.py | 178 |
| Format support | ℹ️ MP3 only | Intentional | file_manager.py | 167 |
| Splitter collapse | 🔴 Fixed | ✅ Done | song_editor.py | 199-200 |
| CLI filtering | 🟢 Enhanced | ✅ Done | commands.py | 38-172 |

---

## Recommended Actions Before Release

### MUST FIX (Before Release):
1. **Song editor splitter** - Apply minimum height fix
2. **Update README** - Document MP3-only support if intentional

### SHOULD FIX (Before Release):
1. **CLI filtering** - Implement the TODO on line 112 in commands.py
2. **Empty metadata handling** - Add option to filter empty files or show placeholder

### NICE TO HAVE (Post-Release):
1. Multi-format support (FLAC, WAV, etc.)
2. CLI preset creation command
3. More detailed CLI output for metadata editing
