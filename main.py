"""Ponto de entrada do simulador de deadlocks."""

import sys

from cli import main as cli_main


def main() -> None:
    cli_main(sys.argv[1:])


if __name__ == "__main__":
    main()
