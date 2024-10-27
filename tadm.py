from enum import IntEnum
import numpy as np
import polars as pl
import pyodbc
import platform
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


def check_driver():
    return get_driver() in pyodbc.drivers()


def get_driver() -> str:
    match platform.system():
        case "Windows":
            return r"Microsoft Access Driver (*.mdb, *.accdb)"
        case "Linux":
            return r"MDBToolsODBC"
        case _:
            raise NotImplementedError("OS must be either Windows or Linux")


def get_data_for_step(df: pl.DataFrame, liquid_class: str, step_type: StepType) -> pl.DataFrame:
    step_data = df.filter(
        pl.col("LiquidClassName").str.contains(liquid_class) & 
        pl.col("StepType") == step_type)
    return step_data


def get_data_for_liquid_class(df: pl.DataFrame, liquid_class: str) -> pl.DataFrame:
    step_data = df.filter(pl.col("LiquidClassName").str.contains(liquid_class))
    return step_data


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

    cols = ["cornflowerblue", "orange", "mediumseagreen", "mediumorchid"]

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


def bin_to_int(byte_string: bytes):
    return pl.Series(np.frombuffer(byte_string, dtype=np.int16))


def import_tadm_data(dbpath: str) -> pl.DataFrame:
    # connection object should be closed automatically when it goes out of
    # scope, but you can explicitly call close() also. Using the context
    # manager does something else, see doc.
    conn = pyodbc.connect(f"Driver={get_driver()};DBQ={dbpath};")
    query = "SELECT CurveId,LiquidClassName,StepType,Volume,TimeStamp,StepNumber,ChannelNumber,CurvePoints FROM TadmCurve"
    
    df = pl.read_database(query, conn)
    df = df.with_columns(pl.col("CurvePoints").map_elements(bin_to_int, return_dtype=pl.List(pl.Int16)).alias("TADM"))
    
    return df


def import_tolerance_band_data(dbpath: str, lc_names: set[str]) -> pl.DataFrame:
    conn = pyodbc.connect(f"Driver={get_driver()};DBQ={dbpath};")
    query = "SELECT LiquidClassId,LiquidClassName FROM LiquidClass"

    df = pl.read_database(query, conn)
    df = df.filter(pl.col("LiquidClassName").is_in(lc_names))

    query = "SELECT LiquidClassId,StepType,LowerToleranceBand,UpperToleranceBand FROM TadmToleranceBand"
    data = pl.read_database(query, conn)
    data = data.with_columns((
        pl.col("LowerToleranceBand").map_elements(bin_to_int, return_dtype=pl.List(pl.Int16)).alias("LowerToleranceBandTADM"),
        pl.col("UpperToleranceBand").map_elements(bin_to_int, return_dtype=pl.List(pl.Int16)).alias("UpperToleranceBandTADM")
    ))

    data = data.join(df, how="inner", on="LiquidClassId")

    return data


def merge_tadm_and_tolerance_data(tadm_data: pl.DataFrame, tol_band_data: pl.DataFrame) -> pl.DataFrame:
    return(tadm_data.join(tol_band_data, how="left", on=["LiquidClassName", "StepType"]))


def get_liquid_class_names(df: pl.DataFrame) -> set[str]:
    lc_names = set(df.get_column("LiquidClassName").unique())
    return lc_names
