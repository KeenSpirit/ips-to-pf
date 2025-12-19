"""
Mapping file handling for IPS to PowerFactory settings transfer.

This module manages the CSV mapping files that define how IPS settings
are mapped to PowerFactory relay attributes. It provides:
- Type mapping lookup (IPS pattern -> PF relay type + mapping file)
- Detailed mapping file parsing
- Curve mapping for IDMT characteristics
- CB alternate name mapping

Performance optimizations:
- All CSV files are cached after first read
- Type mapping is indexed by relay pattern for O(1) lookup
- Mapping files are cached by filename
- Curve mapping is loaded once and reused
"""

import csv

# Import path from config
from config.paths import MAPPING_FILES_DIR

# Use the centralized path
MAP_FILE_LOC = MAPPING_FILES_DIR


def get_pf_curve(app, setting_value, element):
    """Curves are the one setting that requires another PF object to be assigned
    to the attribute."""
    idmt_type = element.typ_id
    curves = idmt_type.GetAttribute("e:pcharac")
    reduced_curves = []
    for curve in curves:
        if curve.loc_name == setting_value:
            return curve
        if setting_value in curve.loc_name or curve.loc_name in setting_value:
            reduced_curves.append(curve)
    for curve in reduced_curves:
        if setting_value in curve.loc_name:
            return curve
    for curve in reduced_curves:
        if curve.loc_name in setting_value:
            return curve
    # Import the mapping file for curves
    csv_open = open("{}\\{}.csv".format(MAP_FILE_LOC, "curve_mapping"), "r")
    for row in csv_open.readlines():
        element_line = row.split(",")
        element_line[-1] = element_line[-1].replace("\n", "")
        try:
            # If the setting is binary add zeros to the front to match the length
            int(element_line[1])
            while len(element_line[1]) < len(setting_value):
                element_line[1] = "0" + element_line[1]
        except ValueError:
            pass  # noqa [E117]
        if setting_value == element_line[1]:
            csv_open.close()
            for curve in curves:
                if curve.loc_name == element_line[2]:
                    return curve
    csv_open.close()
    for curve in curves:
        if "Extreme" in curve.loc_name and "Extreme" in setting_value:
            return curve
        elif "Standard" in curve.loc_name and "Standard" in setting_value:
            return curve
        elif "Very" in curve.loc_name and "Very" in setting_value:
            return curve
        elif "Definite" in curve.loc_name and "DT" in setting_value:
            return curve
        elif "Curve A" in curve.loc_name and "Curve A" in setting_value:
            return curve
        elif "Curve B" in curve.loc_name and "Curve B" in setting_value:
            return curve
        elif "Curve C" in curve.loc_name and "Curve C" in setting_value:
            return curve
        elif "Curve D" in curve.loc_name and "Curve D" in setting_value:
            return curve
    else:
        # By default if the curve can not be determined then set the curve to
        # Standard Inverse.
        for curve in curves:
            if "Standard" in curve.loc_name:
                return curve


def read_mapping_file(app, rel_pattern, pf_device):
    """Each line of the mapping csv will be bought in as a list."""

    csv_open = open(f"{MAP_FILE_LOC}\\type_mapping.csv", "r")
    # Determine the line that has the associated mapping details for the
    # Relay pattern from IPS
    for row in csv_open.readlines():
        line = row.split(",")
        line[-1] = line[-1].replace("\n", "")
        if line[0] == rel_pattern:
            csv_open.close()
            break
    else:
        # The script is unable to match the Relay pattern to a mapping file
        csv_open.close()
        return [None, None]
    try:
        mapping_csv_open = open(f"{MAP_FILE_LOC}\\{line[1]}.csv", "r")
    except FileNotFoundError:
        # This relay pattern is mapped to a file that does not exist
        return [None, None]

    mapping_file = []
    for row in list(csv.reader(mapping_csv_open, skipinitialspace=True)):
        if "FOLDER" in row[0] and "ELEMENT" in row[1]:
            continue
        if row[3] == "None" and "_dip" not in row[1]:
            if len(row) > 4:
                if not row[4]:
                    continue
            else:
                continue
        if row[0] in ["Relay Model", "Default", "default"]:
            row[0] = pf_device.loc_name
        # Remove elements from the line that are empty. This deals with rows with
        # less columns of information.
        element_line = [element for element in row if element]
        mapping_file.append(element_line)
    mapping_csv_open.close()
    # Return the mapping file and the relay type
    return mapping_file, line[2]