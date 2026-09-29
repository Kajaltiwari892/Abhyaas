"""Bounded image decoding; no uploaded image is written to disk or the database."""

import base64
import binascii
import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_IMAGE_PIXELS = 12_000_000
MAX_IMAGE_EDGE = 6000
MAX_REQUEST_BYTES = 6 * 1024 * 1024
IMAGE_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def normalize_image(data: str, mime_type: str) -> str:
    """Verify bytes and dimensions before decoding; flatten and strip all metadata."""
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("The image could not be read. Attach a valid JPG, PNG or WebP.") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Images must be no larger than 4 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as probe:
                if IMAGE_FORMATS.get(probe.format) != mime_type:
                    raise ValueError("The image contents must match its JPG, PNG or WebP type.")
                if getattr(probe, "n_frames", 1) != 1:
                    raise ValueError("Animated images are not supported. Use a still image.")
                width, height = probe.size
                if width * height > MAX_IMAGE_PIXELS or max(width, height) > MAX_IMAGE_EDGE:
                    raise ValueError("Use an image under 12 megapixels and 6000 pixels per side.")
                if min(width, height) < 16:
                    raise ValueError("The image is too small to read. Use a clearer screenshot.")
                probe.verify()
            with Image.open(io.BytesIO(raw)) as original:
                oriented = ImageOps.exif_transpose(original)
                oriented.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
                rgba = oriented.convert("RGBA")
                clean = Image.new("RGB", rgba.size, "white")
                clean.paste(rgba, mask=rgba.getchannel("A"))
                buffer = io.BytesIO()
                clean.save(buffer, format="JPEG", quality=90)
                return base64.b64encode(buffer.getvalue()).decode("ascii")
    except (UnidentifiedImageError, OSError, SyntaxError,
            Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ValueError(
            "The image is damaged or too large to process. Try another image."
        ) from exc
