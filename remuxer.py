import ffmpeg
import os
from pathlib import Path
import subprocess
from time import perf_counter
from mutagen.id3 import ID3, COMM
from mutagen import File
import codecs

def remux_song(file_path: str, new_path: str) -> None:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", file_path,
                "-map_metadata", "0",
                "-c:a", "copy",
                "-write_xing", "1",
                new_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        if result.returncode != 0:
            print(f"Error: ffmpeg encountered an issue. Stderr: {result.stderr}")
            return
    except Exception as e:
        print("Error:", e)
        return

if __name__ == "__main__":
    from engraver import get_all_mp3, get_content_from_tags

    original_folder = r'C:\Users\Nyss\Downloads\ArchiveV3.4\old'
    new_folder = r"C:\Users\Nyss\Downloads\ArchiveV3.4\DISC 8 - Third Anniversary (2025-12-19 - Present)"
    all_files = get_all_mp3(original_folder)

    start = perf_counter()

    for file_path in all_files:

        tags = ID3(file_path)
        payload = get_content_from_tags(tags, "COMM::ved")
        comm = get_content_from_tags(tags, "COMM::eng")

        del tags

        rel_path = os.path.relpath(file_path, original_folder)
        new_path = os.path.join(new_folder, rel_path)

        os.makedirs(os.path.dirname(new_path), exist_ok=True)

        remux_song(file_path=file_path, new_path=new_path)

        if not os.path.isfile(new_path):
            print("File creation error!")
            break

        new_tags = ID3(new_path)

        new_tags.delall("TXXX")

        NEW_COMM_ENG_FRAME = COMM(encoding=2,lang='eng', desc='',text=[comm])
        new_tags.add(NEW_COMM_ENG_FRAME)

        NEW_COMM_VED_FRAME = COMM(encoding=3,lang='ved', desc='',text=[payload])
        new_tags.add(NEW_COMM_VED_FRAME)    

        new_tags.save()

    end = perf_counter()
    print(f"Runtime: {round(end - start, 2)} secs")
