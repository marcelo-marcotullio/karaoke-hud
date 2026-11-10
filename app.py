"""HUD de desktop: ouve o microfone, reconhece a faixa e mostra a letra no tempo."""

import asyncio
import fcntl
import json
import os
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import sounddevice as sd
import webview
from AppKit import NSObject

from get_lyrics import fetch_lyrics, lines_around
from identify import identify
from record import DURATION, input_devices, record_sample, resolve_input
from settings import (
    CENTER_CODE,
    COMMAND,
    CONTROL,
    ESCAPE_CODE,
    OPTION,
    SHIFT,
    WINDOW_HEIGHT,
    captured_shortcut,
    load_config,
    menu_spec,
    save_config,
    shortcut_label,
    shortcut_matches,
    style_payload,
    sync_login_item,
)

_INSTANCE_LOCK = None
SAMPLE = Path(__file__).with_name("sample.wav")
TEMPLATE = Path(__file__).with_name("iconTemplate.png")
WIDTH = 920
VERSION = "0.2"

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  :root {
    --current-size: 34px;
    --side-size: 16px;
    --lyric-color: #ffffff;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; height: 100%;
    background: transparent; color: white;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  .hud {
    height: 100%;
    padding: 10px 22px 46px;
    display: flex; flex-direction: column; justify-content: center;
    text-align: center;
  }
  .lyrics {
    border-radius: 18px;
    padding: 6px 16px;
  }
  body.backdrop .lyrics {
    background: rgba(0, 0, 0, 0.55);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.28);
  }
  #status, #prev, #next, #current {
    text-shadow: 0 2px 14px rgba(0,0,0,0.95), 0 0 2px #000;
  }
  #status { color: rgba(255,255,255,0.72); font-size: 12px; min-height: 16px; }
  #prev, #next {
    color: var(--lyric-color);
    opacity: 0.55;
    font-size: var(--side-size);
    min-height: 22px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  #current {
    color: var(--lyric-color);
    font-size: var(--current-size);
    font-weight: 650; line-height: 1.15; padding: 4px 0;
  }
  #current.plain {
    font-size: 15px; font-weight: 450; text-align: left; color: white;
    overflow: auto; white-space: pre-wrap;
  }
  .controls {
    position: absolute; left: 50%; bottom: 8px; transform: translateX(-50%);
    display: flex; gap: 6px; align-items: center;
    opacity: 0; padding: 6px;
    border-radius: 999px; background: rgba(12,12,14,0.78);
    transition: opacity 0.15s ease;
  }
  .hud:hover .controls { opacity: 1; }
  button {
    background: transparent; color: white; border: 0; border-radius: 999px;
    padding: 5px 10px; font: inherit; font-size: 12px; cursor: pointer;
  }
  button:hover { background: rgba(255,255,255,0.16); }
  button.primary { background: white; color: #111; font-weight: 650; }
  .hint { color: rgba(255,255,255,0.55); font-size: 11px; padding: 0 4px; }
</style>
</head>
<body>
  <div class="hud">
    <div id="status"></div>
    <div class="lyrics">
      <div id="prev"></div>
      <div id="current"></div>
      <div id="next"></div>
    </div>
    <div class="controls">
      <button class="primary" onclick="call('listen')">Ouvir</button>
      <button onclick="call('nudge', -1)">−1s</button>
      <button onclick="call('nudge', -0.1)">−0.1s</button>
      <button onclick="call('nudge', 0.1)">+0.1s</button>
      <button onclick="call('nudge', 1)">+1s</button>
      <span class="hint">esc fecha</span>
      <button onclick="call('shutdown')">Fechar</button>
    </div>
  </div>
  <script>
    const SIZES = {s: ['26px', '14px'], m: ['34px', '16px'], l: ['46px', '20px']};
    function applyStyle(style) {
      if (!style) return;
      const pair = SIZES[style.size] || SIZES.m;
      const root = document.documentElement.style;
      root.setProperty('--current-size', pair[0]);
      root.setProperty('--side-size', pair[1]);
      root.setProperty('--lyric-color', style.color || '#ffffff');
      document.body.classList.toggle('backdrop', !!style.backdrop);
    }
    function render(state) {
      applyStyle(state.style);
      document.getElementById('status').textContent = state.status || '';
      document.getElementById('prev').textContent = state.prev || '';
      const current = document.getElementById('current');
      current.textContent = state.current || '';
      current.classList.toggle('plain', state.mode === 'plain');
      document.getElementById('next').textContent = state.next || '';
    }
    function call(name, arg) {
      if (!window.pywebview) return;
      const fn = pywebview.api[name];
      if (arg === undefined) fn();
      else fn(arg);
    }
    window.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        call('shutdown');
      }
    });
  </script>
