import numpy as np, struct, zlib
from PIL import Image

def _blocks(a):  # a: HxWx4 uint8 -> (N,16,4) float
    h,w,_=a.shape; H=(h+3)//4*4; W=(w+3)//4*4
    p=np.zeros((H,W,4),np.uint8); p[:h,:w]=a
    if H>h: p[h:,:w]=a[h-1:h]
    if W>w: p[:,w:]=p[:,w-1:w]
    b=p.reshape(H//4,4,W//4,4,4).transpose(0,2,1,3,4).reshape(-1,16,4)
    return b.astype(np.float32)

def _to565(c):
    r=np.clip(np.round(c[...,0]*31/255),0,31).astype(np.uint32)
    g=np.clip(np.round(c[...,1]*63/255),0,63).astype(np.uint32)
    b=np.clip(np.round(c[...,2]*31/255),0,31).astype(np.uint32)
    return (r<<11)|(g<<5)|b
def _from565(v):
    r=(v>>11)&31; g=(v>>5)&63; b=v&31
    return np.stack([(r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)],-1).astype(np.float32)

def encode_level(img):
    a=np.asarray(img.convert('RGBA'))
    B=_blocks(a); N=len(B)
    # alpha
    al=B[:,:,3]; amax=al.max(1); amin=al.min(1)
    a0=np.round(amax).astype(np.int32); a1=np.round(amin).astype(np.int32)
    same=a0==a1
    a1=np.where(same&(a0>0),a0-1,a1); a0=np.where(same&(a0==0),1,a0)
    pal=np.stack([a0,a1]+[((7-i)*a0+i*a1)/7 for i in range(1,7)],1).astype(np.float32)  # N,8
    ai=np.abs(al[:,:,None]-pal[:,None,:]).argmin(2).astype(np.uint64)  # N,16
    abits=np.zeros(N,np.uint64)
    for i in range(16): abits|=ai[:,i]<<np.uint64(3*i)
    # color: PCA endpoints
    c=B[:,:,:3]; mean=c.mean(1,keepdims=True); d=c-mean
    cov=np.einsum('nki,nkj->nij',d,d)
    v=np.ones((N,3),np.float32)
    for _ in range(8):
        v=np.einsum('nij,nj->ni',cov,v); v/=np.linalg.norm(v,axis=1,keepdims=True)+1e-9
    t=np.einsum('nki,ni->nk',d,v)
    e0=mean[:,0]+v*t.max(1,keepdims=True); e1=mean[:,0]+v*t.min(1,keepdims=True)
    q0=_to565(e0); q1=_to565(e1)
    sw=q0<q1; q0,q1=np.where(sw,q1,q0),np.where(sw,q0,q1)
    eq=q0==q1
    c0=_from565(q0); c1=_from565(q1)
    cp=np.stack([c0,c1,(2*c0+c1)/3,(c0+2*c1)/3],1)  # N,4,3
    ci=((c[:,:,None,:]-cp[:,None,:,:])**2).sum(-1).argmin(2).astype(np.uint32)
    ci=np.where(eq[:,None],0,ci)
    cbits=np.zeros(N,np.uint32)
    for i in range(16): cbits|=ci[:,i]<<np.uint32(2*i)
    out=np.zeros((N,16),np.uint8)
    out[:,0]=a0; out[:,1]=a1
    for i in range(6): out[:,2+i]=((abits>>np.uint64(8*i))&np.uint64(255)).astype(np.uint8)
    out[:,8]=q0&255; out[:,9]=q0>>8; out[:,10]=q1&255; out[:,11]=q1>>8
    for i in range(4): out[:,12+i]=(cbits>>np.uint32(8*i))&255
    return out.tobytes()

def downsample(img):
    w,h=img.size; nw,nh=max(1,w//2),max(1,h//2)
    a=np.asarray(img.convert('RGBA')).astype(np.float32)
    pm=a.copy(); pm[...,:3]*=a[...,3:4]/255
    im=Image.fromarray(np.clip(pm,0,255).astype(np.uint8),'RGBA').resize((nw,nh),Image.BOX)
    b=np.asarray(im).astype(np.float32); al=b[...,3:4]
    b[...,:3]=np.where(al>0,b[...,:3]*255/np.maximum(al,1),0)
    return Image.fromarray(np.clip(b,0,255).astype(np.uint8),'RGBA')

def encode_chain(img,total):
    out=b''; cur=img.convert('RGBA')
    while len(out)<total:
        out+=encode_level(cur)
        if cur.size==(1,1): break
        cur=downsample(cur)
    assert len(out)>=total, (len(out),total)
    return out[:total]

def rebuild_tex(orig_path,img,out_path):
    d=open(orig_path,'rb').read(); hdr=d[:0x80]; b=d[0x80:]
    assert b[:4]==b'BILZ'
    raw=zlib.decompress(b[16:])
    w,h=struct.unpack_from('<HH',raw,0); assert img.size==(w,h)
    body=raw[:12]+encode_chain(img,len(raw)-12)
    assert len(body)==len(raw)
    comp=zlib.compress(body,9)
    bilz=b'BILZ'+struct.pack('>III',len(body),len(comp),struct.unpack('>I',b[12:16])[0])+comp
    open(out_path,'wb').write(hdr+bilz)
