__all__ = ['Filter', 'TestRun',
           'FilterKeywordError', 'TestFailedError', 'BadFilterError', 'AcceptedError', 'SubprocessError',
           '_extract_numbers', '_parse_args', '_filter_file']

# ------------------------------------------------------------------------------


def _is_float(x):
    return isinstance(x, float)

# ------------------------------------------------------------------------------


def _is_int(n):
    return isinstance(n, int)

# ------------------------------------------------------------------------------


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

# ------------------------------------------------------------------------------


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

# ------------------------------------------------------------------------------


def _tuple_matches(f, tup):
    """Checks if tuple matches based on filter f.

    Args:
        f: filter
        tup: tuple

    Returns:
        (tuple matches, error message) - error message is None if there is no error
    """

    x, x_ref = tup

    if f.ignore_sign:
        # if ignore sign take absolute values
        x = abs(x)
        x_ref = abs(x_ref)

    if _is_int(x) and _is_int(x_ref):
        if x == x_ref:
            return (True, None)
        else:
            return (False, "expected: %s" % x_ref)

    if abs(x_ref) < f.ignore_below:
        return (True, None)

    if abs(x_ref) > f.ignore_above:
        return (True, None)

    error = x - x_ref
    if f.tolerance_is_relative:
        error /= x_ref
        if abs(error) <= f.tolerance:
            return (True, None)
        else:
            if f.ignore_sign:
                return (False, "expected: %s (rel diff: %6.2e ignoring signs)" % (x_ref, abs(1.0 - abs(x) / abs(x_ref))))
            else:
                return (False, "expected: %s (rel diff: %6.2e)" % (x_ref, abs(1.0 - x / x_ref)))
    else:
        if abs(error) <= f.tolerance:
            return (True, None)
        else:
            if f.ignore_sign:
                return (False, "expected: %s (abs diff: %6.2e ignoring signs)" % (x_ref, abs(abs(x) - abs(x_ref))))
            else:
                return (False, "expected: %s (abs diff: %6.2e)" % (x_ref, abs(x - x_ref)))

# ------------------------------------------------------------------------------


class FilterKeywordError(Exception):
    pass


class TestFailedError(Exception):
    pass


class BadFilterError(Exception):
    pass


class AcceptedError(Exception):
    pass


class SubprocessError(Exception):
    pass

# ------------------------------------------------------------------------------


def _extract_numbers(f, text):
    """
    Input:
        - f -- filter task
        - text -- list of lines where we extract numbers from

    Returns:
        - numbers -- list of numbers
        - locations -- locations of each number, list of triples
                      (line, start position, length)
    """
    import re

    numeric_const_pattern = r"""
    [-+]? # optional sign
    (?:
        (?: \d* \. \d+ ) # .1 .12 .123 etc 9.1 etc 98.1 etc
        |
        (?: \d+ \.? ) # 1. 12. 123. etc 1 12 123 etc
    )
    # followed by optional exponent part if desired
    (?: [EeDd] [+-]? \d+ ) ?
    """

    pattern_int = re.compile('^-?[0-9]+$', re.VERBOSE)
    pattern_float = re.compile(numeric_const_pattern, re.VERBOSE)
    pattern_d = re.compile(r'[dD]')

    numbers = []
    locations = []

    for n, line in enumerate(text):
        i = 0
        for w in line.split():
            # do not consider words like TzB1g
            # otherwise we would extract 1 later
            if re.match(r'^[0-9\.eEdD\+\-]*$', w):
                i += 1
                if (f.use_mask) and (i not in f.mask):
                    continue
                is_integer = False
                if len(pattern_float.findall(w)) > 0:
                    is_integer = (pattern_float.findall(w) == pattern_int.findall(w))
                # apply floating point regex
                for m in pattern_float.findall(w):
                    index = line.index(m)
                    # substitute dD by e
                    m = pattern_d.sub('e', m)
                    if is_integer:
                        numbers.append(int(m))
                    else:
                        numbers.append(float(m))
                    locations.append((n, index, len(m)))

    return numbers, locations

# ------------------------------------------------------------------------------


def _parse_args(input_dir, argv):
    from optparse import OptionParser
    from runtest import __version__

    parser = OptionParser(description='runtest %s - Numerically tolerant test library.' % __version__)
    parser.add_option('--binary-dir',
                      '-b',
                      action='store',
                      default=input_dir,
                      help='directory containing the binary/launcher [default: %default]')
    parser.add_option('--work-dir',
                      '-w',
                      action='store',
                      default=input_dir,
                      help='working directory [default: %default]')
    parser.add_option('--verbose',
                      '-v',
                      action='store_true',
                      default=False,
                      help='give more verbose output upon test failure [default: %default]')
    parser.add_option('--skip-run',
                      '-s',
                      action='store_true',
                      default=False,
                      help='skip actual calculation(s) [default: %default]')
    parser.add_option('--debug',
                      '-d',
                      action='store_true',
                      default=False,
                      help='print verbose debug information [default: %default]')
    parser.add_option('--log',
                      '-l',
                      action='store',
                      default=None,
                      help='log file [default: no logging]')
    (options, args) = parser.parse_args(args=argv[1:])

    return options

