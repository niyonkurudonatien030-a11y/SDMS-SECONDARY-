# Advanced Student Data Management System (SDMS)
# Each subject has its own marks and maximum entry

from tkinter import *
from tkinter import ttk, messagebox

root = Tk()
root.title("SDMS Advanced")
root.geometry("360x620")
root.configure(bg="#dfe6d5")

subjects = []
markEntries = []
maxEntries = []

# ---------------- FUNCTIONS ----------------

def load_subjects():

    global subjects, markEntries, maxEntries

    # Clear old widgets
    for widget in subjectFrame.winfo_children():
        widget.destroy()

    subjects.clear()
    markEntries.clear()
    maxEntries.clear()

    level = levelBox.get()

    if level == "Primary":
        subjects = [
            "Math", "SET", "Socio", "Eng",
            "Kiny", "Fra", "Rel", "PES",
            "Arts", "ICT"
        ]

    elif level == "O-Level":
        subjects = [
            "Math", "Phy", "Bio", "Chem",
            "Geo", "Hist", "Eng",
            "Kiny", "Fra", "ICT"
        ]

    elif level == "A-Level":
        subjects = [
            "Math", "Phy", "Bio",
            "Chem", "ICT", "Eng"
        ]

    # Create entries
    for sub in subjects:

        row = Frame(subjectFrame, bg="#dfe6d5")
        row.pack(fill=X, pady=1)

        Button(
            row,
            text=sub,
            width=7,
            font=("Arial", 7, "bold"),
            bg="#3c5a78",
            fg="white"
        ).pack(side=LEFT, padx=2)

        mark = Entry(row, width=6, font=("Arial", 8))
        mark.pack(side=LEFT, padx=2)

        maxm = Entry(row, width=6, font=("Arial", 8))
        maxm.pack(side=LEFT, padx=2)

        Label(
            row,
            text=" / ",
            bg="#dfe6d5",
            font=("Arial", 8)
        ).pack(side=LEFT)

        markEntries.append(mark)
        maxEntries.append(maxm)

def calculate():

    try:

        totalPercent = 0

        for i in range(len(subjects)):

            mark = float(markEntries[i].get())
            maximum = float(maxEntries[i].get())

            if maximum == 0:
                messagebox.showerror(
                    "Error",
                    f"Maximum of {subjects[i]} cannot be 0"
                )
                return

            percent = (mark / maximum) * 100
            totalPercent += percent

        average = totalPercent / len(subjects)

        resultVar.set(f"Average: {average:.2f}%")

        # Ranking
        if average >= 80:
            rankVar.set("Urahebuje")

        elif average >= 70:
            rankVar.set("Urarenze")

        elif average >= 60:
            rankVar.set("Ni byiza")

        elif average >= 50:
            rankVar.set("Watsinze")

        else:
            rankVar.set("Watsinzwe")

    except:
        messagebox.showerror(
            "Error",
            "Enter valid numbers"
        )

# ---------------- TITLE ----------------

Label(
    root,
    text="STUDENT DATA SYSTEM",
    bg="#2f4f4f",
    fg="white",
    font=("Arial", 11, "bold")
).pack(fill=X)

# ---------------- STUDENT NAME ----------------

Label(
    root,
    text="Student Name",
    bg="#dfe6d5",
    font=("Arial", 8, "bold")
).pack()

nameEntry = Entry(root, font=("Arial", 8))
nameEntry.pack(fill=X, padx=5)

# ---------------- LEVEL ----------------

Label(
    root,
    text="Select Level",
    bg="#dfe6d5",
    font=("Arial", 8, "bold")
).pack()

levelBox = ttk.Combobox(
    root,
    values=["Primary", "O-Level", "A-Level"],
    font=("Arial", 8)
)
levelBox.pack(fill=X, padx=5)

Button(
    root,
    text="LOAD SUBJECTS",
    bg="#3c5a78",
    fg="white",
    font=("Arial", 8, "bold"),
    command=load_subjects
).pack(pady=4)

# ---------------- HEADERS ----------------

header = Frame(root, bg="#dfe6d5")
header.pack(fill=X)

Label(
    header,
    text="Subject",
    width=10,
    bg="#dfe6d5",
    font=("Arial", 8, "bold")
).pack(side=LEFT)

Label(
    header,
    text="Marks",
    width=7,
    bg="#dfe6d5",
    font=("Arial", 8, "bold")
).pack(side=LEFT)

Label(
    header,
    text="Max",
    width=7,
    bg="#dfe6d5",
    font=("Arial", 8, "bold")
).pack(side=LEFT)

# ---------------- SUBJECT FRAME ----------------

subjectFrame = Frame(root, bg="#dfe6d5")
subjectFrame.pack(fill=BOTH, padx=4)

# ---------------- CALCULATE BUTTON ----------------

Button(
    root,
    text="CALCULATE RESULTS",
    bg="#1b5e20",
    fg="white",
    font=("Arial", 9, "bold"),
    command=calculate
).pack(fill=X, padx=5, pady=5)

# ---------------- RESULTS ----------------

resultVar = StringVar()
rankVar = StringVar()

Label(
    root,
    textvariable=resultVar,
    bg="#dfe6d5",
    font=("Arial", 10, "bold")
).pack()

Label(
    root,
    textvariable=rankVar,
    bg="#dfe6d5",
    fg="blue",
    font=("Arial", 11, "bold")
).pack()

root.mainloop()