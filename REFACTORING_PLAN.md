# MainWindow Refactoring Plan

## Overview
The current `main_window.py` contains 3488 lines with 105 methods in a single `MainWindow` class. This plan breaks it into 8 focused, reusable modules with clear responsibilities.

## Current State Analysis

### Method Categories (105 methods)
**Legend:** ← Used by | → Uses

---

## Proposed Module Structure

```
df_metadata_customizer/ui/
├── main_window.py          (refactored - 600 lines, orchestrator)
├── platform_utils.py       ✅ (already exists)
├── styles.py               ✅ (already exists)
├── window_manager.py        (NEW - 350 lines)
├── tree_view_manager.py     (NEW - 400 lines)
├── search_sort_manager.py   (NEW - 450 lines)
├── rules_manager.py         (NEW - 500 lines)
├── preset_manager.py        (NEW - 450 lines)
├── metadata_editor.py       (NEW - 350 lines)
├── file_operations.py       (NEW - 300 lines)
├── cover_manager.py         (NEW - 200 lines)
└── theme_settings.py        (NEW - 250 lines)
```

---

## Detailed Module Breakdown

### 1. **window_manager.py** (NEW) - Window lifecycle & UI setup
**Purpose:** Window initialization, lifecycle, preferences, and theme management

**Methods (15):**
- `__init__()` - Initialization
- `center_window()` - Center window on screen
- `keyPressEvent()` - Keyboard shortcuts (Ctrl+F)
- `eventFilter()` - Event handling (ESC in search)
- `_setup_ui()` - Build main layout
- `_setup_menubar()` - Menu bar setup
- `_apply_theme_from_system()` - Apply system theme
- `_apply_ui_scale()` - UI scaling
- `_apply_theme()` - Theme application
- `show_preferences()` - Preferences dialog
- `_save_preferences()` - Save preferences
- `_reset_all_settings()` - Reset to defaults
- `show_about()` - About dialog
- `closeEvent()` - Handle window close
- `save_settings()` / `load_settings()` - Persistence

**Dependencies:**
- Imports: PyQt6, SettingsManager
- Uses: styles.py, platform_utils.py
- Used by: main_window.py (MainWindow.__init__)

**Data Structures:**
```python
class WindowConfig:
    window_title: str = "Database Formatter — Metadata Customizer"
    default_width: int = 1280
    default_height: int = 720
    min_width: int = 960
    min_height: int = 540
```

---

### 2. **tree_view_manager.py** (NEW) - Tree widget operations
**Purpose:** Tree view creation, rendering, and interaction

**Methods (10):**
- `_create_tree_view()` - Tree initialization
- `populate_tree()` - Populate with song data
- `on_column_moved()` - Column reordering
- `on_tree_current_item_changed()` - Keyboard nav
- `on_tree_item_clicked()` - Single click
- `on_tree_item_double_clicked()` - Double click (play)
- `on_tree_right_click()` - Context menu
- `on_tree_selection_changed()` - Selection handling
- `update_selection_info()` - Update selection label
- `toggle_select_all()` - Select/deselect all

**Context Menu Operations (5):**
- `play_file()` - Open file
- `copy_metadata()` - Copy all metadata
- `copy_field_value()` - Copy single field
- `copy_all_metadata()` - Copy selected
- `goto_file_location()` - Open in file manager

**Dependencies:**
- Imports: PyQt6, Path
- Uses: platform_utils.py
- Used by: main_window.py, search_sort_manager.py

**Data Structure:**
```python
class TreeColumn(Enum):
    TITLE = "Title"
    ARTIST = "Artist"
    COVER_ARTIST = "Cover Artist"
    VERSION = "Version"
    DATE = "Date"
    DISC = "Disc"
    TRACK = "Track"
    FILE = "File"
    SPECIAL = "Special"
```

---

### 3. **search_sort_manager.py** (NEW) - Filtering & sorting
**Purpose:** Advanced search and multi-level sorting

**Search Methods (15):**
- `on_search_changed()` - Main search handler
- `_parse_search_value()` - Parse quoted values
- `_get_numeric_value_for_search()` - Extract numbers
- `_is_latest_version_match()` - Version matching
- Operator handlers: `==`, `!=`, `>`, `<`, `>=`, `<=`, `=` (contains)