</body>
</html>
"""


@dataclass
class Session:
    record_start: float
    offset: float
    artist: str
    title: str
    lines: list[tuple[float, str]] = field(default_factory=list)
    plain: str = ""


class StatusTarget(NSObject):
    """Alvo dos itens da barra de menus. Precisa ser NSObject para o AppKit chamar."""

    def listen_(self, _sender) -> None:
        self.app.listen()

    def quit_(self, _sender) -> None:
        self.app.shutdown()

    def pick_(self, sender) -> None:
        token = sender.representedObject()
        if token is not None:
            self.app.pick(str(token))

    def menuWillOpen_(self, menu) -> None:
        self.app.fill_menu(menu)


def _clock(seconds: float) -> str:
    whole = max(0, int(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def _acquire_lock():
    path = Path.home() / "Library/Application Support/karaoke-hud/instance.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("karaoke-hud já está aberto.", flush=True)
        raise SystemExit(0) from None
    return handle


class App:
    def __init__(self) -> None:
        self.window = None
        self.config = load_config()
        self.phase = "idle"
        self.session: Session | None = None
        self.adjust = 0.0
        self.generation = 0
        self._shown: tuple | None = None
        self._closing = False
        self._visible = False
        self._capturing = False
        self._placing = False
        self._pending_xy: tuple[float, float] | None = None
        self._save_at = 0.0
        self._lock = threading.Lock()
        self._audio = threading.Lock()
        self._js = threading.Lock()
        self._status = None
        self._status_target = None
        self._hotkey = None
        self._local_hotkey = None

    def attach(self, window) -> None:
        self.window = window
        window.events.moved += self._on_moved
        self._prepare_chrome()

    def _native_window(self):
        from webview.platforms.cocoa import BrowserView

        view = BrowserView.instances.get(self.window.uid) if self.window is not None else None
        return None if view is None else view.window

    def _prepare_chrome(self) -> None:
        from AppKit import NSApplication, NSApplicationActivationPolicyRegular
        from PyObjCTools import AppHelper

        def settle() -> None:
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
            self._name_and_icon(app)
            self._place()

        AppHelper.callAfter(settle)

    def _name_and_icon(self, app) -> None:
        from AppKit import NSImage
        from Foundation import NSBundle

        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info is not None:
            try:
                info["CFBundleName"] = "Karaoke HUD"
                info["CFBundleDisplayName"] = "Karaoke HUD"
            except TypeError:
                pass
        image = _dock_icon(str(TEMPLATE))
        if image is not None:
            app.setApplicationIconImage_(image)
        else:
            fallback = NSImage.alloc().initWithContentsOfFile_(str(TEMPLATE))
            if fallback is not None:
                app.setApplicationIconImage_(fallback)

    def _place(self) -> None:
        nswindow = self._native_window()
        if nswindow is None:
            return
        self._placing = True
        self._join_spaces(nswindow)
        self._set_height()
        if self.config.x is not None and self.config.y is not None:
            nswindow.setFrameOrigin_((self.config.x, self.config.y))
        else:
            nswindow.setFrameOrigin_(self._default_origin(nswindow))

        def unlock() -> None:
            time.sleep(0.3)
            self._placing = False

        threading.Thread(target=unlock, daemon=True).start()

    def _join_spaces(self, nswindow) -> None:
        from AppKit import (
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorIgnoresCycle,
        )

        nswindow.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorIgnoresCycle
        )
        nswindow.setHidesOnDeactivate_(False)

    def _set_height(self) -> None:
        nswindow = self._native_window()
        if nswindow is None:
            return
        frame = nswindow.frame()
        frame.size.height = WINDOW_HEIGHT[self.config.font_size]
        nswindow.setFrame_display_(frame, False)

    def _default_origin(self, nswindow):
        screen = nswindow.screen()
        frame = screen.frame() if screen is not None else None
        if frame is None:
            from AppKit import NSScreen

            frame = NSScreen.screens()[0].frame()
        size = nswindow.frame().size
        x = frame.origin.x + (frame.size.width - size.width) / 2
        y = frame.origin.y + 110
        return (x, y)

    def _on_moved(self, _x, _y) -> None:
        if self._placing or self._closing:
            return
        from PyObjCTools import AppHelper

        self._save_at = time.time() + 0.4
        AppHelper.callAfter(self._capture_origin)

    def _capture_origin(self) -> None:
        if self._placing:
            return
        nswindow = self._native_window()
        if nswindow is None:
            return
        origin = nswindow.frame().origin
        self._pending_xy = (float(origin.x), float(origin.y))

    def center(self) -> None:
        from PyObjCTools import AppHelper

        def go() -> None:
            nswindow = self._native_window()
            if nswindow is None:
                return
            self._placing = True
            self._pending_xy = None
            nswindow.setFrameOrigin_(self._default_origin(nswindow))
            self.config.x = None
            self.config.y = None
            save_config(self.config)

            def unlock() -> None:
                time.sleep(0.3)
                self._placing = False

            threading.Thread(target=unlock, daemon=True).start()

        AppHelper.callAfter(go)

    def reveal(self) -> None:
        """Mostra a letra sem virar a janela ativa."""
        if self._closing or self.window is None or self._visible:
            return
        self._visible = True
        from PyObjCTools import AppHelper

        nswindow = self._native_window()
        if nswindow is None:
            self.window.show()
            return

        def _show() -> None:
            self._join_spaces(nswindow)
            nswindow.orderFrontRegardless()

        AppHelper.callAfter(_show)

    def conceal(self) -> None:
        if self.window is None or not self._visible:
            return
        self._visible = False
        self.window.hide()

    def _note(self, message: str) -> None:
        if self.phase == "playing":
            return
        self._flash(message)

    def _flash(self, message: str) -> None:
        self.ui(status="", current=message, prev="", next="")
        self.reveal()
        generation = self.generation

        def hide_later() -> None:
            time.sleep(3.5)
            with self._lock:
                if generation != self.generation or self.phase == "playing":
                    return
            self.conceal()

        threading.Thread(target=hide_later, daemon=True).start()

    def ui(self, **state) -> None:
        if self._closing or self.window is None:
            return
        # evaluate_js espera a thread da interface. Chamá-lo dela mesma trava.
        if threading.current_thread() is threading.main_thread():
            threading.Thread(target=lambda: self.ui(**state), daemon=True).start()
            return
        state.setdefault("style", style_payload(self.config))
        script = f"render({json.dumps(state, ensure_ascii=False)})"
        try:
            with self._js:
                self.window.evaluate_js(script)
        except Exception:
            traceback.print_exc()

    def listen(self) -> None:
        with self._lock:
            self.generation += 1
            generation = self.generation
            self.phase = "recording"
            self.session = None
            self.adjust = 0.0
            self._shown = None
        self.conceal()
        sd.stop()
        threading.Thread(target=self._run, args=(generation,), daemon=True).start()

    def nudge(self, seconds: float) -> None:
        with self._lock:
            self.adjust += float(seconds)
            self._shown = None

    def shutdown(self) -> None:
        # Fechar pelo botão chama isto num fio que, em seguida, espera o JS.
        # window.destroy() nesse momento deixa os dois se esperando. O processo sai depois.
        self._closing = True

        def _close() -> None:
            time.sleep(0.25)
            os._exit(0)

        threading.Thread(target=_close, daemon=True).start()

    def pick(self, token: str) -> None:
        if token == "auto-next":
            self.config.auto_next = not self.config.auto_next
        elif token == "backdrop":
            self.config.backdrop = not self.config.backdrop
        elif token == "login":
            self.config.login_item = not self.config.login_item
            save_config(self.config)
            sync_login_item(self.config.login_item)
            return
        elif token == "center":
            self.center()
            return
        elif token == "capture-shortcut":
            self._capturing = True
            self._note("Pressione o novo atalho. Esc cancela.")
            return
        elif token.startswith("size:"):
            chosen = token.split(":", 1)[1]
            if chosen in WINDOW_HEIGHT:
                self.config.font_size = chosen
                self._set_height()
        elif token.startswith("color:"):
            self.config.color = token.split(":", 1)[1]
        elif token.startswith("mic:"):
            self.config.microphone = token[4:] or None
        else:
            return
        self.config.normalized()
        save_config(self.config)
        self._shown = None
        if self._visible and self.phase != "playing":
            self.ui(status="", current="", prev="", next="")

    def install_hotkey(self) -> None:
        # O monitor global tem de nascer na thread da interface. pynput derruba o processo.
        from AppKit import (
            NSEvent,
            NSEventMaskKeyDown,
            NSImage,
            NSMenu,
            NSSquareStatusItemLength,
            NSStatusBar,
        )
        from PyObjCTools import AppHelper

        def register() -> None:
            def global_handler(event) -> None:
                self._on_key(event)

            def local_handler(event):
                if self._on_key(event):
                    return None
                return event

            self._hotkey = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown,
                global_handler,
            )
            self._local_hotkey = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown,
                local_handler,
            )
            if self._hotkey is None:
                print(
                    "Atalho global indisponível. O macOS não entregou o monitor de teclado.",
                    flush=True,
                )

            icon = NSImage.alloc().initWithContentsOfFile_(str(TEMPLATE))
            if icon is not None:
                icon.setSize_((18, 18))
                icon.setTemplate_(True)

            target = StatusTarget.alloc().init()
            target.app = self
            self._status_target = target
            menu = NSMenu.alloc().init()
            menu.setDelegate_(target)
            menu.setAutoenablesItems_(False)
            self.fill_menu(menu)

            status = NSStatusBar.systemStatusBar().statusItemWithLength_(NSSquareStatusItemLength)
            button = status.button()
            if icon is not None:
                button.setImage_(icon)
            button.setToolTip_("karaoke-hud")
            status.setMenu_(menu)
            self._status = status

        AppHelper.callAfter(register)

    def _on_key(self, event) -> bool:
        chars = event.charactersIgnoringModifiers() or ""
        flags = int(event.modifierFlags())
        code = int(event.keyCode())
        if self._capturing:
            if code == ESCAPE_CODE:
                self._capturing = False
                self._note("Atalho mantido.")
                return True
            captured = captured_shortcut(chars, code, flags)
            if captured is None:
                return False
            self._capturing = False
            self._apply_shortcut(captured)
            return True
        if shortcut_matches(self.config, chars, code, flags):
            self.listen()
            return True
        if (
            code == CENTER_CODE
            and flags & COMMAND
            and flags & SHIFT
            and not flags & OPTION
            and not flags & CONTROL
        ):
            self.center()
            return True
        return False

    def _apply_shortcut(self, captured: dict) -> None:
        self.config.key = captured["key"]
        self.config.code = captured["code"]
        self.config.command = captured["command"]
        self.config.shift = captured["shift"]
        self.config.option = captured["option"]
        self.config.control = captured["control"]
        save_config(self.config)
        self._note(f"Novo atalho: {shortcut_label(self.config)}")

    def fill_menu(self, menu) -> None:
        from AppKit import (
            NSDownArrowFunctionKey,
            NSEventModifierFlagCommand,
            NSEventModifierFlagControl,
            NSEventModifierFlagOption,
            NSEventModifierFlagShift,
            NSLeftArrowFunctionKey,
            NSMenu,
            NSMenuItem,
            NSRightArrowFunctionKey,
            NSUpArrowFunctionKey,
        )

        arrows = {
            125: NSDownArrowFunctionKey,
            126: NSUpArrowFunctionKey,
            123: NSLeftArrowFunctionKey,
            124: NSRightArrowFunctionKey,
        }
        while menu.numberOfItems() > 0:
            menu.removeItemAtIndex_(0)
        menu.setAutoenablesItems_(False)
        devices = [name for _index, name in input_devices()]

        def append(host, entry: dict) -> None:
            title = entry.get("title") or ""
            token = entry.get("token") or ""
            children = entry.get("children")
            if not title and not token and not children:
                host.addItem_(NSMenuItem.separatorItem())
                return
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "", "")
            if children:
                submenu = NSMenu.alloc().init()
                submenu.setAutoenablesItems_(False)
                for child in children:
                    append(submenu, child)
                item.setSubmenu_(submenu)
            else:
                item.setEnabled_(entry.get("enabled", bool(token)))
                if token and self._status_target is not None:
                    action = {"listen": "listen:", "quit": "quit:"}.get(token, "pick:")
                    item.setAction_(action)
                    item.setTarget_(self._status_target)
                    item.setRepresentedObject_(token)
                    if entry.get("checked"):
                        item.setState_(1)
                    self._bind_key(item, token, arrows, {
                        "command": NSEventModifierFlagCommand,
                        "shift": NSEventModifierFlagShift,
                        "option": NSEventModifierFlagOption,
                        "control": NSEventModifierFlagControl,
                    })
            host.addItem_(item)

        for entry in menu_spec(self.config, devices):
            append(menu, entry)

    def _bind_key(self, item, token: str, arrows: dict, flags: dict) -> None:
        if token == "listen":
            key = arrows.get(self.config.code) if self.config.code and not self.config.key else self.config.key
            if not key:
                return
            item.setKeyEquivalent_(key)
            item.setKeyEquivalentModifierMask_(self._modifier_mask(flags))
        elif token == "center":
            item.setKeyEquivalent_(arrows[CENTER_CODE])
            item.setKeyEquivalentModifierMask_(flags["command"] | flags["shift"])
        elif token == "quit":
            item.setKeyEquivalent_("q")
            item.setKeyEquivalentModifierMask_(flags["command"])

    def _modifier_mask(self, flags: dict) -> int:
        mask = 0
        if self.config.command:
            mask |= int(flags["command"])
        if self.config.shift:
            mask |= int(flags["shift"])
        if self.config.option:
            mask |= int(flags["option"])
        if self.config.control:
            mask |= int(flags["control"])
        return mask

    def loop(self) -> None:
        while not self._closing:
            time.sleep(0.1)
            if self._pending_xy is not None and time.time() >= self._save_at:
                self.config.x, self.config.y = self._pending_xy
                self._pending_xy = None
                save_config(self.config)
            self._publish()

    def _publish(self) -> None:
        with self._lock:
            if self.phase != "playing" or self.session is None:
                return
            session = self.session
            position = session.offset + (time.time() - session.record_start) + self.adjust
            adjust = self.adjust

        if session.lines:
            previous, current, upcoming = lines_around(session.lines, position)
            mode = "sync"
        else:
            previous, current, upcoming = "", session.plain, ""
            mode = "plain"

        if session.lines and position > session.lines[-1][0] + 6:
            with self._lock:
                self.phase = "idle"
                self.session = None
            self.conceal()
            if self.config.auto_next and not self._closing:
                self.listen()
            return

        marker = (previous, current, upcoming, int(position), round(adjust, 1), self.config.font_size, self.config.color, self.config.backdrop)
        if marker == self._shown:
            return
        self._shown = marker
        label = f"{session.artist} — {session.title}   {_clock(position)}"
        if adjust:
            label += f"   {adjust:+.1f}s"
        self.ui(status=label, prev=previous, current=current, next=upcoming, mode=mode)
        self.reveal()

    def _run(self, generation: int) -> None:
        try:
            self._listen(generation)
        except Exception as exc:
            traceback.print_exc()
            with self._lock:
                if generation != self.generation:
                    return
                self.phase = "error"
                self.session = None
            self._flash(f"Falhou: {exc}")

    def _listen(self, generation: int) -> None:
        def still_current() -> bool:
            with self._lock:
                return generation == self.generation

        with self._lock:
            recording = generation == self.generation
        if not recording:
            return
        device = resolve_input(self.config.microphone)
        with self._audio:
            if not still_current():
                return
            record_start = record_sample(SAMPLE, device=device)
        if not still_current():
            return
        with self._lock:
            self.phase = "identifying"
        found = asyncio.run(identify(SAMPLE))

        if not still_current():
            return
        if found is None:
            with self._lock:
                self.phase = "error"
            self._flash("Não reconheci a música.")
            return

        artist, title, offset = found
        lyrics = fetch_lyrics(artist, title)
        if not still_current():
            return

        synced = lyrics["synced"] if lyrics else []
        plain = lyrics["plain"] if lyrics else ""
        instrumental = bool(lyrics and lyrics["instrumental"])
        if not synced and (instrumental or not plain):
            self._flash(f"{artist} — {title}. Sem letra.")
            with self._lock:
                if generation == self.generation:
                    self.phase = "error"
                    self.session = None
            return

        session = Session(
            record_start=record_start,
            offset=offset,
            artist=artist,
            title=title,
            lines=synced,
            plain=plain,
        )
        with self._lock:
            if generation != self.generation:
                return
            self.session = session
            self.adjust = 0.0
            self.phase = "playing"
            self._shown = None


def _dock_icon(template_path: str):
    from AppKit import (
        NSBezierPath,
        NSColor,
        NSCompositingOperationDestinationIn,
        NSCompositingOperationSourceOver,
        NSImage,
    )

    if not Path(template_path).is_file():
        return None
    side = 256.0
    icon = NSImage.alloc().initWithSize_((side, side))
    icon.lockFocus()
    NSColor.colorWithCalibratedRed_green_blue_alpha_(0.11, 0.12, 0.16, 1).set()
    NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(((0, 0), (side, side)), 58, 58).fill()
    mark = NSImage.alloc().initWithContentsOfFile_(template_path)
    if mark is not None:
        glyph = 150.0
        white = NSImage.alloc().initWithSize_((glyph, glyph))
        white.lockFocus()
        NSColor.whiteColor().set()
        NSBezierPath.fillRect_(((0, 0), (glyph, glyph)))
        mark.drawInRect_fromRect_operation_fraction_(
            ((0, 0), (glyph, glyph)),
            ((0, 0), (0, 0)),
            NSCompositingOperationDestinationIn,
            1.0,
        )
        white.unlockFocus()
        margin = (side - glyph) / 2
        white.drawInRect_fromRect_operation_fraction_(
            ((margin, margin), (glyph, glyph)),
            ((0, 0), (0, 0)),
            NSCompositingOperationSourceOver,
            1.0,
        )
    icon.unlockFocus()
    return icon


def main() -> None:
    from AppKit import NSApplicationActivateIgnoringOtherApps, NSWorkspace

    global _INSTANCE_LOCK
    _INSTANCE_LOCK = _acquire_lock()
    config = load_config()
    if config.login_item:
        sync_login_item(True)
    print(
        f"karaoke-hud {VERSION} · {shortcut_label(config)} · {config.microphone or 'microfone padrão'}",
        flush=True,
    )
    previous = NSWorkspace.sharedWorkspace().frontmostApplication()
    app = App()
    window = webview.create_window(
        "karaoke-hud",
        html=HTML,
        js_api=app,
        width=WIDTH,
        height=WINDOW_HEIGHT[config.font_size],
        resizable=True,
        min_size=(520, 150),
        frameless=True,
        easy_drag=True,
        on_top=True,
        hidden=True,
        focus=False,
        transparent=True,
        shadow=False,
        background_color="#000000",
        text_select=False,
    )

    def ready(window) -> None:
        app.attach(window)
        app.install_hotkey()

        def give_focus_back() -> None:
            if previous is not None:
                previous.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)

        from PyObjCTools import AppHelper

        AppHelper.callAfter(give_focus_back)
        app.loop()

    webview.start(ready, window)


if __name__ == "__main__":
    main()
