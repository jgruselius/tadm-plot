import logging
import platform
import subprocess


def get_data_module() -> str:
    if check_odbc():
        logging.info("Using pyodbc for mdb export")
        return "tadm_polars.pyodbc"
    elif check_for_mdbtools():
        logging.info("Using mdbtools for mdb export")
        return "tadm_polars.mdbtools"
    else:
        raise RuntimeError("Neither pyodbc or mdbtools was found")


def check_odbc() -> bool:
    try:
        import pyodbc
        driver = get_driver()
        if driver in pyodbc.drivers():
            return True
        else:
            logging.warning(f"No driver named '{driver}' configured")
    except NotImplementedError as e:
        logging.warning(e)
    except ModuleNotFoundError:
        logging.warning("pyodbc is not available")

    return False


def get_driver() -> str:
    match platform.system():
        case "Windows":
            return r"Microsoft Access Driver (*.mdb, *.accdb)"
        case "Linux" | "Darwin":
            return r"MDBToolsODBC"
        case _:
            raise NotImplementedError("OS must be either Windows, Linux or Mac")


def check_for_mdbtools() -> bool:
    # or get path with shutil.which
    try:
        mdb_version = subprocess.check_output(["mdb-export", "--version"]).decode()
        logging.info(f"Found {mdb_version}")
        return True
    except FileNotFoundError:
        logging.warning("could not find mdb-export on PATH")

    return False
