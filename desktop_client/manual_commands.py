class ManualCommandController:
    def __init__(self, engine):
        self.engine = engine
        self._cached_active_ie = None
        self._cached_active_ie_title = ""

    def capture_environment(self):
        provider = self.engine.window.runtime.environment_provider
        active_ie = provider.active_ie
        if not active_ie.visible:
            self._cached_active_ie = None
            self._cached_active_ie_title = ""
            return
        self._cached_active_ie = type(active_ie)(
            left=active_ie.left,
            top=active_ie.top,
            right=active_ie.right,
            bottom=active_ie.bottom,
        )
        self._cached_active_ie_title = getattr(provider, "active_ie_title", "")

    def force(self, name: str, **params):
        self._restore_cached_environment()
        resolved = self.engine._resolve_name(name)
        behavior = self.engine.config.behaviors.get(resolved)
        action = self.engine.config.actions.get(resolved)
        if behavior is not None and self.engine._conditions_pass(behavior.conditions, behavior.params):
            self._push_behavior(resolved, mode="behavior", params=params)
        elif self._push_ie_edge_action(resolved, params):
            return
        elif action is not None and (behavior is None or self._allows_manual_action_fallback(resolved)):
            self._push_action(resolved, mode="action", params=params)
        else:
            feedback = self._feedback_action()
            if feedback is not None:
                self._push_action(feedback, mode="feedback")

    def _allows_manual_action_fallback(self, name: str) -> bool:
        return "IE" in name and "投げる" in name

    def _push_ie_edge_action(self, name: str, params: dict[str, object] | None = None) -> bool:
        if name not in {"IEの左に飛びつく", "IEの右に飛びつく"}:
            return False
        active_ie = self.engine.window.runtime.environment_provider.active_ie
        if not active_ie.visible:
            return False
        anchor = self.engine.window.anchor_point()
        if anchor.x < active_ie.left:
            action_name = self.engine._resolve_name("IEの左に飛びつく")
        elif anchor.x > active_ie.right:
            action_name = self.engine._resolve_name("IEの右に飛びつく")
        else:
            left_distance = abs(anchor.x - active_ie.left)
            right_distance = abs(anchor.x - active_ie.right)
            action_name = self.engine._resolve_name(
                "IEの左に飛びつく" if left_distance <= right_distance else "IEの右に飛びつく"
            )
        if action_name not in self.engine.config.actions:
            return False
        self._trace(
            name,
            mode="ie_edge_action",
            selected_action=action_name,
            active_ie_left=active_ie.left,
            active_ie_top=active_ie.top,
            active_ie_right=active_ie.right,
            active_ie_bottom=active_ie.bottom,
            active_ie_title=getattr(self.engine.window.runtime.environment_provider, "active_ie_title", ""),
            anchor_x=anchor.x,
            anchor_y=anchor.y,
        )
        self.engine._trace().forced_action(self.engine.tick_count, action_name)
        self.engine.override_controller.push_action(action_name, **(params or {}))
        return True

    def _feedback_action(self) -> str | None:
        for candidate in ("振り向く", "Look"):
            resolved = self.engine._resolve_name(candidate)
            if resolved in self.engine.config.actions:
                return resolved
        return None

    def _push_behavior(self, name: str, mode: str, params: dict[str, object] | None = None):
        self._trace(name, mode=mode, params=params or {})
        self.engine._trace().forced_behavior(self.engine.tick_count, name)
        self.engine.override_controller.push_behavior(name, **(params or {}))

    def _push_action(self, name: str, mode: str, params: dict[str, object] | None = None):
        self._trace(name, mode=mode, params=params or {})
        self.engine._trace().forced_action(self.engine.tick_count, name)
        self.engine.override_controller.push_action(name, **(params or {}))

    def _trace(self, name: str, **data):
        self.engine._trace().record(
            "manual_command",
            self.engine.tick_count,
            name=name,
            **data,
        )

    def _restore_cached_environment(self):
        if self._cached_active_ie is None:
            return
        provider = self.engine.window.runtime.environment_provider
        freeze = getattr(provider, "freeze_active_ie", None)
        if freeze is not None:
            freeze(self._cached_active_ie, self._cached_active_ie_title)
