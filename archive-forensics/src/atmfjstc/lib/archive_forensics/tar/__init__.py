from enum import IntEnum
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
