import argparse
import os
import pandas as pd
import warnings

import libsbml as sbml
import petab
import yaml


from .yaml2sbml import _parse_yaml_dict, _load_yaml_file
from .yaml_validation import _validate_yaml_from_dict


def yaml2petab(yaml_file: str,
               output_dir: str,
               model_name: str,
               petab_yaml_name: str = None,
               measurement_table_name: str = None):
    """
    Takes in a yaml file with the ODE specification, parses it, converts
    it into SBML format, and writes the SBML file. Further it translates the
    given information into PEtab tables.

    If a petab_yaml_name is given, a .yaml file is created, that organizes
    the petab problem. If additionally a measurement_table_file_name is
    specified, this file name is written into the created .yaml file.

    Arguments:
        yaml_file : path to the yaml file with the ODEs specification
        output_dir: path the output file(s) are be written out
        model_name: name of SBML model
        petab_yaml_name: name of yaml organizing the PEtab problem.
        measurement_table_name: Name of measurement table

    Returns:

    Raises:

    """
    yaml_model_dict = _load_yaml_file(yaml_file)
    _yaml2petab(yaml_model_dict,
                output_dir,
                model_name,
                petab_yaml_name,
                measurement_table_name)


def _yaml2petab(yaml_model_dict: dict,
                output_dir: str,
                model_name: str,
                petab_yaml_name: str = None,
                measurement_table_name: str = None):
    """
    Similar to 'yaml2petab', but takes a yaml_model_dict as input,
    instead of a file path.

    Takes in a yaml model dict with the ODE specification, parses it, converts
    it into SBML format, and writes the SBML file. Further it translates the
    given information into PEtab tables.

    If a petab_yaml_name is given, a .yaml file is created, that organizes
    the petab problem. If additionally a measurement_table_file_name is
    specified, this file name is written into the created .yaml file.

    Arguments:
        yaml_model_dict : dictionary, containing the yaml model
        output_dir: path the output file(s) are be written out
        model_name: name of SBML model
        petab_yaml_name: name of yaml organizing the PEtab problem.
        measurement_table_name: Name of measurement table

    Returns:

    Raises:

    """
    # validate yaml
    _validate_yaml_from_dict(yaml_model_dict)

    # output make directory, if it doesn't exist yet.
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    if model_name.endswith('.xml') or model_name.endswith('.sbml'):
        sbml_dir = os.path.join(output_dir, model_name)
    else:
        sbml_dir = os.path.join(output_dir, model_name + '.xml')

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        sbml_as_string = _parse_yaml_dict(yaml_model_dict)

    with open(sbml_dir, 'w') as f_out:
        f_out.write(sbml_as_string)

    # create petab tsv files:
    _create_petab_tables_from_yaml(yaml_model_dict, output_dir)

    # create yaml file, that organizes the petab problem:
    if (petab_yaml_name is None) and (measurement_table_name is not None):

        warnings.warn('Since no petab_yaml_file_name is specified, the '
                      'specified measurement_table_name will have no effect.',
                      RuntimeWarning)

    elif petab_yaml_name is not None:
        _create_petab_problem_yaml(yaml_model_dict,
                                   output_dir,
                                   sbml_dir,
                                   petab_yaml_name,
                                   measurement_table_name)
    # validate PEtab tables:
    validate_petab_tables(sbml_dir, output_dir)


def _create_petab_tables_from_yaml(yaml_dict: dict,
                                   output_dir: str):
    """
    Parses the yaml dict to a PEtab observable/parameter table.

    Arguments:
        yaml_dict: dict, that contains the yaml file.
        output_dir: directory, where the PEtab tables should be written.

    Raises:

    """
    parameter_table = _create_parameter_table(yaml_dict)
    parameter_table.to_csv(os.path.join(output_dir, 'parameter_table.tsv'),
                           sep='\t',
                           index=False)

    # create PEtab observable table, if observables occur in the yaml file.
    if 'observables' in yaml_dict.keys():
        observable_table = _create_observable_table(yaml_dict)
        observable_table.to_csv(os.path.join(output_dir,
                                             'observable_table.tsv'),
                                sep='\t',
                                index=False)

    # create PEtab condition table, if conditions occur in the yaml file.
    if 'conditions' in yaml_dict.keys():
        condition_table = _create_condition_table(yaml_dict)
        condition_table.to_csv(os.path.join(output_dir, 'condition_table.tsv'),
                               sep='\t',
                               index=False)


def _create_petab_problem_yaml(yaml_dict: dict,
                               output_dir: str,
                               sbml_dir: str,
                               petab_yaml_name: str,
                               measurement_table_name: str = None):
    """
    Creates the yaml file, that can be used for structuring a PEtab problem in
    the corresponding directory.

    Arguments:
        yaml_dict: dict, that contains the yaml file.
        output_dir: directory, where the PEtab tables should be written.
        sbml_dir: directory of the SBML model.
        petab_yaml_name: name of file, where PEtab yaml is written.
        measurement_table_name: directory of the  measurement table.

    Raises:

    """
    petab_yaml_dict = {'format_version': 1,
                       'parameter_file': 'parameter_table.tsv',
                       'problems': [{'sbml_files':
                                         [os.path.basename(sbml_dir)]}]}

    # fill the corresponding entries, if they are contained in the yaml/input.

    if 'observables' in yaml_dict.keys():
        petab_yaml_dict['problems'][0]['observable_files'] = \
            ['observable_table.tsv']

    if 'conditions' in yaml_dict.keys():
        petab_yaml_dict['problems'][0]['condition_files'] = \
            ['condition_table.tsv']

    if measurement_table_name is not None:
        petab_yaml_dict['problems'][0]['measurement_files'] = \
            [measurement_table_name]

    petab_yaml_dir = os.path.join(output_dir, petab_yaml_name)

    with open(petab_yaml_dir, 'w') as file:
        yaml.dump(petab_yaml_dict, file)


