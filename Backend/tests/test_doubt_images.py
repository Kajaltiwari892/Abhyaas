import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from app.services.doubt_images import MAX_IMAGE_BYTES, MAX_REQUEST_BYTES, normalize_image


def image_data(size: tuple[int, int] = (300, 100), *, metadata: bool = False) -> str:
    image = Image.new("RGB", size, "white")
    info = PngImagePlugin.PngInfo()
    if metadata:
        info.add_text("private-note", "Remove this metadata")
    out = io.BytesIO()
    image.save(out, format="PNG", pnginfo=info)
    return base64.b64encode(out.getvalue()).decode()


def test_normalization_strips_metadata_and_bounds_dimensions() -> None:
    cleaned = normalize_image(image_data((2400, 1000), metadata=True), "image/png")
    with Image.open(io.BytesIO(base64.b64decode(cleaned))) as result:
        assert result.format == "JPEG"
        assert result.width == 1800
        assert "private-note" not in result.info


@pytest.mark.parametrize("data,mime", [
    ("!!!!", "image/png"),
    (base64.b64encode(b"not an image").decode(), "image/png"),
    (image_data(), "image/jpeg"),
    (image_data((4000, 3100)), "image/png"),
    (image_data((7000, 20)), "image/png"),
    (image_data((10, 10)), "image/png"),
    (base64.b64encode(b"x" * (MAX_IMAGE_BYTES + 1)).decode(), "image/png"),
], ids=["bad-base64", "not-image", "wrong-type", "too-many-pixels", "too-wide", "too-small",
        "too-many-bytes"])
def test_reject_invalid_mislabeled_oversized_or_unreadable_images(data: str, mime: str) -> None:
    with pytest.raises(ValueError):
        normalize_image(data, mime)


def test_reject_animated_png() -> None:
    out = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(
        out, format="PNG", save_all=True,
        append_images=[Image.new("RGB", (32, 32), "black")], duration=100, loop=0,
    )
    with pytest.raises(ValueError, match="Animated"):
        normalize_image(base64.b64encode(out.getvalue()).decode(), "image/png")


def test_request_limit_rejects_declared_and_streamed_oversize(client: TestClient) -> None:
    response = client.post("/api/v1/doubts/ask", content=b"{}", headers={
        "Content-Length": str(MAX_REQUEST_BYTES + 1), "Origin": "http://localhost:3000",
    })
    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    streamed = client.post(
        "/api/v1/doubts/ask", content=iter([b"x" * (MAX_REQUEST_BYTES // 2)] * 3)
    )
    assert streamed.status_code == 413
