from __future__ import annotations

from typing import Any

from furminder.i18n import ru

_LOCALES: dict[str, dict[str, str]] = {
    "ru": ru.MESSAGES,
}


def t(key: str, locale: str = "ru", **kwargs: Any) -> str:
    messages = _LOCALES.get(locale, _LOCALES["ru"])
    template = messages.get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template
