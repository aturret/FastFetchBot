"""Tests for packages/shared/fastfetchbot_shared/database/mongodb/models/metadata.py

Only tests pure logic (prepare_for_insert, from_dict, DatabaseMediaFile).
Does NOT require a running MongoDB instance.

NOTE: Beanie Document.__init__ calls get_motor_collection() which requires
init_beanie(). We use model_construct() to bypass validation and init for
most tests, since we're testing business logic not Beanie integration.
"""

from unittest.mock import patch

import pytest

from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType
from fastfetchbot_shared.database.mongodb.models.metadata import (
    DatabaseMediaFile,
    Metadata,
    document_list,
)


# ---------------------------------------------------------------------------
# DatabaseMediaFile
# ---------------------------------------------------------------------------


class TestDatabaseMediaFile:
    def test_inherits_from_media_file(self):
        assert issubclass(DatabaseMediaFile, MediaFile)

    def test_default_file_key_is_none(self):
        dmf = DatabaseMediaFile(media_type="photo", url="https://img.com/1.jpg")
        assert dmf.file_key is None

    def test_file_key_can_be_set(self):
        dmf = DatabaseMediaFile(
            media_type="photo",
            url="https://img.com/1.jpg",
            file_key="s3://bucket/key.jpg",
        )
        assert dmf.file_key == "s3://bucket/key.jpg"

    def test_inherits_media_file_fields(self):
        dmf = DatabaseMediaFile(
            media_type="video",
            url="https://vid.com/v.mp4",
            original_url="https://original.com/v.mp4",
            caption="test caption",
        )
        assert dmf.media_type == "video"
        assert dmf.url == "https://vid.com/v.mp4"
        assert dmf.original_url == "https://original.com/v.mp4"
        assert dmf.caption == "test caption"


# ---------------------------------------------------------------------------
# Metadata model (using model_construct to avoid Beanie init)
# ---------------------------------------------------------------------------


def _make_metadata(**kwargs):
    """Create a Metadata via model_construct (bypasses Beanie motor check)."""
    defaults = {
        "url": "https://example.com",
        "title": "untitled",
        "message_type": MessageType.SHORT,
        "text_length": 0,
        "content_length": 0,
        "scrape_status": False,
        "version": 1,
    }
    defaults.update(kwargs)
    return Metadata.model_construct(**defaults)


class TestMetadataModel:
    def test_document_list_contains_metadata(self):
        assert Metadata in document_list

    def test_default_field_values(self):
        m = _make_metadata()
        assert m.title == "untitled"
        assert m.message_type == MessageType.SHORT
        assert m.version == 1
        assert m.scrape_status is False

    def test_custom_fields(self):
        m = _make_metadata(
            url="https://example.com",
            title="Test",
            version=2,
        )
        assert m.url == "https://example.com"
        assert m.title == "Test"
        assert m.version == 2

    def test_from_dict_raises_for_non_dict(self):
        with pytest.raises(AssertionError):
            Metadata.from_dict("not a dict")

    def test_settings_has_indexes(self):
        assert hasattr(Metadata, "Settings")
        assert hasattr(Metadata.Settings, "indexes")
        indexes = Metadata.Settings.indexes
        assert len(indexes) >= 1
        # First index should be (url, version) compound index
        first_index = indexes[0]
        field_names = [idx[0] for idx in first_index]
        assert "url" in field_names
        assert "version" in field_names


# ---------------------------------------------------------------------------
# prepare_for_insert
# ---------------------------------------------------------------------------


class TestPrepareForInsert:
    def test_computes_text_length(self):
        m = _make_metadata(text="<p>Hello world</p>")
        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.get_html_text_length",
            return_value=11,
        ):
            m.prepare_for_insert()
        assert m.text_length == 11

    def test_computes_content_length(self):
        m = _make_metadata(content="<div>Some content</div>")
        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.get_html_text_length",
            side_effect=lambda x: len(x) if x else 0,
        ):
            m.prepare_for_insert()
        assert m.content_length == len("<div>Some content</div>")

    def test_preserves_existing_database_media_files(self):
        dmf = DatabaseMediaFile(
            media_type="photo",
            url="https://img.com/1.jpg",
            file_key="s3://bucket/key.jpg",
        )
        m = _make_metadata(media_files=[dmf])
        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.get_html_text_length",
            return_value=0,
        ):
            m.prepare_for_insert()

        assert m.media_files[0] is dmf
        assert m.media_files[0].file_key == "s3://bucket/key.jpg"

    def test_converts_dict_media_files(self):
        m = _make_metadata(
            media_files=[
                {"media_type": "photo", "url": "https://img.com/1.jpg"},
            ],
        )
        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.get_html_text_length",
            return_value=0,
        ):
            m.prepare_for_insert()

        assert len(m.media_files) == 1
        assert isinstance(m.media_files[0], DatabaseMediaFile)
        assert m.media_files[0].url == "https://img.com/1.jpg"

    def test_converts_media_file_objects_via_dict(self):
        """MediaFile dataclass instances get converted via __dict__."""
        mf = MediaFile(media_type="video", url="https://vid.com/v.mp4")
        m = _make_metadata(media_files=[mf])
        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.get_html_text_length",
            return_value=0,
        ):
            m.prepare_for_insert()

        assert isinstance(m.media_files[0], DatabaseMediaFile)
        assert m.media_files[0].url == "https://vid.com/v.mp4"

    def test_handles_none_media_files(self):
        m = _make_metadata(media_files=None)
        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.get_html_text_length",
            return_value=0,
        ):
            m.prepare_for_insert()

        assert m.media_files is None

    def test_handles_none_text_and_content(self):
        m = _make_metadata(text=None, content=None)
        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.get_html_text_length",
            return_value=0,
        ):
            m.prepare_for_insert()

        assert m.text_length == 0
        assert m.content_length == 0
