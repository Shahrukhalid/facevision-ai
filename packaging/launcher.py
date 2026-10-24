"""Entry point for the packaged desktop build (PyInstaller).

Starts the local server on 127.0.0.1 and opens the browser. Models are downloaded on first use from the
Model Manager, exactly as in the source install, so the package itself contains no model weights.
"""

import os
import socket
import sys


def free_port(preferred: int = 8600) -> int:
    for port in [preferred, *range(preferred + 1, preferred + 50)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


def main() -> int:
    os.environ.setdefault("FV_HOST", "127.0.0.1")
    os.environ.setdefault("FV_PORT", str(free_port()))
    from facevision.__main__ import main as cli

    args = sys.argv[1:] or ["serve", "--open"]
    return cli(args)


if __name__ == "__main__":
    sys.exit(main())
