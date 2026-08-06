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
    from sentinel.core.config import load_config
    from sentinel.server.app import build_llm, create_app

    config = load_config(args.config)
    cs = get_credential_store()
    try:
        llm = build_llm(config=config, credential_store=cs)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        print("hint: run 'sentinel config set-key --provider "
              f"{config.provider}' first", file=sys.stderr)
        return 1

    app = create_app(
        workspace=args.workspace,
        llm=llm,
        use_human_approval=True,
        approval_timeout=config.approval_timeout,
    )
    uvicorn.run(app, host=args.host, port=args.port)
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
    serve.add_argument("--config", default="sentinel.yaml")
    serve.add_argument("--workspace", default=".")

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
