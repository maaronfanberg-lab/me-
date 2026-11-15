import json,sys,math,subprocess,os,colorsys
OUT=os.environ.get('SE_OUT','out')
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
W,H,FPS=1280,720,30
HUE=[8,190,48,300,150,335,95,220,270,120]+[(i*137.5+40)%360 for i in range(10,64)]
SC=json.load(open(os.path.join(OUT,'scenes.json')));S=SC['scenes'];TOTAL=SC['total'];TN=1400
FONTS=['/usr/share/fonts/opentype/inter/Inter-Regular.otf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
font=next((ImageFont.truetype(f,22) for f in FONTS if os.path.exists(f)),None) or ImageFont.load_default()
def col(h,s,l):
    r,g,b=colorsys.hls_to_rgb((h%360)/360,l,s);return (r,g,b)
def cells(on):
    n=len(on);cols=math.ceil(math.sqrt(n));rows=math.ceil(n/cols)
    if n==2:cols,rows=2,1
    cw,ch=W/cols,H/rows;out=[]
    for k,i in enumerate(on):out.append((i,(k%cols+.5)*cw,(k//cols+.5)*ch,min(cw,ch)*.42))
    return out
def proj(P,yaw,pit):
    x,y,z=P[:,0],P[:,1],P[:,2]
    cy,sy=math.cos(yaw),math.sin(yaw);x2=x*cy+z*sy;z2=-x*sy+z*cy
    cp,sp=math.cos(pit),math.sin(pit);y2=y*cp-z2*sp
    return x2,y2
def frames(lo,hi):
    tr={};bg={};f=0
    with open(os.path.join(OUT,'frames.jsonl')) as fh:
        for line in fh:
            if f>=hi:break
            r=json.loads(line)
            if 'pre' in r:
                bg={int(k):np.array(v,dtype=np.float32).reshape(-1,3) for k,v in r['pre'].items()};tr={}
            for k,v in r['tr'].items():
                k=int(k);a=np.array(v,dtype=np.float32).reshape(-1,3)
                tr[k]=np.vstack([tr.get(k,np.zeros((0,3),np.float32)),a])[-TN:]
            if f>=lo:yield f,r,(tr,bg)
            f+=1
def draw(f,r,tr):
    t=f/FPS;yaw=.5+t*.09;pit=.3+.12*math.sin(t*.05)
    im=Image.new('RGB',(W,H),(14,16,25));d=ImageDraw.Draw(im)
    tr,bg=tr
    for i,cx,cy,sc in cells(r['on']):
        G=bg.get(i)
        if G is not None and len(G)>2:
            x,y=proj(G,yaw,pit);rr,gg,bb=col(HUE[i],.6,.2)
            d.line(list(zip((cx+x*sc).tolist(),(cy-y*sc).tolist())),fill=(int(rr*255),int(gg*255),int(bb*255)),width=1)
        P=tr.get(i)
        if P is not None and len(P)>2:
            x,y=proj(P,yaw,pit);X=cx+x*sc;Y=cy-y*sc;n=len(X);ch=12
            for c in range(ch):
                a=c*n//ch;b=min(n,(c+1)*n//ch+1)
                if b-a<2:continue
                age=(c+1)/ch;rr,gg,bb=col(HUE[i],.85,.18+.38*age*age)
                d.line(list(zip(X[a:b].tolist(),Y[a:b].tolist())),fill=(int(rr*255),int(gg*255),int(bb*255)),width=1)
        p=r['pt'].get(str(i))
        if p:
            Q=np.array(p,dtype=np.float32).reshape(-1,3);x,y=proj(Q,yaw,pit);rad=4 if len(Q)<=8 else 2.6 if len(Q)<=32 else 1.8
            hr,hg,hb=col(HUE[i]+40,.9,.55);cr,cg,cb=col(HUE[i]+40,.9,.86)
            for xx,yy in zip(cx+x*sc,cy-y*sc):
                d.ellipse([xx-rad*2.6,yy-rad*2.6,xx+rad*2.6,yy+rad*2.6],fill=(int(hr*90),int(hg*90),int(hb*90)))
            for xx,yy in zip(cx+x*sc,cy-y*sc):
                d.ellipse([xx-rad,yy-rad,xx+rad,yy+rad],fill=(int(cr*255),int(cg*255),int(cb*255)))
    glow=im.resize((W//4,H//4)).filter(ImageFilter.GaussianBlur(3)).resize((W,H))
    im=Image.fromarray(np.minimum(255,np.asarray(im,dtype=np.uint16)+np.asarray(glow,dtype=np.uint16)*7//10).astype(np.uint8))
    s0=S[r['s']][0];a=min(1,(t-s0)/1.2)
    a*=max(0,min(1,(TOTAL-t)/4))
    d=ImageDraw.Draw(im);v=int(150*a)+14
    d.text((36,H-50),S[r['s']][1],font=font,fill=(v,v,int(v*1.08)))
    if t>TOTAL-4:im=Image.fromarray((np.asarray(im)*max(0,(TOTAL-t)/4)).astype(np.uint8))
    if t<1.5:im=Image.fromarray((np.asarray(im)*(t/1.5)).astype(np.uint8))
    return im
if __name__=='__main__':
    if sys.argv[1]=='still':
        want=[int(float(x)*FPS) for x in sys.argv[2:]]
        for f,r,tr in frames(0,max(want)+1):
            if f in want:draw(f,r,tr).save('still_%d.png'%(f//FPS))
    else:
        # one chunk of the whole render: frames lo..hi
        lo,hi=int(sys.argv[2]),int(sys.argv[3]);tmp=os.path.join(OUT,'part_%06d.tmp.mp4'%lo)
        p=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','%dx%d'%(W,H),'-r',str(FPS),'-i','-','-c:v','libx264','-preset','veryfast','-crf','26','-pix_fmt','yuv420p',tmp],stdin=subprocess.PIPE)
        for f,r,tr in frames(lo,hi):p.stdin.write(draw(f,r,tr).tobytes())
        p.stdin.close()
        if p.wait()==0:os.replace(tmp,os.path.join(OUT,'part_%06d.mp4'%lo))
        else:sys.exit('encode failed')
