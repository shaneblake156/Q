#!/usr/bin/env python3
"""QAI V4 real telemetry analyzer.

Operates on the latest finite CSV chunk in ~/QAI/multidim/chunks.
'Negative energy' here is only a sonification label for negative correlation / phase-inverted modes.
No physical negative-energy or exotic-particle detection is performed.
"""
from __future__ import annotations
import csv, glob, json, math, wave
from pathlib import Path
import numpy as np

SR=44100
ROOT=Path.home()/"QAI"
FILES=sorted(glob.glob(str(ROOT/"multidim/chunks/chunk_*.csv")))
if not FILES: raise SystemExit("No chunk CSV found")
PATH=FILES[-1]
OUT=ROOT/"multidim"/"v4"
AUDIO=OUT/"audio"; REPORT=OUT/"report"
for d in (OUT,AUDIO,REPORT): d.mkdir(parents=True,exist_ok=True)

cols=["cpu_package_c","core_spread_c","voltage_mean_v","fan_mean_rpm","gpu_temp_c","gpu_util_pct","gpu_vram_mib","load1","mem_used_pct","net_rx_Bps","net_tx_Bps","tcp_established","listening_sockets"]
with open(PATH,newline="") as f: rows=list(csv.DictReader(f))
X=np.array([[float(r[c]) for c in cols] for r in rows],float)
for j in range(X.shape[1]):
    c=X[:,j]; good=np.isfinite(c); fill=c[good].mean() if good.any() else 0.; c[~good]=fill; X[:,j]=c
mu=X.mean(0); sd=X.std(0); var=sd>1e-9
active=[c for c,v in zip(cols,var) if v]; Z=(X[:,var]-mu[var])/sd[var]

# Correlations
C=np.corrcoef(Z,rowvar=False); pairs=[]
for i in range(len(active)):
    for j in range(i+1,len(active)): pairs.append((float(C[i,j]),active[i],active[j],i,j))
pos=sorted(pairs,reverse=True)[:8]; neg=sorted(pairs)[:8]

# PCA/SVD temporal modes
U,S,VT=np.linalg.svd(Z,full_matrices=False); modes=[U[:,k]*S[k] for k in range(min(3,len(S)))]

