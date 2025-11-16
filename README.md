# DF — Metadata Customizer

> **Fan Tool Disclaimer**: This application is created by and for fans to help organize cover song collections. It only manages MP3 metadata and does not include any copyrighted content. Users must provide their audio files.

A powerful metadata management tool designed specifically for Neuro-sama and Evil Neuro cover song archives. This application helps standardize ID3 tags across large collections, extract embedded JSON metadata, and apply consistent formatting rules - making your cover song library organized and player-friendly.

![Screenshot](assets/mainscreen_dark.png)
![Screenshot](assets/mainscreen_light.png)

## 🎵 What This Tool Does
- Reads existing metadata from your MP3 files
- Applies custom formatting rules to ID3 tags  
- Helps maintain consistent naming across collections
- Manages multiple versions of the same cover
- Works with community-shared archive structures

## ❌ What This Tool Doesn't Do
- Provide or distribute copyrighted music
- Modify audio content
- Include any Neuro-sama/Evil Neuro songs

## ✨ Features

- 🎵 **MP3 Metadata Editing** - Read/write ID3 tags
- 🎨 **Modern UI** - CustomTkinter with dark/light theme support
- 📝 **Rule-Based Tagging** - Conditional rules for automatic metadata generation
- 🔍 **JSON in Comments** - Extract metadata from MP3 comment fields
- 🖼️ **Cover Art** - Display and manage album artwork
- 📚 **Version Management** - Track different versions of songs
- 💾 **Preset System** - Save and load rule configurations
- 🚀 **Batch Processing** - Apply changes to multiple files
- 🔄 **Cross-Platform** - Available as Python script or Windows EXE

## Neuro-sama / Evil Neuro Use Case

This tool is perfect for managing cover songs from:
- **Neuro-sama** - The AI Vtuber's singing covers
- **Evil Neuro** - The chaotic alternative personality

The app reads JSON metadata embedded in MP3 comment fields (common in fan archives) and lets you customize how the tags appear in music players.

## 🚀 Installation

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

1. Load Your MP3 Files:
   Click "Select Folder" and choose your Neuro-sama cover song folder
   The app will scan for MP3 files and extract existing metadata
2. Understand the Data Structure:
   MP3 files should have JSON metadata in their comment fields
   Typical fields:
   ```bash
   Date, Title, Artist, CoverArtist, Version, Discnumber, Track, Comment
#### !!! IMPORTANT !!!
   📁metadata_presets.json📁
   have to be in same folder as main app (DF_Metadata_Customizer.exe or DF_Metadata_Customizer.py)
3. Create Rules:
   Use the Title/Artist/Album tabs to create conditional rules
   Example: "IF CoverArtist is not empty THEN Title = {CoverArtist} - {Title}"
4. Apply Changes:
   Preview changes in the bottom panel
   Use "Apply to Selected" or "Apply to All" to save changes

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
}