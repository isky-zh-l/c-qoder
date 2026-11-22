"""Local development mail catcher.

Usage:
    python scripts/dev_mailbox.py

Messages are written as .eml files under backend/data/mailbox and printed to
the console. Configure backend/.env with SMTP_HOST=127.0.0.1 SMTP_PORT=2525
(or pass --port). This is not a production mail service.
"""

import argparse
import asyncio
import email
from datetime import datetime
from email import policy
from pathlib import Path
from uuid import uuid4

from aiosmtpd.controller import Controller

BACKEND_DIR = Path(__file__).resolve().parents[1]


class FileMailboxHandler:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    async def handle_DATA(self, server, session, envelope):
        message = email.message_from_bytes(envelope.content, policy=policy.default)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.directory / f"{stamp}-{uuid4().hex[:8]}.eml"
        path.write_bytes(envelope.content)
        print(
            f"[mail] to={', '.join(envelope.rcpt_tos)} "
            f"subject={message.get('Subject', '')} saved={path}"
        )
        return "250 Message accepted for delivery"


async def run(host: str, port: int, directory: Path) -> None:
    controller = Controller(
        FileMailboxHandler(directory),
        hostname=host,
        port=port,
    )
    controller.start()
    print(f"Local SMTP listening on {host}:{port}; mailbox={directory}")
    try:
        await asyncio.Event().wait()
    finally:
        controller.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2525)
    parser.add_argument(
        "--dir",
        type=Path,
        default=BACKEND_DIR / "data" / "mailbox",
    )
    args = parser.parse_args()
    try:
        asyncio.run(run(args.host, args.port, args.dir))
    except KeyboardInterrupt:
        print("Stopped local mail catcher")


if __name__ == "__main__":
    main()
