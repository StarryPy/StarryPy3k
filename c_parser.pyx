import struct
from libc.string cimport memcpy

def parse_variant(object stream):
    return c_parse_variant(stream)

def parse_vlq(object stream):
    return c_parse_vlq(stream)

def parse_svlq(object stream):
    return c_parse_svlq(stream)

def parse_dict_variant(object stream):
    return c_parse_dict_variant(stream)

def parse_variant_variant(object stream):
    return c_parse_variant_variant(stream)

def parse_starbytearray(object stream):
    return c_parse_starbytearray(stream)

def parse_starstring(object stream):
    return c_parse_starstring(stream)

cdef c_parse_variant(object stream):
    cdef char x = ord(stream.read(1))

    if x == 1:
        return None
    elif x == 2:
        y = struct.unpack(">d", stream.read(8))[0]
        return y
    elif x == 3:
        c = stream.read(1)
        if c == 1:
            return True
        else:
            return False
    elif x == 4:
        return c_parse_svlq(stream)
    elif x == 5:
        return c_parse_starstring(stream)
    elif x == 6:
        return c_parse_variant_variant(stream)
    elif x == 7:
        return c_parse_dict_variant(stream)

cdef int c_parse_vlq(object stream):
    cdef long long value = 0
    cdef char tmp
    while True:
        try:
            tmp = ord(stream.read(1))
            value = (value << 7) | (tmp & 0x7f)
            if tmp & 0x80 == 0:
                break
        except TypeError:
            break
    return value

cdef int c_parse_svlq(object stream):
    cdef long long v = c_parse_vlq(stream)
    if (v & 1) == 0x00:
        return v >> 1
    else:
        return -((v >> 1) + 1)


cdef c_parse_dict_variant(object stream):
    cdef int i = c_parse_vlq(stream)
    c = {}
    for _ in range(i):
        key = c_parse_starstring(stream)
        value = c_parse_variant(stream)
        c[key] = value
    return c

cdef c_parse_variant_variant(object stream):
    cdef int i = c_parse_vlq(stream)
    return [c_parse_variant(stream) for _ in range(i)]

cdef c_parse_starbytearray(object stream):
    cdef int i = c_parse_vlq(stream)
    s = stream.read(i)
    return s

cdef c_parse_starstring(object stream):
    s = c_parse_starbytearray(stream)
    try:
        return str(s, encoding="utf-8")
    except UnicodeDecodeError:
        return s