# ------------------------------------------------------------------------------


def _copy_path(root_src_dir, root_dst_dir, exclude_files=[]):
    from shutil import copy
    import os
    for src_dir, dirs, files in os.walk(root_src_dir):
        dst_dir = src_dir.replace(root_src_dir, root_dst_dir)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        for f in files:
            if f not in exclude_files:
                src_file = os.path.join(src_dir, f)
                dst_file = os.path.join(dst_dir, f)
                copy(src_file, dst_file)

# ------------------------------------------------------------------------------


def _filter_file(f, file_name, output):
    """
    Input:
        - f -- filter task
        - file_name -- the output file to filter

    Returns:
        - output_filtered -- the filtered output

    Raises:
        - BadFilterError
    """
    import re

    output_filtered = []

    for i in range(len(output)):
        start_line_matches = False
        if f.from_is_re:
            start_line_matches = re.match(r'.*%s' % f.from_string, output[i])
        else:
            start_line_matches = (f.from_string in output[i])
        if start_line_matches:
            if f.num_lines > 0:
                for n in range(i, i + f.num_lines):
                    output_filtered.append(output[n])
            else:
                for j in range(i, len(output)):
                    f.end_line_matches = False
                    if f.to_is_re:
                        f.end_line_matches = re.match(r'.*%s' % f.to_string, output[j])
                    else:
                        f.end_line_matches = (f.to_string in output[j])
                    if f.end_line_matches:
                        for n in range(i, j + 1):
                            output_filtered.append(output[n])
                        break

    if output_filtered == []:
        if f.num_lines > 0:
            r = '[%i lines from "%s"]' % (f.num_lines, f.from_string)
        else:
            r = '["%s" ... "%s"]' % (f.from_string, f.to_string)
        message = 'ERROR: filter %s did not extract anything from file %s\n' % (r, file_name)
        raise BadFilterError(message)

    return output_filtered

# ------------------------------------------------------------------------------


def _check(filter_list, out_name, ref_name, verbose=False):
    """
    Compares output (work_dir/out_name) with reference (work_dir/ref_name)
    applying all filters tasks from the list of filters.

    Input:
        - work_dir -- working directory
        - out_name -- actual output file name
        - ref_name -- reference output file name
        - verbose  -- give verbose output upon failure

    Returns:
        - nothing

    Generates the following files in work_dir:
        - out_name.filtered  -- numbers extracted from output
        - out_name.reference -- numbers extracted from reference
        - out_name.diff      -- difference between the two above

    Raises:
        - TestFailedError
    """
    import os

    log_out = open('%s.filtered' % out_name, 'w')
    log_ref = open('%s.reference' % out_name, 'w')
    log_diff = open('%s.diff' % out_name, 'w')

    for f in filter_list:

        out_filtered = _filter_file(f, out_name, open(out_name).readlines())
        log_out.write(''.join(out_filtered))
        out_numbers, out_locations = _extract_numbers(f, out_filtered)
        if f.use_mask and out_numbers == []:
            raise FilterKeywordError('ERROR: mask %s did not extract any numbers\n' % f.mask)

        ref_filtered = _filter_file(f, ref_name, open(ref_name).readlines())
        log_ref.write(''.join(ref_filtered))
        ref_numbers, ref_locations = _extract_numbers(f, ref_filtered)
        if f.use_mask and ref_numbers == []:
            raise FilterKeywordError('ERROR: mask %s did not extract any numbers\n' % f.mask)

        if out_numbers == [] and ref_numbers == []:
            # no numbers are extracted
            if out_filtered != ref_filtered:
                log_diff.write('ERROR: extracted strings do not match\n')
                log_diff.write('own gave:\n')
                log_diff.write(''.join(out_filtered) + '\n')
                log_diff.write('reference gave:\n')
                log_diff.write(''.join(ref_filtered) + '\n')

        # we need to check for len(out_numbers) > 0
        # for pure strings len(out_numbers) is 0
        # TODO need to consider what to do with pure strings in future versions
        if len(out_numbers) == len(ref_numbers) and len(out_numbers) > 0:
            if not f.tolerance_is_set and (any(map(_is_float, out_numbers)) or any(map(_is_float, ref_numbers))):
                raise FilterKeywordError('ERROR: for floats you have to specify either rel_tolerance or abs_tolerance\n')
            l = map(lambda t: _tuple_matches(f, t), zip(out_numbers, ref_numbers))
            matching, errors = zip(*l)  # unzip tuples to two lists
            if not all(matching):
                log_diff.write('\n')
                for k, line in enumerate(out_filtered):
                    log_diff.write('.       %s' % line)
                    for i, num in enumerate(out_numbers):
                        (line_num, start_char, length) = out_locations[i]
                        if line_num == k:
                            if errors[i]:
                                log_diff.write('ERROR   %s%s %s\n' % (' ' * start_char, '#' * length, errors[i]))

        if len(out_numbers) != len(ref_numbers):
            log_diff.write('ERROR: extracted sizes do not match\n')
            log_diff.write('own gave %i numbers:\n' % len(out_numbers))
            log_diff.write(''.join(out_filtered) + '\n')
            log_diff.write('reference gave %i numbers:\n' % len(ref_numbers))
            log_diff.write(''.join(ref_filtered) + '\n')

    log_out.close()
    log_ref.close()
    log_diff.close()

    if os.path.getsize('%s.diff' % out_name) > 0:
        log_diff = open('%s.diff' % out_name, 'r')
        diff = ''
        for line in log_diff.readlines():
            diff += line
        log_diff.close()
        message = "ERROR: test %s failed\n" % out_name
        if verbose:
            message += diff
        raise TestFailedError(message)

