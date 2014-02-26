import struct
def parse_variant(bytes pybytes):
    cdef char* _cstring = pybytes
    cdef char** cstring = &_cstring
    return c_parse_variant(cstring)

def parse_vlq(bytes pybytes):
    cdef char* _cstring = pybytes
    cdef char** cstring = &_cstring
    return c_parse_vlq(cstring)

def parse_svlq(bytes pybytes):
    cdef char* _cstring = pybytes
    cdef char** cstring = &_cstring
    return c_parse_variant(cstring)

def parse_dict_variant(bytes pybytes):
    cdef char* _cstring = pybytes
    cdef char** cstring = &_cstring
    return c_parse_dict_variant(cstring)

def parse_variant_variant(bytes pybytes):
    cdef char* _cstring = pybytes
    cdef char** cstring = &_cstring
    return c_parse_variant_variant(cstring)

def parse_starstring(bytes pybytes):
    cdef char* _cstring = pybytes
    cdef char** cstring = &_cstring
    return c_parse_starstring(cstring)

cdef c_parse_variant(char ** stream):
    cdef char x = stream[0][0]
    cdef char c = stream[0][1]
    stream[0]+=1

    if x == 1:
        return None
    elif x == 2:
        y = struct.unpack(">d", stream[0][:8])
        stream[0] += 8
        return y
    elif x == 3:
        stream[0] += 1
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

cdef int c_parse_vlq(char ** stream):
    cdef long long value = 0
    cdef char tmp
    while True:
        tmp = stream[0][0]
        value = (value << 7) | (tmp & 0x7f)
        if tmp & 0x80 == 0:
            break
        stream[0] = stream[0]+1
    stream[0] = stream[0]+1
    return value

cdef int c_parse_svlq(char ** stream):
    cdef long long v = c_parse_vlq(stream)
    if (v & 1) == 0x00:
        return v >> 1
    else:
        return -((v >> 1) + 1)


cdef c_parse_dict_variant(char ** stream):
    cdef int l = c_parse_vlq(stream)
    c = {}
    for _ in range(l):
        key = c_parse_starstring(stream)
        value = c_parse_variant(stream)
        c[key] = value
    return c

cdef c_parse_variant_variant(char ** stream):
    cdef int l = c_parse_vlq(stream)
    return [c_parse_variant(stream) for _ in range(l)]

cdef c_parse_starstring(char ** stream):
    cdef int l = c_parse_vlq(stream)
    cdef char* s
    py_string = stream[0][:l]
    stream[0]+= l
    return py_string