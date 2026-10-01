"""
Library Management System - Tkinter GUI Application
---------------------------------------------------
A comprehensive GUI for managing the SQLite / MySQL Library database.
Allows users to:
  - Connect to MySQL Workbench / MySQL Server (localhost:3306) or SQLite.
  - Insert, edit, view, and safely deactivate Books (Entity A).
  - Insert, edit, view, and safely deactivate Readers (Entity B).
  - Register Borrows with user-set Date (expires in 7 days, stock -1).
  - Process Returns with user-set Date (closure: stock +1).
  - View the Obligatory JOIN (Borrow + Reader Name + Book Title).
  - Generate the Overdue Report with a user-set evaluation date.
  - Directly edit table rows via forms or double-click dialogs.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List

# Import MySQL and SQLite database connector classes
try:
    from mysql_library import MySQLLibrary
except ImportError:
    MySQLLibrary = None

try:
    from library_db import LibraryDB
except ImportError:
    LibraryDB = None


class LibraryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Library Management System - Database Manager")
        self.geometry("1180x760")
        self.minsize(980, 640)

        # Style configuration
        self._setup_styles()

        # Database instance and engine type
        self.db = None
        self.db_type = "None"
        self._init_db_connection()

        # Build Main UI
        self._create_widgets()

        # Initial data load
        if self.db:
            self.refresh_all_data()

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[12, 6])
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#e1e6eb")
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=24)
        style.map("Treeview", background=[("selected", "#0078d7")])

    def _init_db_connection(self):
        """Attempts connection to local MySQL server; falls back to SQLite library.db."""
        if MySQLLibrary:
            try:
                self.db = MySQLLibrary(
                    host="localhost",
                    user="root",
                    password="1234",
                    port=3306,
                    database="library_db"
                )
                with self.db.get_connection():
                    pass
                self.db_type = "MySQL"
                return
            except Exception as e:
                print(f"Notice: MySQL not reachable, trying SQLite: {e}")

        # Fallback to local SQLite library.db
        if LibraryDB:
            sqlite_file = os.path.join(os.path.dirname(__file__), "library.db")
            try:
                self.db = LibraryDB(sqlite_file)
                self.db_type = "SQLite"
                return
            except Exception as ex:
                print(f"Warning: Could not connect to SQLite library.db: {ex}")

        self.db = None
        self.db_type = "None"

    # =========================================================================
    # UI CONSTRUCTION
    # =========================================================================
    def _create_widgets(self):
        # 1. Top Connection Bar
        top_bar = ttk.Frame(self, padding=(10, 6))
        top_bar.pack(side=tk.TOP, fill=tk.X)

        if self.db_type == "MySQL":
            status_text = f"● Connected to MySQL ({self.db.database} @ {self.db.host}:{self.db.port})"
            status_color = "#008000"
        elif self.db_type == "SQLite":
            status_text = f"● Connected to SQLite ({os.path.basename(self.db.db_path)})"
            status_color = "#0066cc"
        else:
            status_text = "○ Not Connected"
            status_color = "#cc0000"

        self.lbl_status = ttk.Label(
            top_bar,
            text=status_text,
            font=("Segoe UI", 9, "bold"),
            foreground=status_color
        )
            font=("Segoe UI", 9, "bold"),
            foreground="#008000" if self.db else "#cc0000"
        )
        self.lbl_status.pack(side=tk.LEFT, padx=5)

        btn_reconnect = ttk.Button(top_bar, text="⚙️ DB Settings", command=self._open_db_settings)
        btn_reconnect.pack(side=tk.RIGHT, padx=5)

        btn_init_sql = ttk.Button(top_bar, text="⚡ Run SQL Schema File", command=self._run_sql_schema)
        btn_init_sql.pack(side=tk.RIGHT, padx=5)

        btn_refresh_all = ttk.Button(top_bar, text="🔄 Refresh All", command=self.refresh_all_data)
        btn_refresh_all.pack(side=tk.RIGHT, padx=5)

        # 2. Main Tabbed Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # Create Tabs
        self.tab_books = ttk.Frame(self.notebook, padding=8)
        self.tab_readers = ttk.Frame(self.notebook, padding=8)
        self.tab_movements = ttk.Frame(self.notebook, padding=8)
        self.tab_join = ttk.Frame(self.notebook, padding=8)
        self.tab_overdue = ttk.Frame(self.notebook, padding=8)

        self.notebook.add(self.tab_books, text=" 📚 Books (Entity A) ")
        self.notebook.add(self.tab_readers, text=" 👥 Readers (Entity B) ")
        self.notebook.add(self.tab_movements, text=" 🔄 Movements (Borrow / Return) ")
        self.notebook.add(self.tab_join, text=" 🔗 Obligatory JOIN View ")
        self.notebook.add(self.tab_overdue, text=" ⚠️ Overdue Report ")

        self._build_books_tab()
        self._build_readers_tab()
        self._build_movements_tab()
        self._build_join_tab()
        self._build_overdue_tab()

    # =========================================================================
    # TAB 1: BOOKS (ENTITY A)
    # =========================================================================
    def _build_books_tab(self):
        # Form Container (Left)
        left_frame = ttk.LabelFrame(self.tab_books, text="Book Details (Insert / Edit)", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=2)

        fields = [
            ("ISBN:", "b_isbn"),
            ("Title:", "b_title"),
            ("Author:", "b_author"),
            ("Category:", "b_category"),
            ("Year:", "b_year"),
            ("Total Stock:", "b_total_stock"),
            ("Available Stock:", "b_available_stock"),
        ]

        self.book_entries = {}
        for row_idx, (label_text, var_name) in enumerate(fields):
            lbl = ttk.Label(left_frame, text=label_text, font=("Segoe UI", 9))
            lbl.grid(row=row_idx, column=0, sticky=tk.W, pady=3)
            ent = ttk.Entry(left_frame, width=28)
            ent.grid(row=row_idx, column=1, sticky=tk.EW, pady=3, padx=(5, 0))
            self.book_entries[var_name] = ent

        # Active checkbox
        ttk.Label(left_frame, text="Active:").grid(row=len(fields), column=0, sticky=tk.W, pady=3)
        self.book_active_var = tk.IntVar(value=1)
        chk_active = ttk.Checkbutton(left_frame, text="Is Active (1/0)", variable=self.book_active_var)
        chk_active.grid(row=len(fields), column=1, sticky=tk.W, pady=3, padx=(5, 0))

        # Button Frame
        btn_frame = ttk.Frame(left_frame, padding=(0, 10))
        btn_frame.grid(row=len(fields)+1, column=0, columnspan=2, sticky=tk.EW)

        ttk.Button(btn_frame, text="➕ Add Book", command=self._add_book).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="💾 Save Edit (Update)", command=self._update_book).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="🗑️ Delete / Deactivate", command=self._delete_book).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="🧹 Clear Form", command=self._clear_book_form).pack(fill=tk.X, pady=2)

        # Treeview (Right)
        right_frame = ttk.Frame(self.tab_books)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        cols = ("isbn", "title", "author", "category", "year", "total_stock", "available_stock", "active")
        self.tree_books = ttk.Treeview(right_frame, columns=cols, show="headings", selectmode="browse")
        
        headers = {
            "isbn": "ISBN", "title": "Title", "author": "Author", "category": "Category",
            "year": "Year", "total_stock": "Total", "available_stock": "Available", "active": "Active"
        }
        col_widths = {
            "isbn": 120, "title": 180, "author": 140, "category": 120,
            "year": 60, "total_stock": 60, "available_stock": 70, "active": 50
        }
        for col in cols:
            self.tree_books.heading(col, text=headers[col])
            self.tree_books.column(col, width=col_widths[col], anchor=tk.CENTER if col in ("year", "total_stock", "available_stock", "active") else tk.W)

        # Scrollbars
        vsb = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.tree_books.yview)
        hsb = ttk.Scrollbar(right_frame, orient=tk.HORIZONTAL, command=self.tree_books.xview)
        self.tree_books.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree_books.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        self.tree_books.bind("<<TreeviewSelect>>", self._on_book_select)
        self.tree_books.bind("<Double-1>", lambda e: self._on_book_select(e))

    def _on_book_select(self, event=None):
        selected = self.tree_books.selection()
        if not selected:
            return
        vals = self.tree_books.item(selected[0], "values")
        if not vals:
            return
        # Map values into entries
        self.book_entries["b_isbn"].delete(0, tk.END)
        self.book_entries["b_isbn"].insert(0, vals[0])

        self.book_entries["b_title"].delete(0, tk.END)
        self.book_entries["b_title"].insert(0, vals[1])

        self.book_entries["b_author"].delete(0, tk.END)
        self.book_entries["b_author"].insert(0, vals[2])

        self.book_entries["b_category"].delete(0, tk.END)
        self.book_entries["b_category"].insert(0, vals[3])

        self.book_entries["b_year"].delete(0, tk.END)
        self.book_entries["b_year"].insert(0, vals[4])

        self.book_entries["b_total_stock"].delete(0, tk.END)
        self.book_entries["b_total_stock"].insert(0, vals[5])

        self.book_entries["b_available_stock"].delete(0, tk.END)
        self.book_entries["b_available_stock"].insert(0, vals[6])

        self.book_active_var.set(int(vals[7]))

    def _clear_book_form(self):
        for ent in self.book_entries.values():
            ent.delete(0, tk.END)
        self.book_active_var.set(1)

    def _add_book(self):
        if not self.db:
            messagebox.showerror("Error", "No database connected.")
            return
        try:
            isbn = self.book_entries["b_isbn"].get().strip()
            title = self.book_entries["b_title"].get().strip()
            author = self.book_entries["b_author"].get().strip()
            category = self.book_entries["b_category"].get().strip()
            year = int(self.book_entries["b_year"].get().strip())
            total = int(self.book_entries["b_total_stock"].get().strip())
            avail_str = self.book_entries["b_available_stock"].get().strip()
            avail = int(avail_str) if avail_str else total
            active = self.book_active_var.get()

            if not (isbn and title and author):
                messagebox.showwarning("Validation", "ISBN, Title, and Author are required.")
                return

            self.db.add_book(isbn, title, author, category, year, total, avail, active)
            messagebox.showinfo("Success", f"Book '{title}' added successfully!")
            self.refresh_books()
            self._update_movement_combos()
        except Exception as e:
            messagebox.showerror("Database Error", str(e))

    def _update_book(self):
        if not self.db:
            messagebox.showerror("Error", "No database connected.")
            return
        try:
            isbn = self.book_entries["b_isbn"].get().strip()
            title = self.book_entries["b_title"].get().strip()
            author = self.book_entries["b_author"].get().strip()
            category = self.book_entries["b_category"].get().strip()
            year = int(self.book_entries["b_year"].get().strip())
            total = int(self.book_entries["b_total_stock"].get().strip())
            avail = int(self.book_entries["b_available_stock"].get().strip())
            active = self.book_active_var.get()

            if hasattr(self.db, "update_book"):
                self.db.update_book(isbn, title, author, category, year, total, avail, active)
            else:
                self.db.add_book(isbn, title, author, category, year, total, avail, active)

            messagebox.showinfo("Success", f"Book '{title}' (ISBN: {isbn}) updated successfully!")
            self.refresh_books()
            self._update_movement_combos()
        except Exception as e:
            messagebox.showerror("Update Error", str(e))

    def _delete_book(self):
        if not self.db:
            messagebox.showerror("Error", "No database connected.")
            return
        isbn = self.book_entries["b_isbn"].get().strip()
        if not isbn:
            messagebox.showwarning("Selection", "Select a book from the table to delete.")
            return
        try:
            # Enforces Rule 3 (deactivate instead of delete if active borrow exists)
            msg = self.db.delete_book(isbn, safe_deactivate=True)
            messagebox.showinfo("Action Result", msg)
            self.refresh_books()
            self._clear_book_form()
            self._update_movement_combos()
        except Exception as e:
            messagebox.showerror("Delete Error", str(e))

    def refresh_books(self):
        if not self.db:
            return
        for row in self.tree_books.get_children():
            self.tree_books.delete(row)
        try:
            books = self.db.list_books()
            for b in books:
                self.tree_books.insert("", tk.END, values=(
                    b["isbn"], b["title"], b["author"], b["category"],
                    b["year"], b["total_stock"], b["available_stock"], b["active"]
                ))
        except Exception as e:
            print("Error refreshing books:", e)

    # =========================================================================
    # TAB 2: READERS (ENTITY B)
    # =========================================================================
    def _build_readers_tab(self):
        # Form Container (Left)
        left_frame = ttk.LabelFrame(self.tab_readers, text="Reader Details (Insert / Edit)", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=2)

        fields = [
            ("Folio:", "r_folio"),
            ("Nombre (Name):", "r_nombre"),
            ("Email:", "r_email"),
            ("Phone Number:", "r_phone"),
        ]

        self.reader_entries = {}
        for row_idx, (label_text, var_name) in enumerate(fields):
            lbl = ttk.Label(left_frame, text=label_text, font=("Segoe UI", 9))
            lbl.grid(row=row_idx, column=0, sticky=tk.W, pady=3)
            ent = ttk.Entry(left_frame, width=28)
            ent.grid(row=row_idx, column=1, sticky=tk.EW, pady=3, padx=(5, 0))
            self.reader_entries[var_name] = ent

        # Reader Type (Enum / Combobox)
        ttk.Label(left_frame, text="Reader Type:").grid(row=len(fields), column=0, sticky=tk.W, pady=3)
        self.reader_type_var = tk.StringVar(value="student")
        cbo_type = ttk.Combobox(
            left_frame,
            textvariable=self.reader_type_var,
            values=["student", "docent", "outsider"],
            state="readonly",
            width=26
        )
        cbo_type.grid(row=len(fields), column=1, sticky=tk.EW, pady=3, padx=(5, 0))

        # Active checkbox
        ttk.Label(left_frame, text="Active:").grid(row=len(fields)+1, column=0, sticky=tk.W, pady=3)
        self.reader_active_var = tk.IntVar(value=1)
        chk_active = ttk.Checkbutton(left_frame, text="Is Active (1/0)", variable=self.reader_active_var)
        chk_active.grid(row=len(fields)+1, column=1, sticky=tk.W, pady=3, padx=(5, 0))

        # Button Frame
        btn_frame = ttk.Frame(left_frame, padding=(0, 10))
        btn_frame.grid(row=len(fields)+2, column=0, columnspan=2, sticky=tk.EW)

        ttk.Button(btn_frame, text="➕ Add Reader", command=self._add_reader).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="💾 Save Edit (Update)", command=self._update_reader).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="🗑️ Delete / Deactivate", command=self._delete_reader).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="🧹 Clear Form", command=self._clear_reader_form).pack(fill=tk.X, pady=2)

        # Treeview (Right)
        right_frame = ttk.Frame(self.tab_readers)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        cols = ("folio", "nombre", "email", "phone_number", "reader_type", "active")
        self.tree_readers = ttk.Treeview(right_frame, columns=cols, show="headings", selectmode="browse")

        headers = {
            "folio": "Folio", "nombre": "Nombre (Name)", "email": "Email",
            "phone_number": "Phone", "reader_type": "Type", "active": "Active"
        }
        col_widths = {
            "folio": 100, "nombre": 170, "email": 170,
            "phone_number": 110, "reader_type": 90, "active": 60
        }
        for col in cols:
            self.tree_readers.heading(col, text=headers[col])
            self.tree_readers.column(col, width=col_widths[col], anchor=tk.CENTER if col in ("reader_type", "active") else tk.W)

        vsb = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.tree_readers.yview)
        hsb = ttk.Scrollbar(right_frame, orient=tk.HORIZONTAL, command=self.tree_readers.xview)
        self.tree_readers.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree_readers.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        self.tree_readers.bind("<<TreeviewSelect>>", self._on_reader_select)
        self.tree_readers.bind("<Double-1>", lambda e: self._on_reader_select(e))

    def _on_reader_select(self, event=None):
        selected = self.tree_readers.selection()
        if not selected:
            return
        vals = self.tree_readers.item(selected[0], "values")
        if not vals:
            return
        self.reader_entries["r_folio"].delete(0, tk.END)
        self.reader_entries["r_folio"].insert(0, vals[0])

        self.reader_entries["r_nombre"].delete(0, tk.END)
        self.reader_entries["r_nombre"].insert(0, vals[1])

        self.reader_entries["r_email"].delete(0, tk.END)
        self.reader_entries["r_email"].insert(0, vals[2])

        self.reader_entries["r_phone"].delete(0, tk.END)
        self.reader_entries["r_phone"].insert(0, vals[3] if vals[3] else "")

        self.reader_type_var.set(vals[4])
        self.reader_active_var.set(int(vals[5]))

    def _clear_reader_form(self):
        for ent in self.reader_entries.values():
            ent.delete(0, tk.END)
        self.reader_type_var.set("student")
        self.reader_active_var.set(1)

    def _add_reader(self):
        if not self.db:
            messagebox.showerror("Error", "No database connected.")
            return
        try:
            folio = self.reader_entries["r_folio"].get().strip()
            nombre = self.reader_entries["r_nombre"].get().strip()
            email = self.reader_entries["r_email"].get().strip()
            phone = self.reader_entries["r_phone"].get().strip()
            rtype = self.reader_type_var.get()
            active = self.reader_active_var.get()

            if not (folio and nombre and email):
                messagebox.showwarning("Validation", "Folio, Nombre, and Email are required.")
                return

            self.db.add_reader(folio, nombre, email, phone, rtype, active)
            messagebox.showinfo("Success", f"Reader '{nombre}' added successfully!")
            self.refresh_readers()
            self._update_movement_combos()
        except Exception as e:
            messagebox.showerror("Database Error", str(e))

    def _update_reader(self):
        if not self.db:
            messagebox.showerror("Error", "No database connected.")
            return
        try:
            folio = self.reader_entries["r_folio"].get().strip()
            nombre = self.reader_entries["r_nombre"].get().strip()
            email = self.reader_entries["r_email"].get().strip()
            phone = self.reader_entries["r_phone"].get().strip()
            rtype = self.reader_type_var.get()
            active = self.reader_active_var.get()

            if hasattr(self.db, "update_reader"):
                self.db.update_reader(folio, nombre, email, phone, rtype, active)
            else:
                self.db.add_reader(folio, nombre, email, phone, rtype, active)

            messagebox.showinfo("Success", f"Reader '{nombre}' (Folio: {folio}) updated successfully!")
            self.refresh_readers()
            self._update_movement_combos()
        except Exception as e:
            messagebox.showerror("Update Error", str(e))

    def _delete_reader(self):
        if not self.db:
            messagebox.showerror("Error", "No database connected.")
            return
        folio = self.reader_entries["r_folio"].get().strip()
        if not folio:
            messagebox.showwarning("Selection", "Select a reader from the table to delete.")
            return
        try:
            msg = self.db.delete_reader(folio, safe_deactivate=True)
            messagebox.showinfo("Action Result", msg)
            self.refresh_readers()
            self._clear_reader_form()
            self._update_movement_combos()
        except Exception as e:
            messagebox.showerror("Delete Error", str(e))

    def refresh_readers(self):
        if not self.db:
            return
        for row in self.tree_readers.get_children():
            self.tree_readers.delete(row)
        try:
            readers = self.db.list_readers()
            for r in readers:
                self.tree_readers.insert("", tk.END, values=(
                    r["folio"], r["nombre"], r["email"], r.get("phone_number", ""),
                    r["reader_type"], r["active"]
                ))
        except Exception as e:
            print("Error refreshing readers:", e)

    # =========================================================================
    # TAB 3: MOVEMENTS (BORROW & RETURN)
    # =========================================================================
    def _build_movements_tab(self):
        top_container = ttk.Frame(self.tab_movements)
        top_container.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        # Panel 1: New Borrow
        f_borrow = ttk.LabelFrame(top_container, text="1. Register Borrow (Stock -1, Expires in 7 Days)", padding=10)
        f_borrow.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        ttk.Label(f_borrow, text="Reader:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.cbo_borrow_reader = ttk.Combobox(f_borrow, state="readonly", width=32)
        self.cbo_borrow_reader.grid(row=0, column=1, sticky=tk.EW, pady=3, padx=(5, 0))

        ttk.Label(f_borrow, text="Book:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.cbo_borrow_book = ttk.Combobox(f_borrow, state="readonly", width=32)
        self.cbo_borrow_book.grid(row=1, column=1, sticky=tk.EW, pady=3, padx=(5, 0))

        ttk.Label(f_borrow, text="Borrow Date:").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.ent_borrow_date = ttk.Entry(f_borrow, width=20)
        self.ent_borrow_date.insert(0, date.today().strftime("%Y-%m-%d"))
        self.ent_borrow_date.grid(row=2, column=1, sticky=tk.W, pady=3, padx=(5, 0))
        ttk.Label(f_borrow, text="(YYYY-MM-DD)", font=("Segoe UI", 8), foreground="gray").grid(row=2, column=1, sticky=tk.E)

        ttk.Button(f_borrow, text="➕ Register Borrow", command=self._do_borrow).grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0))

        # Panel 2: Process Return / Closure
        f_return = ttk.LabelFrame(top_container, text="2. Closure: Return Book (Stock +1)", padding=10)
        f_return.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        ttk.Label(f_return, text="Active Borrow ID:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.ent_return_id = ttk.Entry(f_return, width=20)
        self.ent_return_id.grid(row=0, column=1, sticky=tk.W, pady=3, padx=(5, 0))

        ttk.Label(f_return, text="Return Date:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.ent_return_date = ttk.Entry(f_return, width=20)
        self.ent_return_date.insert(0, date.today().strftime("%Y-%m-%d"))
        self.ent_return_date.grid(row=1, column=1, sticky=tk.W, pady=3, padx=(5, 0))
        ttk.Label(f_return, text="(YYYY-MM-DD)", font=("Segoe UI", 8), foreground="gray").grid(row=1, column=1, sticky=tk.E)

        ttk.Label(f_return, text="Select active borrow from table below or type ID").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=4)
        ttk.Button(f_return, text="↩️ Process Return / Refund", command=self._do_return).grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0))

        # Lower Container: Table of Borrows
        lbl_tbl = ttk.Label(self.tab_movements, text="Borrow Records (Click row to select for return):", font=("Segoe UI", 9, "bold"))
        lbl_tbl.pack(anchor=tk.W, pady=(4, 2))

        cols = ("id", "reader_folio", "isbn", "borrow_date", "expiration_date", "return_date", "status")
        self.tree_borrows = ttk.Treeview(self.tab_movements, columns=cols, show="headings", selectmode="browse")

        headers = {
            "id": "ID", "reader_folio": "Reader Folio", "isbn": "ISBN",
            "borrow_date": "Borrow Date", "expiration_date": "Expires (+7d)",
            "return_date": "Return Date", "status": "Status"
        }
        for col in cols:
            self.tree_borrows.heading(col, text=headers[col])
            self.tree_borrows.column(col, width=120, anchor=tk.CENTER if col in ("id", "borrow_date", "expiration_date", "return_date", "status") else tk.W)

        vsb = ttk.Scrollbar(self.tab_movements, orient=tk.VERTICAL, command=self.tree_borrows.yview)
        self.tree_borrows.configure(yscrollcommand=vsb.set)
        self.tree_borrows.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_borrows.bind("<<TreeviewSelect>>", self._on_borrow_select)

    def _update_movement_combos(self):
        """Populates Reader and Book comboboxes with available choices."""
        if not self.db:
            return
        try:
            readers = self.db.list_readers()
            reader_items = [f"{r['folio']} | {r['nombre']} ({'Active' if r['active'] else 'INACTIVE'})" for r in readers]
            self.cbo_borrow_reader["values"] = reader_items
            if reader_items:
                self.cbo_borrow_reader.current(0)

            books = self.db.list_books()
            book_items = [f"{b['isbn']} | {b['title']} (Avail: {b['available_stock']})" for b in books]
            self.cbo_borrow_book["values"] = book_items
            if book_items:
                self.cbo_borrow_book.current(0)
        except Exception as e:
            print("Error updating combos:", e)

    def _on_borrow_select(self, event=None):
        selected = self.tree_borrows.selection()
        if not selected:
            return
        vals = self.tree_borrows.item(selected[0], "values")
        if vals:
            self.ent_return_id.delete(0, tk.END)
            self.ent_return_id.insert(0, vals[0])

    def _do_borrow(self):
        if not self.db:
            messagebox.showerror("Error", "No database connected.")
            return
        try:
            reader_sel = self.cbo_borrow_reader.get()
            book_sel = self.cbo_borrow_book.get()
            b_date = self.ent_borrow_date.get().strip()

            if not (reader_sel and book_sel and b_date):
                messagebox.showwarning("Validation", "Select reader, book, and enter borrow_date.")
                return

            folio = reader_sel.split("|")[0].strip()
            isbn = book_sel.split("|")[0].strip()

            # Execute borrow with user-supplied date parameter
            b_id = self.db.borrow_book(folio, isbn, borrow_date=b_date)
            messagebox.showinfo("Borrow Success", f"Borrow #{b_id} registered successfully for date {b_date}!\nExpires in 7 days.")
            self.refresh_all_data()
        except Exception as e:
            messagebox.showerror("Borrow Rejected (Rule Violation)", str(e))

    def _do_return(self):
        if not self.db:
            messagebox.showerror("Error", "No database connected.")
            return
        try:
            b_id_str = self.ent_return_id.get().strip()
            r_date = self.ent_return_date.get().strip()

            if not (b_id_str and r_date):
                messagebox.showwarning("Validation", "Provide active Borrow ID and return_date.")
                return

            b_id = int(b_id_str)
            res = self.db.return_book(borrow_id=b_id, return_date=r_date)
            messagebox.showinfo("Return Success", f"Borrow #{res['borrow_id']} successfully returned on {res['return_date']}.\nAvailable stock restored (+1)!")
            self.refresh_all_data()
        except Exception as e:
            messagebox.showerror("Return Error", str(e))

    def refresh_borrows(self):
        if not self.db:
            return
        for row in self.tree_borrows.get_children():
            self.tree_borrows.delete(row)
        try:
            if hasattr(self.db, "list_borrows"):
                borrows = self.db.list_borrows()
            else:
                with self.db.get_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT * FROM borrows ORDER BY id DESC")
                    borrows = c.fetchall()

            for b in borrows:
                self.tree_borrows.insert("", tk.END, values=(
                    b["id"], b["reader_folio"], b["isbn"],
                    b["borrow_date"], b["expiration_date"],
                    b["return_date"] or "-", b["status"]
                ))
        except Exception as e:
            print("Error refreshing borrows:", e)

    # =========================================================================
    # TAB 4: OBLIGATORY JOIN VIEW
    # =========================================================================
    def _build_join_tab(self):
        top_frame = ttk.Frame(self.tab_join, padding=(0, 4))
        top_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(
            top_frame,
            text="Obligatory Query: Borrows + Reader Name + Book Title",
            font=("Segoe UI", 10, "bold")
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(top_frame, text="🔄 Refresh JOIN View", command=self.refresh_join_view).pack(side=tk.RIGHT, padx=5)

        cols = ("id", "folio", "reader_name", "reader_type", "isbn", "book_title", "author", "borrow_date", "expiration_date", "status")
        self.tree_join = ttk.Treeview(self.tab_join, columns=cols, show="headings", selectmode="browse")

        headers = {
            "id": "Borrow ID", "folio": "Folio", "reader_name": "Reader Name",
            "reader_type": "Type", "isbn": "ISBN", "book_title": "Book Title",
            "author": "Author", "borrow_date": "Borrow Date",
            "expiration_date": "Expires", "status": "Status"
        }
        for col in cols:
            self.tree_join.heading(col, text=headers[col])
            self.tree_join.column(col, width=110, anchor=tk.CENTER if col in ("id", "borrow_date", "expiration_date", "status", "reader_type") else tk.W)

        vsb = ttk.Scrollbar(self.tab_join, orient=tk.VERTICAL, command=self.tree_join.yview)
        hsb = ttk.Scrollbar(self.tab_join, orient=tk.HORIZONTAL, command=self.tree_join.xview)
        self.tree_join.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree_join.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

    def refresh_join_view(self):
        if not self.db:
            return
        for row in self.tree_join.get_children():
            self.tree_join.delete(row)
        try:
            borrows = self.db.get_borrows_with_details()
            for b in borrows:
                self.tree_join.insert("", tk.END, values=(
                    b["borrow_id"], b["reader_folio"], b["reader_name"],
                    b["reader_type"], b["isbn"], b["book_title"],
                    b.get("book_author", ""), b["borrow_date"],
                    b["expiration_date"], b["status"]
                ))
        except Exception as e:
            print("Error refreshing join view:", e)

    # =========================================================================
    # TAB 5: OVERDUE REPORT
    # =========================================================================
    def _build_overdue_tab(self):
        top_frame = ttk.LabelFrame(self.tab_overdue, text="Report Parameters (Evaluation Date)", padding=10)
        top_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        ttk.Label(top_frame, text="Current / Evaluation Date:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=5)
        self.ent_eval_date = ttk.Entry(top_frame, width=15)
        self.ent_eval_date.insert(0, date.today().strftime("%Y-%m-%d"))
        self.ent_eval_date.pack(side=tk.LEFT, padx=5)

        ttk.Button(top_frame, text="🔍 Generate Overdue Report", command=self.refresh_overdue_report).pack(side=tk.LEFT, padx=10)

        self.lbl_overdue_summary = ttk.Label(top_frame, text="", font=("Segoe UI", 9, "italic"), foreground="#a00")
        self.lbl_overdue_summary.pack(side=tk.LEFT, padx=10)

        cols = ("id", "reader_name", "email", "phone", "book_title", "borrow_date", "expiration_date", "days_overdue")
        self.tree_overdue = ttk.Treeview(self.tab_overdue, columns=cols, show="headings", selectmode="browse")

        headers = {
            "id": "Borrow ID", "reader_name": "Reader Name", "email": "Email",
            "phone": "Phone", "book_title": "Book Title",
            "borrow_date": "Borrow Date", "expiration_date": "Expired On", "days_overdue": "Days Overdue"
        }
        for col in cols:
            self.tree_overdue.heading(col, text=headers[col])
            self.tree_overdue.column(col, width=120, anchor=tk.CENTER if col in ("id", "borrow_date", "expiration_date", "days_overdue") else tk.W)

        vsb = ttk.Scrollbar(self.tab_overdue, orient=tk.VERTICAL, command=self.tree_overdue.yview)
        self.tree_overdue.configure(yscrollcommand=vsb.set)
        self.tree_overdue.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh_overdue_report(self):
        if not self.db:
            return
        eval_date = self.ent_eval_date.get().strip()
        if not eval_date:
            messagebox.showwarning("Validation", "Enter an evaluation date (format: YYYY-MM-DD).")
            return

        for row in self.tree_overdue.get_children():
            self.tree_overdue.delete(row)

        try:
            overdue = self.db.get_overdue_borrows(current_date=eval_date)
            count = len(overdue)
            self.lbl_overdue_summary.config(text=f"Found {count} overdue loan(s) as of {eval_date}")
            for o in overdue:
                self.tree_overdue.insert("", tk.END, values=(
                    o["borrow_id"], o["reader_name"], o["reader_email"],
                    o.get("reader_phone", ""), o["book_title"],
                    o["borrow_date"], o["expiration_date"],
                    f"{o['days_overdue']} days"
                ))
        except Exception as e:
            messagebox.showerror("Report Error", str(e))

    # =========================================================================
    # GLOBAL REFRESH & DATABASE SETTINGS DIALOG
    # =========================================================================
    def refresh_all_data(self):
        self.refresh_books()
        self.refresh_readers()
        self.refresh_borrows()
        self.refresh_join_view()
        self.refresh_overdue_report()
        self._update_movement_combos()

    def _open_db_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title("MySQL Database Connection Settings")
        dlg.geometry("400x320")
        dlg.transient(self)
        dlg.grab_set()

        fields = [
            ("Host:", "host", "localhost"),
            ("Port:", "port", "3306"),
            ("User:", "user", "root"),
            ("Password:", "password", "1234"),
            ("Database:", "database", "library_db"),
        ]

        entries = {}
        for idx, (label, key, default_val) in enumerate(fields):
            ttk.Label(dlg, text=label).grid(row=idx, column=0, sticky=tk.W, padx=15, pady=8)
            ent = ttk.Entry(dlg, width=25, show="*" if key == "password" else "")
            current_val = getattr(self.db, key, default_val) if self.db else default_val
            ent.insert(0, str(current_val))
            ent.grid(row=idx, column=1, sticky=tk.EW, padx=15, pady=8)
            entries[key] = ent

        def save_and_connect():
            try:
                new_db = MySQLLibrary(
                    host=entries["host"].get().strip(),
                    port=int(entries["port"].get().strip()),
                    user=entries["user"].get().strip(),
                    password=entries["password"].get().strip(),
                    database=entries["database"].get().strip()
                )
                with new_db.get_connection():
                    pass
                self.db = new_db
                self.lbl_status.config(
                    text=f"● Connected to MySQL ({self.db.database} @ {self.db.host}:{self.db.port})",
                    foreground="#008000"
                )
                messagebox.showinfo("Connected", "Successfully connected to MySQL database!")
                dlg.destroy()
                self.refresh_all_data()
            except Exception as ex:
                messagebox.showerror("Connection Failed", str(ex))

        ttk.Button(dlg, text="Connect & Save", command=save_and_connect).grid(row=len(fields), column=0, columnspan=2, pady=15)

    def _run_sql_schema(self):
        if not self.db:
            messagebox.showerror("Error", "No database connected.")
            return
        if messagebox.askyesno("Confirm", "Execute 'library_workbench.sql' to recreate/update the schema?\nExisting tables will be initialized."):
            try:
                sql_path = os.path.join(os.path.dirname(__file__), "library_workbench.sql")
                self.db.execute_sql_file(sql_path)
                messagebox.showinfo("Success", "SQL schema executed and database updated successfully!")
                self.refresh_all_data()
            except Exception as e:
                messagebox.showerror("SQL Execution Error", str(e))


def main():
    app = LibraryApp()
    app.mainloop()


if __name__ == "__main__":
    main()
