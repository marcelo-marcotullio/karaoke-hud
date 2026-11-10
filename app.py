"""HUD de desktop: ouve o microfone, reconhece a faixa e mostra a letra no tempo."""

import asyncio
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
from record import DURATION, record_sample

SAMPLE = Path(__file__).with_name("sample.wav")
WIDTH = 920
HEIGHT = 188

HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; }
  html, body {
    margin: 0; height: 100%;
    background: transparent; color: white;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  .hud {
    height: 100%;
    padding: 8px 28px 46px;
    display: flex; flex-direction: column; justify-content: center;
    text-align: center;
  }
  #status, #prev, #next, #current {
    text-shadow: 0 2px 14px rgba(0,0,0,0.95), 0 0 2px #000;
  }
  #status { color: rgba(255,255,255,0.72); font-size: 12px; min-height: 16px; }
  #prev, #next {
    color: rgba(255,255,255,0.55); font-size: 16px; min-height: 22px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  #current { font-size: 34px; font-weight: 650; line-height: 1.15; padding: 4px 0; }
  #current.plain {
    font-size: 15px; font-weight: 450; text-align: left;
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
    <div id="prev"></div>
    <div id="current"></div>
    <div id="next"></div>
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
    function render(state) {
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
      if (event.metaKey && event.shiftKey && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        call('listen');
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


def _clock(seconds: float) -> str:
    whole = max(0, int(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


class App:
    def __init__(self) -> None:
        self.window = None
        self.phase = "idle"
        self.session: Session | None = None
        self.adjust = 0.0
        self.generation = 0
        self._shown: tuple | None = None
        self._closing = False
        self._visible = False
        self._lock = threading.Lock()
        self._audio = threading.Lock()

    def attach(self, window) -> None:
        self.window = window
        self._stay_in_background()

    def _native_window(self):
        from webview.platforms.cocoa import BrowserView

        view = BrowserView.instances.get(self.window.uid) if self.window is not None else None
        return None if view is None else view.window

    def _stay_in_background(self) -> None:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        from PyObjCTools import AppHelper

        nswindow = self._native_window()

        def settle() -> None:
            NSApplication.sharedApplication().setActivationPolicy_(
                NSApplicationActivationPolicyAccessory
            )
            if nswindow is not None:
                nswindow.setHidesOnDeactivate_(False)

        AppHelper.callAfter(settle)

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
            nswindow.setHidesOnDeactivate_(False)
            nswindow.orderFrontRegardless()

        AppHelper.callAfter(_show)

    def conceal(self) -> None:
        if self.window is None or not self._visible:
            return
        self._visible = False
        self.window.hide()

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
        script = f"render({json.dumps(state, ensure_ascii=False)})"
        try:
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

    def install_hotkey(self) -> None:
        # O monitor global tem de nascer na thread da interface. pynput derruba o processo.
        from AppKit import (
            NSEvent,
            NSEventMaskKeyDown,
            NSEventModifierFlagCommand,
            NSEventModifierFlagShift,
            NSImage,
            NSMenu,
            NSMenuItem,
            NSSquareStatusItemLength,
            NSStatusBar,
        )
        from PyObjCTools import AppHelper

        def register() -> None:
            def handler(event) -> None:
                chars = event.charactersIgnoringModifiers() or ""
                flags = int(event.modifierFlags())
                wanted = int(NSEventModifierFlagCommand | NSEventModifierFlagShift)
                if chars.lower() == "k" and (flags & wanted) == wanted:
                    self.listen()

            self._hotkey = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown,
                handler,
            )
            if self._hotkey is None:
                print("Atalho global indisponível. O macOS não entregou o monitor de teclado.", flush=True)

            icon = NSImage.alloc().initWithContentsOfFile_(
                str(Path(__file__).with_name("iconTemplate.png"))
            )
            icon.setSize_((18, 18))
            icon.setTemplate_(True)

            target = StatusTarget.alloc().init()
            target.app = self
            menu = NSMenu.alloc().init()
            listen_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Ouvir", "listen:", "k"
            )
            listen_item.setKeyEquivalentModifierMask_(
                NSEventModifierFlagCommand | NSEventModifierFlagShift
            )
            listen_item.setTarget_(target)
            menu.addItem_(listen_item)
            menu.addItem_(NSMenuItem.separatorItem())
            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Sair", "quit:", "q")
            quit_item.setTarget_(target)
            menu.addItem_(quit_item)

            status = NSStatusBar.systemStatusBar().statusItemWithLength_(NSSquareStatusItemLength)
            button = status.button()
            button.setImage_(icon)
            button.setToolTip_("karaoke-hud")
            status.setMenu_(menu)
            self._status = status
            self._status_target = target

        AppHelper.callAfter(register)

    def loop(self) -> None:
        while not self._closing:
            time.sleep(0.1)
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
            return

        marker = (previous, current, upcoming, int(position), round(adjust, 1))
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
        with self._audio:
            if not still_current():
                return
            record_start = record_sample(SAMPLE)
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


def main() -> None:
    from AppKit import NSApplicationActivateIgnoringOtherApps, NSWorkspace

    previous = NSWorkspace.sharedWorkspace().frontmostApplication()
    app = App()
    window = webview.create_window(
        "karaoke-hud",
        html=HTML,
        js_api=app,
        width=WIDTH,
        height=HEIGHT,
        resizable=True,
        min_size=(520, 140),
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
        screen = webview.screens[0]
        window.move(
            int((screen.width - WIDTH) / 2),
            int(screen.height - HEIGHT - 110),
        )
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
