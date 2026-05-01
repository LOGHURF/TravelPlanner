from app.config.settings import Settings


def test_settings_treats_release_debug_value_as_false() -> None:
    settings = Settings(DEBUG="release")

    assert settings.DEBUG is False
