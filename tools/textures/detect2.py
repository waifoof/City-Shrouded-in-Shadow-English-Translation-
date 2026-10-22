import numpy as np
from PIL import Image
from scipy import ndimage as ndi
def boxes2(a,dx=8,dy=3,lum=90,alpha=120,minpix=15):
    r,g,b,al=[a[...,i].astype(int) for i in range(4)]
    m=((r+g+b)/3>lum)&(al>alpha)
    d=ndi.binary_dilation(m,np.ones((2*dy+1,2*dx+1)))
    lab,n=ndi.label(d); out=[]
    for sl in ndi.find_objects(lab):
        sub=m[sl]; yy,xx=np.nonzero(sub)
        if len(yy)<minpix: continue
        out.append((int(sl[1].start+xx.min()),int(sl[0].start+yy.min()),int(sl[1].start+xx.max()+1),int(sl[0].start+yy.max()+1)))
    return sorted(out,key=lambda b:(b[1],b[0]))
