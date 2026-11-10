"""Tests for packages/shared/fastfetchbot_shared/services/file_export/video_download.py"""

from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from fastfetchbot_shared.services.file_export.video_download import VideoDownloader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_real_guest_download():
    """Never hit Bilibili from unit tests: the guest fallback fails unless a test patches it."""
    from fastfetchbot_file_export import video_download as vdmod
    from fastfetchbot_file_export.bilibili_guest import GuestDownloadError

    with patch.object(vdmod, "guest_download", side_effect=GuestDownloadError("disabled in tests")):
        yield


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


BV = "BV1xx411c7mD"


def _redirect_client(final_url: str):
    resp = MagicMock()
    resp.url = final_url  # httpx returns a URL object; resolver must str() it
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestParseUrlBilibili:
    @pytest.mark.asyncio
    async def test_bilibili_standard_url_strips_tracking(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(url="", category="bilibili", celery_app=app)
        result = await vd._parse_url(f"https://www.bilibili.com/video/{BV}?spm=tracking")
        assert result == f"https://www.bilibili.com/video/{BV}"

    @pytest.mark.asyncio
    async def test_bilibili_preserves_p_param(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(url="", category="bilibili", celery_app=app)
        result = await vd._parse_url(f"https://www.bilibili.com/video/{BV}?p=3&spm=tracking")
        assert result == f"https://www.bilibili.com/video/{BV}?p=3"

    @pytest.mark.asyncio
    async def test_bilibili_mobile_url_rewritten(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(url="", category="bilibili", celery_app=app)
        result = await vd._parse_url(f"https://m.bilibili.com/video/{BV}")
        assert result == f"https://www.bilibili.com/video/{BV}"

    @pytest.mark.asyncio
    @patch("fastfetchbot_shared.services.scrapers.bilibili.url.httpx.AsyncClient")
    async def test_bilibili_b23_redirect_to_mobile_is_normalized(self, mock_client_cls, mock_celery):
        app, _ = mock_celery
        mock_client_cls.return_value = _redirect_client(
            f"https://m.bilibili.com/video/{BV}?share_source=copy&p=1"
        )
        vd = VideoDownloader(url="", category="bilibili", celery_app=app)
        result = await vd._parse_url("https://b23.tv/abc")
        assert result == f"https://www.bilibili.com/video/{BV}"


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


# ---------------------------------------------------------------------------
# Exception handling in fastfetchbot_file_export.video_download
# ---------------------------------------------------------------------------


class TestVideoDownloadExceptions:
    def test_unsupported_extractor_raises_file_export_error(self):
        from fastfetchbot_file_export.video_download import get_format_for_orientation
        from fastfetchbot_shared.exceptions import FileExportError

        with pytest.raises(FileExportError, match="no available extractor found"):
            get_format_for_orientation("tiktok", "horizontal", False)

    def test_download_video_wraps_errors_in_file_export_error(self):
        from fastfetchbot_file_export.video_download import download_video
        from fastfetchbot_shared.exceptions import FileExportError

        with patch(
            "fastfetchbot_file_export.video_download.init_yt_downloader"
        ) as mock_init:
            mock_ydl = MagicMock()
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_ydl.extract_info.side_effect = RuntimeError("network error")
            mock_init.return_value = mock_ydl

            with pytest.raises(FileExportError, match="视频下载失败"):
                download_video("https://youtube.com/watch?v=test", download=True)

    def test_download_video_preserves_original_cause(self):
        from fastfetchbot_file_export.video_download import download_video
        from fastfetchbot_shared.exceptions import FileExportError

        original = RuntimeError("connection reset")
        with patch(
            "fastfetchbot_file_export.video_download.init_yt_downloader"
        ) as mock_init:
            mock_ydl = MagicMock()
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            mock_ydl.extract_info.side_effect = original
            mock_init.return_value = mock_ydl

            with pytest.raises(FileExportError) as exc_info:
                download_video("https://youtube.com/watch?v=x", download=True)
            assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# get_video: Bilibili official API first, yt-dlp fallback
# ---------------------------------------------------------------------------

API_META = {
    "id": "BV1xx411c7mD",
    "title": "官方标题",
    "author": "UP主",
    "author_url": "https://space.bilibili.com/1",
    "author_avatar": "https://i0.hdslb.com/pic.jpg",
    "ext": "mp4",
    "description": "desc",
    "playback_data": "视频播放量：1 弹幕数：2 点赞数：3",
    "upload_date": "2024-01-01 08:00",
    "timestamp": 1704067200,
    "duration": "00:05:00",
}
META_PATCH = "fastfetchbot_shared.services.file_export.video_download.fetch_bilibili_video_meta"


class TestGetVideoBilibili:
    @pytest.mark.asyncio
    async def test_api_meta_without_download_skips_celery(self, mock_celery):
        app, _ = mock_celery
        vd = VideoDownloader(
            url="https://www.bilibili.com/video/BV1xx411c7mD",
            category="bilibili", celery_app=app, download=False,
        )
        with patch(META_PATCH, AsyncMock(return_value=dict(API_META))):
            await vd.get_video()
        app.send_task.assert_not_called()
        assert vd.title == "官方标题"
        assert vd.media_files == []

    @pytest.mark.asyncio
    async def test_api_meta_with_download_uses_api_meta_and_file(self, mock_celery, bilibili_video_info):
        app, result = mock_celery
        result.get.return_value = {"content_info": bilibili_video_info, "file_path": "/tmp/b.mp4"}
        vd = VideoDownloader(
            url="https://www.bilibili.com/video/BV1xx411c7mD",
            category="bilibili", celery_app=app, download=True,
        )
        with patch(META_PATCH, AsyncMock(return_value=dict(API_META))):
            await vd.get_video()
        app.send_task.assert_called_once()
        assert vd.title == "官方标题"
        assert vd.media_files[0].url == "/tmp/b.mp4"

    @pytest.mark.asyncio
    async def test_api_unavailable_falls_back_to_ytdlp(self, mock_celery, bilibili_video_info):
        from fastfetchbot_shared.services.scrapers.bilibili import BilibiliApiUnavailable

        app, result = mock_celery
        result.get.return_value = {"content_info": bilibili_video_info, "file_path": None}
        vd = VideoDownloader(
            url="https://www.bilibili.com/video/BV1xx411c7mD",
            category="bilibili", celery_app=app, download=False,
        )
        with patch(META_PATCH, AsyncMock(side_effect=BilibiliApiUnavailable("412"))):
            await vd.get_video()
        app.send_task.assert_called_once()
        assert vd.title == bilibili_video_info["title"]

    @pytest.mark.asyncio
    async def test_fatal_api_error_propagates(self, mock_celery):
        from fastfetchbot_shared.exceptions import ScraperError

        app, _ = mock_celery
        vd = VideoDownloader(
            url="https://www.bilibili.com/video/BV1xx411c7mD",
            category="bilibili", celery_app=app,
        )
        with patch(META_PATCH, AsyncMock(side_effect=ScraperError("B 站视频获取失败：稿件不可见"))):
            with pytest.raises(ScraperError, match="稿件不可见"):
                await vd.get_video()
        app.send_task.assert_not_called()


# ---------------------------------------------------------------------------
# Worker download_video: single extraction, h264 preference, error reasons
# ---------------------------------------------------------------------------


def _fake_ydl(info=None):
    ydl = MagicMock()
    ydl.__enter__ = MagicMock(return_value=ydl)
    ydl.__exit__ = MagicMock(return_value=False)
    info = info if info is not None else {
        "id": "x", "title": "t", "formats": [],
        "requested_downloads": [{"filepath": "/dl/x.mp4"}],
    }
    ydl.extract_info.return_value = info
    ydl.process_ie_result.return_value = info
    ydl.sanitize_info.side_effect = lambda i, remove_private_keys=False: i
    return ydl


class TestWorkerSingleExtraction:
    def test_bilibili_download_extracts_once(self):
        from fastfetchbot_file_export import video_download as vdmod

        ydl = _fake_ydl()
        with patch.object(vdmod, "init_yt_downloader", return_value=ydl) as init:
            out = vdmod.download_video("https://www.bilibili.com/video/BV1xx411c7mD", extractor="bilibili")
        assert ydl.extract_info.call_count == 1
        ydl.extract_info.assert_called_with("https://www.bilibili.com/video/BV1xx411c7mD", download=True)
        assert init.call_count == 1
        assert out["file_path"] == "/dl/x.mp4"
        assert out["content_info"]["title"] == "t"

    def test_audio_only_extracts_once(self):
        from fastfetchbot_file_export import video_download as vdmod

        ydl = _fake_ydl()
        with patch.object(vdmod, "init_yt_downloader", return_value=ydl):
            vdmod.download_video("https://youtube.com/watch?v=x", extractor="youtube", audio_only=True)
        assert ydl.extract_info.call_count == 1

    def test_info_only_extracts_once_without_download(self):
        from fastfetchbot_file_export import video_download as vdmod

        ydl = _fake_ydl()
        with patch.object(vdmod, "init_yt_downloader", return_value=ydl):
            out = vdmod.download_video("https://www.bilibili.com/video/BV1xx411c7mD", download=False, extractor="bilibili")
        ydl.extract_info.assert_called_once_with("https://www.bilibili.com/video/BV1xx411c7mD", download=False)
        assert out["file_path"] is None

    def test_youtube_reuses_probe_info(self):
        from fastfetchbot_file_export import video_download as vdmod

        ydl = _fake_ydl()
        with patch.object(vdmod, "init_yt_downloader", return_value=ydl):
            out = vdmod.download_video("https://youtube.com/watch?v=x", extractor="youtube")
        ydl.extract_info.assert_called_once_with("https://youtube.com/watch?v=x", download=False)
        ydl.process_ie_result.assert_called_once()
        assert out["file_path"] == "/dl/x.mp4"

    def test_youtube_reuse_failure_reextracts(self):
        from yt_dlp.utils import DownloadError
        from fastfetchbot_file_export import video_download as vdmod

        ydl = _fake_ydl()
        ydl.process_ie_result.side_effect = DownloadError("HTTP Error 403: Forbidden")
        with patch.object(vdmod, "init_yt_downloader", return_value=ydl):
            vdmod.download_video("https://youtube.com/watch?v=x", extractor="youtube")
        assert ydl.extract_info.call_args_list[-1].kwargs == {"download": True}

    def test_playlist_probe_is_reextracted(self):
        from fastfetchbot_file_export import video_download as vdmod

        ydl = _fake_ydl({"_type": "playlist", "title": "p", "entries": []})
        with patch.object(vdmod, "init_yt_downloader", return_value=ydl):
            vdmod.download_video("https://youtube.com/watch?v=x", extractor="youtube")
        ydl.process_ie_result.assert_not_called()


class TestBilibiliFormatSort:
    def test_bilibili_video_prefers_h264(self):
        from fastfetchbot_file_export.video_download import init_yt_downloader

        ydl = init_yt_downloader(extractor="bilibili")
        assert ydl.params["format_sort"] == ["vcodec:h264"]

    def test_bilibili_audio_has_no_format_sort(self):
        from fastfetchbot_file_export.video_download import init_yt_downloader

        ydl = init_yt_downloader(extractor="bilibili", audio_only=True)
        assert "format_sort" not in ydl.params

    @pytest.mark.parametrize("mode", [{}, {"audio_only": True}, {"extract_only": True}])
    def test_bilibili_never_downloads_whole_playlist(self, mode):
        from fastfetchbot_file_export.video_download import init_yt_downloader

        assert init_yt_downloader(extractor="bilibili", **mode).params["noplaylist"] is True

    def test_youtube_has_no_format_sort(self):
        from fastfetchbot_file_export.video_download import init_yt_downloader

        ydl = init_yt_downloader(extractor="youtube")
        assert "format_sort" not in ydl.params


class TestExplainYtdlpError:
    @pytest.mark.parametrize(
        "message, reason",
        [
            ("ERROR: [BiliBili] BV1: HTTP Error 412: Precondition Failed", "B 站风控拦截"),
            ("ERROR: Requested format is not available. Use --list-formats", "没有可用的视频格式"),
            ("ERROR: This video is only available for registered users", "需要登录或大会员"),
            ("ERROR: 该视频为大会员专享", "需要登录或大会员"),
            ("ERROR: The uploader has not made this video available in your country", "地区限制"),
            ("ERROR: [BiliBili] BV1: HTTP Error 404: Not Found", "视频不存在或已删除"),
            (
                "ERROR: [BiliBili] 1GJ411x7h7: This video may be deleted or geo-restricted. "
                "You might want to try a VPN or a proxy server (with --proxy)",
                "视频不存在、已删除或有地区限制",
            ),
            ("ERROR: Video is geo-restricted", "地区限制"),
        ],
    )
    def test_known_reasons(self, message, reason):
        from fastfetchbot_file_export.video_download import explain_ytdlp_error

        assert reason in explain_ytdlp_error(RuntimeError(message))

    def test_unknown_keeps_first_line(self):
        from fastfetchbot_file_export.video_download import explain_ytdlp_error

        assert explain_ytdlp_error(RuntimeError("ERROR: boom\ntrace")) == "boom"

    def test_carriage_return_prefix_is_not_a_line_break(self):
        from fastfetchbot_file_export.video_download import explain_ytdlp_error

        msg = "ERROR: \r[download] Got error: HTTP Error 567: Unknown Status"
        assert explain_ytdlp_error(RuntimeError(msg)) == "[download] Got error: HTTP Error 567: Unknown Status"

    def test_empty_message_uses_type_name(self):
        from fastfetchbot_file_export.video_download import explain_ytdlp_error

        assert explain_ytdlp_error(RuntimeError("")) == "RuntimeError"

    def test_message_reaches_file_export_error(self):
        from fastfetchbot_file_export import video_download as vdmod
        from fastfetchbot_shared.exceptions import FileExportError

        ydl = _fake_ydl()
        ydl.extract_info.side_effect = RuntimeError("ERROR: HTTP Error 412: Precondition Failed")
        with patch.object(vdmod, "init_yt_downloader", return_value=ydl):
            with pytest.raises(FileExportError, match="视频下载失败：B 站风控拦截"):
                vdmod.download_video("https://www.bilibili.com/video/BV1xx411c7mD", extractor="bilibili")


# ---------------------------------------------------------------------------
# Worker download_video: Bilibili guest fallback
# ---------------------------------------------------------------------------

GUEST_RESULT = {
    "content_info": {"id": "BV1xx411c7mD", "title": "游客", "formats": []},
    "file_path": "/dl/guest.mp4",
}


class TestBilibiliGuestFallback:
    def _failing_ydl(self, message="ERROR: [download] Got error: HTTP Error 567: Unknown Status"):
        ydl = _fake_ydl()
        ydl.extract_info.side_effect = RuntimeError(message)
        return ydl

    def test_guest_succeeds_after_ytdlp_failure(self):
        from fastfetchbot_file_export import video_download as vdmod

        with patch.object(vdmod, "init_yt_downloader", return_value=self._failing_ydl()), \
                patch.object(vdmod, "guest_download", return_value=GUEST_RESULT) as guest:
            out = vdmod.download_video(
                "https://www.bilibili.com/video/BV1xx411c7mD", extractor="bilibili",
                config={"DOWNLOAD_DIR": "/dl", "PROXY_MODE": True, "PROXY_URL": "http://p:1"},
            )
        guest.assert_called_once_with("https://www.bilibili.com/video/BV1xx411c7mD", "/dl", proxy="http://p:1")
        assert out["file_path"] == "/dl/guest.mp4"
        assert out["content_info"]["title"] == "游客"

    def test_guest_respects_remote_file_url(self):
        from fastfetchbot_file_export import video_download as vdmod

        with patch.object(vdmod, "init_yt_downloader", return_value=self._failing_ydl()), \
                patch.object(vdmod, "guest_download", return_value=GUEST_RESULT):
            out = vdmod.download_video(
                "https://www.bilibili.com/video/BV1xx411c7mD", extractor="bilibili",
                config={"LOCAL_MODE": False, "BASE_URL": "https://files"},
            )
        assert out["file_path"] == "https://files/fileDownload/dl/guest.mp4"

    def test_both_failures_reported(self):
        from fastfetchbot_file_export import video_download as vdmod
        from fastfetchbot_file_export.bilibili_guest import GuestDownloadError
        from fastfetchbot_shared.exceptions import FileExportError

        ydl = self._failing_ydl("ERROR: HTTP Error 412: Precondition Failed")
        with patch.object(vdmod, "init_yt_downloader", return_value=ydl), \
                patch.object(vdmod, "guest_download", side_effect=GuestDownloadError("所有下载节点都失败（HTTP 567）")):
            with pytest.raises(FileExportError) as exc_info:
                vdmod.download_video("https://www.bilibili.com/video/BV1xx411c7mD", extractor="bilibili")
        message = str(exc_info.value)
        assert "B 站风控拦截" in message
        assert "游客下载也失败：所有下载节点都失败（HTTP 567）" in message
        assert isinstance(exc_info.value.__cause__, RuntimeError)

    def test_unexpected_guest_crash_still_wrapped(self):
        from fastfetchbot_file_export import video_download as vdmod
        from fastfetchbot_shared.exceptions import FileExportError

        with patch.object(vdmod, "init_yt_downloader", return_value=self._failing_ydl()), \
                patch.object(vdmod, "guest_download", side_effect=OSError("disk full")):
            with pytest.raises(FileExportError, match="游客下载也失败：OSError"):
                vdmod.download_video("https://www.bilibili.com/video/BV1xx411c7mD", extractor="bilibili")

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"extractor": "youtube"},
            {"extractor": "bilibili", "audio_only": True},
            {"extractor": "bilibili", "download": False},
        ],
    )
    def test_no_guest_fallback_outside_bilibili_video_download(self, kwargs):
        from fastfetchbot_file_export import video_download as vdmod
        from fastfetchbot_shared.exceptions import FileExportError

        with patch.object(vdmod, "init_yt_downloader", return_value=self._failing_ydl()), \
                patch.object(vdmod, "guest_download") as guest:
            with pytest.raises(FileExportError):
                vdmod.download_video("https://www.bilibili.com/video/BV1xx411c7mD", **kwargs)
        guest.assert_not_called()
