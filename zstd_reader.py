import asyncio
from io import BufferedReader
import io
import zstandard as zstd

from utilities import Direction

class ZstdFrameReader:
    def __init__(self, reader: asyncio.StreamReader, direction: Direction):
        self.outputbuffer = NonSeekableMemoryStream()
        self.decompressor = zstd.ZstdDecompressor().stream_writer(self.outputbuffer)
        self.raw_reader = reader
        self.direction = direction
        self.zstd_enabled = False
    
    def enable_zstd(self):
        self.zstd_enabled = True

    async def readexactly(self, count):
        # print(f"Reading exactly {count} bytes")

        while True:
            # if there are enough bytes, return them
            if self.outputbuffer.remaining() >= count:
                # print (f"Returning {count} bytes from buffer {self.direction}")
                return self.outputbuffer.read(count)
        
            # print(f"Reading from network since there are only {self.remaining} bytes in buffer")
            await self.read_from_network(count)

    async def read_from_network(self, target_count):
        while self.outputbuffer.remaining() < target_count:

            chunk = await self.raw_reader.read(32768)  # Read in chunks; we'll only get what's available
            # print(f"Read {len(chunk)} bytes from network")
            if not chunk:
                raise asyncio.CancelledError("Connection closed")
            if not self.zstd_enabled:
                self.outputbuffer.write(chunk)
            else:
                try: 
                    self.decompressor.write(chunk)
                except zstd.ZstdError:
                    print("Zstd error, dropping connection")
                    raise asyncio.CancelledError("Error in compressed data stream!")

class NonSeekableMemoryStream(io.RawIOBase):
    def __init__(self):
        self.buffer = bytearray()
        self.read_pos = 0
        self.write_pos = 0

    def write(self, b):
        self.buffer.extend(b)
        self.write_pos += len(b)
        return len(b)

    def read(self, size=-1):
        if size == -1 or size > self.write_pos - self.read_pos:
            size = self.write_pos - self.read_pos
        if size == 0:
            return b''
        data = self.buffer[self.read_pos:self.read_pos + size]
        self.read_pos += size
        if self.read_pos == self.write_pos:
            self.buffer = bytearray()
            self.read_pos = 0
            self.write_pos = 0
        return bytes(data)
    
    def remaining(self):
        return self.write_pos - self.read_pos

    def readable(self):
        return True

    def writable(self):
        return True