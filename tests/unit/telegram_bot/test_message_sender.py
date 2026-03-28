"""Tests for exception handling in apps/telegram-bot/core/services/message_sender.py"""

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
            media_group, file_group = await media_files_packaging(media_files, data)

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
            media_group, file_group = await media_files_packaging(media_files, data)

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

            media_group, file_group = await media_files_packaging(media_files, data)

        # The image media_group should have the photo, but file_group should be empty
        # because the document download failed and was skipped
        assert file_group == []


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
