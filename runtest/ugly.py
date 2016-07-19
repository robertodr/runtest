from .exceptions import FilterKeywordError, SubprocessError


def execute(command,
            stdout_file_name='',
            accepted_errors=[]):
    """
    Runs the command.

    Raises:
        - AcceptedError
        - SubprocessError
    """
    import shlex
    import subprocess
    import sys

    if sys.platform != "win32":
        command = shlex.split(command)

    process = subprocess.Popen(command,
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    for error in accepted_errors:
        if error in stderr:
            # we found an error that we expect/accept
            raise AcceptedError('found error which is expected/accepted: %s\n' % error)
    if process.returncode != 0:
        raise SubprocessError('ERROR: crash during %s\n%s' % (command, stderr))
    if stdout_file_name != '':
        f = open(stdout_file_name, 'w')
        f.write(stdout)
        f.close()


def _check_for_unknown_kw(kwargs):
    """Checks whether there are any unknown keywords.

    Args:
        kwargs: keyword arguments

    Returns:
        Error message. None if all keywords are known.
    """
    recognized_kw = ['from_re',
                     'to_re',
                     're',
                     'from_string',
                     'to_string',
                     'string',
                     'ignore_below',
                     'ignore_above',
                     'ignore_sign',
                     'mask',
                     'num_lines',
                     'rel_tolerance',
                     'abs_tolerance']

    unrecoginzed_kw = [kw for kw in kwargs.keys() if kw not in recognized_kw]
    if unrecoginzed_kw == []:
        return None
    else:
        return 'ERROR: keyword(s) ({unrecognized}) not recognized\n       available keywords: ({available})\n'.format(unrecognized=(', ').join(sorted(unrecoginzed_kw)),
                                                                                                                      available=(', ').join(recognized_kw))


def _check_for_incompatible_kw(kwargs):
    """Checks whether there are any incompatible keyword pairs.

    Args:
        kwargs: keyword arguments

    Returns:
        Error message. Empty if all keywords are compatible.
    """
    incompatible_pairs = [('from_re', 'from_string'),
                          ('to_re', 'to_string'),
                          ('to_string', 'num_lines'),
                          ('to_re', 'num_lines'),
                          ('string', 'from_string'),
                          ('string', 'to_string'),
                          ('string', 'from_re'),
                          ('string', 'to_re'),
                          ('string', 'num_lines'),
                          ('re', 'from_string'),
                          ('re', 'to_string'),
                          ('re', 'from_re'),
                          ('re', 'to_re'),
                          ('re', 'num_lines'),
                          ('rel_tolerance', 'abs_tolerance')]

    incompatible_kw = [(kw1, kw2) for (kw1, kw2) in incompatible_pairs if kw1 in kwargs.keys() and kw2 in kwargs.keys()]
    if incompatible_kw == []:
        return None
    else:
        return 'ERROR: incompatible keyword pairs: {0}\n'.format(incompatible_kw)


def copy_and_chdir(work_dir):

    import os
    from .copy import copy_path
    import inspect

    frame = inspect.stack()[-1]
    module = inspect.getmodule(frame[0])
    caller_file = module.__file__
    caller_dir = os.path.dirname(os.path.realpath(caller_file))

    if work_dir != caller_dir:
        copy_path(caller_dir, work_dir)

    os.chdir(work_dir)  # FIXME possibly problematic


def get_filter(**kwargs):
    import sys
    from collections import namedtuple

    foo = namedtuple('foo',
                     ['from_is_re',
                      'from_string',
                      'ignore_above',
                      'ignore_below',
                      'ignore_sign',
                      'mask',
                      'num_lines',
                      'to_is_re',
                      'to_string',
                      'tolerance',
                      'tolerance_is_relative',
                      'tolerance_is_set'])

    error = _check_for_unknown_kw(kwargs)
    if error:
        raise FilterKeywordError(error)

    error = _check_for_incompatible_kw(kwargs)
    if error:
        raise FilterKeywordError(error)

    # now continue with keywords
    foo.from_string = kwargs.get('from_string', '')
    foo.to_string = kwargs.get('to_string', '')
    foo.ignore_sign = kwargs.get('ignore_sign', False)
    foo.ignore_below = kwargs.get('ignore_below', sys.float_info.min)
    foo.ignore_above = kwargs.get('ignore_above', sys.float_info.max)
    foo.num_lines = kwargs.get('num_lines', 0)

    if 'rel_tolerance' in kwargs.keys():
        foo.tolerance = kwargs.get('rel_tolerance')
        foo.tolerance_is_relative = True
        foo.tolerance_is_set = True
    elif 'abs_tolerance' in kwargs.keys():
        foo.tolerance = kwargs.get('abs_tolerance')
        foo.tolerance_is_relative = False
        foo.tolerance_is_set = True
    else:
        foo.tolerance_is_set = False

    foo.mask = kwargs.get('mask', None)

    foo.from_is_re = False
    from_re = kwargs.get('from_re', '')
    if from_re != '':
        foo.from_string = from_re
        foo.from_is_re = True

    foo.to_is_re = False
    to_re = kwargs.get('to_re', '')
    if to_re != '':
        foo.to_string = to_re
        foo.to_is_re = True

    only_string = kwargs.get('string', '')
    if only_string != '':
        foo.from_string = only_string
        foo.num_lines = 1

    only_re = kwargs.get('re', '')
    if only_re != '':
        foo.from_string = only_re
        foo.num_lines = 1
        foo.from_is_re = True

    return foo