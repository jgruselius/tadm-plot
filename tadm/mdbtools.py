import subprocess
import pandas as pd
import numpy as np
import tempfile


def import_tadm_data(dbpath: str) -> pd.DataFrame:
    file = tempfile.TemporaryFile()
    proc = subprocess.run(
        ["mdb-export", "-b", "hex", dbpath, "TadmCurve"],
        stderr=subprocess.STDOUT,
        stdout=file
    )
    file.seek(0)
    df = pd.read_csv(file,
        usecols=("CurveId", "LiquidClassName", "StepType", "Volume",
            "TimeStamp", "StepNumber", "ChannelNumber", "CurvePoints"),
        converters={"CurvePoints": bytes.fromhex})
    file.close()

    df["TADM"] = df["CurvePoints"].apply(lambda x: np.frombuffer(x, np.int16))

    return df


def import_tolerance_band_data(dbpath: str, lc_names: set[str]) -> pd.DataFrame:
    file = tempfile.TemporaryFile()
    proc = subprocess.run(
        ["mdb-export", "-b", "hex", dbpath, "LiquidClass"],
        stderr=subprocess.STDOUT,
        stdout=file
    )
    file.seek(0)
    df = pd.read_csv(file, usecols=("LiquidClassID", "LiquidClassName"))
    file.close()

    df = df[df["LiquidClassName"].isin(lc_names)]

    file = tempfile.TemporaryFile()
    proc = subprocess.run(
        ["mdb-export", "-b", "hex", dbpath, "TadmToleranceBand"],
        stderr=subprocess.STDOUT,
        stdout=file
    )
    file.seek(0)
    data = pd.read_csv(file,
        usecols=("LiquidClassID", "StepType", "LowerToleranceBand", "UpperToleranceBand"),
        converters={"LowerToleranceBand": bytes.fromhex, "UpperToleranceBand": bytes.fromhex}
    )
    file.close()

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
