"""Tests for telegram_file_id field on MediaFile and DatabaseMediaFile,
and the bson_encoders fix for Beanie serialization.

Does NOT require a running MongoDB instance.
"""

from dataclasses import asdict
from unittest.mock import patch

import pytest

from fastfetchbot_shared.models.metadata_item import MediaFile, MessageType
from fastfetchbot_shared.database.mongodb.models.metadata import (
    DatabaseMediaFile,
    Metadata,
)


# ---------------------------------------------------------------------------
# MediaFile.telegram_file_id
# ---------------------------------------------------------------------------


class TestMediaFileTelegramFileId:
    def test_default_is_none(self):
        mf = MediaFile(media_type="image", url="https://img.com/1.jpg")
        assert mf.telegram_file_id is None

    def test_can_set_value(self):
        mf = MediaFile(
            media_type="image",
            url="https://img.com/1.jpg",
            telegram_file_id="AgACAgI123",
        )
        assert mf.telegram_file_id == "AgACAgI123"

    def test_to_dict_includes_field_when_set(self):
        mf = MediaFile(
            media_type="image",
            url="https://img.com/1.jpg",
            telegram_file_id="AgACAgI123",
        )
        d = mf.to_dict()
        assert d["telegram_file_id"] == "AgACAgI123"

    def test_to_dict_excludes_field_when_none(self):
        mf = MediaFile(media_type="image", url="https://img.com/1.jpg")
        d = mf.to_dict()
        assert "telegram_file_id" not in d

    def test_from_dict_reads_field(self):
        d = {
            "media_type": "image",
            "url": "https://img.com/1.jpg",
            "telegram_file_id": "AgACAgI123",
        }
        mf = MediaFile.from_dict(d)
        assert mf.telegram_file_id == "AgACAgI123"

    def test_from_dict_without_field_defaults_none(self):
        d = {"media_type": "image", "url": "https://img.com/1.jpg"}
        mf = MediaFile.from_dict(d)
        assert mf.telegram_file_id is None

    def test_round_trip_with_file_id(self):
        original = MediaFile(
            media_type="video",
            url="https://vid.com/v.mp4",
            telegram_file_id="BAACAgI456",
        )
        restored = MediaFile.from_dict(original.to_dict())
        assert restored.telegram_file_id == "BAACAgI456"
        assert restored.media_type == "video"
        assert restored.url == "https://vid.com/v.mp4"

    def test_round_trip_without_file_id(self):
        original = MediaFile(media_type="image", url="https://img.com/1.jpg")
        restored = MediaFile.from_dict(original.to_dict())
        assert restored.telegram_file_id is None


# ---------------------------------------------------------------------------
# DatabaseMediaFile inherits telegram_file_id
# ---------------------------------------------------------------------------


class TestDatabaseMediaFileTelegramFileId:
    def test_inherits_field(self):
        dmf = DatabaseMediaFile(
            media_type="image",
            url="https://img.com/1.jpg",
            telegram_file_id="AgACAgI123",
        )
        assert dmf.telegram_file_id == "AgACAgI123"

    def test_default_is_none(self):
        dmf = DatabaseMediaFile(media_type="image", url="https://img.com/1.jpg")
        assert dmf.telegram_file_id is None

    def test_has_both_file_key_and_telegram_file_id(self):
        dmf = DatabaseMediaFile(
            media_type="image",
            url="https://img.com/1.jpg",
            file_key="s3://bucket/key.jpg",
            telegram_file_id="AgACAgI123",
        )
        assert dmf.file_key == "s3://bucket/key.jpg"
        assert dmf.telegram_file_id == "AgACAgI123"


# ---------------------------------------------------------------------------
# bson_encoders — Beanie serialization fix
# ---------------------------------------------------------------------------


