import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
def text_mask(a):
    r,g,b,al=[a[...,i].astype(int) for i in range(4)]
    bright=(r+g+b)/3>110
    green=(g-r>40)
    return bright&(al>120)&~green
def boxes(a,region=None,dx=9,dy=2,minh=6):
    m=text_mask(a)
    if region is not None:
        z=np.zeros_like(m); x0,y0,x1,y1=region; z[y0:y1,x0:x1]=m[y0:y1,x0:x1]; m=z
    d=ndi.binary_dilation(m,np.ones((2*dy+1,2*dx+1)))
    lab,n=ndi.label(d)
    out=[]
    for sl in ndi.find_objects(lab):
        ys,xs=sl; sub=m[sl]
        yy,xx=np.nonzero(sub)
        if len(yy)<15: continue
        bx=(xs.start+xx.min(),ys.start+yy.min(),xs.start+xx.max()+1,ys.start+yy.max()+1)
        if bx[3]-bx[1]<minh: continue
        out.append(bx)
    return sorted(out,key=lambda b:(b[1],b[0]))
def annotate(path,bxs,out,crop=None,bg=(30,60,40,255)):
    im=Image.open(path); c=Image.new('RGBA',im.size,bg); c.alpha_composite(im); d=ImageDraw.Draw(c)
    for i,b in enumerate(bxs):
        d.rectangle(b,outline=(255,60,60,255)); d.text((b[2]+2,b[1]-2),str(i),fill=(255,255,0,255))
    if crop: c=c.crop(crop)
    c.convert('RGB').save(out,quality=85)
