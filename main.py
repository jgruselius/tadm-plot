import sys
import os
import tkinter as tk
from tkinter import ttk
from tkinter.messagebox import showinfo, showerror
from tkinter import filedialog as fd

from tadm import import_tadm_data, get_liquid_class_names, import_tolerance_band_data, \
    merge_tadm_and_tolerance_data, get_data_for_liquid_class, plot_both_steps, check_driver


# Extract data from TADM database (.mdb) and plot curves together with tolerance bands
# Created by: Joel Gruselius <github.com/jgruselius>, 2023-11


def driver_help():
    msg1 = "Could not find a required ODBC driver to read MS Access databases."
    msg2 = "Install the Microsoft Access Database Engine 2010 Redistributable from here:"
    link = "https://www.microsoft.com/en-US/download/details.aspx?id=13255"
    print(msg1, msg2, link)
    showerror(title="Driver not found", message=msg1, detail=f"{msg2} {link}")


def get_path(file_name: str) -> str:
    script_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
    return os.path.join(script_dir, file_name)


class SelectionFrame(ttk.Frame):
    def __init__(self, container, **options):
        super().__init__(container, **options)

        self.selected_file = tk.StringVar()
        self.selected_liquid = tk.StringVar()
        self.columnconfigure(0, weight=1, minsize=90)
        self.columnconfigure(1, weight=4, minsize=90*4)
        self.columnconfigure(2, weight=1, minsize=90)

        self.__create_widgets()

    def __create_widgets(self):
        # File open label
        ttk.Label(self, text="TADM file:").grid(column=0, row=0, sticky=tk.W, pady=5)
        # Selected file entry
        ttk.Entry(self, textvariable=self.selected_file, state="readonly").grid(column=1, row=0, sticky=tk.W+tk.E, pady=5)
        # Open button
        ttk.Button(self, text='Browse', command=self.select_file).grid(column=2, row=0, sticky=tk.E, pady=5)
        # Import button
        self.import_button = ttk.Button(self, text='Import', state=tk.DISABLED, command=self._load_data)
        self.import_button.grid(column=1, row=1, sticky=tk.W, pady=5)
        # Liquid select label
        ttk.Label(self, text="Liquid class:").grid(column=0, row=2, sticky=tk.W, pady=25)
        # Liquid select combobox
        self.lc_combobox = ttk.Combobox(self, textvariable=self.selected_liquid, state=tk.DISABLED)
        self.lc_combobox.grid(column=1, row=2, columnspan=2, sticky=tk.W+tk.E, pady=25)
        # Quit button
        self.generate_button = ttk.Button(self, text='Exit', command=self.master.destroy)
        self.generate_button.grid(column=0, row=3, sticky=tk.W, pady=25)
        # Plot button
        self.generate_button = ttk.Button(self, text='Generate', command=self._generate_plot, state=tk.DISABLED)
        self.generate_button.grid(column=2, row=3, sticky=tk.W, pady=25)
        self.lc_combobox.bind("<<ComboboxSelected>>", lambda x: self.generate_button.configure(state=tk.NORMAL))

        for widget in self.winfo_children():
            widget.grid(padx=15)

    def select_file(self):
        filetypes = (
            ('TADM databse', '*.mdb'),
            ('All files', '*.*')
        )

        filename = fd.askopenfilename(
            title='Open file',
            initialdir='./',
            filetypes=filetypes)

        self.selected_file.set(filename)
        print(self.selected_file.get())
        self.import_button.config(state=tk.ACTIVE)

    def _load_data(self):
        self.master.load_data(self.selected_file.get(), get_path("ML_STARLiquids.mdb"))
        self.lc_combobox.configure(values=list(self.master.lc_names), state="readonly")
        self.lc_combobox.focus_set()
        self.import_button.configure(state=tk.DISABLED)

    def _generate_plot(self):
        lc = self.selected_liquid.get()
        self.master.generate_plot(lc)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        # configure the root window
        self.title("TADM plotter")
        self.geometry("600x230")
        if os.name == "nt":
            self.iconbitmap(get_path("icon.ico"))
        self.configure(background="white")
        s = ttk.Style()
        s.configure("TFrame", background="white")
        s.configure("TLabel", background="white")

        # layout on the root window
        self.columnconfigure(0, weight=4)
        self.columnconfigure(1, weight=1)

        self.__create_widgets()

        self.df = None
        self.lc_names = None

        if not check_driver():
            driver_help()
            self.destroy()

    def __create_widgets(self):
        file_frame = SelectionFrame(self)
        file_frame.grid(column=0, row=0)

        for widget in self.winfo_children():
            widget.grid(padx=15, pady=15, sticky=tk.W)

    # This could be done in a separate thread:
    def load_data(self, tadm_path: str, lcdb_path: str):
        self.df = import_tadm_data(tadm_path)
        self.lc_names = get_liquid_class_names(self.df)
        tol = import_tolerance_band_data(lcdb_path, self.lc_names)
        self.df = merge_tadm_and_tolerance_data(self.df, tol)

    def generate_plot(self, lc_name: str):
        step_data = get_data_for_liquid_class(self.df, lc_name)
        plot_both_steps(step_data, None, False, "tkAgg")


if __name__ == "__main__":
    app = App()
    app.mainloop()
