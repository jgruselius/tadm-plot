import numpy as np
import polars as pl
import subprocess
import tempfile


def import_tadm_data(dbpath: str) -> pl.DataFrame:
    file = tempfile.TemporaryFile()
    proc = subprocess.run(
        ["mdb-export", "-b", "hex", dbpath, "TadmCurve"],
        stderr=subprocess.STDOUT,
        stdout=file,
    )
    file.seek(0)
    df = pl.read_csv(
        file,
        columns=(
            "CurveId",
            "LiquidClassName",
            "StepType",
            "Volume",
            "TimeStamp",
            "StepNumber",
            "ChannelNumber",
            "CurvePoints",
        ),
        schema_overrides={ "Volume": pl.Float32 }
    )
    file.close()

    df = df.with_columns(pl.col("CurvePoints").str.decode("hex")).with_columns(
        pl.col("CurvePoints").map_elements(bin_to_int, return_dtype=pl.List(pl.Int16)).alias("TADM")
    )

    return df


def import_tolerance_band_data(dbpath: str, lc_names: set[str]) -> pl.DataFrame:
    file = tempfile.TemporaryFile()
    proc = subprocess.run(
        ["mdb-export", "-b", "hex", dbpath, "LiquidClass"],
        stderr=subprocess.STDOUT,
        stdout=file,
    )
    file.seek(0)
    df = pl.read_csv(file, columns=("LiquidClassID", "LiquidClassName"))
    file.close()

    df = df.filter(pl.col("LiquidClassName").is_in(lc_names))

    file = tempfile.TemporaryFile()
    proc = subprocess.run(
        ["mdb-export", "-b", "hex", dbpath, "TadmToleranceBand"],
        stderr=subprocess.STDOUT,
        stdout=file,
    )
    file.seek(0)
    data = pl.read_csv(
        file,
        columns=(
            "LiquidClassID",
            "StepType",
            "LowerToleranceBand",
            "UpperToleranceBand",
        ),
    )
    file.close()

    data = data.with_columns(
        pl.col("LowerToleranceBand", "UpperToleranceBand").str.decode("hex")
    ).with_columns(
        pl.col("LowerToleranceBand").map_elements(bin_to_int, return_dtype=pl.List(pl.Int16)).alias("LowerToleranceBandTADM"),
        pl.col("UpperToleranceBand").map_elements(bin_to_int, return_dtype=pl.List(pl.Int16)).alias("UpperToleranceBandTADM"),
    )

    data = data.join(df, how="inner", on="LiquidClassID")

    return data


def bin_to_int(byte_string: bytes):
    return list(np.frombuffer(byte_string, dtype=np.int16))


def merge_tadm_and_tolerance_data(tadm_data: pl.DataFrame, tol_band_data: pl.DataFrame) -> pl.DataFrame:
    return tadm_data.join(tol_band_data, how="left", on=["LiquidClassName", "StepType"])
