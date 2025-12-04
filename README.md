# DF — Metadata Customizer

> **Fan Tool Disclaimer**: This application is created by and for fans to help organize cover song collections. It only manages MP3 metadata and does not include any copyrighted content. Users must provide their audio files.

A powerful metadata management tool designed specifically for Neuro-sama and Evil Neuro cover song archives. This application helps standardize ID3 tags across large collections, extract embedded JSON metadata, and apply consistent formatting rules - making your cover song library organized and player-friendly.

![Screenshot](assets/mainscreen_dark3.png)
![Screenshot](assets/mainscreen_light3.png)
![Screenshot](assets/song_statistics2.png)

## 🎵 What This Tool Does
- Reads existing metadata from your MP3 files
- Applies custom formatting rules to ID3 tags  
- Helps maintain consistent naming across collections
- Manages multiple versions of the same cover
- Works with community-shared archive structures
- **NEW**: Advanced song statistics and categorization
- **NEW**: Enhanced multi-level sorting
- **NEW**: Play songs directly from the interface

## ❌ What This Tool Doesn't Do
- Provide or distribute copyrighted music
- Modify audio content
- Include any Neuro-sama/Evil Neuro songs

## Archive download (Google Drive)
   Download [Neuro Karaoke Archive V3.1](https://drive.google.com/drive/folders/1B1VaWp-mCKk15_7XpFnImsTdBJPOGx7a)

## ✨ Features

### Core Features
- 🎵 **MP3 Metadata Editing** - Read/write ID3 tags
- 🎨 **Modern UI** - CustomTkinter with dark/light theme support
- 📝 **Rule-Based Tagging** - Conditional rules for automatic metadata generation
- 🔍 **JSON in Comments** - Extract metadata from MP3 comment fields
- 🖼️ **Cover Art** - Display and manage album artwork
- 📚 **Version Management** - Track different versions of songs
- 💾 **Preset System** - Save and load rule configurations
- 🚀 **Batch Processing** - Apply changes to multiple files
- 🔄 **Cross-Platform** - Available as Python script or Windows EXE

### New in v2.0
- 📊 **Advanced Statistics** - Categorize songs by artist type (Neuro Solo, Evil Solo, Duets, Other)
- 🔢 **Multi-Level Sorting** - Sort by up to 5 different fields with ascending/descending options
- ▶️ **Direct Playback** - Double-click to play songs in your default player
- 📝 **JSON Editor** - Edit JSON metadata directly in the app with validation
- ✏️ **File Renaming** - Rename MP3 files directly from the interface
- 🔍 **Enhanced Search** - Version=latest filter and improved search operators
- 💫 **Performance Optimizations** - Faster loading, better cover art caching
- 🎯 **Improved Theme Handling** - Better contrast and stability

## Neuro-sama / Evil Neuro Use Case

This tool is perfect for managing cover songs from:
- **Neuro-sama** - The AI Vtuber's singing covers
- **Evil Neuro** - The chaotic alternative personality
- **Neuro & Evil Duets** - Collaborative covers

The app reads JSON metadata embedded in MP3 comment fields (common in fan archives) and lets you customize how the tags appear in music players.

## Installation

### Option 1: Python Script (All Platforms)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/GamerTuruu/DF-Metadata-Customizer.git
   cd DF-Metadata-Customizer
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
3. Run the application:
   ```bash
   python DF_Metadata_Customizer.py

### Option 2: Windows EXE (No Python Required)

1. Download the latest release from the Releases page

2. Run DF_Metadata_Customizer.exe - no installation required

## 📦 Downloads

### Latest Release
Get the ready-to-use Windows executable from the [Releases page](https://github.com/gamerturuu/df-metadata-customizer/releases).

### Source Code
Prefer to run from source? See [Installation](#installation) above.

## 🚀 Quick Download
[![Download EXE](https://img.shields.io/badge/Download-Windows_EXE-blue?style=for-the-badge)](https://github.com/gamerturuu/df-metadata-customizer/releases/latest)

## 📖 Quick Start

#### !!! IMPORTANT !!!
   📁metadata_presets.json📁
   have to be in same folder as main app (DF_Metadata_Customizer.exe or DF_Metadata_Customizer.py)

1. Load Your MP3 Files:
   Click "Select Folder" and choose your Neuro-sama cover song folder
   The app will scan for MP3 files and extract existing metadata
2. Understand the Data Structure:
   MP3 files should have JSON metadata in their comment fields
   Typical fields:
   ```bash
   Date, Title, Artist, CoverArtist, Version, Discnumber, Track, Comment, Special
3. Create Rules:
   Use the Title/Artist/Album tabs to create conditional rules
   Example: "IF CoverArtist is Neuro THEN Title = [Neuro] {Title}"
   Example: "IF CoverArtist is Evil THEN Title = [Evil] {Title}"
4. Apply Changes:
   Preview changes in the bottom panel
   Use "Apply to Selected" or "Apply to All" to save changes

## Advanced Features
### 📊 Song Statistics
#### Click the "📊 Show Statistics 📊" button to see detailed categorization:
   - Total songs and unique combinations
   - Neuro Solos (unique/total)
   - Evil Solos (unique/total)
   - Neuro & Evil Duets (unique/total)
   - Other songs (Neuro & Vedal, etc.)
#### 🔢 Multi-Level Sorting
   Add up to 5 sort rules with custom priorities:
   1. Primary sort (e.g., by Disc number)
   2. Secondary sort (e.g., by Track number)
   3. Tertiary sort (e.g., by Artist)
   - Each sort can be ascending or descending
   - Rules can be reordered using up/down arrows
#### 🔍 Advanced Search
   Use operators for precise filtering:
   - artist=neuro - Contains "neuro" in artist field
   - version=latest - Show only latest versions of each song
   - disc>=3 - Disc number 3 or higher
   - special=1 - Special tagged songs only
   - Combine with free text: neuro evil (finds songs containing both words)
#### 🎵 Direct Playback
   - Double-click any song in the list to play it with your system's default player
   - Works with Windows, macOS, and Linux

### 🔧 JSON Metadata Format
The app expects MP3 files to contain JSON in their comment field (example):
```bash
{
  "Title": "Original Song Name",
  "Artist": "Original Artist", 
  "CoverArtist": "Neuro",
  "Version": "2",
  "Discnumber": "01",
  "Track": "15",
  "Date": "2024",
  "Comment": "Additional notes"
  "Special": "0"
}
```
### 🎨 Theme Support
Toggle between dark and light themes using the ☀️/🌙 button in the top-right corner. The app remembers your preference.

### 💡 Tips & Tricks
#### Rule Building
   - Rules are evaluated top-to-bottom; first matching rule wins
   - Use "AND"/"OR" logic for complex conditions
   - Special operators: "is latest version", "is not latest version"
   - Template fields: {Title}, {Artist}, {CoverArtist}, {Version}, etc
#### Performance
   - The app caches cover art for faster loading
   - Use the "Select All" checkbox for batch operations
   - Statistics are calculated automatically when loading a folder
#### File Management
   - Rename files directly in the filename field
   - Edit JSON metadata directly with validation
   - Presets are saved in individual files in the "presets" folder
#### 🔧 Technical Details
   - Python 3.8+
   - customtkinter
   - Pillow (PIL)
   - mutagen
### 🙏 Acknowledgments
   - Created by and for the Neuro-sama fan community
   - Thanks to all contributors and testers
   - Special thanks to the [Nyss7](https://discord.com/channels/@me/1433267472496201778) and [mm2wood](https://discord.com/channels/@me/1406566620666794114)

### 🐛 Bug Reports & Feature Requests


Please use the [GitHub Issues](https://github.com/gamerturuu/df-metadata-customizer/issues) page to report bugs or request new features.


