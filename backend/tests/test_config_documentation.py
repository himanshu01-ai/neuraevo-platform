"""Release-readiness guard: `.env.example` documents every setting.

Configuration is only "complete and documented" if the example environment file
stays in step with :class:`~app.core.config.Settings`. This test fails the moment
a new setting is added without a corresponding line in ``backend/.env.example`` —
turning silent configuration drift (a setting nobody knows to set in production)
into a failing test at the point the setting is introduced.

It asserts documentation only; it reads no environment and changes no behaviour.

    PYTHONPATH=. python -m unittest tests.test_config_documentation
"""

import re
import unittest
from pathlib import Path

from app.core.config import Settings

#: backend/.env.example, resolved relative to this test (tests/ -> backend/).
_ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


class EnvExampleDocumentationTests(unittest.TestCase):
    """Every `Settings` field is documented in `.env.example`."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _ENV_EXAMPLE.read_text(encoding="utf-8")
        # Keys mentioned in the file, whether active (`KEY=`) or a commented
        # default (`# KEY=`). Matches the pydantic-settings casing (upper).
        cls.documented = set(
            re.findall(r"(?m)^\s*#?\s*([A-Z][A-Z0-9_]+)\s*=", cls.text)
        )

    def test_env_example_exists_and_is_nonempty(self) -> None:
        self.assertTrue(_ENV_EXAMPLE.is_file(), f"missing {_ENV_EXAMPLE}")
        self.assertGreater(len(self.text.strip()), 0)

    def test_every_setting_is_documented(self) -> None:
        missing = sorted(
            name
            for name in Settings.model_fields
            if name not in self.documented
        )
        self.assertEqual(
            missing,
            [],
            "Settings fields missing from backend/.env.example: "
            f"{missing}. Add a line (a commented default is fine) for each.",
        )

    def test_no_unknown_keys_documented(self) -> None:
        """Guard the other direction: no example key that isn't a real setting,
        so the file can't drift into documenting a renamed/removed option."""
        known = set(Settings.model_fields)
        # PLAYWRIGHT_BROWSERS_PATH is a documented runtime knob read by Playwright
        # itself, not a Settings field, so it is legitimately outside the model.
        allowed_extra = {"PLAYWRIGHT_BROWSERS_PATH"}
        unknown = sorted(self.documented - known - allowed_extra)
        self.assertEqual(
            unknown,
            [],
            f"keys in backend/.env.example with no matching Settings field: {unknown}",
        )


if __name__ == "__main__":
    unittest.main()
