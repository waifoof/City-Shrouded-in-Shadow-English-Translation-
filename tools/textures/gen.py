import sys;sys.path.insert(0,'.')
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from relabel import erase, green_keep
FD='/usr/share/fonts/opentype/inter/'
def F(sz,w='SemiBold'): return ImageFont.truetype(FD+f'Inter-{w}.otf',sz)
def sample(a,box,dark=False):
    x0,y0,x1,y1=box; s=a[y0:y1,x0:x1].reshape(-1,4).astype(int)
    s=s[s[:,3]>200]
    if not len(s): return (255,255,255,255)
    lum=s[:,:3].mean(1)
    sel=s[lum<=np.percentile(lum,15)] if dark else s[lum>=np.percentile(lum,85)]
    return tuple(int(v) for v in sel[:,:3].mean(0))+(255,)
def draw_text(size,items):
    """items: dict(xy,text,size,weight,anchor,color,style,spacing)"""
    out=Image.new('RGBA',size,(0,0,0,0))
    for it in items:
        L=Image.new('L',size,0); d=ImageDraw.Draw(L)
        f=F(it['size'],it.get('weight','SemiBold'))
        d.multiline_text(it['xy'],it['text'],font=f,fill=255,anchor=it.get('anchor','mm'),align='center',spacing=it.get('spacing',4))
        col=it['color']; st=it.get('style','shadow')
        if st in('shadow','both'):
            sh=L.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(it.get('blur',2.0))).point(lambda v:min(255,int(v*it.get('sa',1.3))))
            g=Image.new('RGBA',size,(0,0,0,0)); g.putalpha(sh); out.alpha_composite(g)
        if st in('glow','both'):
            gl=L.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(it.get('gblur',6))).point(lambda v:min(255,int(v*0.9)))
            g=Image.new('RGBA',size,it.get('gcolor',col)[:3]+(0,)); g.putalpha(gl); out.alpha_composite(g)
        t=Image.new('RGBA',size,col[:3]+(0,)); t.putalpha(L.point(lambda v:int(v*col[3]/255))); out.alpha_composite(t)
    return out
def fit(text,maxw,size,weight='SemiBold',minsize=8):
    lines=text.split('\n')
    while size>minsize and max(F(size,weight).getlength(l) for l in lines)>maxw: size-=1
    return size
def process(src,dst,regions):
    """regions: dict(box, text, size, maxw, color|None, dark, style, clear, pad, anchor, xy)"""
    im=Image.open(src); a=np.asarray(im).copy(); keep=green_keep(a)
    items=[]
    for r in regions:
        b=r['box']
        col=r.get('color') or sample(a,b,r.get('dark',False))
        if r.get('rowfill') is not None:
            x0,y0,x1,y1=b; p=r.get('pad',4); src=r['rowfill']
            for yy in range(max(0,y0-p),min(a.shape[0],y1+p)):
                for xx in range(max(0,x0-p),min(a.shape[1],x1+p)): a[yy,xx]=a[yy,src(xx) if callable(src) else src]
        elif r.get('erase',True): erase(a,b,pad=r.get('pad',4),keep=None if r.get('nokeep',True) else keep,clear=r.get('clear',True),noprot=r.get('noprot',False))
        cx=(b[0]+b[2])/2; cy=(b[1]+b[3])/2
        xy=r.get('xy',(cx,cy)); anc=r.get('anchor','mm')
        if anc[0]=='l' and 'xy' not in r: xy=(b[0],cy)
        sz=fit(r['text'],r.get('maxw',b[2]-b[0]),r['size'],r.get('weight','SemiBold'))
        items.append(dict(xy=xy,text=r['text'],size=sz,weight=r.get('weight','SemiBold'),anchor=anc,color=col,style=r.get('style','shadow'),gcolor=r.get('gcolor',col),sa=r.get('sa',1.3),blur=r.get('blur',2.0),gblur=r.get('gblur',6)))
    res=Image.fromarray(a,'RGBA'); res.alpha_composite(draw_text(res.size,items)); res.save(dst); return res