**Sort Methods (10):**
- `_create_sort_controls()` - UI setup
- `_add_sort_rule_widget()` - Add sort rule UI
- `add_sort_rule()` - Add new rule
- `remove_sort_rule()` - Remove rule
- `move_sort_rule_up/down()` - Reorder rules
- `_rebuild_sort_ui()` - Rebuild after reorder
- `_update_sort_button_states()` - Button state mgmt
- `on_sort_changed()` - Apply multi-level sort

**Helper Classes:**
```python
class SortRule:
    field: str
    ascending: bool

class ReverseStr(str):  # For descending string sort
    ...
```

**Dependencies:**
- Imports: PyQt6, re
- Uses: MetadataFields
- Used by: main_window.py, tree_view_manager.py

---

### 4. **rules_manager.py** (NEW) - Rule builder & application
**Purpose:** Rule editing, matching, and metadata transformation

**Rule Building (7):**
- `add_rule_to_tab()` - Add rule row
- `delete_rule()` - Remove rule
- `move_rule_up/down()` - Reorder
- `update_rule_button_states()` - Button mgmt
- `collect_rules_for_tab()` - Extract rules
- `load_rules_to_tab()` - Load rules
- `_create_rules_tab()` - UI setup

**Rule Execution (4):**
- `_rule_matches()` - Check if rule condition met
- `_render_template()` - Process {field} substitution
- `_apply_rules_to_metadata()` - Apply all rules
- `_build_id3_metadata()` - Build output tags

**Helpers (3):**
- `_extract_numeric_value()` - For sorting mixed numbers
- Supporting template functions

**Dependencies:**
- Imports: PyQt6, json, re
- Uses: RuleRow, RuleManager, MetadataFields, song_utils
- Used by: main_window.py, preset_manager.py

**Data Structures:**
```python
class RuleData:
    tab: str  # "title", "artist", "album"
    logic: str  # "AND", "OR"
    if_field: str
    if_operator: str
    if_value: str
    then_template: str
    is_first: bool
```

---

### 5. **preset_manager.py** (NEW) - Preset operations
**Purpose:** Preset CRUD and application

**Preset Operations (7):**
- `_load_presets()` - Load available presets
- `on_preset_selected()` - Load preset
- `create_new_preset()` - Create new
- `delete_preset()` - Remove preset
- `save_preset()` - Save current rules
- `apply_preset_to_selected()` - Apply to selection
- `apply_preset_to_all()` - Apply to all files

**UI Creation (2):**
- `_create_preset_controls()` - Preset combo & buttons
- `_create_apply_buttons()` - Apply buttons

**Dependencies:**
- Imports: PyQt6, json
- Uses: PresetService, RuleManager, rules_manager
- Used by: main_window.py

---

### 6. **metadata_editor.py** (NEW) - Metadata editing interface
**Purpose:** Edit individual file metadata and preview

**Preview & Display (2):**
- `update_preview_info()` - Update preview with rules
- `_create_song_edit_tab()` - Editor UI
- `_create_status_bar()` - Status bar

**JSON Editing (2):**
- `on_json_changed()` - Enable save button
- `save_json_changes()` - Persist changes

**Filename Editing (2):**
- `on_filename_changed()` - Track changes
- `save_filename_changes()` - Rename file
- `rename_current_file()` - Interactive rename

**Navigation (2):**
- `prev_file()` - Previous file
- `next_file()` - Next file

**Status (2):**
- `update_preview_info()` - Detailed preview calculation
- `_create_status_bar()` - Load status display

**Dependencies:**
- Imports: PyQt6, json
- Uses: song_utils, MetadataFields
- Used by: main_window.py

---

### 7. **file_operations.py** (NEW) - Folder & file handling
**Purpose:** File loading, folder navigation, stats

**Folder Operations (3):**
- `open_folder()` - Dialog to select folder
- `load_folder()` - Load files from folder
- `check_last_folder()` - Auto-load last

**Statistics (1):**
- `show_statistics()` - Display file stats

**Dependencies:**
- Imports: PyQt6, Path
- Uses: FileManager, ProgressDialog
- Used by: main_window.py

---