class TestBsonEncoders:
    def test_settings_has_bson_encoders(self):
        assert hasattr(Metadata.Settings, "bson_encoders")
        assert DatabaseMediaFile in Metadata.Settings.bson_encoders

    def test_encoder_uses_asdict(self):
        encoder = Metadata.Settings.bson_encoders[DatabaseMediaFile]
        assert encoder is asdict

    def test_encoder_converts_to_dict(self):
        dmf = DatabaseMediaFile(
            media_type="image",
            url="https://img.com/1.jpg",
            telegram_file_id="AgACAgI123",
            file_key="s3://bucket/key.jpg",
        )
        encoder = Metadata.Settings.bson_encoders[DatabaseMediaFile]
        result = encoder(dmf)
        assert isinstance(result, dict)
        assert result["media_type"] == "image"
        assert result["url"] == "https://img.com/1.jpg"
        assert result["telegram_file_id"] == "AgACAgI123"
        assert result["file_key"] == "s3://bucket/key.jpg"

    def test_encoder_handles_none_fields(self):
        dmf = DatabaseMediaFile(media_type="image", url="https://img.com/1.jpg")
        encoder = Metadata.Settings.bson_encoders[DatabaseMediaFile]
        result = encoder(dmf)
        assert result["telegram_file_id"] is None
        assert result["file_key"] is None

    def test_beanie_encoder_can_encode_database_media_file(self):
        """Verify the Beanie Encoder uses our custom encoder."""
        from beanie.odm.utils.encoder import Encoder

        dmf = DatabaseMediaFile(
            media_type="image",
            url="https://img.com/1.jpg",
            telegram_file_id="AgACAgI123",
        )
        encoder = Encoder(
            custom_encoders=Metadata.Settings.bson_encoders,
            to_db=True,
            keep_nulls=True,
        )
        result = encoder.encode(dmf)
        assert isinstance(result, dict)
        assert result["media_type"] == "image"
        assert result["telegram_file_id"] == "AgACAgI123"

    def test_beanie_encoder_can_encode_list_of_database_media_files(self):
        """Verify list of DatabaseMediaFile encodes to list of dicts."""
        from beanie.odm.utils.encoder import Encoder

        files = [
            DatabaseMediaFile(media_type="image", url="https://img.com/1.jpg"),
            DatabaseMediaFile(
                media_type="video",
                url="https://vid.com/v.mp4",
                telegram_file_id="BAACAgI456",
            ),
        ]
        encoder = Encoder(
            custom_encoders=Metadata.Settings.bson_encoders,
            to_db=True,
            keep_nulls=True,
        )
        result = encoder.encode(files)
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], dict)
        assert isinstance(result[1], dict)
        assert result[1]["telegram_file_id"] == "BAACAgI456"


# ---------------------------------------------------------------------------
# prepare_for_insert preserves telegram_file_id
# ---------------------------------------------------------------------------


def _make_metadata(**kwargs):
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


class TestPrepareForInsertFileId:
    def test_preserves_telegram_file_id_from_dict(self):
        m = _make_metadata(
            media_files=[
                {
                    "media_type": "image",
                    "url": "https://img.com/1.jpg",
                    "telegram_file_id": "AgACAgI123",
                },
            ],
        )
        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.get_html_text_length",
            return_value=0,
        ):
            m.prepare_for_insert()

        assert isinstance(m.media_files[0], DatabaseMediaFile)
        assert m.media_files[0].telegram_file_id == "AgACAgI123"

    def test_preserves_telegram_file_id_from_media_file(self):
        mf = MediaFile(
            media_type="image",
            url="https://img.com/1.jpg",
            telegram_file_id="AgACAgI123",
        )
        m = _make_metadata(media_files=[mf])
        with patch(
            "fastfetchbot_shared.database.mongodb.models.metadata.get_html_text_length",
            return_value=0,
        ):
            m.prepare_for_insert()

        assert isinstance(m.media_files[0], DatabaseMediaFile)
        assert m.media_files[0].telegram_file_id == "AgACAgI123"
