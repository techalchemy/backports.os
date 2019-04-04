"""
Partial backport of new functionality in Python 3.5's os module:

    fsencode (new in Python 3.2)
    fsdecode (new in Python 3.2)

Backport modifications are marked with "XXX backport" and "TODO backport".
"""
from __future__ import unicode_literals

import sys

# XXX backport: unicode on Python 2
_str = unicode if sys.version_info < (3,) else str
string_types = basestring if sys.version_info[0] == 2 else str

# XXX backport: Use backported surrogateescape for Python 2
# TODO backport: Find a way to do this without pulling in the entire future package?
if sys.version_info < (3,):
    from future.utils.surrogateescape import register_surrogateescape
    register_surrogateescape()
    _fs_encode_errors = "backslashreplace"
    _fs_decode_errors = "replace"
    _fs_encoding = "utf-8"
else:
    _fs_encoding = "utf-8"
    if sys.platform.startswith("win"):
        _fs_error_fn = None
        alt_strategy = "surrogatepass"
    else:
        if sys.version_info >= (3, 3):
            _fs_encoding = next(iter(enc for enc in [
                sys.getfilesystemencoding(), sys.getdefaultencoding()
            ]), _fs_encoding)
        alt_strategy = "surrogateescape"
        _fs_error_fn = getattr(sys, "getfilesystemencodeerrors", None)
    _fs_encode_errors = _fs_error_fn() if _fs_error_fn else alt_strategy
    _fs_decode_errors = _fs_error_fn() if _fs_error_fn else alt_strategy


# XXX backport: This invalid_utf8_indexes() helper is shamelessly copied from
# Bob Ippolito's pyutf8 package (pyutf8/ref.py), in order to help support the
# Python 2 UTF-8 decoding hack in fsdecode() below.
#
# URL: https://github.com/etrepum/pyutf8/blob/master/pyutf8/ref.py
#
def _invalid_utf8_indexes(bytes):
    skips = []
    i = 0
    len_bytes = len(bytes)
    while i < len_bytes:
        c1 = bytes[i]
        if c1 < 0x80:
            # U+0000 - U+007F - 7 bits
            i += 1
            continue
        try:
            c2 = bytes[i + 1]
            if ((c1 & 0xE0 == 0xC0) and (c2 & 0xC0 == 0x80)):
                # U+0080 - U+07FF - 11 bits
                c = (((c1 & 0x1F) << 6) |
                     (c2 & 0x3F))
                if c < 0x80:  # pragma: no cover
                    # Overlong encoding
                    skips.extend([i, i + 1])  # pragma: no cover
                i += 2
                continue
            c3 = bytes[i + 2]
            if ((c1 & 0xF0 == 0xE0) and
                (c2 & 0xC0 == 0x80) and
                (c3 & 0xC0 == 0x80)):
                # U+0800 - U+FFFF - 16 bits
                c = (((((c1 & 0x0F) << 6) |
                       (c2 & 0x3F)) << 6) |
                     (c3 & 0x3f))
                if ((c < 0x800) or (0xD800 <= c <= 0xDFFF)):
                    # Overlong encoding or surrogate.
                    skips.extend([i, i + 1, i + 2])
                i += 3
                continue
            c4 = bytes[i + 3]
            if ((c1 & 0xF8 == 0xF0) and
                (c2 & 0xC0 == 0x80) and
                (c3 & 0xC0 == 0x80) and
                (c4 & 0xC0 == 0x80)):
                # U+10000 - U+10FFFF - 21 bits
                c = (((((((c1 & 0x0F) << 6) |
                         (c2 & 0x3F)) << 6) |
                       (c3 & 0x3F)) << 6) |
                     (c4 & 0x3F))
                if (c < 0x10000) or (c > 0x10FFFF):  # pragma: no cover
                    # Overlong encoding or invalid code point.
                    skips.extend([i, i + 1, i + 2, i + 3])
                i += 4
                continue
        except IndexError:
            pass
        skips.append(i)
        i += 1
    return skips


# XXX backport: Another helper to support the Python 2 UTF-8 decoding hack.
def _chunks(b, indexes):
    i = 0
    for j in indexes:
        yield b[i:j]
        yield b[j:j + 1]
        i = j + 1
    yield b[i:]


def _get_path(path):
    """
    Fetch the string value from a path-like object

    Returns **None** if there is no string value.
    """

    if isinstance(path, (string_types, bytes)):
        return path
    path_type = type(path)
    try:
        path_repr = path_type.__fspath__(path)
    except AttributeError:
        return
    if isinstance(path_repr, (string_types, bytes)):
        return path_repr
    return


def fsencode(path):
    """
    Encode a filesystem path to the proper filesystem encoding

    :param Union[str, bytes] path: A string-like path
    :returns: A bytes-encoded filesystem path representation
    """

    path = _get_path(path)
    if path is None:
        raise TypeError("expected a valid path to encode")
    if isinstance(path, _str):
        path = path.encode(_fs_encoding, _fs_encode_errors)
    return path


def fsdecode(path):
    """
    Decode a filesystem path using the proper filesystem encoding

    :param path: The filesystem path to decode from bytes or string
    :return: An appropriately decoded path
    :rtype: str
    """

    path = _get_path(path)
    if path is None:
        raise TypeError("expected a valid path to decode")
    binary_type = str if sys.version_info[0] == 2 else bytes
    if isinstance(path, binary_type):
        path = path.decode(_fs_encoding, _fs_decode_errors)
    return path
