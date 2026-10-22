import sys,json,hashlib,os,glob;sys.path.insert(0,'.')
from bc3 import rebuild_tex
from PIL import Image
import struct,zlib
KIT=sys.argv[1]
sha=lambda b: hashlib.sha256(b).hexdigest()
idxp=KIT+'/data/source-index.json'; idx=json.load(open(idxp,encoding='utf-8'))
old={r['path']:r for r in idx.get('textures',[])}
jobs=[]
for f in glob.glob('out2/*.png')+glob.glob('out3/*.png'): 
    fol,n=os.path.basename(f)[:-4].split('__',1); jobs.append((f,f'texA/{fol}/{n}.tex',f'texture/{fol}/{n}.tex'))
for f in glob.glob('out4/*.png'):
    fol,n=os.path.basename(f)[:-4].split('__',1); jobs.append((f,f'texB/{fol}/{n}.tex',f'texture/{fol}/{n}.tex'))
def rebuild_any(src,img,out):
    d=open(src,'rb').read(); b=d[0x80:]; raw=zlib.decompress(b[16:]); w,h=struct.unpack_from('<HH',raw,0)
    L=len(raw)-12
    if L>=w*h*4:  # raw RGBA
        import numpy as np
        a=np.asarray(img.convert('RGBA')).tobytes()
        # mip chain if present
        body=bytearray(raw[:12]); cur=img.convert('RGBA'); data=b''
        from bc3 import downsample
        while len(data)<L:
            data+=cur.tobytes()
            if cur.size==(1,1): break
            cur=downsample(cur)
        body+=data[:L]
        comp=zlib.compress(bytes(body),9)
        open(out,'wb').write(d[:0x80]+b'BILZ'+struct.pack('>III',len(body),len(comp),struct.unpack('>I',b[12:16])[0])+comp)
    else:
        rebuild_tex(src,img,out)
for png,src,rel in jobs:
    out=f'{KIT}/translations/textures/{rel}'; os.makedirs(os.path.dirname(out),exist_ok=True)
    rebuild_any(src,Image.open(png).convert('RGBA'),out)
    old['common/'+rel]=dict(path='common/'+rel,file='translations/textures/'+rel,source_sha256=sha(open(src,'rb').read()),output_sha256=sha(open(out,'rb').read()))
idx['textures']=[old[k] for k in sorted(old)]
open(idxp,'w',encoding='utf-8').write(json.dumps(idx,ensure_ascii=False,indent=1)+'\n')
print(len(jobs),'new;',len(idx['textures']),'total')
