import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import alimama_cli


class AuthHelpersTest(unittest.TestCase):
    def test_cookie_dict_filters_domains_and_prefers_one_domain(self):
        items = [
            {"name": "cookie2", "value": "generic", "domain": ".alimama.com"},
            {"name": "cookie2", "value": "specific", "domain": "one.alimama.com"},
            {"name": "unb", "value": "123", "domain": ".taobao.com"},
            {"name": "ignored", "value": "x", "domain": "example.com"},
        ]
        self.assertEqual(
            alimama_cli._cookie_dict(items),
            {"cookie2": "specific", "unb": "123"},
        )

    def test_login_cookie_accepts_cookie2_or_unb(self):
        self.assertTrue(alimama_cli._has_login_cookie({"cookie2": "x"}))
        self.assertTrue(alimama_cli._has_login_cookie({"unb": "x"}))
        self.assertFalse(alimama_cli._has_login_cookie({"cna": "x"}))

    def test_windows_browser_override(self):
        with tempfile.TemporaryDirectory() as directory:
            browser = Path(directory) / "chrome.exe"
            browser.touch()
            with patch.dict("os.environ", {"ALIMAMA_BROWSER_PATH": str(browser)}, clear=False):
                self.assertEqual(alimama_cli._find_windows_browser(), browser)

    def test_windows_dispatches_to_cdp(self):
        expected = {"cookie2": "secret"}
        with patch("alimama_cli.platform.system", return_value="Windows"), patch(
            "alimama_cli._windows_cdp_cookies", return_value=expected
        ) as cdp:
            self.assertEqual(alimama_cli.load_alimama_cookies(), expected)
            cdp.assert_called_once_with()

    def test_windows_reuses_running_dedicated_browser(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {"LOCALAPPDATA": directory}, clear=False
        ):
            state = Path(directory) / "alimama-cli"
            state.mkdir()
            (state / "cdp-port").write_text("32123", encoding="utf-8")
            with patch(
                "alimama_cli._cdp_cookies", return_value={"cookie2": "secret"}
            ) as read_cookies, patch("alimama_cli.subprocess.Popen") as popen:
                self.assertEqual(
                    alimama_cli._windows_cdp_cookies(), {"cookie2": "secret"}
                )
                read_cookies.assert_called_once_with(32123)
                popen.assert_not_called()

    def test_windows_launches_browser_with_dedicated_profile(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {"LOCALAPPDATA": directory}, clear=False
        ):
            browser = Path(directory) / "chrome.exe"
            browser.touch()
            with patch("alimama_cli._find_windows_browser", return_value=browser), patch(
                "alimama_cli._free_local_port", return_value=32123
            ), patch("alimama_cli._wait_for_cdp"), patch(
                "alimama_cli._wait_for_windows_login", return_value={"unb": "123"}
            ), patch("alimama_cli.subprocess.Popen") as popen:
                self.assertEqual(alimama_cli._windows_cdp_cookies(), {"unb": "123"})
                args = popen.call_args.args[0]
                self.assertIn("--remote-debugging-address=127.0.0.1", args)
                self.assertIn(
                    f"--user-data-dir={Path(directory) / 'alimama-cli' / 'chrome-profile'}",
                    args,
                )


if __name__ == "__main__":
    unittest.main()
