from enum import IntEnum
import numpy as np
import polars as pl
import logging

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection


# Extract data from TADM database (.mdb) and plot curves together with tolerance bands
# Created by: Joel Gruselius <github.com/jgruselius>, 2023-11
#
# TODO:
#  [ ] Handle steps without data
#      [x] Don't plot missing tolerance bands
#      [x] Calculate y limits when tolerance data is missing


class StepType(IntEnum):
    Aspirate = -533331728
    Dispense = -533331727
    Unknown = 0

    def __str__(self):
        return self.name

    @classmethod
    def from_int(cls, integer):
        if integer == -533331728:
            return StepType.Aspirate
        elif integer == -533331727:
            return StepType.Aspirate
        else:
            return StepType.Unknown


def get_data_for_step(df: pl.DataFrame, liquid_class: str, step_type: StepType) -> pl.DataFrame:
    step_data = df.filter(
        pl.col("LiquidClassName").str.contains(liquid_class) &
        df["StepType"] == step_type)
    return step_data


def get_data_for_liquid_class(df: pl.DataFrame, liquid_class: str) -> pl.DataFrame:
    step_data = df.filter(pl.col("LiquidClassName").str.contains(liquid_class))
    return step_data


# NOT USED
def plot_single_step(data: pl.DataFrame):
    cols = ["cornflowerblue", "orange", "mediumseagreen", "mediumorchid",
            "palevioletred","yellowgreen", "lightcoral", "slateblue"]

    fig, ax = plt.subplots()
    ax.grid(True, linestyle="dashed", alpha=0.5)

    for i, r in data.iter_rows():
        ax.plot(r["TADM"],
                linewidth=1,
                color=cols[r["ChannelNumber"]-1],
                alpha=0.6
        )


def calc_y_limits(step_data: pl.DataFrame) -> tuple:
    y_max = step_data.select(pl.col("TADM").list.max().max()).item()
    y_min = step_data.select(pl.col("TADM").list.min().min()).item()
    return y_min-100, y_max+100


def calc_x_limits(step_data: pl.DataFrame) -> tuple:
    x_max = step_data.select(pl.col("TADM").list.len().max()).item()
    return 0, x_max


def plot_both_steps(data: pl.DataFrame, out_plot=None, noshow=False, backend="tkAgg"):
    # Use potentially faster backend for non-interactive plotting:
    # (it does not seem compatible with pyinstaller)
    # if noshow:
    #   mpl.use("Agg")
    mpl.use(backend)

    cols = ["cornflowerblue", "orange", "mediumseagreen", "mediumorchid",
        "palevioletred", "yellowgreen", "lightcoral", "slateblue"]

    fig, (ax1, ax2) = plt.subplots(nrows=2, constrained_layout=True, figsize=(12, 9))
    fig.suptitle(data.select("LiquidClassName").item(0, 0))

    # Takes the array of y values and adds a column of x 0..len(y):
    def _cstack(x):
        return np.column_stack((np.arange(len(x)), x))

    lcs = []

    for axis, step_type in zip((ax1, ax2), (StepType.Aspirate, StepType.Dispense)):
        axis.set_title(step_type.name)
        axis.grid(True, linestyle="dashed", alpha=0.5)
        axis.set_xlabel("Time (10 us)")
        axis.set_ylabel("Pressure")

        step_data = data.filter(pl.col("StepType") == step_type)

        # Plot the tolerance bands:
        for band in ("LowerToleranceBandTADM", "UpperToleranceBandTADM"):
            first = step_data.select(band).item(0, 0)
            if first is None:
                lc_name = step_data.select("LiquidClassName").item(0, 0)
                logging.warning(f"No {band} present for {step_type} of {lc_name}")
                y_lims = calc_y_limits(step_data)
                axis.set_ylim(*y_lims)
                x_lims = calc_x_limits(step_data)
                axis.set_xlim(*x_lims)
            else:
                # even indices are the x break points, odd indices give the pressure value at the
                # pre-ceding x:
                x = first[::2]   # odd indices
                y = first[1::2]  # even indices
                axis.plot(x, y, color="#cccccc", linewidth=2, linestyle="solid", alpha=0.75)

        # Plot the curvepoints for all transfers using LineCollection:
        for i, (key, val) in enumerate(step_data.group_by("ChannelNumber", maintain_order=True)):
            lc = LineCollection(
                [_cstack(y) for y in val.get_column("TADM")],
                linewidth=0.5,
                color=cols[i],
                alpha=1,
                label=f"Channel {i+1}"
            )
            axis.add_collection(lc)
            lcs.append(lc)

    n_channels = step_data.select(pl.col("ChannelNumber")).n_unique()
    plt.legend(handles=lcs[:n_channels], loc="upper left")

    if out_plot:
        fig.savefig(out_plot, bbox_inches="tight")
        logging.debug(f"Saved plot to {out_plot}.\n")
    if noshow:
        logging.debug("Skipping display of plot window")
    else:
        logging.info("Displaying plot...")
        plt.show()  # This actually displays the plot window

    plt.close()


def get_liquid_class_names(df: pl.DataFrame) -> set[str]:
    lc_names = set(df.get_column("LiquidClassName").unique())
    return lc_names
