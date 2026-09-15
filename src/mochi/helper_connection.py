"""Event-driven lifetime of subscriptions to the optional GNOME helper."""


class HelperConnection:
    BUS_NAME = "io.github.mochi_desktop.Mochi.TypingMonitor"
    OBJECT_PATH = "/io/github/mochi_desktop/Mochi/TypingMonitor"
    INTERFACE = BUS_NAME

    def __init__(self, loader, signals, on_state=None, on_lost=None):
        self._loader = loader
        self._signals = signals
        self._on_state = on_state
        self._on_lost = on_lost
        self._connection = None
        self._watch_id = None
        self._subscriptions = []
        self._owner = None
        self._generation = 0
        self.last_error = None

    @property
    def active(self):
        return self._owner is not None

    def start(self):
        """Return whether watching started, even if the helper is absent."""
        if self._watch_id is not None:
            return True
        try:
            self._gio, self._glib = self._loader()
            self._connection = self._gio.bus_get_sync(self._gio.BusType.SESSION, None)
            if self._connection is None:
                raise RuntimeError("session D-Bus connection is unavailable")
            self._watch_id = self._gio.bus_watch_name_on_connection(
                self._connection, self.BUS_NAME,
                self._gio.BusNameWatcherFlags.NONE,
                self._appeared, self._vanished,
            )
            if not self._watch_id:
                raise RuntimeError("helper name watch failed")
            return True
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.stop()
            return False

    def _appeared(self, connection, _name, owner):
        if self._connection is None or owner == self._owner:
            return
        self._detach()
        self._owner = owner
        generation = self._generation
        try:
            for signal, callback in self._signals.items():
                def dispatch(*args, callback=callback):
                    if self._owner == owner and self._generation == generation:
                        callback(*args)
                ident = connection.signal_subscribe(
                    owner, self.INTERFACE, signal, self.OBJECT_PATH, None,
                    self._gio.DBusSignalFlags.NONE, dispatch,
                )
                if not ident:
                    raise RuntimeError("helper signal subscription failed")
                self._subscriptions.append(ident)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._detach()
            return
        self.last_error = None
        if self._on_state is None:
            return
        try:
            # Subscribe first, then query the current owner exactly once. Older
            # helpers without GetState still support subsequent signal events.
            reply = connection.call_sync(
                owner, self.OBJECT_PATH, self.INTERFACE, "GetState", None,
                self._glib.VariantType.new("(bbbs)"),
                self._gio.DBusCallFlags.NONE, 1_000, None,
            )
            state = reply.unpack()
            if self._owner == owner and self._generation == generation:
                self._on_state(state)
        except Exception as exc:
            self.last_error = f"helper state sync unavailable: {type(exc).__name__}"

    def _vanished(self, *_args):
        self._detach()

    def _detach(self):
        was_active = self.active
        self._owner = None
        self._generation += 1
        for ident in self._subscriptions:
            try:
                self._connection.signal_unsubscribe(ident)
            except Exception:
                pass
        self._subscriptions.clear()
        if was_active and self._on_lost is not None:
            self._on_lost()

    def stop(self):
        if self._watch_id is not None:
            self._gio.bus_unwatch_name(self._watch_id)
            self._watch_id = None
        self._detach()
        self._connection = None
