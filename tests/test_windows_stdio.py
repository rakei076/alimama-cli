import io
import unittest


class WindowsStdioCompatibilityTest(unittest.TestCase):
    def test_gbk_replacement_handles_cli_emoji(self):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="gbk", errors="replace")
        stream.write("警告 ⚠️")
        stream.flush()
        self.assertIn("警告", buffer.getvalue().decode("gbk"))


if __name__ == "__main__":
    unittest.main()
