# Student Data Management System (SDMS)
# GUI Version

from tkinter import *
from tkinter import ttk, messagebox

root = Tk()
root.title("SDMS")
root.geometry("320x520")
root.configure(bg="#dfe6d5")

subjects = []

# ---------- FUNCTIONS ----------

def load_subjects():

    global subjects
    subjects.clear()

    level = levelBox.get()

    if level == "Primary":
        subjects.extend([
            "Math", "SET", "Socio", "Eng",
            "Kiny", "Fra", "Rel", "PES",
            "Arts", "ICT"
        ])

    elif level == "O-Level":
        subjects.extend([
            "Math", "Phy", "Bio", "Chem",
            "Geo", "Hist", "Eng",
            "Kiny", "Fra", "ICT"
        ])

    elif level == "A-Level":
        subjects.extend([
            "Math", "Phy", "Bio",
            "Chem", "ICT", "Eng"
        ])

    subjectLabel.config(text="\n".join(subjects))


def calculate():

    try:
        marks = marksEntry.get().split(",")

        if len(marks) != len(subjects):
            messagebox.showerror(
                "Error",
                "Number of marks must match subjects"
            )
            return

        total = 0

        for m in marks:
            total += float(m)

        average = total / len(subjects)

        resultText.set(f"Average: {average:.2f}%")

        if average >= 80:
            rankText.set("Urahebuje")

        elif average >= 70:
            rankText.set("Urarenze")

        elif average >= 60:
            rankText.set("Ni byiza")

        elif average >= 50:
            rankText.set("Watsinze")

        else:
            rankText.set("Watsinzwe")

    except:
        messagebox.showerror(
            "Error",
            "Invalid marks"
        )

# ---------- TITLE ----------

Label(
    root,
    text="STUDENT DATA SYSTEM",
    font=("Arial", 11, "bold"),
    bg="#2f4f4f",
    fg="white"
).pack(fill=X)

# ---------- STUDENT NAME ----------

Label(
    root,
    text="Student Name",
    bg="#dfe6d5",
    font=("Arial", 9, "bold")
).pack()

nameEntry = Entry(root, font=("Arial", 9))
nameEntry.pack(fill=X, padx=5)

# ---------- LEVEL ----------

Label(
    root,
    text="Select Level",
    bg="#dfe6d5",
    font=("Arial", 9, "bold")
).pack()

levelBox = ttk.Combobox(
    root,
    values=["Primary", "O-Level", "A-Level"],
    font=("Arial", 8)
)
levelBox.pack(fill=X, padx=5)

Button(
    root,
    text="Load Subjects",
    bg="#3c5a78",
    fg="white",
    font=("Arial", 8, "bold"),
    command=load_subjects
).pack(pady=4)

# ---------- SUBJECTS ----------

Label(
    root,
    text="Subjects",
    bg="#dfe6d5",
    font=("Arial", 9, "bold")
).pack()

subjectLabel = Label(
    root,
    text="",
    justify=LEFT,
    bg="white",
    relief=RIDGE,
    anchor="w",
    font=("Arial", 8)
)

subjectLabel.pack(
    fill=BOTH,
    padx=5,
    pady=3,
    ipady=10
)

# ---------- MARKS ----------

Label(
    root,
    text="Enter marks separated by commas",
    bg="#dfe6d5",
    font=("Arial", 8)
).pack()

marksEntry = Entry(root, font=("Arial", 8))
marksEntry.pack(fill=X, padx=5)

# ---------- CALCULATE ----------

Button(
    root,
    text="CALCULATE",
    bg="#1b5e20",
    fg="white",
    font=("Arial", 9, "bold"),
    command=calculate
).pack(pady=5)

# ---------- RESULTS ----------

resultText = StringVar()
rankText = StringVar()

Label(
    root,
    textvariable=resultText,
    bg="#dfe6d5",
    font=("Arial", 10, "bold")
).pack()

Label(
    root,
    textvariable=rankText,
    bg="#dfe6d5",
    fg="blue",
    font=("Arial", 11, "bold")
).pack()

root.mainloop()