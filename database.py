import sqlite3
from pathlib import Path


# Duong dan den file database.py va safeguard.db
DB_PATH = Path(__file__).resolve().parent / "safeguard.db"


def init_db():
    """Tao database va bang events neu chua ton tai."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                violation_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN (
                        'pending',
                        'confirmed',
                        'false_positive'
                    ))
            )
        """)


def insert_event(timestamp, violation_type, status="pending"):
    """Them mot su kien va tra ve event_id vua tao."""
    valid_types = ("NO-Hardhat", "NO-Safety Vest", "NO-Mask")
    valid_statuses = ("pending", "confirmed", "false_positive")

    if violation_type not in valid_types:
        raise ValueError("Loai vi pham khong hop le.")

    if status not in valid_statuses:
        raise ValueError("Trang thai khong hop le.")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO events (timestamp, violation_type, status)
            VALUES (?, ?, ?)
            """,
            (timestamp, violation_type, status)
        )

        return cursor.lastrowid


def get_all_events():
    """Lay tat ca su kien, moi nhat xep dau tien."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute("""
            SELECT event_id, timestamp, violation_type, status
            FROM events
            ORDER BY event_id DESC
        """).fetchall()

        return [dict(row) for row in rows]


def update_event_status(event_id, new_status):
    """Cap nhat trang thai cua su kien theo event_id."""
    valid_statuses = ("pending", "confirmed", "false_positive")

    if new_status not in valid_statuses:
        raise ValueError("Trang thai khong hop le.")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            UPDATE events
            SET status = ?
            WHERE event_id = ?
            """,
            (new_status, event_id)
        )

        return cursor.rowcount > 0


if __name__ == "__main__":
    # Khoi tao bang
    init_db()

    # Them du lieu thu de kiem tra
    test_id = insert_event(
        "2026-10-15 08:00:00",
        "NO-Hardhat"
    )
    print("ID su kien vua them:", test_id)

    # Doc danh sach su kien
    print("Danh sach su kien:")
    for event in get_all_events():
        print(event)

    # Thu cap nhat trang thai
    updated = update_event_status(test_id, "confirmed")
    print("Cap nhat thanh cong:", updated)

    # Kiem tra lai du lieu sau cap nhat
    print("Danh sach sau cap nhat:")
    for event in get_all_events():
        print(event)
