"""Tests for the legacy TLS renegotiation fallback (issue #41)."""

from requests.exceptions import SSLError

from tests.conftest import LOGIN_URL, show_cmd_url

_LEGACY_MARKER = "UNSAFE_LEGACY_RENEGOTIATION_DISABLED"


class TestLegacyTLSFallback:
    def test_legacy_ssl_error_triggers_fallback_and_retry_succeeds(
        self, client, requests_mock
    ):
        requests_mock.post(
            LOGIN_URL,
            [
                {
                    "exc": SSLError(
                        f"[SSL: {_LEGACY_MARKER}] unsafe legacy renegotiation disabled"
                    )
                },
                {"json": {"Status": "Success", "sid": "abc123"}},
            ],
        )

        result = client.login()

        assert result is True
        assert client._sid == "abc123"
        assert client._legacy_ssl is True

    def test_legacy_fallback_logs_warning(self, client, requests_mock, caplog):
        requests_mock.post(
            LOGIN_URL,
            [
                {
                    "exc": SSLError(
                        f"[SSL: {_LEGACY_MARKER}] unsafe legacy renegotiation disabled"
                    )
                },
                {"json": {"Status": "Success", "sid": "abc123"}},
            ],
        )

        with caplog.at_level("WARNING"):
            client.login()

        assert "legacy TLS renegotiation" in caplog.text

    def test_non_legacy_ssl_error_is_not_swallowed_as_success(
        self, client, requests_mock
    ):
        requests_mock.post(
            LOGIN_URL,
            exc=SSLError(
                "certificate verify failed: unable to get local issuer certificate"
            ),
        )

        result = client.login()

        assert result is False
        assert client._legacy_ssl is False

    def test_legacy_flag_prevents_repeated_retry_loop(self, client, requests_mock):
        client._legacy_ssl = True  # simulate an already-switched session

        requests_mock.post(
            LOGIN_URL,
            exc=SSLError(
                f"[SSL: {_LEGACY_MARKER}] unsafe legacy renegotiation disabled"
            ),
        )

        result = client.login()

        assert result is False

    def test_subsequent_calls_after_fallback_dont_reattempt_normal_path(
        self, client, requests_mock
    ):
        requests_mock.post(
            LOGIN_URL,
            [
                {
                    "exc": SSLError(
                        f"[SSL: {_LEGACY_MARKER}] unsafe legacy renegotiation disabled"
                    )
                },
                {"json": {"Status": "Success", "sid": "abc123"}},
            ],
        )
        assert client.login() is True
        assert client._legacy_ssl is True

        requests_mock.get(
            show_cmd_url(sid="abc123"),
            json={"Status": "Success", "Command output": "Total Clients:0"},
        )

        assert client.get_clients() == {}
