using System;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Collections.Generic;
using System.Security.Cryptography;
using LibOrbisPkg.Util;

namespace ShadowsTools {
    // PFSC layout follows LibOrbisPkg. ReadExactly is required with modern .NET.
    public sealed class PfscReader : IMemoryReader {
        readonly IMemoryReader source;
        readonly int blockSize;
        readonly long length;
        readonly long[] offsets;
        long cachedIndex = -1;
        byte[] cached;
        public PfscReader(IMemoryReader source) {
            this.source = source;
            var h = new byte[48]; source.Read(0, h, 0, h.Length);
            if (Encoding.ASCII.GetString(h, 0, 4) != "PFSC") throw new InvalidDataException("Missing PFSC header");
            blockSize = BitConverter.ToInt32(h, 12);
            if (blockSize != BitConverter.ToInt64(h, 16) || blockSize <= 0) throw new InvalidDataException("Invalid PFSC block size");
            length = BitConverter.ToInt64(h, 40);
            offsets = new long[checked((int)((length + blockSize - 1) / blockSize) + 1)];
            var raw = new byte[offsets.Length * 8];
            source.Read(BitConverter.ToInt64(h, 24), raw, 0, raw.Length);
            Buffer.BlockCopy(raw, 0, offsets, 0, raw.Length);
        }
        public void Read(long position, byte[] buffer, int offset, int count) {
            if (position < 0 || position + count > length) throw new EndOfStreamException();
            while (count > 0) {
                var index = position / blockSize;
                if (index != cachedIndex) {
                    cached = new byte[blockSize];
                    var stored = offsets[index + 1] - offsets[index];
                    if (stored == blockSize) source.Read(offsets[index], cached, 0, blockSize);
                    else if (stored < blockSize) {
                        if (stored <= 0) throw new InvalidDataException("Invalid PFSC block");
                        var compressed = new byte[checked((int)stored)];
                        source.Read(offsets[index], compressed, 0, compressed.Length);
                        using var input = new MemoryStream(compressed);
                        using var z = new ZLibStream(input, CompressionMode.Decompress);
                        z.ReadExactly(cached);
                        if (z.ReadByte() != -1) throw new InvalidDataException("Oversized PFSC block");
                    }
                    cachedIndex = index;
                }
                var inside = (int)(position % blockSize);
                var take = Math.Min(count, blockSize - inside);
                Buffer.BlockCopy(cached, inside, buffer, offset, take);
                count -= take; offset += take; position += take;
            }
        }
        public void Dispose() { }
    }

    public sealed class PsarcEntry {
        public string Path { get; set; }
        public string NameHash { get; set; }
        public int Block { get; set; }
        public long Size { get; set; }
        public long Offset { get; set; }
    }
    public sealed class PsarcReader {
        readonly IMemoryReader source;
        readonly int blockSize;
        readonly int[] blocks;
        public List<PsarcEntry> Entries { get; } = new List<PsarcEntry>();
        static long BE(byte[] b, int offset, int count) {
            long value = 0;
            for (int i = 0; i < count; i++) value = (value << 8) | b[offset+i];
            return value;
        }
        public PsarcReader(IMemoryReader source) {
            this.source = source;
            var h = new byte[32]; source.Read(0, h, 0, 32);
            if (Encoding.ASCII.GetString(h, 0, 4) != "PSAR" || Encoding.ASCII.GetString(h, 8, 4) != "zlib" || BE(h,16,4) != 30)
                throw new InvalidDataException("Unsupported PSARC header");
            var tocSize = checked((int)BE(h,12,4));
            var count = checked((int)BE(h,20,4));
            blockSize = checked((int)BE(h,24,4));
            var toc = new byte[tocSize-32]; source.Read(32, toc, 0, toc.Length);
            for (int i = 0; i < count; i++) {
                int p = i*30;
                Entries.Add(new PsarcEntry { NameHash=Convert.ToHexString(toc.AsSpan(p,16)), Block=checked((int)BE(toc,p+16,4)), Size=BE(toc,p+20,5), Offset=BE(toc,p+25,5) });
            }
            int width=1; while ((1L << (8*width)) < blockSize) width++;
            blocks = new int[(toc.Length-count*30)/width];
            for (int i=0; i<blocks.Length; i++) blocks[i]=checked((int)BE(toc,count*30+i*width,width));
            var manifest = Encoding.UTF8.GetString(Read(Entries[0]));
            var names = manifest.Contains('\0') ? manifest.TrimEnd('\0').Split('\0') : manifest.TrimEnd('\n').Split('\n');
            if (names.Length != count-1) throw new InvalidDataException("PSARC manifest count mismatch");
            var lookup = new Dictionary<string,string>();
            foreach (var rawName in names) {
                var name=rawName.TrimEnd('\r');
                var hashName = (BE(h,28,4) & 1) != 0 ? name.ToUpperInvariant() : name;
                lookup.Add(Convert.ToHexString(MD5.HashData(Encoding.UTF8.GetBytes(hashName))), name);
            }
            Entries.RemoveAt(0);
            foreach (var entry in Entries) entry.Path=lookup[entry.NameHash];
        }
        public byte[] Read(PsarcEntry entry) {
            var result = new byte[checked((int)entry.Size)];
            int completed=0, index=entry.Block; long position=entry.Offset;
            while (completed<result.Length) {
                int expected=Math.Min(blockSize,result.Length-completed);
                int stored=blocks[index++] == 0 ? blockSize : blocks[index-1];
                var raw=new byte[stored]; source.Read(position,raw,0,stored); position+=stored;
                if (stored==expected) Buffer.BlockCopy(raw,0,result,completed,expected);
                else {
                    using var input=new MemoryStream(raw);
                    using var z=new ZLibStream(input,CompressionMode.Decompress);
                    z.ReadExactly(result,completed,expected);
                    if (z.ReadByte()!=-1) throw new InvalidDataException("Oversized PSARC block");
                }
                completed+=expected;
            }
            return result;
        }
    }
}
