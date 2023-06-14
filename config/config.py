import os
import ast
import jsonc
import inspect
import warnings

from config.utils import (
    Formatter,
    get_env_var,
    alchemize_url,
    load_configs,
    join_dicts,
    subtract_dicts,
)


class Config:
    BOT_TOKEN = "YOUR_TOKEN_GOES_HERE"
    SPOTIFY_ID = ""
    SPOTIFY_SECRET = ""

    # set to empty string to disable
    BOT_PREFIX = "d!"
    ENABLE_SLASH_COMMANDS = False
    MENTION_AS_PREFIX = True

    # seconds
    VC_TIMEOUT = 600
    # default template setting for VC timeout
    # true = yes, timeout; false = no timeout
    VC_TIMOUT_DEFAULT = True
    # allow or disallow editing the vc_timeout guild setting
    ALLOW_VC_TIMEOUT_EDIT = True

    # maximum of 25
    MAX_SONG_PRELOAD = 5
    MAX_HISTORY_LENGTH = 10
    MAX_TRACKNAME_HISTORY_LENGTH = 15

    # if database is not one of sqlite, postgres or MySQL
    # you need to provide the url in SQL Alchemy-supported format.
    # Must be async-compatible
    # CHANGE ONLY IF YOU KNOW WHAT YOU'RE DOING
    DATABASE_URL = os.getenv("HEROKU_DB") or "sqlite:///settings.db"

    ENABLE_BUTTON_PLUGIN = True

    # replace after '0x' with desired hex code ex. '#ff0188' >> "0xff0188"
    EMBED_COLOR: int = "0x4DD4D0"  # converted to int in __init__

    SUPPORTED_EXTENSIONS = (
        ".webm",
        ".mp4",
        ".mp3",
        ".avi",
        ".wav",
        ".m4v",
        ".ogg",
        ".mov",
    )

    COOKIE_PATH = "config/cookies/cookies.txt"

    GLOBAL_DISABLE_AUTOJOIN_VC = False

    def __init__(self):
        current_cfg = self.load()

        self.actual_prefix = (  # for internal use
            self.BOT_PREFIX
            if self.BOT_PREFIX
            else ("/" if self.ENABLE_SLASH_COMMANDS else "@bot ")
        )
        current_cfg["prefix"] = self.actual_prefix

        # ignore empty DB URL in env
        if not self.DATABASE_URL:
            self.DATABASE_URL = current_cfg["DATABASE_URL"]
        self.DATABASE = alchemize_url(self.DATABASE_URL)
        self.DATABASE_LIBRARY = self.DATABASE.partition("+")[2].partition(":")[
            0
        ]

        self.EMBED_COLOR = int(self.EMBED_COLOR, 16)

        data = join_dicts(
            load_configs(
                "en.json",
                lambda d: {
                    k: Formatter(v).format(current_cfg)
                    if isinstance(v, str)
                    else v
                    for k, v in d.items()
                },
            )
        )

        self.messages = {}
        self.dicts = {}
        for k, v in data.items():
            if isinstance(v, str):
                self.messages[k] = v
            elif isinstance(v, dict):
                self.dicts[k] = v

    def load(self) -> dict:
        loaded_cfgs = load_configs(
            "config.json",
            lambda d: {
                k: tuple(v) if isinstance(v, list) else v for k, v in d.items()
            },
        )

        current_cfg = self.as_dict()
        loaded_joined = join_dicts(loaded_cfgs)
        missing = subtract_dicts(current_cfg, loaded_joined)
        self.unknown_vars = subtract_dicts(loaded_joined, current_cfg)

        if missing and not os.getenv("DANDELION_INSTALLING"):
            missing.update(loaded_cfgs[-1])
            comments = self.get_comments()
            # sort according to definition order
            missing = {k: missing[k] for k in comments if k in missing}
            with open("config.json", "w") as f:
                jsonc.dump(
                    missing,
                    f,
                    indent=2,
                    trailing_comma=True,
                    comments=comments,
                )
                f.write("\n")

        current_cfg.update(loaded_joined)

        for key, default in current_cfg.items():
            current_cfg[key] = get_env_var(key, default)

        self.update(current_cfg)
        return current_cfg

    def __getattr__(self, key: str) -> str:
        try:
            return self.messages[key]
        except KeyError as e:
            raise AttributeError(f"No text for {key!r} defined") from e

    def get_dict(self, name: str) -> dict:
        return self.dicts[name]

    def warn_unknown_vars(self):
        for name in self.unknown_vars:
            warnings.warn(f"Unknown variable in config: {name}")

    def update(self, data: dict):
        for k, v in data.items():
            setattr(self, k, v)

    @classmethod
    def as_dict(cls) -> dict:
        return {
            k: v
            for k, v in inspect.getmembers(cls)
            if not k.startswith("__") and not inspect.isroutine(v)
        }

    @classmethod
    def get_comments(cls) -> dict:
        try:
            src = inspect.getsource(cls)
        except OSError:
            return {}
        result = {}
        body = ast.parse(src).body[0].body
        src = src.splitlines()
        for node in body:
            if isinstance(node, ast.Assign):
                target = node.targets
            elif isinstance(node, ast.AnnAssign):
                target = node.target
            else:
                target = None
            if target is not None:
                comment = ""
                for i in range(node.lineno - 2, -1, -1):
                    line = src[i].strip()
                    if line and not line.startswith("#"):
                        break
                    comment = line[1:].strip() + "\n" + comment
                result[ast.unparse(target)] = comment
        return result