def _create_parameter_table(yaml_dict: dict):
    """
    Creates a parameter table from the parameter block in the given yaml_dict.

    Arguments:
        yaml_dict

    Returns:
        parameter_table: pandas data frame containing the parameter table.

    Raises:

    """

    return _create_petab_table(yaml_dict['parameters'],
                               petab.PARAMETER_DF_REQUIRED_COLS,
                               petab.PARAMETER_DF_OPTIONAL_COLS)


def _create_observable_table(yaml_dict: dict):
    """
    Creates an observable table from the observable block
    in the given yaml_dict.

    Arguments:
        yaml_dict

    Returns:
        observable_table: pandas data frame containing the observable table.
            (if observable block is not empty, else None)

    Raises:

    """

    return _create_petab_table(yaml_dict['observables'],
                               petab.OBSERVABLE_DF_REQUIRED_COLS,
                               petab.OBSERVABLE_DF_OPTIONAL_COLS)


def _create_condition_table(yaml_dict: dict):
    """
    Creates a condition table from the observable block in the given yaml_dict.

    Arguments:
        yaml_dict

    Returns:
        condition_table: pandas data frame containing the condition table.
            (if condition block is not empty, else None)

    Raises:

    """
    mandatory_id_list = [petab.CONDITION_ID]

    optional_id_list = [petab.CONDITION_NAME] + \
                       [p['parameterId'] for p in yaml_dict['parameters']] + \
                       [ode['stateId'] for ode in yaml_dict['odes']]

    return _create_petab_table(yaml_dict['conditions'],
                               mandatory_id_list,
                               optional_id_list)


def validate_petab_tables(sbml_dir: str, output_dir: str):
    """
    Validates the petab tables via petab.lint. Throws an error,
    if the petab tables do not follow petab format standard.

    Arguments:
        sbml_dir: directory of the sbml
        output_dir: output directory for petab files

    Returns:

    Raises:
        Errors are raised by lint, if PEtab files are invalid...

    """
    model = sbml.readSBML(sbml_dir).getModel()

    parameter_file_dir = os.path.join(output_dir, 'parameter_table.tsv')
    observable_file_dir = os.path.join(output_dir, 'observable_table.tsv')
    condition_table_dir = os.path.join(output_dir, 'condition_table.tsv')

    # check observable table, if the table exists
    if os.path.exists(observable_file_dir):
        observable_df = pd.read_csv(observable_file_dir,
                                    sep='\t',
                                    index_col='observableId')
        petab.lint.check_observable_df(observable_df)

    else:
        observable_df = None

    # check condition table, if the table exists
    if os.path.exists(condition_table_dir):
        condition_df = pd.read_csv(condition_table_dir,
                                   sep='\t',
                                   index_col='conditionId')
        petab.lint.check_condition_df(condition_df, model)

    # check parameter table
    parameter_df = pd.read_csv(parameter_file_dir,
                               sep='\t',
                               index_col='parameterId')
    petab.lint.check_parameter_df(parameter_df,
                                  sbml_model=model,
                                  observable_df=observable_df)


def _create_petab_table(block_list: list,
                        mandatory_id_list: list,
                        optional_id_list: id):
    """
    Creates a PEtab table from the block_list in the yaml_dict.

    Arguments:
        block_list: entry from yaml_dict.
        mandatory_id_list: list of mandatory ids in the PEtab table
        optional_id_list: list of optional ids in the PEtab table

    Returns:
        petab_table: pandas data frame containing the petab table.

    Raises:

    """

    petab_table = pd.DataFrame({col_id: [] for col_id in mandatory_id_list})

    for row in block_list:
        _petab_table_add_row(petab_table, row)

    # check if every column is part of PEtab standard.
    for col_name in petab_table.head():
        if not (col_name in mandatory_id_list or col_name in optional_id_list):
            warnings.warn(f'PEtab warning: {col_name} is not part of the '
                          f'PEtab standard and hence might have noe effect.')
    return petab_table


def _petab_table_add_row(petab_table: pd.DataFrame, row_dict: dict):
    """
    Adds a row defined by row_dict to the petab_table given by petab_table.
    In the end the last row of petab_table has the entries

        petab_table[-1, key] = row_dict[key]

    for all keys of row_dict.

    Arguments:
        petab_table: pd.DataFrame containing the current petab table.
        row_dict: dict, that contains the values of the new row.

    Returns:

    Raises:

    """
    n_rows = petab_table.shape[0]

    for key in row_dict.keys():
        petab_table.loc[n_rows + 1, key] = row_dict[key]


def main():

    parser = argparse.ArgumentParser(description='Takes in an ODE model in '
                                     '.yaml and converts it to a PEtab file.')

    parser.add_argument('yaml_file', type=str, help='Input yaml directory')
    parser.add_argument('output_dir', type=str, help='Output directory')
    parser.add_argument('model_name', type=str,
                        help='name of created SBML model.')
    parser.add_argument('-y', '--petab_yaml', type=str,
                        help='Optional argument, creates a petab .yml')
    parser.add_argument('-m', '--measurement_table', type=str,
                        help='Optional argument, path to measurement table')

    args = parser.parse_args()

    print(f'Path to yaml file: {args.yaml_file}')
    print(f'Output directory: {args.output_dir}')
    print(f'Path to sbml/petab files: {args.model_name}')

    print('Converting...')

    yaml2petab(args.yaml_file,
               args.output_dir,
               args.model_name,
               args.petab_yaml,
               args.measurement_table)


if __name__ == '__main__':
    main()
