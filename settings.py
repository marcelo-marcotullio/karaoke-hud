"""Configuração local do karaoke-hud.

O arquivo fica em ~/Library/Application Support/karaoke-hud/config.json,
fora do git. O atalho, a legenda, o microfone, a posição da janela e o
item de início de sessão moram aqui.
"""

from __future__ import annotations

import json
import os
import plistlib
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

SUPPORT = Path.home() / "Library/Application Support/karaoke-hud"
CONFIG_PATH = SUPPORT / "config.json"
LOGIN_LABEL = "br.ia.karaoke-hud"
LOGIN_PLIST = Path.home() / "Library/LaunchAgents" / f"{LOGIN_LABEL}.plist"

COMMAND = 1 << 20
SHIFT = 1 << 17
OPTION = 1 << 19
CONTROL = 1 << 18
MODIFIER_BITS = {
    "command": COMMAND,
    "shift": SHIFT,
    "option": OPTION,
    "control": CONTROL,
}
MODIFIER_KEY_CODES = {54, 55, 56, 57, 58, 59, 60, 61, 62}
ESCAPE_CODE = 53
CENTER_CODE = 125  # seta para baixo, ⌘⇧↓ centraliza

CODE_LABELS = {
    36: "↩",
    48: "⇥",
    49: "espaço",
    51: "⌫",
    53: "esc",
    123: "←",
    124: "→",
    125: "↓",
    126: "↑",
}

FONT_SIZES = ("s", "m", "l")
COLORS = {
    "white": "#ffffff",
    "amber": "#ffd56a",
    "cyan": "#9be7ff",
}
COLOR_LABELS = {"white": "Branco", "amber": "Âmbar", "cyan": "Ciano"}
SIZE_LABELS = {"s": "Pequena", "m": "Média", "l": "Grande"}
WINDOW_HEIGHT = {"s": 168, "m": 200, "l": 256}


@dataclass
class Config:
    key: str = "k"
    code: int | None = None
    command: bool = True
    shift: bool = True
    option: bool = False
    control: bool = False
    font_size: str = "m"
    color: str = "white"
    backdrop: bool = True
    auto_next: bool = True
    microphone: str | None = None
    login_item: bool = False
    x: float | None = None
    y: float | None = None

    def normalized(self) -> Config:
        if self.font_size not in FONT_SIZES:
            self.font_size = "m"
        if self.color not in COLORS:
            self.color = "white"
        if self.code is not None:
            self.code = int(self.code)
        self.key = (self.key or "").lower()[:1]
        if not self.microphone:
            self.microphone = None
        return self


def load_config(path: Path = CONFIG_PATH) -> Config:
    if not path.is_file():
        return Config()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Config()
    if not isinstance(raw, dict):
        return Config()
    known = {field: raw[field] for field in asdict(Config()) if field in raw}
    if known.get("code") is None:
        known["code"] = None
    try:
        return Config(**known).normalized()
    except TypeError:
        return Config()


