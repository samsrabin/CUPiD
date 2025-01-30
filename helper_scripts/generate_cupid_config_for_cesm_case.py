#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys

import yaml


def _parse_args():
    """Parse command line arguments"""

    parser = argparse.ArgumentParser(
        description="Generate config.yml based on an existing CUPID example",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Command line argument for location of CESM source code (required)
    parser.add_argument(
        "--cesm-root",
        action="store",
        dest="cesm_root",
        required=True,
        help="Location of CESM source code",
    )

    # Command line argument for CUPiD example from which to get config.yml
    parser.add_argument(
        "--cupid-example",
        action="store",
        dest="cupid_example",
        default="key_metrics",
        help="CUPiD example to use as template for config.yml",
    )

    # Command line argument location of CESM case directory
    parser.add_argument(
        "--case-root",
        action="store",
        dest="case_root",
        default=os.getcwd(),
        help="CESM case directory",
    )

    return parser.parse_args()


def generate_cupid_config(case_root, cesm_root, cupid_example, cupid_baseline_case=None, cupid_baseline_root=None, cupid_start_year=None, cupid_end_year=None, cupid_base_start_year=None, cupid_base_end_year=None):
    """
    Generate a CUPiD `config.yml` file based on information from a CESM case and
    a specific CUPiD example configuration (such as 'key metrics').

    This function takes the root directory of the CESM case and the CESM installation,
    along with the name of a CUPiD example. It validates the example, loads information
    from the CESM case (such as the case name and output directory), modifies the
    configuration based on the case-specific data, and generates a new `config.yml` file
    in the current working directory.

    The generated `config.yml` file contains:
    - Global parameters such as case name, start and end dates.
    - Time series information for atmospheric end years.
    - Base output directory paths for CESM results.

    Arguments:
    ----------
    case_root : str
        The root directory of the CESM case from which case-specific data will be retrieved.

    cesm_root : str
        The root directory of the CESM installation, where CIME scripts and CUPiD examples reside.

    cupid_example : str
        The name of a CUPiD example (e.g., 'key metrics') to base the configuration file on.
        Must be a valid subdirectory within the CUPiD examples directory.

    Raises:
    -------
    KeyError:
        If the provided CUPiD example is not found in the valid CUPiD examples directory.

    Outputs:
    --------
    config.yml : file
        A YAML file containing the generated configuration based on the provided CESM case
        and CUPiD example.
    """

    sys.path.append(os.path.join(cesm_root, "cime"))
    from CIME.case import Case

    # Is cupid_example a valid value?
    cupid_root = os.path.join(cesm_root, "tools", "CUPiD")
    cupid_examples = os.path.join(cupid_root, "examples")
    valid_examples = [
        example
        for example in next(os.walk(cupid_examples))[1]
        if example not in ["ilamb"]
    ]
    if cupid_example not in valid_examples:
        error_msg = f"argument --cupid-example: invalid choice '{cupid_example}'"
        raise KeyError(
            f"{error_msg} (choose from subdirectories of {cupid_examples}: {valid_examples})",
        )

    with Case(case_root, read_only=False, record=True) as cesm_case:
        case = cesm_case.get_value("CASE")
        dout_s_root = cesm_case.get_value("DOUT_S_ROOT")

    # Additional options we need to get from env_cupid.xml
    if cupid_baseline_case:
        base_case = cupid_baseline_case
    else:
        base_case = "b.e23_alpha17f.BLT1850.ne30_t232.092"
    if cupid_baseline_root:
        base_case_output_dir = cupid_baseline_root
    else:
        base_case_output_dir = "/glade/campaign/cesm/development/cross-wg/diagnostic_framework/CESM_output_for_testing"
    if cupid_start_year:
        start_date = cupid_start_year
    else:
        start_date = "0001-01-01"
    if cupid_end_year:
        end_date = cupid_end_year
    else:
        end_date = f"{nyears+1:04d}-01-01"
    if cupid_base_start_year:
        base_case_start_date = cupid_base_start_year
    else:
        continue # default for this one?
    if cupid_base_end_year:
        base_end_date = cupid_base_end_year
    else:
        base_end_date = f"{base_nyears+1:04d}-01-01"

    # TODO: these should also perhaps be added as environment vars?
    nyears = 1    
    climo_nyears = nyears
    base_nyears = 100
    base_climo_nyears = 40

    # --------------------------------------------------------------------------------
    with open(os.path.join(cupid_root, "examples", cupid_example, "config.yml")) as f:
        my_dict = yaml.safe_load(f)

    my_dict["data_sources"]["nb_path_root"] = os.path.join(
        cesm_root,
        "tools",
        "CUPiD",
        "nblibrary",
    )
    my_dict["global_params"]["case_name"] = case
    my_dict["global_params"]["start_date"] = start_date
    my_dict["global_params"]["end_date"] = end_date
    my_dict["global_params"]["base_case_name"] = base_case
    my_dict["global_params"]["base_case_output_dir"] = base_case_output_dir
    my_dict["global_params"]["base_end_date"] = base_end_date
    my_dict["timeseries"]["case_name"] = [case, base_case]

    for component in my_dict["timeseries"]:
        if (
            isinstance(my_dict["timeseries"][component], dict)
            and "end_years" in my_dict["timeseries"][component]
        ):
            my_dict["timeseries"][component]["end_years"] = [nyears, base_nyears]
    if "link_to_ADF" in my_dict["compute_notebooks"]["atm"]:
        my_dict["compute_notebooks"]["atm"]["link_to_ADF"]["parameter_groups"]["none"][
            "adf_root"
        ] = os.path.join(case_root, "ADF_output")
    if "Greenland_SMB_visual_compare_obs" in my_dict["compute_notebooks"]["glc"]:
        my_dict["compute_notebooks"]["glc"]["Greenland_SMB_visual_compare_obs"][
            "parameter_groups"
        ]["none"]["climo_nyears"] = climo_nyears
        my_dict["compute_notebooks"]["glc"]["Greenland_SMB_visual_compare_obs"][
            "parameter_groups"
        ]["none"]["base_climo_nyears"] = base_climo_nyears

    # replace with environment variable
    my_dict["global_params"]["CESM_output_dir"] = os.path.dirname(dout_s_root)

    # create new file, make it writeable
    with open("config.yml", "w") as f:
        # Header of file is a comment logging provenance
        f.write(f"# This file has been auto-generated for use with {case}\n")
        f.write(f"# It is based off of examples/{cupid_example}/config.yml\n")
        f.write("# Arguments used:\n")
        f.write(f"# cesm_root = {cesm_root}\n")
        f.write(f"# case_root = {case_root}\n")
        f.write(f"# cupid_example= {cupid_example}\n")

        # enter in each element of the dictionary into the new file
        yaml.dump(my_dict, f, sort_keys=False)


if __name__ == "__main__":
    args = vars(_parse_args())
    generate_cupid_config(**args)
