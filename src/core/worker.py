"""QThread streaming worker for non-blocking AI chat."""

from PyQt6.QtCore import QThread, pyqtSignal

from core.engine import AIEngine


class StreamWorker(QThread):
    """Streams AI response in background thread."""

    token_received = pyqtSignal(str)
    stream_finished = pyqtSignal(str)  # full response text
    stream_error = pyqtSignal(str)
    engine_switched = pyqtSignal(str)  # engine name after completion

    def __init__(
        self,
        engine: AIEngine,
        messages: list[dict],
        system_prompt: str = "",
        image_paths: list[str] | None = None,
    ):
        super().__init__()
        self._engine = engine
        self._messages = messages
        self._system_prompt = system_prompt
        self._image_paths = image_paths
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        full_response = ""
        try:
            for chunk in self._engine.stream_chat(
                self._messages, self._system_prompt, self._image_paths
            ):
                if self._cancelled:
                    break
                full_response += chunk
                self.token_received.emit(chunk)
            self.stream_finished.emit(full_response)
            self.engine_switched.emit(self._engine.get_current_engine_name())
        except Exception as e:
            self.stream_error.emit(str(e))
