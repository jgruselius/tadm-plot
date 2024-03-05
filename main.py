import sys
import os
import logging
import argparse
from pathlib import Path

from concurrent.futures import ProcessPoolExecutor, as_completed

from rich.logging import RichHandler
from InquirerPy import inquirer
from rich.progress import Progress, TextColumn, BarColumn, MofNCompleteColumn, TimeRemainingColumn

from tadm import import_tadm_data, get_liquid_class_names, import_tolerance_band_data, \
    merge_tadm_and_tolerance_data, get_data_for_liquid_class, plot_both_steps, check_driver

# Extract data from TADM database (.mdb) and plot curves together with tolerance bands
# Created by: Joel Gruselius <github.com/jgruselius>, 2023-11
#
# TODO:
#  [ ] Handle steps without data
#  [x] Progress display for '-all'
#  [x] Detect when ODBC driver is not installed and print guide
#  [x] Add option for the liquid class database to use


# Print instructions for installing ODBC driver:
def driver_help():
    logging.error("Could not find a required ODBC driver to read MS Access databases.\n"
                  "Install the [italic]Microsoft Access Database Engine 2010 Redistributable[/italic] from here:\n"
                  "https://www.microsoft.com/en-US/download/details.aspx?id=13255")


def get_path(file_name: str) -> str:
    script_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
    return os.path.join(script_dir, file_name)


def create_progress_bar() -> Progress:
    return Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("ETA:"),
        TimeRemainingColumn(),
        transient=False
    )


def interactive_plot(df, lc_names: list[str], args: argparse.Namespace):
    while True:
        lc = inquirer.fuzzy(
            message="Select liquid:", choices=lc_names,
            instruction="Type or use the up/down arrow keys",
            long_instruction="Type a few letters of the liquid class name and press ENTER to select the highlighted value").execute()
        step_data = get_data_for_liquid_class(df, lc)
        plot_both_steps(step_data)
        if not inquirer.confirm("Do you want to generate another plot?").execute():
            break


def export_all(df, lc_names: list[str], args: argparse.Namespace):
    progress_bar = create_progress_bar()
    with progress_bar:
        for lc in progress_bar.track(lc_names, description="Generating plots..."):
            logging.debug(f"Getting data for {lc}")
            step_data = get_data_for_liquid_class(df, lc)
            file_path = gen_plot_name(args.infile, lc, args.outdir)
            create_out_dir(file_path.parent)
            plot_both_steps(step_data, file_path, True)


def export_all_parallel(df, lc_names: list[str], args: argparse.Namespace):
    progress_bar = create_progress_bar()
    with progress_bar:
        task = progress_bar.add_task("Generating plots...", total=len(lc_names))
        with ProcessPoolExecutor() as ex:
            handles = []
            for lc in lc_names:
                logging.debug(f"Getting data for {lc}")
                step_data = get_data_for_liquid_class(df, lc)
                file_path = gen_plot_name(args.infile, lc, args.outdir)
                create_out_dir(file_path.parent)
                handles.append(ex.submit(plot_both_steps, step_data, file_path, True))
            for h in as_completed(handles):
                progress_bar.advance(task)


def main(args: argparse.Namespace):
    if args.outdir:
        create_out_dir(args.outdir)
    df = import_tadm_data(args.infile)
    lc_names = get_liquid_class_names(df)
    tol = import_tolerance_band_data(args.lcdb, lc_names)
    df = merge_tadm_and_tolerance_data(df, tol)
    if args.all:
        export_all(df, lc_names, args)
    elif args.par:
        export_all_parallel(df, lc_names, args)
    elif args.interactive:
        interactive_plot(df, lc_names, args)
    elif args.liquid:
        assert (any(args.liquid in x for x in lc_names))
        # NOT IMPLEMENTED


def gen_plot_name(source_name: str, liquid_class: str, dir_path: Path) -> Path:
    p = dir_path / Path(source_name).stem / liquid_class
    logging.debug(f"Generated plot name: '{p}'")
    return p.with_suffix(".png")


def create_out_dir(path: Path) -> Path:
    if not path.exists():
        path.mkdir(parents=False)
        logging.debug(f"Created directory '{path}'")
    return path


def file_exists(path: str) -> Path:
    p = Path(path).absolute()
    if not p.exists():
        raise argparse.ArgumentTypeError(f"Path does not exist: {path}")
    if not p.is_file():
        raise argparse.ArgumentTypeError(f"Path is not a file: {path}")
    return p


def dir_exists(path: str):
    p = Path(path).absolute()
    parent = p.parent
    if not (parent.exists() and parent.is_dir()):
        raise argparse.ArgumentTypeError(f"Directory does not exist: {parent}")
    return p


if __name__ == '__main__':
    print("")

    ap = argparse.ArgumentParser(description="Plot TADM data from a .mdb file.",
                                 epilog="Created by Joel Gruselius (github.com/jgruselius)")
    ap.add_argument("infile", help="The TADM file to parse",
                    type=file_exists)

    lc_opt = ap.add_mutually_exclusive_group()
    lc_opt.add_argument("-l", "--liquid", metavar="X", help="The liquid class name to plot")
    lc_opt.add_argument("-i", "--interactive", action="store_true",
                        help="Select the available liquid classes from a menu")
    lc_opt.add_argument("-a", "--all", action="store_true", help="Save plots of all liquid classes")
    lc_opt.add_argument("-P", "--par", action="store_true", help="Save all plots using multiprocessing")

    save_opt = ap.add_mutually_exclusive_group()
    save_opt.add_argument("-p", "--plot", type=dir_exists,
                          help="Save the plot (png) to this file (full path, will overwrite)")
    save_opt.add_argument("-o", "--outdir", metavar="DIR", type=dir_exists,
                          help="Save the plots (png) to this directory (full path, will overwrite)")

    ap.add_argument("-n", "--noshow", action="store_true",
                    help="Don't show the plot window")
    ap.add_argument("-v", "--verbose", action="store_true", required=False,
                    help="Print more details about what's going on")
    ap.add_argument("-L", "--lcdb", metavar="DB", type=file_exists, default=get_path("ML_STARLiquids.mdb"),
                          help="Use some other liquid class definition database")

    args = ap.parse_args()

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=loglevel, style="{", format="{message}",
                        handlers=[RichHandler(show_time=False, markup=True, show_path=False)])
    # At DEBUG level matplotlib spews out a lot of lines related to fonts. We want to ignore that:
    logging.getLogger("matplotlib").setLevel(logging.INFO)

    if not check_driver():
        driver_help()
        sys.exit(1)

    if (args.all or args.par) and args.outdir is None:
        logging.error("Options '--all' and '--par' requires option '--outdir' to be specified")
        sys.exit(1)

    if args.noshow and args.plot is None and args.outdir is None:
        logging.warning("Plot window disabled AND no output path given (-p):\n"
                        "Plotting for nothing!")

    main(args)