def analytic(x):
    n=len(x); F=np.fft.fft(x); h=np.zeros(n)
    if n%2==0: h[0]=h[n//2]=1; h[1:n//2]=2
    else: h[0]=1; h[1:(n+1)//2]=2
    return np.fft.ifft(F*h)

def tone(freq,dur=.10,amp=.25,phase=0.):
    t=np.arange(int(SR*dur))/SR
    return amp*np.sin(2*np.pi*freq*t+phase)*np.hanning(len(t))

def cat(parts,gap=.006):
    z=np.zeros(int(SR*gap)); return np.concatenate([np.concatenate((p,z)) for p in parts]) if parts else np.zeros(SR)

def write_mono(p,x):
    x=np.asarray(x,float); x=x/(np.max(np.abs(x))+1e-12); pcm=(x*.88*32767).astype('<i2')
    with wave.open(str(p),'wb') as f: f.setnchannels(1);f.setsampwidth(2);f.setframerate(SR);f.writeframes(pcm.tobytes())

def write_stereo(p,l,r):
    n=max(len(l),len(r)); l=np.pad(l,(0,n-len(l))); r=np.pad(r,(0,n-len(r))); peak=max(np.max(np.abs(l))+1e-12,np.max(np.abs(r))+1e-12)
    pcm=(np.column_stack((l/peak,r/peak))*.88*32767).astype('<i2')
    with wave.open(str(p),'wb') as f: f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes(pcm.tobytes())

# Heat trace = CPU package + core spread + GPU temp where variable
heat_idx=[cols.index("cpu_package_c"),cols.index("core_spread_c"),cols.index("gpu_temp_c")]
heat=[]
for idx in heat_idx:
    c=X[:,idx]; s=c.std(); heat.append((c-c.mean())/(s if s>1e-9 else 1.0))
heat_trace=np.mean(heat,axis=0)
heat_env=np.abs(analytic(heat_trace))
heat_audio=cat([tone(180+120*np.tanh(abs(v)),.11,.20+.18*np.tanh(e)) for v,e in zip(heat_trace,heat_env)])
write_mono(AUDIO/"heat_time_trace.wav",heat_audio)

# Frequency trace: dominant FFT bin for each active dimension
fft_report={}; freq_audio=[]
for j,c in enumerate(active):
    sig=Z[:,j]-Z[:,j].mean(); spec=np.abs(np.fft.rfft(sig))**2; freq=np.fft.rfftfreq(len(sig),d=1.0)
    if len(spec): spec[0]=0
    k=int(np.argmax(spec)) if np.any(spec>0) else 0
    fft_report[c]={"dominant_hz":float(freq[k]),"power":float(spec[k])}
    freq_audio.append(tone(220+880*float(freq[k]),.13,.24))
write_mono(AUDIO/"frequency_trace.wav",cat(freq_audio,.012))

# Negative-correlation 'energy' trace: phase-inverted pairs
neg_parts=[]
neg_records=[]
for r,a,b,i,j in neg:
    mag=abs(r); root=140+260*mag; ratio=1.0+0.5*mag
    x=tone(root,.18,.25,0)+tone(root*ratio,.18,.20,math.pi)
    neg_parts.append(x); neg_records.append({"corr":r,"a":a,"b":b,"root_hz":root,"ratio":ratio})
write_mono(AUDIO/"negative_link_trace.wav",cat(neg_parts,.02))

# Harmonic bridges from strongest positive/negative links
ratios=[3/2,4/3,5/4,6/5,8/5,9/8]; bridges=[]; bridge_parts=[]
for rank,(r,a,b,_,_) in enumerate(pos[:5]+neg[:5],1):
    ratio=ratios[(rank-1)%len(ratios)]; root=180+300*abs(r); phase=0 if r>=0 else math.pi
    bridge_parts.append(tone(root,.20,.24,0)+tone(root*ratio,.20,.18,phase)); bridges.append({"rank":rank,"corr":r,"a":a,"b":b,"root_hz":root,"ratio":ratio,"bridge_hz":root*ratio})
write_mono(AUDIO/"harmonic_bridges_real.wav",cat(bridge_parts,.02))

# Stereo temporal modes
left=cat([tone(180+80*np.tanh(abs(v)),.10,.22) for v in modes[0]])
right=cat([tone(280+100*np.tanh(abs(v)),.10,.22,math.pi/2) for v in modes[1]]) if len(modes)>1 else np.zeros_like(left)
write_stereo(AUDIO/"multimode_stereo.wav",left,right)

# Anomaly windows
D=np.sqrt((Z**2).sum(1)); top=np.argsort(D)[::-1][:8]
anom=[]
for i in top:
    contrib=np.argsort(np.abs(Z[i]))[::-1][:4]
    anom.append({"sample":int(i),"distance":float(D[i]),"top_dimensions":[{"name":active[j],"z":float(Z[i,j])} for j in contrib]})

# What is odd: finite-chunk statistical observations only
odd=[]
for i in top[:5]:
    if D[i] > np.median(D)+2*np.std(D): odd.append(f"sample {int(i)} is a strong multivariate outlier within this chunk")
for r,a,b,_,_ in pos:
    if abs(r)>.9: odd.append(f"very strong positive coupling {a}<->{b}: r={r:.5f}")
for r,a,b,_,_ in neg:
    if abs(r)>.7: odd.append(f"strong inverse coupling {a}<->{b}: r={r:.5f}")
if not odd: odd.append("no extreme inverse correlation or persistent thermal anomaly in this short chunk")

report={"input":str(PATH),"samples":len(rows),"active_dimensions":active,"constant_dimensions":[c for c,v in zip(cols,var) if not v],"positive_links":[{"corr":r,"a":a,"b":b} for r,a,b,_,_ in pos],"negative_links":neg_records,"fft":fft_report,"anomalies":anom,"harmonic_bridges":bridges,"odd":odd,"definitions":{"negative_energy_trace":"phase-inverted sonification of negative correlations; not physical negative energy","heat_trace":"normalized temperature-derived telemetry","frequency_trace":"FFT of sampled host telemetry"}}
json.dump(report,open(REPORT/"real_v4_report.json","w"),indent=2)

print("════ ⚛️ REAL TELEMETRY V4 COMPLETE ════")
print("input:",PATH)
print("samples:",len(rows),"active dims:",len(active))
print("\n🔥 HEAT")
print("heat mean/std:",round(float(np.mean(heat_trace)),5),round(float(np.std(heat_trace)),5),"envelope max:",round(float(np.max(heat_env)),5))
print("\n🌑 NEGATIVE LINKS")
for x in neg_records[:5]: print(f"{x['corr']:+.5f} {x['a']} ↔ {x['b']}")
print("\n🌊 DOMINANT FREQUENCIES")
for c,v in fft_report.items(): print(f"{c:20s} {v['dominant_hz']:.4f} Hz power={v['power']:.3f}")
print("\n👻 ODD")
for x in odd: print("-",x)
print("\n🎵",AUDIO/"heat_time_trace.wav")
print("🎵",AUDIO/"negative_link_trace.wav")
print("🎵",AUDIO/"frequency_trace.wav")
print("🎵",AUDIO/"harmonic_bridges_real.wav")
print("🎵",AUDIO/"multimode_stereo.wav")
print("📄",REPORT/"real_v4_report.json")
print("NOTE: negative-energy is a sonification label for inverse correlations, not a measured physical energy quantity.")
