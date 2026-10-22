from PIL import Image, ImageDraw
import glob,sys,math
def sheet(files,out,tw=300,th=170,cols=6):
    files=[f for f in files if min(Image.open(f).size)>=16]
    rows=math.ceil(len(files)/cols)
    c=Image.new('RGBA',(cols*tw,rows*(th+14)),(45,55,70,255)); d=ImageDraw.Draw(c)
    for i,f in enumerate(files):
        im=Image.open(f).convert('RGBA'); im.thumbnail((tw-6,th-6))
        x=(i%cols)*tw; y=(i//cols)*(th+14)
        bg=Image.new('RGBA',im.size,(25,35,30,255)); bg.alpha_composite(im)
        c.paste(bg,(x+3,y+14)); d.text((x+3,y+1),f.split('/')[-1][:-4].split('__',1)[-1][:40],fill=(255,255,0,255))
    c.convert('RGB').save(out,quality=80); return len(files)
if __name__=='__main__':
    pat=sys.argv[1]; out=sys.argv[2]
    print(sheet(sorted(glob.glob(pat)),out))
