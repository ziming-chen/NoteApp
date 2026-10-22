"""Convert existing comments atomically without changing IDs or other columns."""

from comment_crypto import CommentCryptoError


def migrate_comments(conn, cipher):
    """Validate encrypted rows and encrypt plaintext rows in one transaction.

    The caller owns the connection. Concurrent writers are blocked until commit.
    Any authentication or database failure rolls back the entire migration.
    """
    conn.autocommit = False
    migrated = 0
    verified = 0
    with conn:
        with conn.cursor() as cur:
            cur.execute("LOCK TABLE notes IN SHARE ROW EXCLUSIVE MODE")
            cur.execute(
                "CREATE TABLE IF NOT EXISTS notesapp_crypto_state "
                "(feature TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            cur.execute(
                "SELECT version FROM notesapp_crypto_state WHERE feature = %s",
                ("notes.comment",),
            )
            state = cur.fetchone()
            if state is not None and state["version"] != 1:
                raise CommentCryptoError("Unsupported comment migration version.")
            cur.execute("SELECT id, comment FROM notes ORDER BY id FOR UPDATE")
            for row in cur.fetchall():
                comment = row["comment"]
                if comment is None:
                    continue
                if comment.startswith("aesgcm:"):
                    cipher.decrypt(comment, row["id"])
                    verified += 1
                else:
                    if state is not None:
                        raise CommentCryptoError("Unencrypted comment after migration.")
                    cur.execute(
                        "UPDATE notes SET comment = %s WHERE id = %s",
                        (cipher.encrypt(comment, row["id"]), row["id"]),
                    )
                    migrated += 1
            cur.execute(
                "INSERT INTO notesapp_crypto_state (feature, version) VALUES (%s, %s) "
                "ON CONFLICT (feature) DO NOTHING",
                ("notes.comment", 1),
            )
    return {"migrated": migrated, "verified": verified}
