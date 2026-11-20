"""Enterprise Smart Inventory & Asset System - single-file version."""
from abc import ABC, abstractmethod
from datetime import date, timedelta


class Item(ABC):
    """Abstract base class for every borrowable asset (LibraryItem)."""

    LOAN_DAYS = 14  # overridden by subclasses

    def __init__(self, item_id: str, title: str, price: float):
        self.__item_id = item_id          # private, read-only
        self.__title = None
        self.__price = None
        self.__borrow_date = None         # private, managed via checkout/return
        self.__borrower = None
        self.title = title                # goes through validating setters
        self.price = price

    # ---------- Encapsulation: properties ----------
    @property
    def item_id(self) -> str:
        return self.__item_id

    @property
    def title(self) -> str:
        return self.__title

    @title.setter
    def title(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Title must be a non-empty string.")
        self.__title = value.strip()

    @property
    def price(self) -> float:
        return self.__price

    @price.setter
    def price(self, value: float) -> None:
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError("Price must be a non-negative number.")
        self.__price = float(value)

    @property
    def borrow_date(self):
        return self.__borrow_date

    @property
    def borrower(self):
        return self.__borrower

    @property
    def is_available(self) -> bool:
        return self.__borrow_date is None

    # ---------- Shared behaviour ----------
    def checkout(self, borrower: str, on: date = None) -> None:
        if not self.is_available:
            raise RuntimeError(f"'{self.title}' is already checked out.")
        if not borrower or not borrower.strip():
            raise ValueError("Borrower name is required.")
        self.__borrower = borrower.strip()
        self.__borrow_date = on or date.today()

    def check_in(self, on: date = None) -> float:
        """Returns the fee owed, then resets the loan state."""
        if self.is_available:
            raise RuntimeError(f"'{self.title}' is not checked out.")
        fee = self.calculate_fee(on)
        self.__borrower = None
        self.__borrow_date = None
        return fee

    def overdue_days(self, as_of: date = None) -> int:
        if self.is_available:
            return 0
        as_of = as_of or date.today()
        return max(0, (as_of - self.__borrow_date).days - self.LOAN_DAYS)

    # ---------- Abstraction ----------
    @abstractmethod
    def calculate_fee(self, as_of: date = None) -> float:
        """Late fee as of the given date."""

    @abstractmethod
    def display_metadata(self) -> str:
        """Type-specific description line."""

    @abstractmethod
    def __len__(self) -> int:
        """Size of the item (pages, minutes, ...)."""

    # ---------- Dunder methods ----------
    def __str__(self) -> str:
        status = "Available" if self.is_available else f"Borrowed by {self.borrower}"
        return f"[{self.item_id}] {self.title} - {status}"

    def __repr__(self) -> str:
        return (f"{type(self).__name__}(item_id={self.item_id!r}, "
                f"title={self.title!r}, price={self.price!r})")

    def __eq__(self, other) -> bool:
        if not isinstance(other, Item):
            return NotImplemented
        return type(self) is type(other) and self.item_id == other.item_id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.item_id))


