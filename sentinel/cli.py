from __future__ import annotations
import argparse
import getpass
import sys

from sentinel.credentials import CredentialStore


def get_credential_store() -> CredentialStore:
    return CredentialStore()


def cmd_config(args: argparse.Namespace) -> int:
    cs = get_credential_store()
    if args.config_cmd == "status":
        for provider, state in cs.status().items():
            print(f"{provider}: {state}")
        return 0
    if args.config_cmd == "set-key":
        key = getpass.getpass(prompt=f"Enter API key for {args.provider}: ")
        cs.set_key(args.provider, key)
        print(f"key stored for {args.provider}")
        return 0
    if args.config_cmd == "clear-key":
        cs.clear_key(args.provider)
        print(f"key cleared for {args.provider}")
        return 0
    return 1


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn
    uvicorn.run("sentinel.server.app:app",
                host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sentinel")
    sub = parser.add_subparsers(dest="command", required=True)

    config = sub.add_parser("config")
    config_sub = config.add_subparsers(dest="config_cmd", required=True)

    sk = config_sub.add_parser("set-key")
    sk.add_argument("--provider", required=True,
                    choices=["openai", "anthropic"])

    config_sub.add_parser("status")

    ck = config_sub.add_parser("clear-key")
    ck.add_argument("--provider", required=True,
                    choices=["openai", "anthropic"])

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "config":
        return cmd_config(args)
    if args.command == "serve":
        return cmd_serve(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
