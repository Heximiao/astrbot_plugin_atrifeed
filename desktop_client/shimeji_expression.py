import math
import random
import re


UNARY_NOT_RE = re.compile(r"(?<![=!<>])!(?!=)")
BARE_RANDOM_RE = re.compile(r"Math\.random(?!\s*\()")


class ExpressionRuntime:
    def __init__(self, env_provider, state_provider):
        self.env_provider = env_provider
        self.state_provider = state_provider

    def eval(self, expression: str | None, default=None, variables: dict | None = None):
        if expression is None:
            return default
        text = expression.strip()
        if not text:
            return default
        if (text.startswith("${") or text.startswith("#{")) and text.endswith("}"):
            text = text[2:-1]
        translated = self._translate(text)
        env = self._environment(variables)
        try:
            return eval(translated, {"__builtins__": {}}, env)
        except Exception:
            return default

    def eval_bool(self, expression: str | None, default: bool = False, variables: dict | None = None) -> bool:
        value = self.eval(expression, default=default, variables=variables)
        return bool(value)

    def _environment(self, variables: dict | None):
        env = {
            "Math": MathProxy(),
            "random": random,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "int": int,
            "float": float,
            "True": True,
            "False": False,
            "None": None,
            "mascot": self.state_provider.mascot_proxy(),
            "action": self.state_provider.action_proxy(),
        }
        if variables:
            env.update(variables)
        return env

    def _translate(self, text: str) -> str:
        text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
        text = BARE_RANDOM_RE.sub("Math.random()", text)
        text = text.replace("Math.min", "min")
        text = text.replace("Math.max", "max")
        text = text.replace("Math.abs", "abs")
        text = text.replace("true", "True")
        text = text.replace("false", "False")
        text = text.replace("null", "None")
        text = text.replace("&&", " and ")
        text = text.replace("||", " or ")
        text = UNARY_NOT_RE.sub(" not ", text)
        return self._translate_ternary(text)

    def _translate_ternary(self, text: str) -> str:
        question = self._find_top_level(text, "?")
        if question < 0:
            return text
        colon = self._matching_colon(text, question)
        if colon < 0:
            return text
        condition = text[:question].strip()
        when_true = text[question + 1 : colon].strip()
        when_false = text[colon + 1 :].strip()
        return (
            f"({self._translate_ternary(when_true)} if "
            f"{self._translate_ternary(condition)} else "
            f"{self._translate_ternary(when_false)})"
        )

    def _find_top_level(self, text: str, target: str) -> int:
        depth = 0
        for index, char in enumerate(text):
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            elif char == target and depth == 0:
                return index
        return -1

    def _matching_colon(self, text: str, question_index: int) -> int:
        depth = 0
        ternary_depth = 0
        for index, char in enumerate(text[question_index + 1 :], start=question_index + 1):
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            elif char == "?" and depth == 0:
                ternary_depth += 1
            elif char == ":" and depth == 0:
                if ternary_depth == 0:
                    return index
                ternary_depth -= 1
        return -1


class MathProxy:
    @staticmethod
    def random():
        return random.random()

    @staticmethod
    def min(*values):
        return min(*values)

    @staticmethod
    def max(*values):
        return max(*values)

    @staticmethod
    def abs(value):
        return math.fabs(value)
