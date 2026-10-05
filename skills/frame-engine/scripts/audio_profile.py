import subprocess, sys, json, numpy as np
SR=48000
def load(p, ss=None, t=None):
    cmd=["ffmpeg","-v","error"]+(["-ss",str(ss)] if ss is not None else [])+(["-t",str(t)] if t else [])+["-i",p,"-ac","1","-ar",str(SR),"-f","f32le","-"]
    return np.frombuffer(subprocess.run(cmd,capture_output=True).stdout,np.float32).astype(np.float64)
def lufs(p):
    r=subprocess.run(["ffmpeg","-hide_banner","-i",p,"-af","loudnorm=print_format=json","-f","null","-"],capture_output=True,text=True).stderr
    j=json.loads(r[r.rfind("{"):r.rfind("}")+1]); return float(j["input_i"]),float(j["input_tp"]),float(j["input_lra"])
def bands(x):
    n=1<<int(np.log2(len(x))); X=np.abs(np.fft.rfft(x[:n]*np.hanning(n)))**2; f=np.fft.rfftfreq(n,1/SR)
    edges=[20,60,150,400,1000,2500,6000,12000,20000]; tot=X[(f>20)&(f<20000)].sum()
    return [10*np.log10(X[(f>=a)&(f<b)].sum()/tot+1e-12) for a,b in zip(edges,edges[1:])]
for p in sys.argv[1:]:
    x=load(p); I,TP,LRA=lufs(p)
    rms=np.sqrt(np.mean(x**2)); crest=20*np.log10(np.max(np.abs(x))/rms)
    print(f"{p.split('/')[-1]:28s} I {I:6.1f}  TP {TP:5.1f}  LRA {LRA:4.1f}  crest {crest:4.1f} dB")
    print("   bands 20-60/60-150/150-400/400-1k/1-2.5k/2.5-6k/6-12k/12-20k:", " ".join(f"{b:6.1f}" for b in bands(x)))
