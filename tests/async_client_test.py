import sys
import json
import pytest

from nio import (
    LoginResponse,
    SyncResponse,
    LoginError,
    LocalProtocolError,
    KeysUploadResponse,
    Rooms,
    RoomInfo,
    Timeline,
    RoomMemberEvent,
    RoomEncryptionEvent,
    RoomSummary,
    DeviceOneTimeKeyCount,
    DeviceList
)

TEST_ROOM_ID = "!testroom:example.org"

ALICE_ID = "@alice:example.org"
ALICE_DEVICE_ID = "JLAFKJWSCS"


if sys.version_info >= (3, 5):
    import asyncio


@pytest.mark.skipif(sys.version_info < (3, 5), reason="Python 3 specific asyncio tests")
class TestClass(object):
    @staticmethod
    def _load_response(filename):
        with open(filename) as f:
            return json.loads(f.read(), encoding="utf-8")

    @property
    def login_response(self):
        return self._load_response("tests/data/login_response.json")

    @property
    def keys_upload_response(self):
        return self._load_response("tests/data/keys_upload.json")

    @property
    def sync_response(self):
        return self._load_response("tests/data/sync.json")

    @property
    def keys_query_response(self):
        return self._load_response(
            "tests/data/keys_query.json")

    @property
    def encryption_sync_response(self):
        timeline = Timeline(
            [
                RoomMemberEvent(
                    "event_id_1",
                    ALICE_ID,
                    1516809890615,
                    ALICE_ID,
                    {"membership": "join"}
                ),
                RoomEncryptionEvent("event_id_2", ALICE_ID, 1516809890615)
            ],
            False,
            "prev_batch_token"
        )
        test_room_info = RoomInfo(timeline, [], [], [], RoomSummary(1, 2, []))
        rooms = Rooms(
            {},
            {
                TEST_ROOM_ID: test_room_info
            },
            {}
        )
        return SyncResponse(
            "token123",
            rooms,
            DeviceOneTimeKeyCount(49, 50),
            DeviceList([ALICE_ID], []),
            []
        )

    def test_login(self, async_client, aioresponse):
        loop = asyncio.get_event_loop()

        assert not async_client.access_token
        assert not async_client.logged_in

        aioresponse.post(
            "https://example.org/_matrix/client/r0/login",
            status=200,
            payload=self.login_response
        )
        resp = loop.run_until_complete(async_client.login("wordpass"))

        assert isinstance(resp, LoginResponse)
        assert async_client.access_token
        assert async_client.logged_in

    def test_failed_login(self, async_client, aioresponse):
        loop = asyncio.get_event_loop()

        assert not async_client.access_token
        assert not async_client.logged_in

        aioresponse.post(
            "https://example.org/_matrix/client/r0/login",
            status=400,
            body=""
        )
        resp = loop.run_until_complete(async_client.login("wordpass"))
        assert isinstance(resp, LoginError)
        assert not async_client.logged_in

        assert async_client.client_session
        async_client.close()
        loop.run_until_complete(async_client.close())
        assert not async_client.client_session

    def test_sync(self, async_client, aioresponse):
        loop = asyncio.get_event_loop()

        aioresponse.post(
            "https://example.org/_matrix/client/r0/login",
            status=200,
            payload=self.login_response
        )
        aioresponse.get(
            "https://example.org/_matrix/client/r0/sync?access_token=abc123",
            status=200,
            payload=self.sync_response
        )
        with pytest.raises(LocalProtocolError):
            resp2 = loop.run_until_complete(async_client.sync())

        resp = loop.run_until_complete(async_client.login("wordpass"))
        resp2 = loop.run_until_complete(async_client.sync())

        assert isinstance(resp, LoginResponse)
        assert isinstance(resp2, SyncResponse)

    def test_keys_upload(self, async_client, aioresponse):
        loop = asyncio.get_event_loop()

        with pytest.raises(LocalProtocolError):
            resp2 = loop.run_until_complete(async_client.keys_upload())

        assert not async_client.should_upload_keys

        aioresponse.post(
            "https://example.org/_matrix/client/r0/login",
            status=200,
            payload=self.login_response
        )
        aioresponse.post(
            "https://example.org/_matrix/client/r0/keys/upload?access_token=abc123",
            status=200,
            payload=self.keys_upload_response
        )

        resp = loop.run_until_complete(async_client.login("wordpass"))
        assert async_client.should_upload_keys
        assert not async_client.olm_account_shared

        resp2 = loop.run_until_complete(async_client.keys_upload())

        assert isinstance(resp2, KeysUploadResponse)
        assert async_client.olm_account_shared
        assert async_client.should_upload_keys

    def test_keys_query(self, async_client, aioresponse):
        loop = asyncio.get_event_loop()
        aioresponse.post(
            "https://example.org/_matrix/client/r0/login",
            status=200,
            payload=self.login_response
        )
        aioresponse.post(
            "https://example.org/_matrix/client/r0/keys/query?access_token=abc123",
            status=200,
            payload=self.keys_query_response
        )

        loop.run_until_complete(async_client.login("wordpass"))
        assert not async_client.should_query_keys

        async_client.receive_response(self.encryption_sync_response)
        assert async_client.should_query_keys

        loop.run_until_complete(async_client.keys_query())
        assert not async_client.should_query_keys
