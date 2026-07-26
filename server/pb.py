"""
Protobuf encoding/decoding utilities matching the game's custom PbObj format.
Standard protobuf wire format: tag = (field_number << 3) | wire_type
Wire types: 0=varint, 1=fixed64, 2=length-delimited, 5=fixed32
"""
import struct
import io


def encode_varint(value):
    """Encode an unsigned integer as a protobuf varint."""
    if value < 0:
        value += (1 << 64)
    buf = bytearray()
    while value > 0x7F:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    buf.append(value & 0x7F)
    return bytes(buf)


def decode_varint(data, offset):
    """Decode a varint from data at offset. Returns (value, new_offset)."""
    result = 0
    shift = 0
    while True:
        if offset >= len(data):
            raise ValueError("Unexpected end of data while decoding varint")
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return result, offset


def encode_tag(field_number, wire_type):
    """Encode a protobuf field tag."""
    return encode_varint((field_number << 3) | wire_type)


def encode_field_varint(field_number, value):
    """Encode a varint field."""
    if value == 0:
        return b''
    return encode_tag(field_number, 0) + encode_varint(value)


def encode_field_bool(field_number, value):
    """Encode a bool field."""
    if not value:
        return b''
    return encode_tag(field_number, 0) + b'\x01'


def encode_field_string(field_number, value):
    """Encode a string field."""
    if not value:
        return b''
    encoded = value.encode('utf-8')
    return encode_tag(field_number, 2) + encode_varint(len(encoded)) + encoded


def encode_field_bytes(field_number, value):
    """Encode a bytes field."""
    if not value:
        return b''
    return encode_tag(field_number, 2) + encode_varint(len(value)) + value


def encode_field_message(field_number, data):
    """Encode a nested message field."""
    return encode_tag(field_number, 2) + encode_varint(len(data)) + data


def encode_field_packed_varint(field_number, values):
    """Encode a packed repeated varint field."""
    if not values:
        return b''
    packed = b''.join(encode_varint(v) for v in values)
    return encode_tag(field_number, 2) + encode_varint(len(packed)) + packed


class PBReader:
    """Protobuf reader for decoding messages."""
    def __init__(self, data, offset=0, length=None):
        self.data = data
        self.offset = offset
        if length is not None:
            self.end = offset + length
        else:
            self.end = len(data)

    def read_varint(self):
        val, self.offset = decode_varint(self.data, self.offset)
        return val

    def read_tag(self):
        val = self.read_varint()
        return val >> 3, val & 7

    def read_bytes(self):
        length = self.read_varint()
        result = self.data[self.offset:self.offset + length]
        self.offset += length
        return result

    def read_string(self):
        return self.read_bytes().decode('utf-8', errors='replace')

    def read_float(self):
        """Read a 32-bit float (wire type 5)."""
        result = struct.unpack_from('<f', self.data, self.offset)[0]
        self.offset += 4
        return result

    def read_fixed32(self):
        """Read a 32-bit fixed unsigned integer (wire type 5)."""
        result = struct.unpack_from('<I', self.data, self.offset)[0]
        self.offset += 4
        return result

    def read_fixed64(self):
        """Read a 64-bit fixed unsigned integer (wire type 1)."""
        result = struct.unpack_from('<Q', self.data, self.offset)[0]
        self.offset += 8
        return result

    def read_message(self):
        data = self.read_bytes()
        return PBReader(data, 0, len(data))

    def has_more(self):
        return self.offset < self.end

    def skip_field(self, wire_type):
        if wire_type == 0:
            self.read_varint()
        elif wire_type == 1:
            self.offset += 8
        elif wire_type == 2:
            length = self.read_varint()
            self.offset += length
        elif wire_type == 5:
            self.offset += 4
        else:
            raise ValueError(f"Unknown wire type: {wire_type}")


class PBWriter:
    """Protobuf writer for encoding messages."""
    def __init__(self):
        self.buf = io.BytesIO()

    def write_varint(self, value):
        self.buf.write(encode_varint(value))

    def write_tag(self, field_number, wire_type):
        self.buf.write(encode_tag(field_number, wire_type))

    def write_varint_field(self, field_number, value):
        if value != 0:
            self.write_tag(field_number, 0)
            self.write_varint(value)

    def write_bool_field(self, field_number, value):
        if value:
            self.write_tag(field_number, 0)
            self.buf.write(b'\x01')

    def write_string_field(self, field_number, value):
        if value:
            encoded = value.encode('utf-8')
            self.write_tag(field_number, 2)
            self.write_varint(len(encoded))
            self.buf.write(encoded)

    def write_bytes_field(self, field_number, value):
        if value:
            self.write_tag(field_number, 2)
            self.write_varint(len(value))
            self.buf.write(value)

    def write_message_field(self, field_number, data):
        self.write_tag(field_number, 2)
        self.write_varint(len(data))
        self.buf.write(data)

    def write_packed_varint_field(self, field_number, values):
        if values:
            packed = b''.join(encode_varint(v) for v in values)
            self.write_tag(field_number, 2)
            self.write_varint(len(packed))
            self.buf.write(packed)

    def write_float_field(self, field_number, value):
        """Write a float field (wire type 5)."""
        self.write_tag(field_number, 5)
        self.buf.write(struct.pack('<f', value))

    def write_fixed32_field(self, field_number, value):
        """Write a fixed32 field (wire type 5)."""
        self.write_tag(field_number, 5)
        self.buf.write(struct.pack('<I', value))

    def get_bytes(self):
        return self.buf.getvalue()