def save_config(config: Config, path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(config.normalized())
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def shortcut_label(config: Config) -> str:
    parts: list[str] = []
    if config.control:
        parts.append("⌃")
    if config.option:
        parts.append("⌥")
    if config.shift:
        parts.append("⇧")
    if config.command:
        parts.append("⌘")
    if config.code is not None and not config.key:
        parts.append(CODE_LABELS.get(int(config.code), "tecla"))
    else:
        parts.append((config.key or "?").upper())
    return "".join(parts)


def shortcut_matches(config: Config, chars: str, key_code: int, flags: int) -> bool:
    for name, bit in MODIFIER_BITS.items():
        if bool(flags & bit) != bool(getattr(config, name)):
            return False
    if config.code is not None and not config.key:
        return int(key_code) == int(config.code)
    text = (chars or "").lower()
    return len(text) == 1 and text == config.key


def captured_shortcut(chars: str, key_code: int, flags: int) -> dict | None:
    """Atalho novo, ou None se a tecla ainda não completa uma combinação."""
    if key_code in MODIFIER_KEY_CODES or key_code == ESCAPE_CODE:
        return None
    mods = {name: bool(flags & bit) for name, bit in MODIFIER_BITS.items()}
    if not any(mods.values()):
        return None
    text = (chars or "")
    if len(text) == 1 and text.isprintable() and ord(text) < 0xF700:
        return {**mods, "key": text.lower(), "code": None}
    return {**mods, "key": "", "code": int(key_code)}


def style_payload(config: Config) -> dict:
    config.normalized()
    return {
        "size": config.font_size,
        "color": COLORS[config.color],
        "backdrop": config.backdrop,
    }


def menu_spec(config: Config, devices: list[str]) -> list[dict]:
    """Descrição do menu da barra. `token` vazio é separador."""
    config.normalized()
    microphone = config.microphone
    known = set(devices)
    items: list[dict] = [
        {"title": "Ouvir", "token": "listen", "key": shortcut_label(config)},
        {
            "title": "Ouvir a próxima sozinho",
            "token": "auto-next",
            "checked": config.auto_next,
        },
        {"title": "Centralizar", "token": "center", "key": "⌘⇧↓"},
        {"title": ""},
        {
            "title": "Tamanho",
            "children": [
                {
                    "title": SIZE_LABELS[name],
                    "token": f"size:{name}",
                    "checked": config.font_size == name,
                }
                for name in FONT_SIZES
            ],
        },
        {
            "title": "Cor",
            "children": [
                {
                    "title": COLOR_LABELS[name],
                    "token": f"color:{name}",
                    "checked": config.color == name,
                }
                for name in COLORS
            ],
        },
        {
            "title": "Fundo atrás da letra",
            "token": "backdrop",
            "checked": config.backdrop,
        },
        {"title": ""},
    ]
    mics: list[dict] = [
        {
            "title": "Padrão do sistema",
            "token": "mic:",
            "checked": microphone is None or microphone not in known,
        }
    ]
    for name in devices:
        mics.append(
            {
                "title": name,
                "token": f"mic:{name}",
                "checked": microphone == name,
            }
        )
    if microphone and microphone not in known:
        mics.append(
            {
                "title": f"{microphone} (ausente)",
                "token": "",
                "enabled": False,
            }
        )
    items.append({"title": "Microfone", "children": mics})
    items.extend(
        [
            {"title": f"Atalho: {shortcut_label(config)}", "token": "capture-shortcut"},
            {
                "title": "Abrir ao entrar",
                "token": "login",
                "checked": config.login_item,
            },
            {"title": ""},
            {"title": "Sair", "token": "quit", "key": "⌘Q"},
        ]
    )
    return items


def login_plist(python: str, app_py: str, workdir: str, log_path: str) -> dict:
    return {
        "Label": LOGIN_LABEL,
        "ProgramArguments": [python, "-u", app_py],
        "WorkingDirectory": workdir,
        "RunAtLoad": True,
        "LimitLoadToSessionType": "Aqua",
        "ProcessType": "Interactive",
        "StandardOutPath": log_path,
        "StandardErrorPath": log_path,
    }


def sync_login_item(enabled: bool, *, apply_launchctl: bool = True) -> None:
    """Registra ou tira o app do início da sessão.

    `enable`/`disable` não encerram o processo que já está aberto. O plist
    aponta para o Python e o app.py deste diretório.
    """
    root = Path(__file__).resolve().parent
    interpreter = _interpreter()
    plist_path = LOGIN_PLIST
    if enabled:
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        payload = login_plist(
            interpreter,
            str(root / "app.py"),
            str(root),
            str(SUPPORT / "launchd.log"),
        )
        SUPPORT.mkdir(parents=True, exist_ok=True)
        plist_path.write_bytes(plistlib.dumps(payload))
        _launchctl("enable", apply_launchctl)
        return
    _launchctl("disable", apply_launchctl)
    plist_path.unlink(missing_ok=True)


def _interpreter() -> str:
    override = os.environ.get("KARAOKE_PYTHON")
    if override:
        return override
    return str(Path(__file__).resolve().parent / "venv" / "bin" / "python")


def _launchctl(verb: str, apply: bool) -> None:
    if not apply:
        return
    target = f"gui/{os.getuid()}/{LOGIN_LABEL}"
    subprocess.run(["launchctl", verb, target], check=False, capture_output=True)
