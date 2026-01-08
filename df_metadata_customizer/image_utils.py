"""Image cache with optimized resizing for cover images."""

import hashlib
from collections import deque

from PIL import Image


class LRUImageCache:
    """Optimized cache for cover images with pre-resized versions."""

    def __init__(self, max_size: int = 100) -> None:
        """Initialize the image cache."""
        self.max_size = max_size
        self._hash_cache: dict[str, str] = {}  # Filepath to image hash
        self._image_cache: dict[str, Image.Image] = {}  # Image hash to Image
        self._access_order: deque[str] = deque()  # LRU with image hashes

    def get(self, key: str) -> Image.Image | None:
        """Get image from cache, optionally resized."""
        image_hash = self._hash_cache.get(key)
        if not image_hash or image_hash not in self._image_cache:
            return None

        # Update access order
        if image_hash in self._access_order:
            self._access_order.remove(image_hash)
        self._access_order.append(image_hash)

        return self._image_cache.get(image_hash)

    def put(self, key: str, image: Image.Image | None, *, resize: bool = True) -> Image.Image | None:
        """Add image to cache with LRU eviction."""
        if resize:
            image = LRUImageCache.optimize_image_for_display(image)

        if not image:
            return None

        image_hash = hashlib.sha256(image.tobytes()).hexdigest()

        self._hash_cache[key] = image_hash

        if image_hash not in self._image_cache:
            self._image_cache[image_hash] = image

        if image_hash in self._access_order:
            self._access_order.remove(image_hash)

        self._access_order.append(image_hash)

        # Evict LRU if over size limit
        while len(self._image_cache) > self.max_size:
            oldest_key = self._access_order.popleft()
            del self._image_cache[oldest_key]

        return image

    def clear(self) -> None:
        """Clear the cache."""
        self._hash_cache.clear()
        self._image_cache.clear()
        self._access_order.clear()

    def update_file_path(self, old_path: str, new_path: str) -> None:
        """Update the file path in the cache (e.g., if a file is renamed)."""
        if old_path in self._hash_cache:
            image_hash = self._hash_cache.pop(old_path)
            self._hash_cache[new_path] = image_hash

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
