"""
A collection of utilities for working with plain text.
"""

from atmfjstc.lib.py_lang_utils.iteration import iter_with_first


def find_line_col(text, offset):
    """
    Returns the line and column corresponding to an offset in a given text (i.e. the position of the character at
    ``text[offset]``).

    Notes:
    - The reported line and column are 1-based. The offset is 0-based.
    - The offset, line and column all refer to character, not byte, offsets.
    - If text[offset] is a newline, its reported column will be 1 more than the position of the last character in the
      line. Thus, for a file of 80-column text, the column may be 81.
    - Offset can be between 0 and the length of the text. An offset of len(text) refers to a potential character after
      the last character in the text, and can thus occur either one column to the right of it, or on the next line
      number, if the last character was a newline.
    - This only handles input where the lines are separated by a single \n character.
    - The function is not particularly optimized for working with huge data and cannot use a prebuilt line index, etc.
      It is meant for one-off analyses such as when building an exception text for a syntax error in a config file.
    """
    if (offset < 0) or (offset > len(text)):
        raise IndexError(f"Offset {offset} lies outside text of length {len(text)}")

    cur_line_no = 1
    cur_line_start = 0

    while cur_line_start < len(text):
        cur_line_end = text.find('\n', cur_line_start)
        if cur_line_end == -1:
            cur_line_end = len(text) - 1

        if offset <= cur_line_end:
            break

        cur_line_no += 1
        cur_line_start = cur_line_end + 1

    return cur_line_no, 1 + offset - cur_line_start


def add_prompt(prompt, value):
    """
    Returns the ``str()`` of a value with a prompt prepended. The prompt will clear all space below it, such that a
    multiline representation of the value will not be disrupted.
    """
    return '\n'.join(
        (prompt if is_first else ' ' * len(prompt)) + line
        for line, is_first in iter_with_first(str(value).splitlines(True))
    )


def iter_limit_text(
    lines, max_lines=20, max_width=120, long_lines='chop',
    long_line_ellipsis='...({} more chars)', bulk_ellipsis='...({} more lines)...', count_all_lines=True,
):
    """
    Filters a text given as an iterable of lines, so as to limit it to a given number of lines and columns.

    :param lines: An iterable going over the lines of the text to be limited. The lines MUST have had their newline
                  characters stripped!
    :param max_lines: The maximum number of lines allowed. If the text has more lines, only max_lines-1 lines will be
                      returned, followed a special ellipsis line indicating how many more lines would follow (subject
                      to certain limitations, see below). Specify max_lines=None to allow any number of lines.
    :param max_width: The maximum width (number of columns) allowed. Lines exceeding this will be either wrapped or
                      truncated depending on the ``long_lines=`` option. A truncated line will also end in a special
                      ellipsis text indicating how many characters were not displayed.
    :param long_lines: Specify 'chop' to truncate long lines, 'wrap' to wrap them.
    :param long_line_ellipsis: The text that will be appear at the end of an elided line. It should contain a format
                               specifier that will receive the number of characters not displayed (it can be absent if
                               you want the ellipsis to always look the same).
    :param bulk_ellipsis: The line that will appear at the end of an elided text. As for the long line ellipsis, it
                          can contain a format specifier that will receive the number of lines not displayed.
    :param count_all_lines: Normally the function will go through all the text so as to get its complete line count.
                            Specify False here to cause the function to stop reading as soon as the line limit has
                            been reached. In this case the bulk ellipsis will receive the string '?' for its format
                            specifier, as the number of lines hidden is unknown.
    :return: The function returns a stream of each line in the filtered text (without ending newlines)
    """
    assert (max_lines is None) or (max_lines > 0), "max_lines must be >= 1"
    assert (long_lines in ['chop', 'wrap']), "long_lines= must be either 'chop' or 'wrap'"

    def _wrap_lines():
        for line in lines:
            for base in range(0, len(line), max_width):
                yield line[base:base+max_width]

    def _chop_lines():
        for line in lines:
            yield _chop_line(line, max_width, long_line_ellipsis)

    intermediate_lines = lines
    if max_width is not None:
        if long_lines == 'chop':
            intermediate_lines = _chop_lines()
        elif long_lines == 'wrap':
            intermediate_lines = _wrap_lines()

    if max_lines is None:
        yield from intermediate_lines
        return

    n_lines_total = 0
    buffered_last_line = None

    for line in intermediate_lines:
        if n_lines_total < max_lines:
            if buffered_last_line is not None:
                yield buffered_last_line

            buffered_last_line = line

        n_lines_total += 1
        if not count_all_lines and (n_lines_total > max_lines):
            break

    if n_lines_total > max_lines:
        n_hidden_lines = (1 + n_lines_total - max_lines) if count_all_lines else '?'

        if n_hidden_lines != 1:
            yield bulk_ellipsis.format(n_hidden_lines)
            buffered_last_line = None  # Suppress last line

    if buffered_last_line is not None:
        yield buffered_last_line


def _chop_line(line, max_width, ellipsis_format):
    line_len = len(line)
    if line_len <= max_width:
        return line

    # We need to choose how many characters to display from the line, such that, together with the ellipsis formatted
    # with the remaining number of chars, the whole line fits into the max_width.
    #
    # In equation speak, given:
    # x = number of chars we display from the string, 0 <= x < line_len
    # f(y) = length of ellipsis showing "'y' remaining characters"
    #
    # we need to find the max x such that x + f(line_len - x) <= max_width
    #
    # We solve this by noting that f(y) only has a very limited possible set of values. All values of y with the same
    # number of digits will resolve to the same length (assuming a decimal format, which we do). Thus, if we assume that
    # y has 'd' digits, then:
    #
    #     10^(d-1) <= y <=  10^d - 1
    # <-> 10^(d-1) <= line_len - x <= 10^d - 1
    # <-> line_len - 10^d + 1 <= x <= line_len - 10^(d-1)    [1]
    #
    # Since the number of digits is fixed, f(line_len - x) = f(y_min) for all x, a constant. Then the main equation
    # becomes:
    #
    # x + f(y_min) <= max_width  <->  x <= max_width - f(y_min)   [2]
    #
    # Combining [1] and [2] with the initial constraint, 0 <= x < line_len  [3], we get a (possibly empty) range of
    # allowable values fox x, of which we choose the largest.
    #
    # We repeat the process for all possible values of 'd', knowing that it is bound by y_min <= line_len.

    y_min = 1
    y_max = 9
    x_candidates = []

    while y_min <= line_len:
        x_min = max(line_len - y_max, 0)
        x_max = min(line_len - y_min, max_width - len(ellipsis_format.format(y_min)), line_len - 1)

        if x_min <= x_max:
            x_candidates.append(x_max)

        y_min *= 10
        y_max = y_max * 10 + 9

    if len(x_candidates) == 0:
        return ellipsis_format.format(line_len)

    best_x = max(x_candidates)

    return line[:best_x] + ellipsis_format.format(line_len - best_x)


def limit_text(text, *args, **kwargs):
    """
    Convenience function for using ``iter_limit_text`` on a text stored as a string instead of lines. See that
    function for details.
    """
    last_nl = '\n' if text.endswith('\n') else ''

    return '\n'.join(iter_limit_text(text.splitlines(False), *args, **kwargs)) + last_nl


def convert_indent(text, old_indent, new_indent):
    def convert_line(line):
        if line == '' or line == '\n':
            return line

        assert line.startswith(old_indent), "All text should start with the same indent sequence"

        return new_indent + line[len(old_indent):]

    return ''.join(convert_line(line) for line in text.splitlines(True))
