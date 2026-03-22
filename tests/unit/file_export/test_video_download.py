"""Tests for packages/shared/fastfetchbot_shared/services/file_export/video_download.py"""

from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from fastfetchbot_shared.services.file_export.video_download import VideoDownloader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_celery():
    """Mock Celery app with send_task returning a mock result."""
    app = MagicMock()
    result = MagicMock()
    app.send_task.return_value = result
    return app, result


@pytest.fixture
def youtube_video_info():
    """Sample YouTube yt-dlp content_info dict."""
    return {
        "id": "abc123",
        "title": "Test Video",
        "uploader": "TestChannel",
        "uploader_url": "https://youtube.com/@TestChannel",
        "channel_url": "https://youtube.com/channel/UC123",
        "description": "A test video description",
        "view_count": 12345,
        "comment_count": 67,
        "thumbnail": "https://img.youtube.com/thumb.jpg",
        "upload_date": "20240101",
        "duration": 125.7,
        "file_path": "/tmp/video.mp4",
    }


@pytest.fixture
def bilibili_video_info():
    """Sample Bilibili yt-dlp content_info dict."""
    return {
        "id": "BV1abc",
        "title": "B\u7ad9\u89c6\u9891",
        "uploader": "UP\u4e3b",
        "uploader_id": 12345678,
        "thumbnail": "https://i0.hdslb.com/thumb.jpg",
        "ext": "mp4",
        "description": "A bilibili video",
        "view_count": 9999,
        "comment_count": 100,
        "like_count": 500,
        "timestamp": 1704067200,
        "duration": 300.0,
        "file_path": "/tmp/bilibili.mp4",
    }


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestVideoDownloaderInit:
    def test_stores_all_fields(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(
            url="https://youtube.com/watch?v=abc",
            category="youtube",
            celery_app=app,
            timeout=300,
            download=False,
            audio_only=True,
            hd=True,
            transcribe=True,
        )
        assert vd.url == "https://youtube.com/watch?v=abc"
        assert vd.extractor == "youtube"
        assert vd.category == "youtube"
        assert vd.celery_app is app
        assert vd.timeout == 300
        assert vd.download is False
        assert vd.audio_only is True
        assert vd.hd is True
        assert vd.transcribe is True

    def test_defaults(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(url="u", category="youtube", celery_app=app)
        assert vd.download is True
        assert vd.audio_only is False
        assert vd.hd is False
        assert vd.transcribe is False
        assert vd.timeout == 600
        assert vd.media_files == []
        assert vd.file_path is None

    def test_accepts_extra_kwargs(self, mock_celery):
        """Extra kwargs should not raise (used when passed from InfoExtractService)."""
        app, _ = mock_celery
        vd = VideoDownloader(
            url="u", category="youtube", celery_app=app, extra_param="ignored"
        )
        assert vd.url == "u"


# ---------------------------------------------------------------------------
# _youtube_info_parse (static method)
# ---------------------------------------------------------------------------


class TestYoutubeInfoParse:
    def test_parses_standard_youtube_info(self, youtube_video_info):
        result = VideoDownloader._youtube_info_parse(youtube_video_info)
        assert result["id"] == "abc123"
        assert result["title"] == "Test Video"
        assert result["author"] == "TestChannel"
        assert result["author_url"] == "https://youtube.com/@TestChannel"
        assert result["description"] == "A test video description"
        assert result["upload_date"] == "20240101"
        assert result["duration"] == "00:02:06"  # 126 seconds rounded

    def test_falls_back_to_channel_url(self, youtube_video_info):
        youtube_video_info["uploader_url"] = None
        result = VideoDownloader._youtube_info_parse(youtube_video_info)
        assert result["author_url"] == "https://youtube.com/channel/UC123"

    def test_playback_data_format(self, youtube_video_info):
        result = VideoDownloader._youtube_info_parse(youtube_video_info)
        assert "12345" in result["playback_data"]
        assert "67" in result["playback_data"]


# ---------------------------------------------------------------------------
# _bilibili_info_parse (static method)
# ---------------------------------------------------------------------------


class TestBilibiliInfoParse:
    def test_parses_standard_bilibili_info(self, bilibili_video_info):
        result = VideoDownloader._bilibili_info_parse(bilibili_video_info)
        assert result["id"] == "BV1abc"
        assert result["title"] == "B\u7ad9\u89c6\u9891"
        assert result["author"] == "UP\u4e3b"
        assert result["author_url"] == "https://space.bilibili.com/12345678"
        assert result["ext"] == "mp4"

    def test_playback_data_format(self, bilibili_video_info):
        result = VideoDownloader._bilibili_info_parse(bilibili_video_info)
        assert "9999" in result["playback_data"]
        assert "100" in result["playback_data"]
        assert "500" in result["playback_data"]


# ---------------------------------------------------------------------------
# _parse_url — YouTube
# ---------------------------------------------------------------------------


class TestParseUrlYoutube:
    @pytest.mark.asyncio
    async def test_youtube_standard_url_unchanged(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(
            url="https://www.youtube.com/watch?v=abc123",
            category="youtube",
            celery_app=app,
        )
        result = await vd._parse_url("https://www.youtube.com/watch?v=abc123")
        assert result == "https://www.youtube.com/watch?v=abc123"

    @pytest.mark.asyncio
    async def test_youtube_strips_tracking_params(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(
            url="https://www.youtube.com/watch?v=abc123&si=tracking&feature=share",
            category="youtube",
            celery_app=app,
        )
        result = await vd._parse_url(
            "https://www.youtube.com/watch?v=abc123&si=tracking&feature=share"
        )
        assert result == "https://www.youtube.com/watch?v=abc123"

    @pytest.mark.asyncio
    async def test_youtube_shorts_url(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(
            url="https://www.youtube.com/shorts/xyz",
            category="youtube",
            celery_app=app,
        )
        result = await vd._parse_url("https://www.youtube.com/shorts/xyz")
        assert "youtube.com/shorts/xyz" in result

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.file_export.video_download.httpx.AsyncClient")
    async def test_youtube_short_url_follows_redirect(self, mock_client_cls, mock_celery):
        app, _ = mock_celery
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://www.youtube.com/watch?v=resolved"
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        vd = VideoDownloader(
            url="https://youtu.be/abc", category="youtube", celery_app=app
        )
        result = await vd._parse_url("https://youtu.be/abc")
        assert "youtube.com/watch?v=resolved" in str(result)


# ---------------------------------------------------------------------------
# _parse_url — Bilibili
# ---------------------------------------------------------------------------


class TestParseUrlBilibili:
    @pytest.mark.asyncio
    async def test_bilibili_standard_url_strips_tracking(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(
            url="https://www.bilibili.com/video/BV1abc?spm=tracking",
            category="bilibili",
            celery_app=app,
        )
        result = await vd._parse_url(
            "https://www.bilibili.com/video/BV1abc?spm=tracking"
        )
        assert result == "https://www.bilibili.com/video/BV1abc"

    @pytest.mark.asyncio
    async def test_bilibili_preserves_p_param(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(
            url="https://www.bilibili.com/video/BV1abc?p=3&spm=tracking",
            category="bilibili",
            celery_app=app,
        )
        result = await vd._parse_url(
            "https://www.bilibili.com/video/BV1abc?p=3&spm=tracking"
        )
        assert result == "https://www.bilibili.com/video/BV1abc?p=3"

    @pytest.mark.asyncio
    async def test_bilibili_mobile_url_rewritten(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(
            url="https://m.bilibili.com/video/BV1abc",
            category="bilibili",
            celery_app=app,
        )
        result = await vd._parse_url("https://m.bilibili.com/video/BV1abc")
        assert "www.bilibili.com" in result
        assert "m.bilibili.com" not in result

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.file_export.video_download.httpx.AsyncClient")
    async def test_bilibili_b23_follows_redirect(self, mock_client_cls, mock_celery):
        app, _ = mock_celery
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {
            "Location": "https://www.bilibili.com/video/BV1abc"
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        vd = VideoDownloader(
            url="https://b23.tv/abc", category="bilibili", celery_app=app
        )
        result = await vd._parse_url("https://b23.tv/abc")
        assert "bilibili.com/video/BV1abc" in result


# ---------------------------------------------------------------------------
# get_video_info
# ---------------------------------------------------------------------------


class TestGetVideoInfo:
    @pytest.mark.asyncio
    async def test_submits_celery_task_with_correct_kwargs(self, mock_celery):
        app, result = mock_celery
        result.get.return_value = {
            "content_info": {"title": "t"},
            "file_path": "/tmp/v.mp4",
        }
        vd = VideoDownloader(
            url="https://youtube.com/watch?v=abc",
            category="youtube",
            celery_app=app,
        )
        info = await vd.get_video_info()

        app.send_task.assert_called_once_with(
            "file_export.video_download",
            kwargs={
                "url": "https://youtube.com/watch?v=abc",
                "download": True,
                "extractor": "youtube",
                "audio_only": False,
                "hd": False,
            },
        )
        assert info["title"] == "t"
        assert info["file_path"] == "/tmp/v.mp4"

    @pytest.mark.asyncio
    async def test_overrides_defaults_with_explicit_params(self, mock_celery):
        app, result = mock_celery
        result.get.return_value = {
            "content_info": {},
            "file_path": "/tmp/a.mp3",
        }
        vd = VideoDownloader(
            url="u", category="youtube", celery_app=app, download=True
        )
        await vd.get_video_info(
            url="override_url", download=False, audio_only=True, hd=True
        )

        sent_kwargs = app.send_task.call_args.kwargs["kwargs"]
        assert sent_kwargs["url"] == "override_url"
        assert sent_kwargs["download"] is False
        assert sent_kwargs["audio_only"] is True
        assert sent_kwargs["hd"] is True

    @pytest.mark.asyncio
    async def test_celery_failure_reraises(self, mock_celery):
        app, result = mock_celery
        result.get.side_effect = TimeoutError("timed out")

        vd = VideoDownloader(url="u", category="youtube", celery_app=app)
        with pytest.raises(TimeoutError):
            await vd.get_video_info()


# ---------------------------------------------------------------------------
# _video_info_formatting
# ---------------------------------------------------------------------------


class TestVideoInfoFormatting:
    def test_sets_metadata_fields(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(url="https://youtube.com/watch?v=x", category="youtube", celery_app=app)
        meta_info = {
            "title": "My Video",
            "author": "Author",
            "author_url": "https://example.com/author",
            "description": "A short description",
            "upload_date": "2024-01-01",
            "duration": "5:00",
            "playback_data": "1000 views",
        }
        vd._video_info_formatting(meta_info)
        assert vd.title == "My Video"
        assert vd.author == "Author"
        assert vd.author_url == "https://example.com/author"
        assert vd.created == "2024-01-01"
        assert vd.duration == "5:00"

    def test_truncates_long_description(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(url="u", category="youtube", celery_app=app)
        meta_info = {
            "title": "t",
            "author": "a",
            "author_url": "u",
            "description": "x" * 1000,
            "upload_date": "d",
            "duration": "d",
            "playback_data": "p",
        }
        vd._video_info_formatting(meta_info)
        assert len(meta_info["description"]) == 803  # 800 + "..."
        assert meta_info["description"].endswith("...")

    def test_creates_video_media_file_when_download(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(url="u", category="youtube", celery_app=app, download=True)
        vd.file_path = "/tmp/video.mp4"
        meta_info = {
            "title": "t", "author": "a", "author_url": "u",
            "description": "d", "upload_date": "d", "duration": "d",
            "playback_data": "p",
        }
        vd._video_info_formatting(meta_info)
        assert len(vd.media_files) == 1
        assert vd.media_files[0].media_type == "video"

    def test_creates_audio_media_file_when_audio_only(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(
            url="u", category="youtube", celery_app=app, download=True, audio_only=True
        )
        vd.file_path = "/tmp/audio.mp3"
        meta_info = {
            "title": "t", "author": "a", "author_url": "u",
            "description": "d", "upload_date": "d", "duration": "d",
            "playback_data": "p",
        }
        vd._video_info_formatting(meta_info)
        assert len(vd.media_files) == 1
        assert vd.media_files[0].media_type == "audio"

    def test_no_media_file_when_download_false(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(url="u", category="youtube", celery_app=app, download=False)
        vd.file_path = "/tmp/video.mp4"
        meta_info = {
            "title": "t", "author": "a", "author_url": "u",
            "description": "d", "upload_date": "d", "duration": "d",
            "playback_data": "p",
        }
        vd._video_info_formatting(meta_info)
        assert vd.media_files == []
