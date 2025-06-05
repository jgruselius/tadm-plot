import os
import sys
import importlib

import pandas as pd
from pandas._libs.lib import fast_unique_multiple_list_gen
import wx

import numpy as np
import matplotlib as mpl
from matplotlib.collections import LineCollection
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar
from matplotlib.figure import Figure


from tadm.plotter import get_liquid_class_names, \
    get_data_for_liquid_class, StepType, calc_y_limits, calc_x_limits
import tadm.data
# Determine available methods for exporting data from MDB files.
# Either via pyodbc and an installed MDB driver or via mdbtools command line tools:
tadm_data_module = importlib.import_module(tadm.data.get_data_module())
sys.modules["tadm_data_module"] = tadm_data_module
from tadm_data_module import import_tadm_data, import_tolerance_band_data, merge_tadm_and_tolerance_data


# Extract data from TADM database (.mdb) and plot curves together with tolerance bands
# Created by: Joel Gruselius <github.com/jgruselius>, 2023-11

class Data:
    def __init__(self):
        self.tadm_path = None
        self.lcdb_path = get_path("ML_STARLiquids.mdb")
        self.df = None
        self.lc_names = None
        self.step_data = None

    def load_data(self):
        self.df = import_tadm_data(self.tadm_path)
        self.lc_names = get_liquid_class_names(self.df)
        tol = import_tolerance_band_data(self.lcdb_path, self.lc_names)
        self.df = merge_tadm_and_tolerance_data(self.df, tol)

    def get_data_for_step(self, lc_name: str):
        self.step_data = get_data_for_liquid_class(self.df, lc_name)

    @staticmethod
    def check_for_driver():
        try:
            tadm.data.get_data_module()
        except RuntimeError:
            return False
        else:
            return True

class MainFrame(wx.Frame):
    def __init__(self, parent, title, data):

        super(MainFrame, self).__init__(parent, title=title, size=(640, 400))

        # These need to bre references for events:
        self.data = data
        self.file_picker = None
        self.button_import = None
        self.list_box = None
        self.button_plot = None

        self.build_ui()

        self.Centre()
        self.Show()

    def build_ui(self):

        panel = wx.Panel(self)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        vbox = wx.BoxSizer(wx.VERTICAL)

        label_tadm = wx.StaticText(panel, label="TADM file:")
        label_liquid = wx.StaticText(panel, label="Liquid class:")

        self.file_picker = wx.FilePickerCtrl(panel, wx.ID_ANY, wx.EmptyString, "Select a TADM database", "*.mdb",
                                        wx.DefaultPosition, wx.DefaultSize, wx.FLP_DEFAULT_STYLE)
        self.file_picker.Bind(wx.EVT_FILEPICKER_CHANGED, self.on_file_selected)
        self.button_import = wx.Button(panel, label="Import")
        self.button_import.Bind(wx.EVT_BUTTON, self.on_click_import)
        self.button_import.Disable()

        liquids = []
        self.list_box = wx.Choice(panel, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, liquids, 0)
        self.list_box.SetSelection(0)
        self.list_box.Bind(wx.EVT_CHOICE, self.on_select_list)
        self.list_box.Disable()

        self.button_plot = wx.Button(panel, label="Generate")
        self.button_plot.Bind(wx.EVT_BUTTON, self.on_click_plot)
        self.button_plot.Disable()
        button_exit = wx.Button(panel, label="Exit")
        button_exit.Bind(wx.EVT_BUTTON, self.on_click_exit)

        vbox.Add(label_tadm, flag=wx.BOTTOM, border=10)
        vbox.Add(self.file_picker, flag=wx.EXPAND | wx.BOTTOM, border=20)
        vbox.Add(self.button_import)
        vbox.Add(-1, 40)
        vbox.Add(label_liquid, flag=wx.BOTTOM, border=10)
        vbox.Add(self.list_box, flag=wx.EXPAND)
        vbox.Add(-1, 80)

        hbox_buttons = wx.GridBagSizer(1, 3)
        hbox_buttons.Add(self.button_plot, pos=(0,0))
        hbox_buttons.Add(button_exit, pos=(0,2))
        hbox_buttons.AddGrowableCol(1)
        vbox.Add(hbox_buttons, flag=wx.EXPAND | wx.BOTTOM, border=10)

        hbox.Add(vbox, proportion=1, flag=wx.ALL | wx.EXPAND, border=30)
        panel.SetSizer(hbox)


    def on_click_exit(self, e):
        self.Close()

    def on_file_selected(self, e):
        src = e.GetEventObject()
        # self.FindWindowByLabel("Import").Enable()
        self.data.tadm_path = src.GetPath()
        self.button_import.Enable()

    def on_click_import(self, e):
        # Load the data
        # Set the droplist items
        # Enable the drop list
        # self.FindWindowByLabel("Generate").Enable()
        if self.data.tadm_path is not None:
            self.data.load_data()
            self.list_box.SetItems(list(data.lc_names))
            self.list_box.Enable()
            self.list_box.SetFocus()
        else:
            pass

    def on_select_list(self, e):
        # Enable the Plot button
        self.button_plot.Enable()


    def on_click_plot(self, e):
        lc = self.list_box.GetStringSelection()
        self.data.get_data_for_step(lc)
        frame_plot = PlotFrame(self.GetParent(), "TADM data")
        frame_plot.plot_both_steps(self.data.step_data)
        frame_plot.Fit()
        frame_plot.Show()


