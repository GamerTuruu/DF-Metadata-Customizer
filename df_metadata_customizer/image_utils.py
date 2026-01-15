"""Image cache with optimized resizing for cover images."""

import hashlib
from collections import deque

import customtkinter as ctk
from PIL import Image


class LRUCTKImageCache:
    """Optimized cache for cover images with pre-resized versions."""

    def __init__(self, max_size: int = 100) -> None:
        """Initialize the image cache."""
        self.max_size = max_size
        self._path_hash_cache: dict[str, str] = {}  # Filepath to image hash
        self._image_hash_cache: dict[str, str] = {}  # Image hash to resized image hash
        self._ctkimage_cache: dict[str, ctk.CTkImage] = {}  # Resized hash to resized CTKImage
        self._access_order: deque[str] = deque()  # LRU with image hashes

    def get(self, key: str) -> ctk.CTkImage | None:
        """Get CTKImage from cache."""
        org_hash = self._path_hash_cache.get(key)
        if not org_hash:
            return None

        resized_hash = self._image_hash_cache.get(org_hash)
        if not resized_hash or resized_hash not in self._ctkimage_cache:
            return None

        # Update access order
        if org_hash in self._access_order:
            self._access_order.remove(org_hash)
        self._access_order.append(org_hash)

        return self._ctkimage_cache.get(resized_hash)

    def put(self, key: str, image: Image.Image | None, *, resize: bool = True) -> ctk.CTkImage | None:
        """Add image to cache and return CTKImage with LRU eviction."""
        if not image:
            return None

        org_hash = hashlib.sha256(image.tobytes()).hexdigest()
        self._path_hash_cache[key] = org_hash

        # Check if already cached
        res_hash = self._image_hash_cache.get(org_hash)
        if res_hash and res_hash in self._ctkimage_cache:
            if org_hash in self._access_order:
                self._access_order.remove(org_hash)
            self._access_order.append(org_hash)
            return self._ctkimage_cache[res_hash]

        # Process image
        processed_img = self.optimize_image_for_display(image) if resize else image
        if not processed_img:
            return None

        if processed_img.mode != "RGB":
            processed_img = processed_img.convert("RGB")

        new_res_hash = hashlib.sha256(processed_img.tobytes()).hexdigest()
        ctk_img = ctk.CTkImage(
            light_image=processed_img,
            size=(processed_img.width, processed_img.height),
        )

        self._image_hash_cache[org_hash] = new_res_hash
        self._ctkimage_cache[new_res_hash] = ctk_img

        if org_hash in self._access_order:
            self._access_order.remove(org_hash)
        self._access_order.append(org_hash)

        # Evict LRU if over size limit
        while len(self._access_order) > self.max_size:
            old_org_hash = self._access_order.popleft()
            old_res_hash = self._image_hash_cache.pop(old_org_hash, None)
            if old_res_hash:
                self._ctkimage_cache.pop(old_res_hash, None)

        return ctk_img

    def clear(self) -> None:
        """Clear the cache."""
        self._path_hash_cache.clear()
        self._image_hash_cache.clear()
        self._ctkimage_cache.clear()
        self._access_order.clear()

    def update_file_path(self, old_path: str, new_path: str) -> None:
        """Update the file path in the cache (e.g., if a file is renamed)."""
        if old_path in self._path_hash_cache:
            image_hash = self._path_hash_cache.pop(old_path)
            self._path_hash_cache[new_path] = image_hash

    @staticmethod
    def optimize_image_for_display(img: Image.Image | None) -> Image.Image | None:
        """Optimize image for fast display - resize to fit within square container."""
        if not img:
            return None

        # Target square size
        square_size = (170, 170)  # Can be edited to match your display size

        # Calculate the maximum size that fits within the square while maintaining aspect ratio
        img_ratio = img.width / img.height

        if img_ratio >= 1:
            # Landscape or square image - fit to width
            new_width = square_size[0]
            new_height = int(square_size[0] / img_ratio)
        else:
            # Portrait image - fit to height
            new_height = square_size[1]
            new_width = int(square_size[1] * img_ratio)

        # Resize the image to fit within the square container
        resized_img = img.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS,
        )  # TODO: Use NEAREST/HAMMING for future performance mode

        # Convert to RGB if necessary
        if resized_img.mode != "RGB":
            resized_img = resized_img.convert("RGB")

        return resized_img
