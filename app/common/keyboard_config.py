import pathlib
import yaml
import yaml.parser

DEFAULT_KEYBOARD_CONFIG = {
    "basic": {
        "title": "基本",
        "grid": [
            [
                ["()", "(...)"],
                ["7", "7"],
                ["8", "8"],
                ["9", "9"],
                ["\x7f", "DEL"],
                ["\x08", "BAK"],
            ],
            [["(", "("], ["4", "4"], ["5", "5"], ["6", "6"], ["*", "×"], ["/", "÷"]],
            [[")", ")"], ["1", "1"], ["2", "2"], ["3", "3"], ["+", "+"], ["-", "-"]],
            [
                {
                    "text": "const",
                    "items": [[["pi", "π"], ["E", "e"]], [["I", "i"], None]],
                },
                ["0", "0"],
                [".", "."],
                [",", ","],
                None,
                ["=", "="],
            ],
        ],
    },
    "symbols": {
        "title": "符号",
        "grid": [
            [["pi", "π"], ["E", "e"], ["i", "i"]],
            [["oo", "∞"], ["zoo", "-∞"], ["nan", "NaN"]],
        ],
    },
}


def load_keyboard_config():
    config_path = (
        pathlib.Path(__file__).resolve().parent.parent
        / "config"
        / "keyboard_config.yaml"
    )
    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except yaml.parser.ParserErroras or FileNotFoundError as e:
        print(f"Error loading keyboard config from {config_path}")
        config = DEFAULT_KEYBOARD_CONFIG
    return config


if __name__ == "__main__":
    config = load_keyboard_config()
    print(config)
