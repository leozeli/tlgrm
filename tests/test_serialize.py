# tests/test_serialize.py
from datetime import datetime, timezone
from types import SimpleNamespace
from tlgrm.core import serialize


def _msg(**kw):
    base = {
        "media": None,
        "photo": None,
        "voice": None,
        "video": None,
        "audio": None,
        "document": None,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def test_media_type_none_when_no_media():
    assert serialize.media_type(_msg()) is None


def test_media_type_detects_photo():
    assert serialize.media_type(_msg(media=object(), photo=object())) == "photo"


def test_media_type_other_when_unknown_media():
    assert serialize.media_type(_msg(media=object())) == "other"


def test_serialize_member():
    user = SimpleNamespace(
        id=5, first_name="A", last_name=None, username=None, phone=None, bot=False
    )
    assert serialize.serialize_member(user) == {
        "id": 5,
        "first_name": "A",
        "last_name": "",
        "username": "",
        "phone": "",
        "is_bot": False,
    }


def test_serialize_sender_handles_none():
    out = serialize.serialize_sender(None)
    assert out["id"] is None and out["display_name"] == "Unknown"
    assert out["phone"] == ""


def test_serialize_sender_masks_phone_like_the_docs():
    sender = SimpleNamespace(
        id=738667936,
        first_name="Muneerah",
        last_name="",
        username="mneraah",
        phone="+60123456023",
    )
    out = serialize.serialize_sender(sender)
    assert out["phone"] == "+601****6023"
    assert "2345" not in out["phone"]


def test_serialize_sender_hides_short_phone():
    sender = SimpleNamespace(
        id=1, first_name="A", last_name="", username="", phone="12345"
    )
    out = serialize.serialize_sender(sender)
    assert out["phone"] == "****"
    assert "12345" not in out["phone"]


def test_cli_serializers_keep_full_phone():
    # whoami / members stay on the operator's machine; only webhook sender
    # payloads are masked.
    user = SimpleNamespace(
        id=1,
        first_name="A",
        last_name="",
        username="a",
        phone="+15551234567",
        bot=False,
    )
    assert serialize.serialize_member(user)["phone"] == "+15551234567"
    assert serialize.serialize_user(user)["phone"] == "+15551234567"


def test_serialize_dialog_user():
    entity = SimpleNamespace(username="bob")
    dialog = SimpleNamespace(
        entity=entity,
        is_user=True,
        is_group=False,
        is_channel=False,
        id=42,
        name="Bob",
        unread_count=3,
    )
    assert serialize.serialize_dialog(dialog) == {
        "id": 42,
        "name": "Bob",
        "username": "bob",
        "type": "user",
        "unread_count": 3,
    }


def test_serialize_dialog_channel_without_username():
    entity = SimpleNamespace()  # no username attribute
    dialog = SimpleNamespace(
        entity=entity,
        is_user=False,
        is_group=False,
        is_channel=True,
        id=-100,
        name="News",
        unread_count=0,
    )
    out = serialize.serialize_dialog(dialog)
    assert out["type"] == "channel" and out["username"] is None


def test_serialize_history_message_flattens_sender():
    msg = _msg(
        id=7, date=datetime(2026, 1, 1, tzinfo=timezone.utc), sender_id=5, text="hi"
    )
    sender = SimpleNamespace(first_name="Al", last_name=None, username=None)
    out = serialize.serialize_history_message(msg, sender)
    assert out["id"] == 7
    assert out["date"] == "2026-01-01T00:00:00+00:00"
    assert out["sender_id"] == 5
    assert out["text"] == "hi"
    assert out["media_type"] is None
    assert isinstance(out["sender_name"], str)
