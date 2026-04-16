from pathlib import Path

import toml
from pydantic import BaseModel

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class PersonalityConfig(BaseModel):
    assistant_name: str = "JARVIS"
    user_display_name: str = "Sir"
    wake_word_enabled: bool = False
    hotkey: str = "Ctrl+Shift+J"
    use_claude_for_chat: bool = True
    do_not_disturb: bool = False


def load_personality() -> PersonalityConfig:
    path = CONFIG_DIR / "personality.toml"
    if path.exists():
        data = toml.load(path)
        return PersonalityConfig(**data)
    return PersonalityConfig()
