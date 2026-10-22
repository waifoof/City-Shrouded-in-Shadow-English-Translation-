import sys,glob,re;sys.path.insert(0,'.')
from detect import boxes
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
SERIF='/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
def F(sz): return ImageFont.truetype(SERIF,sz,index=0)
T={1:"Nightfall's Giant Shadow",2:'Shadows Below',3:'Shadow over the Bridge',4:'Stealing Shadows',5:'Shadow of Wild Desire',
6:'Night Sea, Waves, Shadows',7:'Clashing Shadows',8:'Ominous Golden Shadow',9:'Shadows of Rival Justice',
'10':'Hungry Shadows Take Flight','10a':'Soaring Shadow','10b':'Shadow Within',11:'A Shadow at Your Side',12:'The Shadow That Cuts All',
13:'Relentless Shadow',14:'The Shadow That Crushes All',15:'Giant Shadow from the Sky',16:'A Giant Shadow Approaches',17:'City Shrouded in Shadow'}
H={'10':'Stage 10 Part 1','10a':'Stage 10 Part 2a','10b':'Stage 10 Part 2b'}
def key_for(name):
    m={'ST_10':'10','ST_10_1A':'10a','ST_10_1B':'10b','ST_15':16,'ST_16':15,'E06_sc_ST10':'10','E06_sc_ST10_2':'10a','E06_sc_ST10_3':'10b'}
    if name in m: return m[name]
    return int(re.findall(r'(\d+)$',name)[0])
def styled(size,draws):
    L=Image.new('L',size,0); d=ImageDraw.Draw(L)
    for (x,y,t,f,anc) in draws: d.text((x,y),t,font=f,fill=255,anchor=anc)
    outline=L.filter(ImageFilter.MaxFilter(5))
    glow=L.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(7)).point(lambda v:min(255,int(v*1.4)))
    out=Image.new('RGBA',size,(0,0,0,0))
    g=Image.new('RGBA',size,(0,0,0,0)); g.putalpha(glow); out.alpha_composite(g)
    o=Image.new('RGBA',size,(0,0,0,0)); o.putalpha(outline); out.alpha_composite(o)
    w=Image.new('RGBA',size,(255,255,255,0)); w.putalpha(L); out.alpha_composite(w)
    return out
def card(path,out):
    name=path.split('__')[-1][:-4]; k=key_for(name)
    im=Image.open(path); W,Hh=im.size; a=np.asarray(im)
    bx=[tuple(int(v) for v in b) for b in boxes(a,dx=14,dy=3)]
    bx=[b for b in bx if b[3]-b[1]>20]
    hb,tb=bx[0],bx[-1]
    hs=round((hb[3]-hb[1])*0.95); ts=round((tb[3]-tb[1])*0.80)
    if name.startswith('E06_sc') or name.startswith('e06_sc'): ts=round((tb[3]-tb[1])*0.82)
    title=T[k]; header=H.get(k,f'Stage {k:02d}' if isinstance(k,int) else '')
    ft=F(ts)
    while ft.getlength(title)>W-50: ts-=1; ft=F(ts)
    fh=F(hs)
    centered=tb[0]>40
    tw=ft.getlength(title)
    tx=(W-tw)/2 if centered else tb[0]
    ty=tb[3]-ts*0.28
    draws=[(tx,hb[3]-hs*0.22,header,fh,'ls'),(tx,ty,title,ft,'ls')]
    res=styled((W,Hh),draws); res.save(out); return res
if __name__=='__main__':
    fs=sorted(glob.glob('pngA/stage_title__ST_[0-9]*.png'))+sorted(glob.glob('pngA/stage_clear__[Ee]06_sc_ST*.png'))
    for f in fs: card(f,'out2/'+f.split('/')[-1])
    print(len(fs))
