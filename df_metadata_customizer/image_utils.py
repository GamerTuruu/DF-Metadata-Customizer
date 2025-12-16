"""Image cache with optimized resizing for cover images."""

from PIL import Image


class OptimizedImageCache:
    """Optimized cache for cover images with pre-resized versions."""

    def __init__(self, max_size: int = 100) -> None:
        self.max_size = max_size
        self._cache = {}
        self._access_order = []
        self._resized_cache = {}  # Cache for pre-resized images

    def get(self, key, size=None):
        """Get image from cache, optionally resized."""
        if key not in self._cache:
            return None

        # Update access order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

        img = self._cache[key]

        # Return pre-resized version if available and size matches
        if size:
            resize_key = f"{key}_{size[0]}_{size[1]}"
            if resize_key in self._resized_cache:
                return self._resized_cache[resize_key]

            # Create and cache resized version
            resized = self._resize_image_optimized(img, size)
            self._resized_cache[resize_key] = resized
            return resized

        return img

    def put(self, key, image):
        """Add image to cache with LRU eviction."""
        if key in self._cache:
            self._access_order.remove(key)

        self._cache[key] = image
        self._access_order.append(key)

        # Evict least recently used if over size limit
        while len(self._cache) > self.max_size:
            oldest_key = self._access_order.pop(0)
            # Also remove resized versions
            for resize_key in list(self._resized_cache.keys()):
                if resize_key.startswith(f"{oldest_key}_"):
                    del self._resized_cache[resize_key]
            del self._cache[oldest_key]

    def _resize_image_optimized(self, img, size):
        """Optimized image resizing with quality/speed balance."""
        if img.size == size:
            return img

        # Use faster resampling for better performance
        return img.resize(size, Image.Resampling.NEAREST)

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._resized_cache.clear()
        self._access_order.clear()

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
    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Convert to RGB if necessary
    if resized_img.mode != "RGB":
        resized_img = resized_img.convert("RGB")

    return resized_img
