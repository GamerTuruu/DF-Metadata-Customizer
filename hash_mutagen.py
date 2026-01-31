import xxhash
from mutagen.id3 import ID3, ID3NoHeaderError
from time import perf_counter

def get_all_mp3(directory: str) -> list[str]: 
    """
    Function to get all mp3 files from the folders.
    Although there were some mp4 and wav files in the drive
    only the mp3s were the target of my enquire.
    """
    p = Path(directory)
    return [(str(f)) for f in p.rglob('*.mp3') if f.is_file()]


def get_audio_hash(file_path):
    try:
        try:
            audio_tags = ID3(file_path)
            header_size = audio_tags.size  # Mutagen provides the full tag size including header
        except ID3NoHeaderError:
            header_size = 0

        with open(file_path, 'rb') as f:
            # We read the whole file to handle the footer check
            # For very large files, you can use f.seek() instead of loading everything
            file_data = f.read()

        # 2. Check for ID3v1 footer (always 128 bytes at the end starting with 'TAG')
        # Mutagen doesn't always expose the ID3v1 offset as a single property,
        # so a quick manual check of the last 128 bytes is still standard.
        footer_size = 128 if file_data[-128:].startswith(b'TAG') else 0
        
        # 3. Slice the data to extract only the audio frames
        # If footer_size is 0, file_data[header_size:] takes everything to the end
        end_index = len(file_data) - footer_size
        raw_audio = file_data[header_size:end_index]

        # 4. Hash the raw audio
        return xxhash.xxh64(raw_audio).hexdigest()

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

if __name__ == "__main__":
    songs = get_all_mp3(r'C:\Users\Nyss\Downloads\ArchiveV3.6')
    start = perf_counter()
    for song in songs:
        get_audio_hash(song)
    print(f"Runtime: {round(perf_counter() - start, 2)} second(s).\n {len(songs)} items processed.")