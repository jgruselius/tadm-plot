import numpy as np
import pandas as pd
import platform
import pyodbc
import warnings


def get_driver() -> str:
    match platform.system():
        case "Windows":
            return r"Microsoft Access Driver (*.mdb, *.accdb)"
        case "Linux":
            return r"MDBToolsODBC"
        case _:
            raise NotImplementedError("OS must be either Windows or Linux")


def import_tadm_data(dbpath: str) -> pd.DataFrame:
    # connection object should be closed automatically when it goes out of
    # scope, but you can explicitly call close() also. Using the context
    # manager does something else, see doc.
    conn = pyodbc.connect(f"Driver={get_driver()};DBQ={dbpath};")
    query = "SELECT CurveId,LiquidClassName,StepType,Volume,TimeStamp,StepNumber,ChannelNumber,CurvePoints FROM TadmCurve"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        df = pd.read_sql(query, conn)
    df["TADM"] = df["CurvePoints"].apply(lambda x: np.frombuffer(x, np.int16))

    return df


def import_tolerance_band_data(dbpath: str, lc_names: set[str]) -> pd.DataFrame:
    conn = pyodbc.connect(f"Driver={get_driver()};DBQ={dbpath};")
    query = "SELECT LiquidClassID,LiquidClassName FROM LiquidClass"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        df = pd.read_sql(query, conn)

    df = df[df["LiquidClassName"].isin(lc_names)]
    query = "SELECT LiquidClassID,StepType,LowerToleranceBand,UpperToleranceBand FROM TadmToleranceBand"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        data = pd.read_sql(query, conn)

    data["LowerToleranceBandTADM"] = data["LowerToleranceBand"].apply(
        lambda x: np.frombuffer(x, np.int16)
    )
    data["UpperToleranceBandTADM"] = data["UpperToleranceBand"].apply(
        lambda x: np.frombuffer(x, np.int16)
    )

    data = pd.merge(df, data, how="inner", on="LiquidClassID")

    return data


def merge_tadm_and_tolerance_data(tadm_data: pd.DataFrame, tol_band_data: pd.DataFrame) -> pd.DataFrame:
    return pd.merge(tadm_data, tol_band_data, how="left", on=["LiquidClassName", "StepType"])