class PlotFrame(wx.Frame):
    def __init__(self, parent, title, id=-1, dpi=None, **kwargs):
        super(PlotFrame, self).__init__(parent, id=id, **kwargs)
        self.figure = Figure(dpi=dpi, figsize=(12, 9), constrained_layout=True)
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.canvas, 1, wx.EXPAND)
        sizer.Add(self.toolbar, 0, wx.LEFT | wx.EXPAND)
        self.SetSizer(sizer)

    def plot_both_steps(self, data: pd.DataFrame):
        mpl.use("WXAgg")

        cols = ["cornflowerblue", "orange", "mediumseagreen", "mediumorchid"]

        ax1 = self.figure.add_subplot(2, 1, 1)  # I.e. 2x1 grid, 1st plot
        ax2 = self.figure.add_subplot(2, 1, 2)  # I.e. 2x1 grid, 2nd plot
        self.figure.suptitle(data.iloc[0]["LiquidClassName"])

        # Takes the array of y values and adds a column of x 0..len(y):
        def _cstack(x):
            return np.column_stack((np.arange(len(x)), x))

        lcs = []

        for axis, step_type in zip((ax1, ax2), (StepType.Aspirate, StepType.Dispense)):
            axis.set_title(step_type.name)
            axis.grid(True, linestyle="dashed", alpha=0.5)
            axis.set_xlabel("Time (10 us)")
            axis.set_ylabel("Pressure")

            # Manual calculation of y limits (probably not needed):
            # step = data[data["StepType"] == step_type]
            # lower = step.iloc[0]["LowerToleranceBandTADM"]
            # upper = step.iloc[0]["UpperToleranceBandTADM"]
            # y_max = np.max(step["TADM"].apply(np.max))
            # y_max = np.max((y_max, np.max(upper[1::2])))
            # y_min = np.min(step["TADM"].apply(np.min))
            # y_min = np.min((y_min, np.min(lower[1::2])))
            # axis.set_ylim(y_min-100, y_max+100)

            step_data = data[data["StepType"] == step_type]

            # Plot the tolerance bands:
            for band in ("LowerToleranceBandTADM", "UpperToleranceBandTADM"):
                # even indices are the x break points, odd indices give the pressure value at the
                # pre-ceding x:
                first = step_data.iloc[0][band]
                if np.all(np.isnan(first)):
                    lc_name = step_data.iloc[0]["LiquidClassName"]
                    print(f"WARNING: No {band} present for {step_type} of {lc_name}")
                    y_lims = calc_y_limits(step_data)
                    axis.set_ylim(*y_lims)
                    x_lims = calc_x_limits(step_data)
                    axis.set_xlim(*x_lims)
                else:
                    x = first[::2]  # odd indices
                    y = first[1::2]  # even indices
                    axis.plot(x, y, color="#cccccc", linewidth=2, linestyle="solid", alpha=0.75)

            # Plot the curvepoints for all transfers in a loop:
            # for i, r in step_data.iterrows():
            #     p = axis.plot(r["TADM"],
            #             linewidth=1,
            #             color=cols[r["ChannelNumber"]-1],
            #             alpha=0.6,
            #             label=cols[r["ChannelNumber"]-1]
            #     )

            # Plot the curvepoints for all transfers using LineCollection:
            for i, g in step_data.groupby("ChannelNumber"):
                lc = LineCollection(
                    [_cstack(y) for y in g["TADM"]],
                    linewidth=0.5,
                    color=cols[i - 1],
                    alpha=1,
                    label=f"Channel {i}",
                )
                axis.add_collection(lc)
                lcs.append(lc)

        self.figure.legend(
            handles=lcs[:4],
            # [f"Channel {i+1}" for i in range(len(cols))],
            loc="center right",
            framealpha=1
        )


def driver_help(parent):
    msg1 = "Could not find a required ODBC driver to read MS Access databases."
    msg2 = "Install the Microsoft Access Database Engine 2010 Redistributable from here:"
    link = "https://www.microsoft.com/en-US/download/details.aspx?id=13255"
    print(msg1, msg2, link)
    dlg = wx.MessageDialog(parent, msg1, "Error: driver not found", wx.ICON_ERROR | wx.OK | wx.CENTRE)
    dlg.SetExtendedMessage(f"{msg2} {link}")
    dlg.ShowModal()
    parent.Close()


def get_path(file_name: str) -> str:
    script_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
    return os.path.join(script_dir, file_name)


if __name__ == "__main__":
    app = wx.App()
    data = Data()
    frame = MainFrame(None, "Test", data)
    if not Data.check_for_driver():
        driver_help(frame)
    app.MainLoop()