### 8. **cover_manager.py** (NEW) - Album art handling
**Purpose:** Load and manage cover images

**Cover Operations (2):**
- `load_cover_image()` - Load and display cover
- `change_cover_image()` - Replace cover art

**Dependencies:**
- Imports: PyQt6, PIL, mutagen
- Uses: song_utils, Path
- Used by: main_window.py

**Data Structure:**
```python
class CoverConfig:
    display_size: tuple = (180, 180)
    fallback_text: str = "No cover"
```

---

## Dependency Graph

```
Platform Layer:
├─ platform_utils.py ✅ (standalone)
├─ styles.py ✅ (standalone)
└─ theme_settings.py (NEW) - extends styles.py

Core Business Logic:
├─ file_operations.py
│  └─ uses: FileManager, ProgressDialog
├─ rules_manager.py
│  └─ uses: RuleManager, MetadataFields, song_utils
├─ search_sort_manager.py
│  └─ uses: MetadataFields, rules_manager, file_operations
└─ preset_manager.py
   └─ uses: PresetService, rules_manager

UI Component Layer:
├─ window_manager.py (standalone theme/window)
├─ tree_view_manager.py
│  └─ uses: platform_utils.py
├─ metadata_editor.py
│  └─ uses: rules_manager, song_utils
└─ cover_manager.py
   └─ uses: song_utils

Orchestration Layer:
└─ main_window.py (MainWindow class)
   └─ uses: ALL of the above
```

## Import Order (for circular dependency safety)

```python
# In main_window.py:
from .platform_utils import open_file_with_default_app, open_folder_with_file_manager
from .styles import apply_dark_theme, apply_light_theme
from .theme_settings import ThemeManager

from .window_manager import WindowManager
from .file_operations import FileOperations
from .tree_view_manager import TreeViewManager
from .search_sort_manager import SearchSortManager
from .rules_manager import RulesManager
from .preset_manager import PresetManager
from .metadata_editor import MetadataEditor
from .cover_manager import CoverManager
```

---

## Migration Strategy

### Phase 1: Extract Non-Interactive Classes
1. **theme_settings.py** - Move theme logic from window_manager
2. **cover_manager.py** - Move cover image logic
3. **file_operations.py** - Move folder/file I/O

### Phase 2: Extract Managers
4. **tree_view_manager.py** - Tree manipulation
5. **search_sort_manager.py** - Search & sort
6. **rules_manager.py** - Rule operations
7. **preset_manager.py** - Preset CRUD

### Phase 3: Extract UI Components
8. **window_manager.py** - Window lifecycle
9. **metadata_editor.py** - Editor interface

### Phase 4: Refactor MainWindow
10. **main_window.py** - Compose all managers

---

## Benefits of This Structure

| Aspect | Current | After |
|--------|---------|-------|
| **File Size** | 3488 lines | 600 lines (main) + 10 × 200-500 line modules |
| **Class Methods** | 105 in one class | 8-15 per module |
| **Cohesion** | Low (mixed concerns) | High (single responsibility) |
| **Testability** | Difficult | Easy (isolated modules) |
| **Reusability** | Low | High |
| **Maintainability** | Low | High |
| **Documentation** | Hard to navigate | Clear module boundaries |

---

## Testing Strategy

Each module can be tested independently:
- **window_manager**: Theme switching, settings persistence
- **tree_view_manager**: Rendering, selection, context menu
- **search_sort_manager**: Filter logic, sort operations
- **rules_manager**: Rule matching, template rendering
- **preset_manager**: CRUD, application logic
- **metadata_editor**: Preview generation, file edits
- **file_operations**: Folder loading, statistics
- **cover_manager**: Image loading, writing

---

## Implementation Checklist

- [ ] Create theme_settings.py
- [ ] Create cover_manager.py
- [ ] Create file_operations.py
- [ ] Create tree_view_manager.py
- [ ] Create search_sort_manager.py
- [ ] Create rules_manager.py
- [ ] Create preset_manager.py
- [ ] Create metadata_editor.py
- [ ] Create window_manager.py
- [ ] Refactor main_window.py to compose managers
- [ ] Update imports in __init__.py
- [ ] Test all modules
- [ ] Update documentation
