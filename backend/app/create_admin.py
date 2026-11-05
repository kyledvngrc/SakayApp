"""Create or reset an admin account.                       (IMPERATIVE PARADIGM)

Run from backend/:  python3 -m app.create_admin you@example.com
"""

from __future__ import annotations

import getpass
import sys

from . import auth, db


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python3 -m app.create_admin EMAIL")
        return 2
    email = sys.argv[1].strip()
    password = getpass.getpass("Password (10+ characters): ")
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match.")
        return 1
    try:
        password_hash = auth.hash_password(password)
    except ValueError as e:
        print(e)
        return 1
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO users (email, password_hash, role) VALUES (%s, %s, 'admin')
               ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash,
                                                 role = 'admin'""",
            (email, password_hash))
    print(f"Admin account ready: {email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
