from types import SimpleNamespace

from environment_provider import EnvironmentProvider
from shimeji_expression import ExpressionRuntime


class ShimejiRuntime:
    def __init__(self, window):
        self.window = window
        self.environment_provider = EnvironmentProvider(window)
        self.expression_runtime = ExpressionRuntime(self.environment_provider, self)
        self.state_vars: dict[str, object] = {}

    def refresh_environment(self):
        self.environment_provider.refresh()

    def set_state_vars(self, state_vars: dict | None):
        self.state_vars = dict(state_vars or {})

    def eval_bool(self, value: str | None, default: bool = False, variables: dict | None = None) -> bool:
        return self.expression_runtime.eval_bool(value, default=default, variables=variables)

    def eval_value(self, value: str | None, default=None, variables: dict | None = None):
        return self.expression_runtime.eval(value, default=default, variables=variables)

    def current_frame_anchor(self):
        return getattr(self.window, "current_frame_anchor", lambda: (64, 128))()

    def mascot_proxy(self):
        anchor = self.window.anchor_point()
        return SimpleNamespace(
            anchor=anchor,
            lookRight=self.window.facing > 0,
            environment=self.environment_provider.mascot_environment(),
            totalCount=getattr(self.window, "mascot_total_count", 1),
            count=getattr(self.window, "mascot_total_count", 1),
            imageSet="ATRI",
            variables=self.state_vars,
        )

    def action_proxy(self):
        return SimpleNamespace(name=getattr(self.window, "current_action_name", ""))
