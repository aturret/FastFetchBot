from fastfetchbot_file_export.video_download import get_video_orientation, get_format_for_orientation


def test_get_video_orientation_vertical():
    content_info = {"formats": [{"aspect_ratio": 0.5}]}
    assert get_video_orientation(content_info, "youtube") == "vertical"


def test_get_video_orientation_horizontal():
    content_info = {"formats": [{"aspect_ratio": 1.78}]}
    assert get_video_orientation(content_info, "youtube") == "horizontal"


def test_get_video_orientation_non_youtube():
    assert get_video_orientation({}, "bilibili") == "horizontal"


def test_get_format_youtube_horizontal_hd():
    fmt = get_format_for_orientation("youtube", "horizontal", hd=True)
    assert "258" in fmt or "256" in fmt


def test_get_format_youtube_vertical():
    fmt = get_format_for_orientation("youtube", "vertical", hd=False)
    assert "bv" in fmt


def test_get_format_bilibili_non_hd():
    fmt = get_format_for_orientation("bilibili", "horizontal", hd=False)
    assert "480" in fmt
