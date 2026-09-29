"""Cap body buffering and concurrent expensive requests, including chunked bodies."""

import asyncio

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.doubt_images import MAX_REQUEST_BYTES


class DoubtRequestLimits:
    def __init__(self, app: ASGIApp, path: str) -> None:
        self.app = app
        self.path = path
        self.active = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != self.path:
            await self.app(scope, receive, send)
            return
        if self.active >= 4:
            await JSONResponse(
                {"detail": "The tutor is busy. Please try again shortly."}, status_code=503
            )(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = MAX_REQUEST_BYTES + 1
        if declared > MAX_REQUEST_BYTES:
            await self.too_large(scope, receive, send)
            return
        self.active += 1
        try:
            body = bytearray()
            try:
                async with asyncio.timeout(15):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        piece = message.get("body", b"")
                        if len(body) + len(piece) > MAX_REQUEST_BYTES:
                            await self.too_large(scope, receive, send)
                            return
                        body.extend(piece)
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                await JSONResponse(
                    {"detail": "Upload timed out. Try a smaller image."}, status_code=408
                )(scope, receive, send)
                return
            delivered = False

            async def bounded_receive() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self.app(scope, bounded_receive, send)
        finally:
            self.active -= 1

    @staticmethod
    async def too_large(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse(
            {"detail": "This upload is too large. Attach one image no larger than 4 MB."},
            status_code=413,
        )(scope, receive, send)
