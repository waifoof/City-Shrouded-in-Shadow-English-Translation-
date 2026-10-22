import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage as ndi
FD='/usr/share/fonts/opentype/inter/'
def F(size,w): return ImageFont.truetype(FD+f'Inter-{w}.otf',size)
TEXT=(206,203,198,255); SHADOW=(8,12,8)
def green_keep(a,dil=2):
    r,g,b,al=[a[...,i].astype(int) for i in range(4)]
    gm=(g-r>60)&(g>90)&(al>120)
    lab,n=ndi.label(gm,np.ones((3,3)))
    if n:
        sz=ndi.sum(gm,lab,range(1,n+1)); big=np.isin(lab,np.nonzero(sz>=40)[0]+1); gm=big
    return ndi.binary_dilation(gm,np.ones((2*dil+1,2*dil+1)))
def icon_end(a,b):
    x0,y0,x1,y1=b; sub=a[y0:y1,x0:x1].astype(int)
    sat=(sub[...,:3].max(-1)-sub[...,:3].min(-1)>45)&(sub[...,3]>100)
    xs=np.nonzero(sat.any(0))[0]
    return x0+xs.max()+3 if len(xs) and xs.min()<8 else None
def erase(a,box,pad=6,keep=None,lpad=None,clear=False,noprot=False):
    import cv2
    x0,y0,x1,y1=box; x0-=pad if lpad is None else lpad;y0-=pad;x1+=pad;y1+=pad
    H,W=a.shape[:2]; x0=max(0,x0);y0=max(0,y0);x1=min(W,x1);y1=min(H,y1)
    reg=np.zeros((H,W),bool); reg[y0:y1,x0:x1]=True
    if keep is not None: reg&=~keep
    r,g,b,al=[a[...,i].astype(int) for i in range(4)]
    txt=(((r+g+b)/3>90)&(al>60)) | ((np.abs(g-r)<14)&(al>12)&(al<215)&((r+g+b)/3<90))
    body=(al>215)&((r+g+b)/3<40)
    lab,n=ndi.label(body)
    if n:
        sz=ndi.sum(body,lab,range(1,n+1)); body=np.isin(lab,np.nonzero(sz>=3000)[0]+1)
    prot=ndi.binary_dilation(body,np.ones((15,15)))
    if noprot: prot=np.zeros_like(prot)
    txt=ndi.binary_dilation(txt,np.ones((3,3)))&reg&~prot
    if clear:
        a[reg&~prot]=0; return
    if not txt.any(): return
    # crop for speed
    cy0,cy1,cx0,cx1=max(0,y0-12),min(H,y1+12),max(0,x0-12),min(W,x1+12)
    sub=a[cy0:cy1,cx0:cx1].astype(np.float32); m=txt[cy0:cy1,cx0:cx1].astype(np.uint8)
    pm=sub[...,:3]*sub[...,3:4]/255
    pm_i=cv2.inpaint(np.clip(pm,0,255).astype(np.uint8),m,5,cv2.INPAINT_TELEA).astype(np.float32)
    al_i=cv2.inpaint(sub[...,3].astype(np.uint8),m,5,cv2.INPAINT_TELEA).astype(np.float32)
    rgb=np.where(al_i[...,None]>0,pm_i*255/np.maximum(al_i[...,None],1),0)
    out=np.concatenate([np.clip(rgb,0,255),al_i[...,None]],-1).astype(np.uint8)
    mm=m.astype(bool)
    a[cy0:cy1,cx0:cx1][mm]=out[mm]
def sample_color(a,box):
    x0,y0,x1,y1=box; sub=a[y0:y1,x0:x1].reshape(-1,4).astype(int)
    m=(sub[:,3]>200)&(sub[:,:3].mean(1)>110)
    if m.sum()<5: return TEXT
    c=np.median(sub[m][:,:3],0); 
    # brighten toward the top quartile
    br=sub[m][:,:3].mean(1); top=sub[m][br>=np.percentile(br,60)][:,:3].mean(0)
    return tuple(int(v) for v in top)+(255,)
def render(size,items,maxw=None):
    """items: list of (x,y,text,kind,maxw,col,sz)"""
    L=Image.new('RGBA',size,(0,0,0,0)); d=ImageDraw.Draw(L)
    for x,y,t,kind,mw,col,sz in items:
        w='Medium' if kind=='h' else 'SemiBold'
        d.text((x,y),t,font=F(sz,w),fill=col,anchor='ls')
    al=L.split()[3]
    sh=al.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2)).point(lambda v:min(160,int(v*1.2)))
    S=Image.new('RGBA',size,SHADOW+(0,)); S.putalpha(sh); S.alpha_composite(L); return S
def label_size(lines,kind,mw):
    sz,w=(13,'Medium') if kind=='h' else (18,'SemiBold')
    while mw and max(F(sz,w).getlength(t) for t in lines)>mw and sz>10: sz-=1
    return sz
def apply(path,labels,out):
    """labels: list of dict(box=(x0,y0,x1,y1), lines=[...], kind='h'|'b', maxw=None, icon=bool)"""
    im=Image.open(path); a=np.asarray(im).copy()
    keep=green_keep(a)
    items=[]
    for lb in labels:
        b=lb['box']; x0=b[0]
        if lb.get('icon'): x0=b[0]+(lb['icon'] if lb['icon'] is not True and lb['icon']>1 else 15)
        col=lb.get('color') or sample_color(a,(x0,b[1],b[2],b[3]))
        erase(a,(x0,b[1],b[2],b[3]),pad=lb.get('pad',6),keep=keep,clear=lb.get('clear',False),lpad=0 if lb.get('icon') else None)
        pitch=22 if lb['kind']=='b' else 14
        base=b[1]+(11 if lb['kind']=='h' else 15)
        sz=label_size(lb['lines'],lb['kind'],lb.get('maxw'))
        for i,t in enumerate(lb['lines']):
            items.append((x0+ (4 if lb.get('icon') else 0),base+i*pitch,t,lb['kind'],lb.get('maxw'),col,sz))
    res=Image.fromarray(a,'RGBA'); res.alpha_composite(render(res.size,items)); res.save(out); return res
