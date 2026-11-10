import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from settings import (
    COMMAND,
    CONTROL,
    SHIFT,
    Config,
    captured_shortcut,
    load_config,
    login_plist,
    menu_spec,
    save_config,
    shortcut_label,
    shortcut_matches,
    style_payload,
)


class SettingsTest(unittest.TestCase):
    def test_roundtrip_and_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            config = Config(font_size="nope", color="nope", microphone="")
            save_config(config, path)
            loaded = load_config(path)
        self.assertEqual(loaded.font_size, "m")
        self.assertEqual(loaded.color, "white")
        self.assertIsNone(loaded.microphone)
        self.assertTrue(loaded.auto_next)
        self.assertTrue(loaded.backdrop)
        self.assertEqual(shortcut_label(loaded), "⇧⌘K")

    def test_shortcut(self) -> None:
        config = Config()
        self.assertTrue(shortcut_matches(config, "K", 40, COMMAND | SHIFT))
        self.assertFalse(shortcut_matches(config, "k", 40, COMMAND))
        self.assertFalse(shortcut_matches(config, "k", 40, COMMAND | SHIFT | CONTROL))
        self.assertIsNone(captured_shortcut("", 55, COMMAND))
        captured = captured_shortcut("m", 46, COMMAND | CONTROL)
        self.assertEqual(captured["key"], "m")
        self.assertIsNone(captured["code"])
        self.assertTrue(captured["control"])
        arrow = captured_shortcut("\uf701", 125, COMMAND | SHIFT)
        self.assertEqual(arrow["code"], 125)
        self.assertEqual(arrow["key"], "")

    def test_menu_reflects_choices(self) -> None:
        config = Config(font_size="l", color="amber", microphone="C922 Pro Stream Webcam", auto_next=False)
        items = menu_spec(config, ["MacBook Pro Microphone", "C922 Pro Stream Webcam"])
        titles = [item["title"] for item in items]
        self.assertIn("Ouvir", titles)
        self.assertIn("Sair", titles)
        auto = next(item for item in items if item.get("token") == "auto-next")
        self.assertFalse(auto["checked"])
        sizes = next(item for item in items if item["title"] == "Tamanho")["children"]
        self.assertTrue(next(item for item in sizes if item["token"] == "size:l")["checked"])
        mics = next(item for item in items if item["title"] == "Microfone")["children"]
        self.assertTrue(next(item for item in mics if item["title"].startswith("C922"))["checked"])
        self.assertFalse(mics[0]["checked"])

    def test_missing_microphone_falls_back(self) -> None:
        items = menu_spec(Config(microphone="Sumiu"), ["MacBook Pro Microphone"])
        mics = next(item for item in items if item["title"] == "Microfone")["children"]
        self.assertTrue(mics[0]["checked"])
        self.assertFalse(mics[-1]["enabled"])

    def test_style_and_login_plist(self) -> None:
        payload = style_payload(Config(font_size="s", color="cyan", backdrop=False))
        self.assertEqual(payload["color"], "#9be7ff")
        self.assertFalse(payload["backdrop"])
        plist = login_plist("/usr/bin/python", "/app.py", "/work", "/log")
        self.assertEqual(plist["ProgramArguments"], ["/usr/bin/python", "-u", "/app.py"])
        self.assertTrue(plist["RunAtLoad"])
        self.assertEqual(plist["LimitLoadToSessionType"], "Aqua")


if __name__ == "__main__":
    unittest.main()
