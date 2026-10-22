import sys;sys.path.insert(0,'.')
import numpy as np
from PIL import Image
from gen import draw_text, fit, sample
P='pngA/'
geo=np.asarray(Image.open(P+'menu_item__mm01_tab01r.png')).astype(int)
rows={}
for y in range(60):
    xs=np.nonzero(geo[y,:,3]>200)[0]
    if len(xs)>100: rows[y]=(xs.min(),xs.max())
ys=sorted(rows); y0,y1=ys[0]+4,ys[-1]-4
def tab(src,dst,text,sel):
    a=np.asarray(Image.open(src)).copy()
    for y in range(y0,y1+1):
        xl,xr=rows[y]; xl+=6; xr-=6
        if sel: a[y,xl:xr]=(43,179,129,255)
        else: a[y,xl:xr]=0
    im=Image.fromarray(a,'RGBA')
    col=(14,40,30,255) if sel else (45,182,130,255)
    sz=fit(text,140,21)
    im.alpha_composite(draw_text(im.size,[dict(xy=(108,(y0+y1)/2+1),text=text,size=sz,color=col,style='none' if sel else 'shadow',sa=0.8)]))
    im.save(dst)
sort={'01':'Most Used','02':'By Category','03':'By Date'}
for fol in ['menu_item','hud']:
    for k,t in sort.items():
        for s in ['','r']:
            n=f'{fol}__mm01_tab{k}{s}'; tab(P+n+'.png','out3/'+n+'.png',t,s=='r')
print(y0,y1)
