"""Tests for ArubaIAPClient: auth, show-cmd parsing, and failure signatures."""

from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ConnectTimeout, Timeout

from tests.conftest import LOGIN_URL, show_cmd_url


class TestLogin:
    def test_login_success_stores_sid(self, client, requests_mock):
        requests_mock.post(LOGIN_URL, json={"Status": "Success", "sid": "abc123"})

        assert client.login() is True
        assert client._sid == "abc123"

    def test_login_bad_credentials_returns_false(self, client, requests_mock):
        requests_mock.post(
            LOGIN_URL, json={"Status": "Fail", "Error message": "Invalid credentials"}
        )

        assert client.login() is False
        assert client._sid is None

    def test_login_connect_timeout_returns_false(self, client, requests_mock):
        requests_mock.post(LOGIN_URL, exc=ConnectTimeout)

        assert client.login() is False

    def test_login_connection_reset_returns_false(self, client, requests_mock):
        requests_mock.post(
            LOGIN_URL,
            exc=RequestsConnectionError(
                ConnectionResetError("Connection reset by peer")
            ),
        )

        assert client.login() is False


class TestShowCmdFailureSignatures:
    """The three known intermittent failure modes, at the _show_cmd layer."""

    def test_empty_body_returns_none_and_clears_sid(
        self, logged_in_client, requests_mock
    ):
        requests_mock.get(
            show_cmd_url(sid="fake-sid-123"),
            text="",
            status_code=200,
            headers={"Content-Length": "0"},
        )

        assert logged_in_client.get_clients() is None
        assert logged_in_client._sid is None

    def test_read_timeout_returns_none_and_clears_sid(
        self, logged_in_client, requests_mock
    ):
        requests_mock.get(
            show_cmd_url(sid="fake-sid-123"), exc=Timeout("Read timed out")
        )

        assert logged_in_client.get_clients() is None
        assert logged_in_client._sid is None

    def test_connection_error_returns_none_and_clears_sid(
        self, logged_in_client, requests_mock
    ):
        requests_mock.get(
            show_cmd_url(sid="fake-sid-123"),
            exc=RequestsConnectionError(
                ConnectionResetError("Connection reset by peer")
            ),
        )

        assert logged_in_client.get_clients() is None
        assert logged_in_client._sid is None

    def test_session_expired_triggers_relogin_and_retry(
        self, logged_in_client, requests_mock
    ):
        requests_mock.get(
            show_cmd_url(sid="fake-sid-123"),
            json={"Status-code": 1},
        )
        requests_mock.post(LOGIN_URL, json={"Status": "Success", "sid": "new-sid-456"})
        requests_mock.get(
            show_cmd_url(sid="new-sid-456"),
            json={"Status": "Success", "Command output": "Total Clients:0"},
        )

        result = logged_in_client.get_clients()

        assert result == {}
        assert logged_in_client._sid == "new-sid-456"


class TestGetClientsParsing:
    def test_parses_two_clients_and_skips_headers(
        self, logged_in_client, requests_mock, raw_output
    ):
        cli_text = raw_output("show_clients_ok.txt")
        requests_mock.get(
            show_cmd_url(sid="fake-sid-123"),
            json={"Status": "Success", "Command output": cli_text.replace("\n", "\\n")},
        )

        clients = logged_in_client.get_clients()

        assert len(clients) == 2
        kitchen = clients["aa:bb:cc:dd:ee:01"]
        assert kitchen["name"] == "Kitchen Echo"
        assert kitchen["ip"] == "192.168.1.50"
        assert kitchen["speed"] == "130M"

        phone = clients["aa:bb:cc:dd:ee:02"]
        assert phone["name"] == "johns-phone"

    def test_missing_speed_column_is_none(
        self, logged_in_client, requests_mock, raw_output
    ):
        cli_text = raw_output("show_clients_no_speed.txt")
        requests_mock.get(
            show_cmd_url(sid="fake-sid-123"),
            json={"Status": "Success", "Command output": cli_text.replace("\n", "\\n")},
        )

        clients = logged_in_client.get_clients()

        assert clients["aa:bb:cc:dd:ee:03"]["speed"] is None

    def test_empty_name_falls_back_to_mac(
        self, logged_in_client, requests_mock, raw_output
    ):
        cli_text = raw_output("show_clients_empty_name.txt")
        requests_mock.get(
            show_cmd_url(sid="fake-sid-123"),
            json={"Status": "Success", "Command output": cli_text.replace("\n", "\\n")},
        )

        clients = logged_in_client.get_clients()

        assert clients["aa:bb:cc:dd:ee:04"]["name"] == "aa:bb:cc:dd:ee:04"

    def test_no_clients_returns_empty_dict(self, logged_in_client, requests_mock):
        requests_mock.get(
            show_cmd_url(sid="fake-sid-123"),
            json={"Status": "Success", "Command output": "Total Clients:0"},
        )

        assert logged_in_client.get_clients() == {}


class TestConnection:
    def test_test_connection_logs_out_after_success(self, client, requests_mock):
        requests_mock.post(LOGIN_URL, json={"Status": "Success", "sid": "abc123"})
        logout = requests_mock.post(
            f"{client.base_url}/logout", json={"Status": "Success"}
        )

        assert client.test_connection() is True
        assert logout.called