class Book(Item):
    LOAN_DAYS = 14
    FEE_PER_DAY = 0.50

    def __init__(self, item_id, title, price, author: str, pages: int):
        super().__init__(item_id, title, price)
        self.author = author
        self.__pages = None
        self.pages = pages

    @property
    def pages(self) -> int:
        return self.__pages

    @pages.setter
    def pages(self, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            raise ValueError("Pages must be a positive integer.")
        self.__pages = value

    def calculate_fee(self, as_of=None) -> float:
        # Fee is capped at the replacement price of the book
        return min(self.overdue_days(as_of) * self.FEE_PER_DAY, self.price)

    def display_metadata(self) -> str:
        return f"Book by {self.author}, {self.pages} pages"

    def __len__(self) -> int:
        return self.pages


class Magazine(Item):
    LOAN_DAYS = 7
    FEE_PER_DAY = 0.25

    def __init__(self, item_id, title, price, issue_number: int, pages: int):
        super().__init__(item_id, title, price)
        self.issue_number = issue_number
        self.__pages = None
        self.pages = pages

    @property
    def pages(self) -> int:
        return self.__pages

    @pages.setter
    def pages(self, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            raise ValueError("Pages must be a positive integer.")
        self.__pages = value

    def calculate_fee(self, as_of=None) -> float:
        return min(self.overdue_days(as_of) * self.FEE_PER_DAY, self.price)

    def display_metadata(self) -> str:
        return f"Magazine issue #{self.issue_number}, {self.pages} pages"

    def __len__(self) -> int:
        return self.pages


class DigitalMedia(Item):
    LOAN_DAYS = 3
    FLAT_LATE_FEE = 2.00

    def __init__(self, item_id, title, price, duration_min: int, file_size_mb: float):
        super().__init__(item_id, title, price)
        self.__duration_min = None
        self.duration_min = duration_min
        self.file_size_mb = file_size_mb

    @property
    def duration_min(self) -> int:
        return self.__duration_min

    @duration_min.setter
    def duration_min(self, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            raise ValueError("Duration must be a positive integer (minutes).")
        self.__duration_min = value

    def calculate_fee(self, as_of=None) -> float:
        # Digital licences: flat fee once overdue, not per day
        return self.FLAT_LATE_FEE if self.overdue_days(as_of) > 0 else 0.0

    def display_metadata(self) -> str:
        return f"Digital media, {self.duration_min} min, {self.file_size_mb} MB"

    def __len__(self) -> int:
        return self.duration_min


# ======================= INVENTORY MANAGER =======================


class InventoryError(Exception):
    """Base error for inventory operations."""


class InventoryManager:
    def __init__(self):
        self._items: dict[str, Item] = {}
        self._log: list[dict] = []
        self.total_fees = 0.0

    # ---------- Catalogue ----------
    def add_item(self, item: Item) -> None:
        if item.item_id in self._items:
            raise InventoryError(f"Duplicate item id: {item.item_id}")
        self._items[item.item_id] = item

    def get(self, item_id: str) -> Item:
        try:
            return self._items[item_id]
        except KeyError:
            raise InventoryError(f"Unknown item id: {item_id}") from None

    # ---------- Transactions ----------
    def checkout(self, item_id: str, borrower: str, on: date = None) -> None:
        item = self.get(item_id)
        item.checkout(borrower, on)
        self._log.append({"date": item.borrow_date, "action": "CHECKOUT",
                          "item": item.item_id, "who": borrower, "fee": 0.0})

    def return_item(self, item_id: str, on: date = None) -> float:
        item = self.get(item_id)
        who = item.borrower
        on = on or date.today()
        fee = item.check_in(on)
        self.total_fees += fee
        self._log.append({"date": on, "action": "RETURN",
                          "item": item.item_id, "who": who, "fee": fee})
        return fee

    # ---------- Reports ----------
    @staticmethod
    def _table(headers, rows) -> str:
        widths = [max(len(str(c)) for c in col) for col in zip(headers, *rows)]
        line = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
        fmt = lambda r: "| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |"
        out = [line, fmt(headers), line] + [fmt(r) for r in rows] + [line]
        return "\n".join(out)

    def audit_report(self, as_of: date = None) -> str:
        as_of = as_of or date.today()
        headers = ["ID", "Type", "Title", "Size", "Price", "Status", "Overdue", "Fee Due"]
        rows = []
        for it in self:
            status = "Available" if it.is_available else f"Out: {it.borrower}"
            rows.append([it.item_id, type(it).__name__, it.title, len(it),
                         f"${it.price:.2f}", status, it.overdue_days(as_of),
                         f"${it.calculate_fee(as_of):.2f}"])
        return self._table(headers, rows)

    def transaction_report(self) -> str:
        headers = ["Date", "Action", "Item", "Borrower", "Fee"]
        rows = [[e["date"], e["action"], e["item"], e["who"], f"${e['fee']:.2f}"]
                for e in self._log]
        return self._table(headers, rows)

    # ---------- Dunder methods ----------
    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items.values())

    def __contains__(self, item_id: str) -> bool:
        return item_id in self._items


if __name__ == "__main__":
    inv = InventoryManager()
    inv.add_item(Book("B001", "Clean Code", 45.0, "Robert C. Martin", 464))
    inv.add_item(Book("B002", "Fluent Python", 60.0, "Luciano Ramalho", 792))
    inv.add_item(Magazine("M001", "Wired", 8.0, 312, 120))
    inv.add_item(DigitalMedia("D001", "Python OOP Course", 20.0, 540, 1850.5))

    today = date.today()
    inv.checkout("B001", "Ali", today - timedelta(days=20))   # 6 days late
    inv.checkout("M001", "Sara", today - timedelta(days=10))  # 3 days late
    inv.checkout("D001", "Hamza", today - timedelta(days=5))  # overdue, flat fee

    print("=== AUDIT REPORT ===")
    print(inv.audit_report())

    print("\nFee on return of B001:", f"${inv.return_item('B001'):.2f}")
    print("Fee on return of D001:", f"${inv.return_item('D001'):.2f}")

    print("\n=== TRANSACTIONS ===")
    print(inv.transaction_report())
    print(f"\nTotal fees collected: ${inv.total_fees:.2f}")

    # Dunder method demos
    b = inv.get("B002")
    print("\nstr :", str(b))
    print("repr:", repr(b))
    print("len :", len(b), "pages")
    print("eq  :", b == Book("B002", "Other title", 1, "X", 1))
    print("Catalogue size:", len(inv), "| 'M001' in inv:", "M001" in inv)

    # Encapsulation / validation demo
    try:
        b.price = -5
    except ValueError as e:
        print("Validation:", e)
    try:
        Item("X", "Y", 1)
    except TypeError as e:
        print("Abstract :", e)