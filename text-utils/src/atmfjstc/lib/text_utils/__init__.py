"""
A collection of utilities for working with plain text.
"""

import re

from typing import Tuple, Any, Iterable, Optional, List, Union

from atmfjstc.lib.py_lang_utils.iteration import iter_with_first


def ucfirst(word: str) -> str:
    """Capitalize the first letter of a word (while leaving the rest alone, unlike ``str.capitalize``)"""
    return '' if len(word) == 0 else (word[0].upper() + word[1:])


def check_nonempty_str(value: str, value_name: str = 'value') -> str:
    """Checks that a string is not empty and returns it, otherwise throws a `ValueError`"""
    if value == '':
        raise ValueError(ucfirst(f"{value_name} must be a non-empty string".lstrip()))

    return value


def check_single_line(value: str, value_name: str = 'value') -> str:
    """Checks that a string does not contain newlines and returns it, otherwise throws a `ValueError`"""
    if '\n' in value:
        raise ValueError(ucfirst(f"{value_name} must be a single-line string".lstrip()))

    return value


def find_line_col(text: str, offset: int) -> Tuple[int, int]:
    """
    Returns the line and column corresponding to an offset in a given text.

    Args:
        text: The text to search.
        offset: The 0-based character offset. The function will essentially look for the position of the character
            at ``text[offset]``. It can also be equal to ``len(text)`` in which case the function will report the
            position of a potential character after the last character in the text.

    Returns:
        A (line, column) tuple corresponding to `offset`. The line and column are 1-based.

    Notes:

    - The offset, line and column all refer to character, not byte, offsets.
    - This only handles input where the lines are separated by a single ``\\n`` character.
    - If ``text[offset]`` is a newline, its reported column will be 1 more than the position of the last character in the
      line. Thus, for a file of 80-column text, the column may be 81.
    - If `offset` is ``len(text)``, the virtual character is placed either:

      - One column to the right of the last character in the last line, if it does not end with a newline
      - On the first column of the next line number, if it does

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


def add_prompt(prompt: str, value: Any) -> str:
    """
    Returns the ``str()`` of a value with a prompt prepended. The prompt will clear all space below it, such that a
    multiline representation of the value will not be disrupted.
    """
    return ''.join(
        (prompt if is_first else ' ' * len(prompt)) + line
        for line, is_first in iter_with_first(str(value).splitlines(True))
    )


def iter_limit_text(
    lines: Iterable[str], max_lines: Optional[int] = 20, max_width: Optional[int] = 120, long_lines: str = 'chop',
    long_line_ellipsis: str = '...({} more chars)', bulk_ellipsis: str = '...({} more lines)...',
    count_all_lines: bool = True,
) -> Iterable[str]:
    """
    Filters a text given as an iterable of lines, so as to limit it to a given number of lines and columns.

    Args:
        lines: An iterable going over the lines of the text to be limited. The lines MUST have had their newline
            characters stripped!
        max_lines: The maximum number of lines allowed. If the text has more lines, only `max_lines-1` lines will be
            returned, followed a special ellipsis line indicating how many more lines would follow (subject to certain
            limitations, see below). Specify a value of None to allow any number of lines.
        max_width: The maximum width (number of columns) allowed. Lines exceeding this will be either wrapped or
            truncated depending on the `long_lines` option.
        long_lines: Specify ``'wrap'`` to wrap long lines, ``'chop'`` to truncate them.
        long_line_ellipsis: When a line is truncated, its end will be replaced by this text, formatted so as to contain
            the number of characters that were omitted. The format specifier can be omitted, e.g. the text can just
            be ``'...'`` if you want.
        bulk_ellipsis: The line that appears at the end of the text, if any lines were omitted. As for
            `long_line_ellipsis`, it can contain a format specifier that will receive the number of lines not displayed.
        count_all_lines: Normally the function will go through all the text so as to get its complete line count.
            Specify False here to cause the function to stop reading as soon as the line limit has been reached. In this
            case the bulk ellipsis will receive the string ``'?'`` for its format specifier, as the number of lines
            hidden is unknown.

    Returns:
        A stream of the lines in the limited text, no more than `max_lines` in height and `max_width` in width. The
        lines will feature no terminating newline.
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


def _chop_line(line: str, max_width: int, ellipsis_format: str) -> str:
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


def limit_text(text: str, *args, **kwargs) -> str:
    """
    Convenience function for using `iter_limit_text` on a text stored as a string instead of lines. See that function
    for details.
    """
    last_nl = '\n' if text.endswith('\n') else ''

    return '\n'.join(iter_limit_text(text.splitlines(False), *args, **kwargs)) + last_nl


def convert_indent(text: str, old_indent: Union[int, str], new_indent: Union[int, str]) -> str:
    """
    Changes the indent of the lines in a text.

    Note: empty lines will be unaffected.

    Args:
        text: The text to be processed.
        old_indent: The indent to remove, given either as a number of columns, or a specific string
        new_indent: The indent to add, given either as a number of columns, or a specific string

    Returns:
        The text with the indent replaced.
    """

    if isinstance(old_indent, int):
        old_indent = ' ' * old_indent
    if isinstance(new_indent, int):
        new_indent = ' ' * new_indent

    def _convert_line(line):
        if line == '' or line == '\n':
            return line

        assert line.startswith(old_indent), "All text should start with the same indent sequence"

        return new_indent + line[len(old_indent):]

    return ''.join(_convert_line(line) for line in text.splitlines(True))


def iter_wrap_items(items: Iterable[str], max_width: Optional[int], separator: str = ' ') -> Iterable[str]:
    """
    Wraps items over multiple lines so as to fit within a given width.

    Args:
        items: An iterable of "items", sort of like words but really they can be any string that must be presented
            unbroken. Items can contain newlines, which will cause them to appear on their own set of lines, breaking
            the flow of the other elements.
        max_width: The maximum width allowed for a line. Use None to disable the limit.
        separator: A string that will be inserted between any two items that appear on the same line.

    Returns:
        A stream of the resulting lines (with no terminating newlines)
    """

    buffer = ''

    for item in items:
        is_multiline = '\n' in item

        # Try to add to current line
        if not is_multiline:
            candidate = buffer + ('' if buffer == '' else separator) + item
            if (max_width is None) or (len(candidate) <= max_width):
                buffer = candidate
                continue

        # Commit line and start new one
        if buffer != '':
            yield buffer

        if is_multiline:
            yield from item.splitlines(False)
            buffer = ''
        else:
            buffer = item

    if buffer != '':
        yield buffer


def split_paragraphs(text: str, keep_separators: bool = False) -> List[str]:
    """
    Roughly splits a text into paragraphs, i.e. areas separated by more than one newline.

    If `keep_separators` is true, the newline sequences that separate the paragraphs will also be returned. They
    will always occur on odd indexes in the returned list.
    """
    pattern = r'\n\s*\n'

    return re.split(f'({pattern})' if keep_separators else pattern, text)