# ------------------------------------------------------------------------------


class TestRun:

    def __init__(self, _file, argv):
        import os

        self.input_dir = input_dir = os.path.dirname(os.path.realpath(_file))

        options = _parse_args(input_dir, argv)
        self.binary_dir = options.binary_dir
        self.work_dir = options.work_dir
        self.verbose = options.verbose
        self.skip_run = options.skip_run
        self.debug = options.debug
        self.log = options.log

        if self.work_dir != self.input_dir:
            _copy_path(self.input_dir, self.work_dir)

        os.chdir(self.work_dir)  # FIXME possibly problematic

    def execute(self,
                command,
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

        if self.skip_run:
            return

        if sys.platform != "win32":
            command = shlex.split(command)

        if self.debug:
            print('\nlaunching command: %s' % ' '.join(command))

        process = subprocess.Popen(command,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if self.debug:
            print('\nstdout:\n%s' % stdout)
            if stderr != '':
                print('\nstderr:\n%s' % stderr)

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


class _SingleFilter:

    def __init__(self, **kwargs):
        import sys

        error = _check_for_unknown_kw(kwargs)
        if error:
            raise FilterKeywordError(error)

        error = _check_for_incompatible_kw(kwargs)
        if error:
            raise FilterKeywordError(error)

        # now continue with keywords
        self.from_string = kwargs.get('from_string', '')
        self.to_string = kwargs.get('to_string', '')
        self.ignore_sign = kwargs.get('ignore_sign', False)
        self.ignore_below = kwargs.get('ignore_below', sys.float_info.min)
        self.ignore_above = kwargs.get('ignore_above', sys.float_info.max)
        self.num_lines = kwargs.get('num_lines', 0)

        if 'rel_tolerance' in kwargs.keys():
            self.tolerance = kwargs.get('rel_tolerance')
            self.tolerance_is_relative = True
            self.tolerance_is_set = True
        elif 'abs_tolerance' in kwargs.keys():
            self.tolerance = kwargs.get('abs_tolerance')
            self.tolerance_is_relative = False
            self.tolerance_is_set = True
        else:
            self.tolerance_is_set = False

        self.mask = kwargs.get('mask', [])
        if self.mask == []:
            self.use_mask = False
        else:
            self.use_mask = True
            for i in self.mask:
                if i < 1:
                    raise FilterKeywordError('ERROR: mask starts counting from 1 (first word)\n')

        self.from_is_re = False
        from_re = kwargs.get('from_re', '')
        if from_re != '':
            self.from_string = from_re
            self.from_is_re = True

        self.to_is_re = False
        to_re = kwargs.get('to_re', '')
        if to_re != '':
            self.to_string = to_re
            self.to_is_re = True

        only_string = kwargs.get('string', '')
        if only_string != '':
            self.from_string = only_string
            self.num_lines = 1

        only_re = kwargs.get('re', '')
        if only_re != '':
            self.from_string = only_re
            self.num_lines = 1
            self.from_is_re = True


class Filter:

    def __init__(self):
        self.filter_list = []

    def add(self, *args, **kwargs):
        """
        Adds filter task to list of filters.

        Raises:
            - FilterKeywordError
        """
        self.filter_list.append(_SingleFilter(*args, **kwargs))

    # FIXME work_dir is not used
    def check(self, work_dir, out_name, ref_name, verbose=False):
        _check(self.filter_list, out_name, ref_name, verbose)