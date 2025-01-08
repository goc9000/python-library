from enum import Enum, IntEnum
from typing import Union


class TarEntryType(IntEnum):
    REGULAR_FILE_ALT = 0
    HARDLINK_ALT = 1
    SYMLINK_ALT = 2
    REGULAR_FILE = 48
    HARDLINK = 49
    SYMLINK = 50
    CHAR_DEVICE = 51
    BLOCK_DEVICE = 52
    DIRECTORY = 53
    FIFO = 54
    CONTIGUOUS_FILE = 55

    @staticmethod
    def is_regular_file_type(value: Union['TarEntryType', int]) -> bool:
        return value in {TarEntryType.REGULAR_FILE, TarEntryType.REGULAR_FILE_ALT}

    @staticmethod
    def is_symlink_type(value: Union['TarEntryType', int]) -> bool:
        return value in {TarEntryType.SYMLINK, TarEntryType.SYMLINK_ALT}

    @staticmethod
    def is_hardlink_type(value: Union['TarEntryType', int]) -> bool:
        return value in {TarEntryType.HARDLINK, TarEntryType.HARDLINK_ALT}

    @staticmethod
    def is_device_type(value: Union['TarEntryType', int]) -> bool:
        return value in {TarEntryType.CHAR_DEVICE, TarEntryType.BLOCK_DEVICE}


class TarCharset(Enum):
    BINARY = 'BINARY'
    UTF8 = 'ISO-IR 10646 2000 UTF-8'
    ISO_646 = 'ISO-IR 646 1990'
    ISO_8859_1 = 'ISO-IR 8859 1 1998'
    ISO_8859_2 = 'ISO-IR 8859 2 1999'
    ISO_8859_3 = 'ISO-IR 8859 3 1999'
    ISO_8859_4 = 'ISO-IR 8859 4 1998'
    ISO_8859_5 = 'ISO-IR 8859 5 1999'
    ISO_8859_6 = 'ISO-IR 8859 6 1999'
    ISO_8859_7 = 'ISO-IR 8859 7 1987'
    ISO_8859_8 = 'ISO-IR 8859 8 1999'
    ISO_8859_9 = 'ISO-IR 8859 9 1999'
    ISO_8859_10 = 'ISO-IR 8859 10 1998'
    ISO_8859_13 = 'ISO-IR 8859 13 1998'
    ISO_8859_14 = 'ISO-IR 8859 14 1998'
    ISO_8859_15 = 'ISO-IR 8859 15 1999'
    ISO_10646 = 'ISO-IR 10646 2000'
