from backend.application import Application
from backend.config import ConfigError


def main() -> None:
    try:
        Application().run()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
