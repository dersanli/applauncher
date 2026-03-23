from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib

# ── D-Bus interface XMLs ──────────────────────────────────────────────────────

_SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="ContextMenu">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="Activate">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="Scroll">
      <arg type="i" name="delta" direction="in"/>
      <arg type="s" name="orientation" direction="in"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus">
      <arg type="s" name="status"/>
    </signal>
  </interface>
</node>
"""

_MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/>
      <arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/>
      <arg type="(ia{sv}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{sv})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/>
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" name="events" direction="in"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" name="id" direction="in"/>
      <arg type="b" name="needUpdate" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="ai" name="updatesNeeded" direction="out"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg type="a(ia{sv})" name="updatedProps"/>
      <arg type="a(ias)" name="removedProps"/>
    </signal>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parent"/>
    </signal>
    <signal name="ItemActivationRequested">
      <arg type="i" name="id"/>
      <arg type="u" name="timestamp"/>
    </signal>
  </interface>
</node>
"""

# Menu item IDs
_ID_TOGGLE = 1
_ID_SEP = 2
_ID_QUIT = 3


class TrayIcon:
    """System tray icon via StatusNotifierItem D-Bus protocol."""

    _SNI_PATH = "/StatusNotifierItem"
    _MENU_PATH = "/MenuBar"

    def __init__(self, app, window) -> None:
        self._app = app
        self._window = window
        self._bus: Gio.DBusConnection | None = None
        self._bus_name_id = 0
        self._sni_reg_id = 0
        self._menu_reg_id = 0
        self._revision = 1

        self._bus_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"

        node = Gio.DBusNodeInfo.new_for_xml(_SNI_XML)
        self._sni_iface = node.interfaces[0]
        node = Gio.DBusNodeInfo.new_for_xml(_MENU_XML)
        self._menu_iface = node.interfaces[0]

        self._bus_name_id = Gio.bus_own_name(
            Gio.BusType.SESSION,
            self._bus_name,
            Gio.BusNameOwnerFlags.NONE,
            self._on_bus_acquired,
            self._on_name_acquired,
            self._on_name_lost,
        )

    # ── Bus lifecycle ─────────────────────────────────────────────────────────

    def _on_bus_acquired(self, connection: Gio.DBusConnection, name: str) -> None:
        self._bus = connection
        self._sni_reg_id = connection.register_object(
            self._SNI_PATH,
            self._sni_iface,
            self._sni_method_call,
            self._sni_get_property,
            None,
        )
        self._menu_reg_id = connection.register_object(
            self._MENU_PATH,
            self._menu_iface,
            self._menu_method_call,
            self._menu_get_property,
            None,
        )

    def _on_name_acquired(self, connection: Gio.DBusConnection, name: str) -> None:
        try:
            connection.call_sync(
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (name,)),
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
        except Exception as e:
            print(f"[tray] Could not register with StatusNotifierWatcher: {e}")

    def _on_name_lost(self, connection: Gio.DBusConnection | None, name: str) -> None:
        pass

    # ── SNI properties ────────────────────────────────────────────────────────

    def _sni_get_property(
        self, connection, sender, path, iface, prop
    ) -> GLib.Variant | None:
        match prop:
            case "Category":
                return GLib.Variant("s", "ApplicationStatus")
            case "Id":
                return GLib.Variant("s", "DevLauncher")
            case "Title":
                return GLib.Variant("s", "DevLauncher")
            case "Status":
                return GLib.Variant("s", "Active")
            case "WindowId":
                return GLib.Variant("i", 0)
            case "IconName":
                return GLib.Variant("s", "utilities-terminal")
            case "OverlayIconName" | "AttentionIconName":
                return GLib.Variant("s", "")
            case "ItemIsMenu":
                return GLib.Variant("b", False)
            case "Menu":
                return GLib.Variant("o", self._MENU_PATH)
        return None

    # ── SNI methods ───────────────────────────────────────────────────────────

    def _sni_method_call(
        self, connection, sender, path, iface, method, params, invocation
    ) -> None:
        match method:
            case "Activate" | "SecondaryActivate":
                GLib.idle_add(self._toggle_window)
                invocation.return_value(None)
            case "ContextMenu" | "Scroll":
                invocation.return_value(None)
            case _:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownMethod",
                    f"Unknown method: {method}",
                )

    def _toggle_window(self) -> bool:
        if self._window.is_visible():
            self._window.hide()
        else:
            self._window.present()
        return False

    # ── DBusMenu properties ───────────────────────────────────────────────────

    def _menu_get_property(
        self, connection, sender, path, iface, prop
    ) -> GLib.Variant | None:
        match prop:
            case "Version":
                return GLib.Variant("u", 3)
            case "TextDirection":
                return GLib.Variant("s", "ltr")
            case "Status":
                return GLib.Variant("s", "normal")
            case "IconThemePath":
                return GLib.Variant("as", [])
        return None

    # ── DBusMenu methods ──────────────────────────────────────────────────────

    def _build_layout(self) -> GLib.Variant:
        toggle_label = (
            "Hide DevLauncher"
            if self._window.is_visible()
            else "Show DevLauncher"
        )
        # Children for `av` must be pre-built GLib.Variant objects.
        children = [
            GLib.Variant("(ia{sv}av)", (_ID_TOGGLE, {
                "label": GLib.Variant("s", toggle_label),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
                "type": GLib.Variant("s", "standard"),
            }, [])),
            GLib.Variant("(ia{sv}av)", (_ID_SEP, {
                "type": GLib.Variant("s", "separator"),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            }, [])),
            GLib.Variant("(ia{sv}av)", (_ID_QUIT, {
                "label": GLib.Variant("s", "Quit"),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
                "type": GLib.Variant("s", "standard"),
            }, [])),
        ]
        # Root is a raw tuple so PyGObject can map it to (ia{sv}av).
        root = (0, {"children-display": GLib.Variant("s", "submenu")}, children)
        return GLib.Variant("(u(ia{sv}av))", (self._revision, root))

    def _handle_event(self, id_: int, event_id: str) -> None:
        if event_id != "clicked":
            return
        if id_ == _ID_TOGGLE:
            GLib.idle_add(self._toggle_window)
        elif id_ == _ID_QUIT:
            GLib.idle_add(self._do_quit)

    def _do_quit(self) -> bool:
        GLib.idle_add(self._window.request_quit)
        return False

    def _menu_method_call(
        self, connection, sender, path, iface, method, params, invocation
    ) -> None:
        match method:
            case "GetLayout":
                invocation.return_value(self._build_layout())

            case "GetGroupProperties":
                ids, _props = params.unpack()
                result = []
                for id_ in ids:
                    if id_ == _ID_TOGGLE:
                        label = (
                            "Hide DevLauncher"
                            if self._window.is_visible()
                            else "Show DevLauncher"
                        )
                        result.append((id_, {"label": GLib.Variant("s", label)}))
                    elif id_ == _ID_QUIT:
                        result.append((id_, {"label": GLib.Variant("s", "Quit")}))
                invocation.return_value(GLib.Variant("(a(ia{sv}))", (result,)))

            case "GetProperty":
                invocation.return_value(GLib.Variant("(v)", (GLib.Variant("s", ""),)))

            case "Event":
                id_, event_id, _data, _ts = params.unpack()
                self._handle_event(id_, event_id)
                invocation.return_value(None)

            case "EventGroup":
                (events,) = params.unpack()
                for id_, event_id, _data, _ts in events:
                    self._handle_event(id_, event_id)
                invocation.return_value(GLib.Variant("(ai)", ([],)))

            case "AboutToShow":
                # Refresh label on menu open
                self._revision += 1
                if self._bus:
                    self._bus.emit_signal(
                        None,
                        self._MENU_PATH,
                        "com.canonical.dbusmenu",
                        "LayoutUpdated",
                        GLib.Variant("(ui)", (self._revision, 0)),
                    )
                invocation.return_value(GLib.Variant("(b)", (True,)))

            case "AboutToShowGroup":
                (ids,) = params.unpack()
                invocation.return_value(GLib.Variant("(aiai)", ([], [])))

            case _:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownMethod",
                    f"Unknown method: {method}",
                )

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def destroy(self) -> None:
        if self._bus:
            if self._sni_reg_id:
                self._bus.unregister_object(self._sni_reg_id)
            if self._menu_reg_id:
                self._bus.unregister_object(self._menu_reg_id)
        if self._bus_name_id:
            Gio.bus_unown_name(self._bus_name_id)
