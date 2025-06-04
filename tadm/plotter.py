from enum import IntEnum
import numpy as np
import pandas as pd
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


def get_data_for_step(df: pd.DataFrame, liquid_class: str, step_type: StepType) -> pd.DataFrame:
    step_data = df[(df["LiquidClassName"].str.contains(liquid_class)) & (df["StepType"] == step_type)]
    return step_data


def get_data_for_liquid_class(df: pd.DataFrame, liquid_class: str) -> pd.DataFrame:
    step_data = df[df["LiquidClassName"].str.contains(liquid_class)]
    return step_data


# NOT USED
def plot_single_step(data: pd.DataFrame):
    cols = ["blue", "orange", "green", "purple"]

    fig, ax = plt.subplots()
    ax.grid(True, linestyle="dashed", alpha=0.5)

    for i, r in data.iterrows():
        ax.plot(r["TADM"], linewidth=1, color=cols[r["ChannelNumber"] - 1], alpha=0.6)


def calc_y_limits(step_data: pd.DataFrame) -> tuple:
    y_max = np.max(step_data["TADM"].apply(np.max))
    y_min = np.min(step_data["TADM"].apply(np.min))
    return y_min-100, y_max+100


def calc_x_limits(step_data: pd.DataFrame) -> tuple:
    x_max = np.max(step_data["TADM"].apply(np.size))
    return 0, x_max


def plot_both_steps(data: pd.DataFrame, out_plot=None, noshow=False, backend="TkAgg"):
    # Use potentially faster backend for non-interactive plotting:
    # (it does not seem compatible with pyinstaller)
    #if noshow:
    #   mpl.use("Agg")
    mpl.use(backend)

    cols = ["cornflowerblue", "orange", "mediumseagreen", "mediumorchid",
        "palevioletred", "yellowgreen", "lightcoral", "slateblue"]

    fig, (ax1, ax2) = plt.subplots(nrows=2, constrained_layout=True, figsize=(12, 9))
    fig.suptitle(data.iloc[0]["LiquidClassName"])

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
                logging.warning(f"No {band} present for {step_type} of {lc_name}")
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
                color=cols[i-1],
                alpha=1,
                label=f"Channel {i}",
            )
            axis.add_collection(lc)
            lcs.append(lc)

    n_channels = step_data["ChannelNumber"].nunique()
    plt.legend(
        handles=lcs[:n_channels],
        # [f"Channel {i+1}" for i in range(len(cols))],
        loc="upper left",
    )

    if out_plot:
        fig.savefig(out_plot, bbox_inches="tight")
        logging.debug(f"Saved plot to {out_plot}.\n")
    if noshow:
        logging.debug("Skipping display of plot window")
    else:
        logging.info("Displaying plot...")
        plt.show()  # This actually displays the plot window

    plt.close()


def get_liquid_class_names(df: pd.DataFrame) -> set[str]:
    lc_names = set(df["LiquidClassName"].unique())
    return lc_names
