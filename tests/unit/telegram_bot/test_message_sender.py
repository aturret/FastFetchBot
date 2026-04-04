"""Tests for apps/telegram-bot/core/services/message_sender.py

Covers exception handling, the telegram_file_id shortcut in media_files_packaging,
and the background file_id capture wiring.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMediaFilesPackagingDownloadFailure:
    """Test that download failures in media_files_packaging are caught and skipped."""

    @pytest.mark.asyncio
    async def test_http_download_failure_skips_media(self):
        from core.services.message_sender import media_files_packaging

        media_files = [
            {"media_type": "image", "url": "https://example.com/img.jpg", "caption": ""},
        ]
        data = {
            "url": "https://example.com",
            "category": "twitter",
            "message_type": "short",
        }

        with patch(
            "core.services.message_sender.download_file_by_metadata_item",
            new_callable=AsyncMock,
            side_effect=RuntimeError("network error"),
        ):
            media_group, file_group, uncached = await media_files_packaging(media_files, data)

        # Media item should be skipped, not crash
        assert media_group == []
        assert file_group == []

    @pytest.mark.asyncio
    async def test_gif_download_failure_skips_media(self):
        from core.services.message_sender import media_files_packaging

        media_files = [
            {"media_type": "gif", "url": "https://example.com/anim.gif", "caption": ""},
        ]
        data = {
            "url": "https://example.com",
            "category": "twitter",
            "message_type": "short",
        }

        with patch(
            "core.services.message_sender.download_file_by_metadata_item",
            new_callable=AsyncMock,
            side_effect=ConnectionError("timeout"),
        ):
            media_group, file_group, uncached = await media_files_packaging(media_files, data)

        assert media_group == []
        assert file_group == []

    @pytest.mark.asyncio
    async def test_image_document_download_failure_skips(self):
        """Test the second download_file_by_metadata_item call for large image documents."""
        from core.services.message_sender import media_files_packaging

        mock_io = MagicMock()
        mock_io.name = "media-abc.jpg"
        mock_io.size = 15 * 1024 * 1024  # 15MB, over image size limit to trigger document path

        mock_image = MagicMock()
        mock_image.size = (5000, 5000)  # large image to trigger document download
        mock_image.width = 5000
        mock_image.height = 5000

        call_count = [0]

        async def download_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_io
            raise RuntimeError("second download failed")

        media_files = [
            {"media_type": "image", "url": "https://example.com/big.jpg", "caption": ""},
        ]
        data = {
            "url": "https://example.com",
            "category": "twitter",
            "message_type": "short",
        }

        with patch(
            "core.services.message_sender.download_file_by_metadata_item",
            new_callable=AsyncMock,
            side_effect=download_side_effect,
        ), patch(
            "core.services.message_sender.check_image_type",
            new_callable=AsyncMock,
            return_value="jpg",
        ), patch(
            "core.services.message_sender.Image"
        ) as MockImage, patch(
            "core.services.message_sender.image_compressing",
            return_value=mock_image,
        ), patch(
            "core.services.message_sender.settings"
        ) as mock_settings:
            MockImage.open.return_value = mock_image
            mock_settings.TELEBOT_API_SERVER = None
            mock_settings.TELEGRAM_IMAGE_DIMENSION_LIMIT = 2000
            mock_settings.TELEGRAM_IMAGE_SIZE_LIMIT = 10 * 1024 * 1024  # 10MB

            media_group, file_group, uncached = await media_files_packaging(media_files, data)

        # The image media_group should have the photo, but file_group should be empty
        # because the document download failed and was skipped
        assert file_group == []


# ---------------------------------------------------------------------------
# file_id shortcut in media_files_packaging
# ---------------------------------------------------------------------------


class TestMediaFilesPackagingFileIdShortcut:
    """Test that media_files_packaging uses telegram_file_id when available."""

    @pytest.mark.asyncio
    async def test_uses_file_id_for_image(self):
        from core.services.message_sender import media_files_packaging
        from telegram import InputMediaPhoto

        media_files = [
            {
                "media_type": "image",
                "url": "https://img.com/1.jpg",
                "telegram_file_id": "AgACAgI123",
            },
        ]
        data = {"url": "https://example.com", "category": "twitter", "message_type": "short"}

        media_group, file_group, uncached = await media_files_packaging(media_files, data)

        assert len(media_group) == 1
        assert len(media_group[0]) == 1
        # file_id was used — no download should have been attempted
        assert uncached == [None]

    @pytest.mark.asyncio
    async def test_uses_file_id_for_video(self):
        from core.services.message_sender import media_files_packaging

        media_files = [
            {
                "media_type": "video",
                "url": "https://vid.com/v.mp4",
                "telegram_file_id": "BAACAgI456",
            },
        ]
        data = {"url": "https://example.com", "category": "twitter", "message_type": "short"}

        media_group, file_group, uncached = await media_files_packaging(media_files, data)

        assert len(media_group) == 1
        assert len(media_group[0]) == 1
        assert uncached == [None]

    @pytest.mark.asyncio
    async def test_uses_file_id_for_gif(self):
        from core.services.message_sender import media_files_packaging

        media_files = [
            {
                "media_type": "gif",
                "url": "https://img.com/anim.gif",
                "telegram_file_id": "CgACAgI789",
            },
        ]
        data = {"url": "https://example.com", "category": "twitter", "message_type": "short"}

        media_group, file_group, uncached = await media_files_packaging(media_files, data)

        assert len(media_group) == 1
        assert uncached == [None]

    @pytest.mark.asyncio
    async def test_uses_file_id_for_document(self):
        from core.services.message_sender import media_files_packaging

        media_files = [
            {
                "media_type": "document",
                "url": "https://example.com/doc.pdf",
                "telegram_file_id": "BQACAgI000",
            },
        ]
        data = {"url": "https://example.com", "category": "twitter", "message_type": "short"}

        media_group, file_group, uncached = await media_files_packaging(media_files, data)

        assert len(file_group) == 1
        assert uncached == [None]

    @pytest.mark.asyncio
    async def test_no_download_when_file_id_present(self):
        """Verify that download_file_by_metadata_item is NOT called for cached items."""
        from core.services.message_sender import media_files_packaging

        media_files = [
            {
                "media_type": "image",
                "url": "https://img.com/1.jpg",
                "telegram_file_id": "AgACAgI123",
            },
        ]
        data = {"url": "https://example.com", "category": "twitter", "message_type": "short"}

        with patch(
            "core.services.message_sender.download_file_by_metadata_item",
            new_callable=AsyncMock,
        ) as mock_download:
            await media_files_packaging(media_files, data)

        mock_download.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_uncached_info_for_downloaded_items(self):
        """Items without file_id should appear in uncached_media_info."""
        from core.services.message_sender import media_files_packaging

        mock_io = MagicMock()
        mock_io.name = "video.mp4"
        mock_io.size = 1024

        media_files = [
            {
                "media_type": "video",
                "url": "https://vid.com/v.mp4",
            },
        ]
        data = {"url": "https://example.com", "category": "twitter", "message_type": "short"}

        with patch(
            "core.services.message_sender.download_file_by_metadata_item",
            new_callable=AsyncMock,
            return_value=mock_io,
        ), patch(
            "core.services.message_sender.settings"
        ) as mock_settings:
            mock_settings.TELEBOT_API_SERVER = "http://local:8081/bot"
            media_group, file_group, uncached = await media_files_packaging(media_files, data)

        assert len(uncached) == 1
        assert uncached[0] is not None
        assert uncached[0]["url"] == "https://vid.com/v.mp4"
        assert uncached[0]["media_type"] == "video"

    @pytest.mark.asyncio
    async def test_mixed_cached_and_uncached(self):
        """Test a mix of items with and without file_ids."""
        from core.services.message_sender import media_files_packaging

        mock_io = MagicMock()
        mock_io.name = "video.mp4"
        mock_io.size = 1024

        media_files = [
            {
                "media_type": "image",
                "url": "https://img.com/1.jpg",
                "telegram_file_id": "AgACAgI123",
            },
            {
                "media_type": "video",
                "url": "https://vid.com/v.mp4",
                # no telegram_file_id — will be downloaded
            },
        ]
        data = {"url": "https://example.com", "category": "twitter", "message_type": "short"}

        with patch(
            "core.services.message_sender.download_file_by_metadata_item",
            new_callable=AsyncMock,
            return_value=mock_io,
        ), patch(
            "core.services.message_sender.settings"
        ) as mock_settings:
            mock_settings.TELEBOT_API_SERVER = "http://local:8081/bot"
            media_group, file_group, uncached = await media_files_packaging(media_files, data)

        assert len(media_group) == 1  # one group with 2 items
        assert len(media_group[0]) == 2
        assert len(uncached) == 2
        assert uncached[0] is None  # cached
        assert uncached[1] is not None  # downloaded
        assert uncached[1]["media_type"] == "video"

    @pytest.mark.asyncio
    async def test_file_id_skips_even_for_long_messages(self):
        """file_id check is above the message_type guard, so it works for long messages too."""
        from core.services.message_sender import media_files_packaging

        media_files = [
            {
                "media_type": "image",
                "url": "https://img.com/1.jpg",
                "telegram_file_id": "AgACAgI123",
            },
        ]
        data = {"url": "https://example.com", "category": "twitter", "message_type": "long"}

        media_group, file_group, uncached = await media_files_packaging(media_files, data)

        # Should still use file_id even though message_type is "long"
        assert len(media_group) == 1
        assert uncached == [None]


class TestSendItemMessageExceptionHandling:
    @pytest.mark.asyncio
    async def test_exception_logged_and_sent_to_debug_channel(self):
        from core.services.message_sender import send_item_message

        mock_app = MagicMock()
        mock_bot = AsyncMock()
        mock_app.bot = mock_bot

        mock_chat = MagicMock()
        mock_chat.type = "private"
        mock_chat.linked_chat_id = None
        mock_bot.get_chat = AsyncMock(return_value=mock_chat)
        mock_bot.send_message = AsyncMock(side_effect=RuntimeError("telegram API down"))

        with patch("core.services.message_sender._get_application", return_value=mock_app), \
             patch("core.services.message_sender.send_debug_channel", new_callable=AsyncMock) as mock_debug:

            # Should not raise — the exception is caught and logged
            await send_item_message(
                data={
                    "media_files": [],
                    "message_type": "short",
                    "text": "test",
                    "title": "Test",
                    "author": "a",
                    "author_url": "",
                    "url": "https://example.com",
                    "telegraph_url": "",
                    "category": "twitter",
                    "content": "",
                },
                chat_id=12345,
            )

            # Debug channel should have been called with the traceback
            mock_debug.assert_awaited_once()
            assert "telegram API down" in mock_debug.call_args[0][0]
