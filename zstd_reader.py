import asyncio
from io import BufferedReader, BytesIO
import zstandard as zstd

class ZstdFrameReader:
    def __init__(self, reader: asyncio.StreamReader):
        self.decompressor = zstd.ZstdDecompressor()
        self.inputbuffer = bytearray()
        self.outputbuffer = BytesIO()
        self.remaining = 0
        self.raw_reader = reader

    async def readexactly(self, count):
        # print(f"Reading exactly {count} bytes")

        while True:
            # if there are enough bytes, return them
            if self.remaining >= count:
                # print (f"Returning {count} bytes from buffer")
                self.remaining -= count;
                return self.outputbuffer.read1(count)
        
            # print(f"Reading from network since there are only {self.remaining} bytes in buffer")
            await self.read_from_network()

    async def read_from_network(self):
        while True:
            chunk = await self.raw_reader.read(1024)  # Read in chunks of 1024 bytes
            # print(f"Read {len(chunk)} bytes from network")
            if not chunk:
                raise asyncio.CancelledError("Connection closed")
            self.inputbuffer.extend(chunk)
            
            decompressor = self.decompressor.decompressobj() # single use decompressor
            try:
                decompressed_data = decompressor.decompress(self.inputbuffer)
                if decompressed_data:
                    # write to the output buffer
                    self.outputbuffer = BytesIO(decompressed_data)# assume that previous reads emptied the buffer (no packets split across zstd frames)
                    self.remaining = len(decompressed_data)
                    # Save leftover bytes
                    self.inputbuffer = bytearray(decompressor.unused_data)
                    # print("Decompressed frame of size", len(decompressed_data))
                    return
            except zstd.ZstdError:
                continue  # Continue reading if the frame is not complete
