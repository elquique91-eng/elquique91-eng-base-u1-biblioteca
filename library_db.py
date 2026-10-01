"""
Library Management System with SQLite 3
---------------------------------------
Entities:
  - Books: ISBN, TITLE, AUTHOR, CATEGORY, YEAR, TOTAL STOCK, AVAILABLE STOCK, ACTIVE
  - Readers: FOLIO, NOMBRE, EMAIL, PHONE_NUMBER, TYPE (student, docent, outsider), ACTIVE
Movements:
  - Borrow: Reader + Book, expires in 7 days, discounts 1 from available stock.
  - Return / Refund: Marks borrow returned, adds 1 back to available stock.
Reports:
  - Overdue borrows: Active borrows where expiration_date < today.
Rules:
  1. No borrowing if available stock <= 0 or if reader is inactive.
  2. A reader cannot have two active borrows of the same book.
  3. No deleting a book or reader with an active borrow; deactivate instead.
  4. Obligatory JOIN: borrow + reader name + book title.
"""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional


class LibraryDB:
    def __init__(self, db_path: str = "library.db"):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a database connection with foreign key enforcement and row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # SQLite disables foreign keys by default; enable them per connection:
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self) -> None:
        """Initializes tables, indexes, and triggers."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # ---------------------------------------------------------
            # 1. ENTITY A: BOOKS
            # ---------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                isbn TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                category TEXT NOT NULL,
                year INTEGER NOT NULL,
                total_stock INTEGER NOT NULL CHECK (total_stock >= 0),
                available_stock INTEGER NOT NULL CHECK (available_stock >= 0 AND available_stock <= total_stock),
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
            );
            """)

            # ---------------------------------------------------------
            # 2. ENTITY B: READERS
            # ---------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS readers (
                folio TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone_number TEXT,
                reader_type TEXT NOT NULL CHECK (reader_type IN ('student', 'docent', 'outsider')),
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
            );
            """)

            # ---------------------------------------------------------
            # 3. MOVEMENT: BORROWS
            # ---------------------------------------------------------
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS borrows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reader_folio TEXT NOT NULL,
                isbn TEXT NOT NULL,
                borrow_date TEXT NOT NULL,
                expiration_date TEXT NOT NULL,
                return_date TEXT,
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'returned')),
                FOREIGN KEY (reader_folio) REFERENCES readers(folio) ON UPDATE CASCADE,
                FOREIGN KEY (isbn) REFERENCES books(isbn) ON UPDATE CASCADE
            );
            """)

            # ---------------------------------------------------------
            # RULE: A reader cannot have two active borrows of the same book
            # Enforced at DB level with a conditional unique index
            # ---------------------------------------------------------
            cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_borrow_per_book
            ON borrows(reader_folio, isbn)
            WHERE status = 'active';
            """)

            # ---------------------------------------------------------
            # RULE: No deleting a reader with an active borrow
            # SQLite Trigger enforcement
            # ---------------------------------------------------------
            cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_reader_with_active_borrow
            BEFORE DELETE ON readers
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN EXISTS (
                        SELECT 1 FROM borrows
                        WHERE reader_folio = OLD.folio AND status = 'active'
                    )
                    THEN RAISE(ABORT, 'Cannot delete reader with active borrow. Deactivate reader instead.')
                END;
            END;
            """)

            # ---------------------------------------------------------
            # RULE: No deleting a book with an active borrow
            # SQLite Trigger enforcement
            # ---------------------------------------------------------
            cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_prevent_delete_book_with_active_borrow
            BEFORE DELETE ON books
            FOR EACH ROW
            BEGIN
                SELECT CASE
                    WHEN EXISTS (
                        SELECT 1 FROM borrows
                        WHERE isbn = OLD.isbn AND status = 'active'
                    )
                    THEN RAISE(ABORT, 'Cannot delete book with active borrow. Deactivate book instead.')
                END;
            END;
            """)

            conn.commit()

    # =========================================================================
    # BOOK OPERATIONS
    # =========================================================================
    def add_book(
        self,
        isbn: str,
        title: str,
        author: str,
        category: str,
        year: int,
        total_stock: int,
        available_stock: Optional[int] = None,
        active: int = 1
    ) -> None:
        """Adds a new book record."""
        if available_stock is None:
            available_stock = total_stock

        if available_stock > total_stock:
            raise ValueError(f"Available stock ({available_stock}) cannot exceed total stock ({total_stock}).")

        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO books (isbn, title, author, category, year, total_stock, available_stock, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (isbn, title, author, category, year, total_stock, available_stock, active))
            conn.commit()

    def get_book(self, isbn: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single book by ISBN."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM books WHERE isbn = ?", (isbn,)).fetchone()
            return dict(row) if row else None

    def list_books(self) -> List[Dict[str, Any]]:
        """Lists all books."""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM books ORDER BY title ASC").fetchall()
            return [dict(r) for r in rows]

    def update_book(
        self,
        isbn: str,
        title: str,
        author: str,
        category: str,
        year: int,
        total_stock: int,
        available_stock: int,
        active: int
    ) -> None:
        """Updates an existing book record in SQLite."""
        if available_stock > total_stock:
            raise ValueError(f"Available stock ({available_stock}) cannot exceed total stock ({total_stock}).")
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE books
                SET title = ?, author = ?, category = ?, year = ?,
                    total_stock = ?, available_stock = ?, active = ?
                WHERE isbn = ?
            """, (title, author, category, year, total_stock, available_stock, active, isbn))
            conn.commit()

    def deactivate_book(self, isbn: str) -> None:
        """Deactivates a book (active = 0)."""
        with self.get_connection() as conn:
            conn.execute("UPDATE books SET active = 0 WHERE isbn = ?", (isbn,))
            conn.commit()

    def delete_book(self, isbn: str, safe_deactivate: bool = True) -> str:
        """
        Deletes a book if it has no active borrows.
        If safe_deactivate=True and active borrows exist, deactivates instead.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            active_borrows = cursor.execute(
                "SELECT COUNT(*) AS count FROM borrows WHERE isbn = ? AND status = 'active'",
                (isbn,)
            ).fetchone()["count"]

            if active_borrows > 0:
                if safe_deactivate:
                    cursor.execute("UPDATE books SET active = 0 WHERE isbn = ?", (isbn,))
                    conn.commit()
                    return f"Book '{isbn}' has {active_borrows} active borrow(s). Deactivated instead of deleted."
                else:
                    # Will trigger the SQLite abort trigger
                    cursor.execute("DELETE FROM books WHERE isbn = ?", (isbn,))
                    conn.commit()
                    return f"Book '{isbn}' deleted."
            else:
                cursor.execute("DELETE FROM books WHERE isbn = ?", (isbn,))
                conn.commit()
                return f"Book '{isbn}' successfully deleted."

    # =========================================================================
    # READER OPERATIONS
    # =========================================================================
    def add_reader(
        self,
        folio: str,
        nombre: str,
        email: str,
        phone_number: str,
        reader_type: str,
        active: int = 1
    ) -> None:
        """Adds a new reader record."""
        valid_types = ('student', 'docent', 'outsider')
        if reader_type not in valid_types:
            raise ValueError(f"Invalid reader type '{reader_type}'. Must be one of: {valid_types}")

        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO readers (folio, nombre, email, phone_number, reader_type, active)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (folio, nombre, email, phone_number, reader_type, active))
            conn.commit()

    def get_reader(self, folio: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single reader by folio."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM readers WHERE folio = ?", (folio,)).fetchone()
            return dict(row) if row else None

    def list_readers(self) -> List[Dict[str, Any]]:
        """Lists all readers."""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM readers ORDER BY folio ASC").fetchall()
            return [dict(r) for r in rows]

    def update_reader(
        self,
        folio: str,
        nombre: str,
        email: str,
        phone_number: str,
        reader_type: str,
        active: int
    ) -> None:
        """Updates an existing reader record in SQLite."""
        valid_types = ('student', 'docent', 'outsider')
        if reader_type not in valid_types:
            raise ValueError(f"Invalid reader type '{reader_type}'. Must be one of: {valid_types}")
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE readers
                SET nombre = ?, email = ?, phone_number = ?, reader_type = ?, active = ?
                WHERE folio = ?
            """, (nombre, email, phone_number, reader_type, active, folio))
            conn.commit()

    def deactivate_reader(self, folio: str) -> None:
        """Deactivates a reader (active = 0)."""
        with self.get_connection() as conn:
            conn.execute("UPDATE readers SET active = 0 WHERE folio = ?", (folio,))
            conn.commit()

    def delete_reader(self, folio: str, safe_deactivate: bool = True) -> str:
        """
        Deletes a reader if they have no active borrows.
        If safe_deactivate=True and active borrows exist, deactivates instead.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            active_borrows = cursor.execute(
                "SELECT COUNT(*) AS count FROM borrows WHERE reader_folio = ? AND status = 'active'",
                (folio,)
            ).fetchone()["count"]

            if active_borrows > 0:
                if safe_deactivate:
                    cursor.execute("UPDATE readers SET active = 0 WHERE folio = ?", (folio,))
                    conn.commit()
                    return f"Reader '{folio}' has {active_borrows} active borrow(s). Deactivated instead of deleted."
                else:
                    # Will trigger the SQLite abort trigger
                    cursor.execute("DELETE FROM readers WHERE folio = ?", (folio,))
                    conn.commit()
                    return f"Reader '{folio}' deleted."
            else:
                cursor.execute("DELETE FROM readers WHERE folio = ?", (folio,))
                conn.commit()
                return f"Reader '{folio}' successfully deleted."

    # =========================================================================
    # MOVEMENT: BORROW
    # =========================================================================
    def borrow_book(
        self,
        reader_folio: str,
        isbn: str,
        borrow_date: str  # User-supplied date parameter (format: 'YYYY-MM-DD', no time required)
    ) -> int:
        """
        Registers a new borrow with validation of all business rules:
        - borrow_date: Standard user-supplied date parameter (format: 'YYYY-MM-DD').
        - Reader must exist and be active.
        - Book must exist, be active, and have available_stock > 0.
        - Reader cannot already hold an active borrow of the same book.
        - Expiration date is automatically set to borrow_date + 7 days.
        - Decrements available_stock by 1.
        Returns the new borrow ID.
        """
        if not borrow_date:
            raise ValueError("borrow_date is a required date parameter (format: 'YYYY-MM-DD').")

        if isinstance(borrow_date, (datetime, date)):
            b_date = borrow_date if isinstance(borrow_date, date) else borrow_date.date()
        else:
            b_date = datetime.strptime(str(borrow_date).strip(), "%Y-%m-%d").date()

        exp_date = b_date + timedelta(days=7)
        b_date_str = b_date.strftime("%Y-%m-%d")
        exp_date_str = exp_date.strftime("%Y-%m-%d")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Rule 1a: Validate Reader
            reader = cursor.execute("SELECT * FROM readers WHERE folio = ?", (reader_folio,)).fetchone()
            if not reader:
                raise ValueError(f"Reader with folio '{reader_folio}' does not exist.")
            if reader["active"] == 0:
                raise ValueError(f"Borrow rejected: Reader '{reader['nombre']}' (Folio: {reader_folio}) is inactive.")

            # Rule 1b: Validate Book and Stock
            book = cursor.execute("SELECT * FROM books WHERE isbn = ?", (isbn,)).fetchone()
            if not book:
                raise ValueError(f"Book with ISBN '{isbn}' does not exist.")
            if book["active"] == 0:
                raise ValueError(f"Borrow rejected: Book '{book['title']}' (ISBN: {isbn}) is inactive.")
            if book["available_stock"] <= 0:
                raise ValueError(f"Borrow rejected: Book '{book['title']}' has no available stock (Current: {book['available_stock']}).")

            # Rule 2: Reader cannot have two active borrows of the same book
            existing_borrow = cursor.execute("""
                SELECT id FROM borrows
                WHERE reader_folio = ? AND isbn = ? AND status = 'active'
            """, (reader_folio, isbn)).fetchone()
            if existing_borrow:
                raise ValueError(
                    f"Borrow rejected: Reader '{reader['nombre']}' already has an active borrow (ID: {existing_borrow['id']}) for book '{book['title']}'."
                )

            # Atomic transaction: Insert borrow + discount 1 from available stock
            cursor.execute("""
                INSERT INTO borrows (reader_folio, isbn, borrow_date, expiration_date, status)
                VALUES (?, ?, ?, ?, 'active')
            """, (reader_folio, isbn, b_date_str, exp_date_str))
            borrow_id = cursor.lastrowid

            cursor.execute("""
                UPDATE books
                SET available_stock = available_stock - 1
                WHERE isbn = ?
            """, (isbn,))

            conn.commit()
            return borrow_id

    # =========================================================================
    # CLOSURE: REFUNDS / RETURNS
    # =========================================================================
    def return_book(
        self,
        borrow_id: Optional[int] = None,
        reader_folio: Optional[str] = None,
        isbn: Optional[str] = None,
        return_date: Optional[str] = None  # User-supplied date parameter (format: 'YYYY-MM-DD')
    ) -> Dict[str, Any]:
        """
        Processes a return (refund of stock):
        - return_date: Standard user-supplied date parameter (format: 'YYYY-MM-DD').
        - Marks the borrow as 'returned' with return_date.
        - Adds 1 stock back to available_stock.
        """
        if not return_date:
            raise ValueError("return_date is a required date parameter (format: 'YYYY-MM-DD').")

        if isinstance(return_date, (datetime, date)):
            r_date_str = (return_date if isinstance(return_date, date) else return_date.date()).strftime("%Y-%m-%d")
        else:
            r_date_str = datetime.strptime(str(return_date).strip(), "%Y-%m-%d").date().strftime("%Y-%m-%d")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Find active borrow
            if borrow_id is not None:
                borrow = cursor.execute(
                    "SELECT * FROM borrows WHERE id = ? AND status = 'active'", (borrow_id,)
                ).fetchone()
            elif reader_folio is not None and isbn is not None:
                borrow = cursor.execute("""
                    SELECT * FROM borrows
                    WHERE reader_folio = ? AND isbn = ? AND status = 'active'
                """, (reader_folio, isbn)).fetchone()
            else:
                raise ValueError("Must provide either borrow_id or both reader_folio and isbn.")

            if not borrow:
                raise ValueError("No active borrow found matching the specified parameters.")

            b_id = borrow["id"]
            book_isbn = borrow["isbn"]

            # Update borrow record
            cursor.execute("""
                UPDATE borrows
                SET status = 'returned', return_date = ?
                WHERE id = ?
            """, (r_date_str, b_id))

            # Refund stock: add 1 back
            cursor.execute("""
                UPDATE books
                SET available_stock = available_stock + 1
                WHERE isbn = ?
            """, (book_isbn,))

            conn.commit()

            return {
                "borrow_id": b_id,
                "reader_folio": borrow["reader_folio"],
                "isbn": book_isbn,
                "return_date": r_date_str,
                "status": "returned"
            }

    def list_borrows(self) -> List[Dict[str, Any]]:
        """Lists all raw borrow records."""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM borrows ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]

    # =========================================================================
    # OBLIGATORY JOIN: Borrow + Reader Name + Book Title
    # =========================================================================
    def get_borrows_with_details(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Obligatory JOIN query:
        Combines borrows table with reader name and book title.
        """
        query = """
            SELECT
                b.id AS borrow_id,
                b.reader_folio,
                r.nombre AS reader_name,
                r.reader_type,
                b.isbn,
                bk.title AS book_title,
                bk.author AS book_author,
                b.borrow_date,
                b.expiration_date,
                b.return_date,
                b.status
            FROM borrows b
            JOIN readers r ON b.reader_folio = r.folio
            JOIN books bk ON b.isbn = bk.isbn
        """
        params = []
        if status:
            query += " WHERE b.status = ?"
            params.append(status)

        query += " ORDER BY b.id DESC"

        with self.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # =========================================================================
    # REPORT: OVERDUE BORROWS
    # =========================================================================
    def get_overdue_borrows(self, current_date: str) -> List[Dict[str, Any]]:
        """
        Report of overdue borrows:
        - current_date: Standard user-supplied date parameter (format: 'YYYY-MM-DD', no time required).
        - Active borrows with expiration_date < current_date.
        - Uses obligatory JOIN to display reader name and book title.
        """
        if not current_date:
            raise ValueError("current_date is a required date parameter (format: 'YYYY-MM-DD').")

        if isinstance(current_date, (datetime, date)):
            ref_date_str = (current_date if isinstance(current_date, date) else current_date.date()).strftime("%Y-%m-%d")
        else:
            ref_date_str = datetime.strptime(str(current_date).strip(), "%Y-%m-%d").date().strftime("%Y-%m-%d")

        query = """
            SELECT
                b.id AS borrow_id,
                b.reader_folio,
                r.nombre AS reader_name,
                r.email AS reader_email,
                r.phone_number AS reader_phone,
                r.reader_type,
                b.isbn,
                bk.title AS book_title,
                b.borrow_date,
                b.expiration_date,
                b.status,
                CAST(julianday(?) - julianday(b.expiration_date) AS INTEGER) AS days_overdue
            FROM borrows b
            JOIN readers r ON b.reader_folio = r.folio
            JOIN books bk ON b.isbn = bk.isbn
            WHERE b.status = 'active'
              AND b.expiration_date < ?
            ORDER BY b.expiration_date ASC
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (ref_date_str, ref_date_str)).fetchall()
            return [dict(r) for r in rows]
