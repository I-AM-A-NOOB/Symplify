import pathlib
import yaml


def load_keyboard_config():
    config_path = (
        pathlib.Path(__file__).resolve().parent.parent
        / "config"
        / "keyboard_config.yaml"
    )
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


if __name__ == "__main__":
    config = load_keyboard_config()
    print(config)
