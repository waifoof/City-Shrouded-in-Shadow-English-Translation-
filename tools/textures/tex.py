import zlib,struct,io
from PIL import Image
def load(path):
    d=open(path,'rb').read(); b=d[0x80:]
    raw=zlib.decompress(b[16:]) if b[:4]==b'BILZ' else b
    return raw
def dds(w,h,data,fourcc=None,dxgi=None):
    hdr=bytearray(128); hdr[0:4]=b'DDS '
    struct.pack_into('<7I',hdr,4,124,0x1007|0x80000,h,w,len(data),0,1)
    struct.pack_into('<2I',hdr,76,32,4)
    hdr[84:88]= b'DX10' if dxgi else fourcc
    struct.pack_into('<I',hdr,108,0x1000)
    ext=struct.pack('<5I',dxgi,3,0,1,0) if dxgi else b''
    return Image.open(io.BytesIO(bytes(hdr)+ext+data))

def decode(path):
    r=load(path); w,h=struct.unpack_from('<HH',r,0)
    n=((w+3)//4)*((h+3)//4)*16
    im=dds(w,h,r[12:12+n],fourcc=b'DXT5'); im.load(); return im.convert('RGBA')

def decode_any(path):
    r=load(path); w,h=struct.unpack_from('<HH',r,0); L=len(r)-12; d=r[12:]
    bw,bh=(w+3)//4,(h+3)//4
    if L>=w*h*4:
        a=__import__('numpy').frombuffer(d[:w*h*4],'uint8').reshape(h,w,4)
        return Image.fromarray(a.copy(),'RGBA'),'rgba'
    if L>=bw*bh*16:
        im=dds(w,h,d[:bw*bh*16],fourcc=b'DXT5'); im.load(); return im.convert('RGBA'),'bc3'
    im=dds(w,h,d[:bw*bh*8],fourcc=b'DXT1'); im.load(); return im.convert('RGBA'),'bc1'
