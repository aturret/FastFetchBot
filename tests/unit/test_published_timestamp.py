from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType, MetadataItem


def test_metadata_item_to_dict_includes_timestamp_without_changing_content():
    item = MetadataItem(
        url="https://example.com/post",
        telegraph_url="",
        content="<p>Body</p>",
        text="Body",
        media_files=[MediaFile(media_type="image", url="https://example.com/a.jpg")],
        author="Author",
        title="Title",
        author_url="https://example.com/author",
        category="example",
        message_type=MessageType.SHORT,
        timestamp=1704067200,
    )

    data = item.to_dict()

    assert data["timestamp"] == 1704067200
    assert data["content"] == "<p>Body</p>"


def test_metadata_item_to_dict_does_not_parse_datetime_strings():
    item = MetadataItem(
        url="https://example.com/post",
        telegraph_url="",
        content="<p>Body</p>",
        text="Body",
        media_files=[],
        author="Author",
        title="Title",
        author_url="https://example.com/author",
        category="example",
        message_type=MessageType.SHORT,
        timestamp="2024-01-01T00:00:00",  # type: ignore[arg-type]
    )

    data = item.to_dict()

    assert data["timestamp"] is None
    assert data["content"] == "<p>Body</p>"
