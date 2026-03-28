"""Tests for exception handling in packages/shared/fastfetchbot_shared/utils/network.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastfetchbot_shared.models.classes import NamedBytesIO


class TestDownloadFileByMetadataItem:
    @pytest.mark.asyncio
    async def test_success_returns_named_bytes_io(self):
        from fastfetchbot_shared.utils.network import download_file_by_metadata_item

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake image data"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.utils.network.httpx.AsyncClient", return_value=mock_client), \
             patch("fastfetchbot_shared.utils.network.get_random_user_agent", return_value="TestAgent"):
            result = await download_file_by_metadata_item(
                url="https://example.com/image.jpg",
                data={"url": "https://example.com", "category": "twitter"},
            )

        assert isinstance(result, NamedBytesIO)
        assert result.name.endswith(".jpg")

    @pytest.mark.asyncio
    async def test_network_error_raises(self):
        from fastfetchbot_shared.utils.network import download_file_by_metadata_item

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.utils.network.httpx.AsyncClient", return_value=mock_client), \
             patch("fastfetchbot_shared.utils.network.get_random_user_agent", return_value="TestAgent"):
            with pytest.raises(ConnectionError, match="connection refused"):
                await download_file_by_metadata_item(
                    url="https://example.com/image.jpg",
                    data={"url": "https://example.com", "category": "twitter"},
                )

    @pytest.mark.asyncio
    async def test_redirect_follows_location(self):
        from fastfetchbot_shared.utils.network import download_file_by_metadata_item

        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {"Location": "https://cdn.example.com/real.jpg"}
        mock_response.content = b"redirected content"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("fastfetchbot_shared.utils.network.httpx.AsyncClient", return_value=mock_client), \
             patch("fastfetchbot_shared.utils.network.get_random_user_agent", return_value="TestAgent"):
            result = await download_file_by_metadata_item(
                url="https://example.com/image.jpg",
                data={"url": "https://example.com", "category": "twitter"},
            )

        assert isinstance(result, NamedBytesIO)


class TestGetResponseJson:
    @pytest.mark.asyncio
    async def test_exception_returns_none_and_logs(self):
        from fastfetchbot_shared.utils.network import get_response_json

        with patch(
            "fastfetchbot_shared.utils.network.get_response",
            new_callable=AsyncMock,
            side_effect=ConnectionError("timeout"),
        ):
            result = await get_response_json("https://example.com/api")

        assert result is None

    @pytest.mark.asyncio
    async def test_json_decode_error_returns_none(self):
        from fastfetchbot_shared.utils.network import get_response_json

        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("invalid json")

        with patch(
            "fastfetchbot_shared.utils.network.get_response",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await get_response_json("https://example.com/api")

        assert result is None
