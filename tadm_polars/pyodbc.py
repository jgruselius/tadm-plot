import numpy as np
import polars as pl
import platform
import pyodbc


def get_driver() -> str:
    match platform.system():
        case "Windows":
            return r"Microsoft Access Driver (*.mdb, *.accdb)"
        case "Linux":
            return r"MDBToolsODBC"
        case _:
            raise NotImplementedError("OS must be either Windows or Linux")


def import_tadm_data(dbpath: str) -> pl.DataFrame:
    # connection object should be closed automatically when it goes out of
    # scope, but you can explicitly call close() also. Using the context
    # manager does something else, see doc.
    conn = pyodbc.connect(f"Driver={get_driver()};DBQ={dbpath};")
    query = "SELECT CurveId,LiquidClassName,StepType,Volume,TimeStamp,StepNumber,ChannelNumber,CurvePoints FROM TadmCurve"

    df = pl.read_database(query, conn)
    df = df.with_columns(pl.col("CurvePoints").map_elements(bin_to_int, return_dtype=pl.Int16).alias("TADM"))

    return df


def import_tolerance_band_data(dbpath: str, lc_names: set[str]) -> pl.DataFrame:
    conn = pyodbc.connect(f"Driver={get_driver()};DBQ={dbpath};")
    query = "SELECT LiquidClassID,LiquidClassName FROM LiquidClass"

    df = pl.read_database(query, conn)
    df = df.filter(pl.col("LiquidClassName").is_in(lc_names))

    query = "SELECT LiquidClassID,StepType,LowerToleranceBand,UpperToleranceBand FROM TadmToleranceBand"
    data = pl.read_database(query, conn)
    data = data.with_columns((
        pl.col("LowerToleranceBand").map_elements(bin_to_int, return_dtype=pl.Int16).alias("LowerToleranceBandTADM"),
        pl.col("UpperToleranceBand").map_elements(bin_to_int, return_dtype=pl.Int16).alias("UpperToleranceBandTADM")
    ))

    data = data.join(df, how="inner", on="LiquidClassID")

    return data


def bin_to_int(byte_string: bytes):
    return pl.Series(np.frombuffer(byte_string, dtype=np.int16))


def merge_tadm_and_tolerance_data(tadm_data: pl.DataFrame, tol_band_data: pl.DataFrame) -> pl.DataFrame:
    return(tadm_data.join(tol_band_data, how="left", on=["LiquidClassName", "StepType"]))
