# Program: UR-CST Library Portal (console prototype)
# Purpose: Manage the library catalogue, students, borrowing, returns,
#          two-day due-date reminders, late fines and lost-book reports.

from datetime import date, timedelta


class LibraryPortal:
    def __init__(self):
        # Lists hold records; each record is a dictionary.
        self.books = [
            {"code": "PHY001", "title": "University Physics", "author": "Young and Freedman",
             "publisher": "Pearson", "year": 2020, "edition": "15th", "isbn": "9780135159552",
             "affiliation": "Physics", "cost": 45000, "available": True},
            {"code": "EEE001", "title": "Basic Electrical Engineering", "author": "V. K. Mehta",
             "publisher": "S. Chand", "year": 2018, "edition": "11th", "isbn": "9788121920805",
             "affiliation": "Electrical Engineering", "cost": 30000, "available": True},
            {"code": "MAT001", "title": "Engineering Mathematics", "author": "K. A. Stroud",
             "publisher": "Palgrave", "year": 2016, "edition": "7th", "isbn": "9781137031204",
             "affiliation": "Mathematics", "cost": 38000, "available": True}
        ]
        self.students = []
        self.loans = []
        self.messages = []

    def find_book(self, code):
        for book in self.books:
            if book["code"].lower() == code.lower():
                return book
        return None

    def find_student(self, reg_no):
        for student in self.students:
            if student["reg_no"].lower() == reg_no.lower():
                return student
        return None

    def add_book(self, book):
        if self.find_book(book["code"]):
            print("A book with that code already exists.")
            return
        self.books.append(book)
        print("Book added to the catalogue.")

    def register_student(self, student):
        if self.find_student(student["reg_no"]):
            print("That registration number is already registered.")
            return
        self.students.append(student)
        print("Student registered successfully.")

    def show_books(self, sort_choice="code", available_only=False):
        book_list = []
        for book in self.books:
            if not available_only or book["available"]:
                book_list.append(book)

        sort_options = {
            "1": ("affiliation", False),
            "2": ("title", False),
            "3": ("year", True),       # newest publication year first
            "4": ("year", False),      # oldest publication year first
            "5": ("title", True),      # Z to A
            "6": ("code", False),
            "7": ("author", False)
        }
        sort_field, reverse_order = sort_options.get(sort_choice, ("code", False))
        book_list = sorted(book_list,
                           key=lambda item: str(item[sort_field]).lower(),
                           reverse=reverse_order)

        if len(book_list) == 0:
            print("No books found.")
            return

        print("\nUR-CST LIBRARY CATALOGUE")
        print("-" * 100)
        for book in book_list:
            status = "AVAILABLE" if book["available"] else "BORROWED"
            print("Code:", book["code"], "| Title:", book["title"])
            print("Author:", book["author"], "| Publisher:", book["publisher"])
            print("Year:", book["year"], "| Edition:", book["edition"])
            print("ISBN:", book["isbn"], "| Affiliation:", book["affiliation"])
            print("Cost: RWF", book["cost"], "| Status:", status)
            print("-" * 100)

    def search_books(self, keyword, available_only=False):
        found = []
        keyword = keyword.lower()
        for book in self.books:
            details = (book["title"] + " " + book["author"] + " " +
                       book["affiliation"] + " " + book["code"]).lower()
            if keyword in details and (not available_only or book["available"]):
                found.append(book)

        if len(found) == 0:
            print("No matching books were found.")
        else:
            for book in found:
                status = "AVAILABLE" if book["available"] else "BORROWED"
                print(book["code"], "-", book["title"], "|", book["author"], "|", status)

    def borrow_book(self, reg_no, book_code):
        student = self.find_student(reg_no)
        book = self.find_book(book_code)

        if student is None:
            print("Student is not registered. Please contact the librarian.")
            return

        if book is None:
            print("Book code was not found.")
            return

        if not book["available"]:
            print("This book is already borrowed.")
            return

        borrow_date = date.today()
        due_date = borrow_date + timedelta(days=14)

        loan = {
            "reg_no": reg_no,
            "book_code": book_code,
            "borrow_date": borrow_date,
            "due_date": due_date,
            "return_date": None,
            "fine": 0,
            "reminder_sent": False,
            "lost": False
        }

        self.loans.append(loan)
        book["available"] = False

        print("Book borrowed successfully.")
        print("Borrow date:", borrow_date.strftime("%d/%m/%Y"))
        print("Return by:", due_date.strftime("%d/%m/%Y"))
        print("Loan period: 14 days.")

    def return_book(self, reg_no, book_code):
        active_loan = None
        for loan in self.loans:
            if (loan["reg_no"].lower() == reg_no.lower()
                    and loan["book_code"].lower() == book_code.lower()
                    and loan["return_date"] is None and not loan["lost"]):
                active_loan = loan
                break

        if active_loan is None:
            print("No active borrowing record was found.")
            return

        today = date.today()
        late_days = (today - active_loan["due_date"]).days
        if late_days < 0:
            late_days = 0

        fine = late_days * 500
        active_loan["return_date"] = today
        active_loan["fine"] = fine

        book = self.find_book(book_code)
        if book is not None:
            book["available"] = True

        print("Book returned successfully.")
        print("Late days:", late_days)
        print("Fine: RWF", fine)
        print("The book is available for another student.")
        print("A student may borrow it again if it is still available.")

    def show_student_loans(self, reg_no):
        found = False
        for loan in self.loans:
            if loan["reg_no"].lower() == reg_no.lower():
                found = True
                status = "RETURNED" if loan["return_date"] else "BORROWED"
                print("Book:", loan["book_code"],
                      "| Borrowed:", loan["borrow_date"].strftime("%d/%m/%Y"),
                      "| Due:", loan["due_date"].strftime("%d/%m/%Y"),
                      "| Status:", status,
                      "| Fine: RWF", loan["fine"])
        if not found:
            print("No borrowing record found for this student.")

    def check_reminders(self):
        # A reminder is generated once when the due date is two days away.
        today = date.today()
        for loan in self.loans:
            reminder_date = loan["due_date"] - timedelta(days=2)
            if (loan["return_date"] is None and not loan["lost"]
                    and not loan["reminder_sent"] and today >= reminder_date
                    and today <= loan["due_date"]):
                student = self.find_student(loan["reg_no"])
                if student is not None:
                    message = ("Dear " + student["name"] + ", your book "
                               + loan["book_code"] + " is due on "
                               + loan["due_date"].strftime("%d/%m/%Y")
                               + ". Please return it on time to avoid a fine.")
                    self.messages.append(message)
                    print("\nAUTOMATIC REMINDER (prototype message)")
                    print("To:", student["phone"])
                    print(message)
                    loan["reminder_sent"] = True

    def report_lost_book(self, reg_no, book_code):
        for loan in self.loans:
            if (loan["reg_no"].lower() == reg_no.lower()
                    and loan["book_code"].lower() == book_code.lower()
                    and loan["return_date"] is None and not loan["lost"]):
                book = self.find_book(book_code)
                if book is None:
                    print("Book record not found.")
                    return
                loan["lost"] = True
                loan["fine"] = book["cost"]
                book["available"] = False
                print("Lost-book report recorded.")
                print("Student debt to be reported to the school system: RWF", book["cost"])
                print("Librarian has been notified in this prototype.")
                return
        print("No active loan was found for that student and book.")

    def delete_book(self, book_code):
        # Do not delete a book while it has an active borrowing record.
        for loan in self.loans:
            if loan["book_code"].lower() == book_code.lower() and loan["return_date"] is None and not loan["lost"]:
                print("Cannot delete: this book has an active loan.")
                return
        book = self.find_book(book_code)
        if book is None:
            print("Book code was not found.")
            return
        self.books.remove(book)
        print("Book record deleted.")

    def delete_student(self, reg_no):
        # Do not delete a student while the student has an active loan.
        for loan in self.loans:
            if loan["reg_no"].lower() == reg_no.lower() and loan["return_date"] is None and not loan["lost"]:
                print("Cannot delete: this student has an active loan.")
                return
        student = self.find_student(reg_no)
        if student is None:
            print("Student was not found.")
            return
        self.students.remove(student)
        print("Student record deleted.")

    def librarian_menu(self):
        while True:
            print("\n--- LIBRARIAN MENU ---")
            print("1. Add a book")
            print("2. Register a student")
            print("3. View all books")
            print("4. View available books")
            print("5. Search books")
            print("6. View all borrowed books")
            print("7. View registered students")
            print("8. View generated reminder messages")
            print("9. Report a lost book")
            print("10. Delete a book record")
            print("11. Delete a student record")
            print("0. Back")
            choice = input("Choose: ")

            if choice == "1":
                book = {
                    "code": input("Book code: "),
                    "title": input("Title: "),
                    "author": input("Author: "),
                    "publisher": input("Publisher: "),
                    "year": int(input("Publication year: ")),
                    "edition": input("Edition number: "),
                    "isbn": input("ISBN: "),
                    "affiliation": input("Affiliation/department: "),
                    "cost": int(input("Book cost in RWF: ")),
                    "available": True
                }
                self.add_book(book)
            elif choice == "2":
                student = {
                    "reg_no": input("Registration number: "),
                    "department": input("Department: "),
                    "email": input("Email: "),
                    "phone": input("Phone number: "),
                    "name": input("Full name: "),
                    "age": input("Age: "),
                    "grade": input("Year/grade: ")
                }
                self.register_student(student)
            elif choice == "3":
                self.show_books("5")
            elif choice == "4":
                self.show_books("5", True)
            elif choice == "5":
                self.search_books(input("Enter title, author, code or affiliation: "))
            elif choice == "6":
                for loan in self.loans:
                    if loan["return_date"] is None and not loan["lost"]:
                        print(loan["reg_no"], loan["book_code"],
                              "Due:", loan["due_date"].strftime("%d/%m/%Y"))
            elif choice == "7":
                for student in self.students:
                    print(student["reg_no"], student["name"],
                          student["department"], student["phone"])
            elif choice == "8":
                if len(self.messages) == 0:
                    print("No reminder messages have been generated.")
                for message in self.messages:
                    print(message)
            elif choice == "9":
                self.report_lost_book(input("Student registration number: "),
                                      input("Book code: "))
            elif choice == "10":
                self.delete_book(input("Book code to delete: "))
            elif choice == "11":
                self.delete_student(input("Student registration number to delete: "))
            elif choice == "0":
                break
            else:
                print("Invalid choice.")

    def student_menu(self):
        reg_no = input("Enter your student registration number: ")
        student = self.find_student(reg_no)
        if student is None:
            print("Not registered. Ask the librarian to register you first.")
            return

        while True:
            print("\n--- STUDENT MENU ---")
            print("1. View available books")
            print("2. Search available books")
            print("3. Borrow a book")
            print("4. Return a book")
            print("5. View my borrowing records")
            print("0. Back")
            choice = input("Choose: ")

            if choice == "1":
                print("Sort by: 1-Affiliation 2-A-Z title 3-Newest year 4-Oldest year")
                print("          5-Z-A title 6-Book code 7-Author")
                self.show_books(input("Sort choice: "), True)
            elif choice == "2":
                self.search_books(input("Search keyword: "), True)
            elif choice == "3":
                self.borrow_book(reg_no, input("Book code: "))
            elif choice == "4":
                self.return_book(reg_no, input("Book code: "))
            elif choice == "5":
                self.show_student_loans(reg_no)
            elif choice == "0":
                break
            else:
                print("Invalid choice.")

    def guest_menu(self):
        print("\n--- GUEST MENU ---")
        print("1. View available books")
        print("2. Search available books")
        print("3. Donate a book (contact the librarian)")
        print("4. Read e-books (future portal feature)")
        choice = input("Choose: ")
        if choice == "1":
            self.show_books("5", True)
        elif choice == "2":
            self.search_books(input("Search keyword: "), True)
        elif choice == "3":
            print("Thank you. Please contact the library to arrange the donation.")
        elif choice == "4":
            print("E-book access will be added when digital materials are provided.")
        else:
            print("Returning to the main menu.")


def main():
    portal = LibraryPortal()

    # Check reminders when the program starts.
    portal.check_reminders()

    while True:
        print("\n======================================")
        print("       UR-CST LIBRARY PORTAL")
        print("======================================")
        print("1. Student")
        print("2. Librarian")
        print("3. Guest")
        print("0. Exit")
        choice = input("Login as: ")

        if choice == "1":
            portal.student_menu()
        elif choice == "2":
            portal.librarian_menu()
        elif choice == "3":
            portal.guest_menu()
        elif choice == "0":
            print("Thank you for using UR-CST Library Portal.")
            break
        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()
