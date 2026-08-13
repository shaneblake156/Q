#!/usr/bin/env python3
"""QAI V5 — finite real-telemetry -> CUDA nonlinear field pipeline.

Grounding:
- Inputs come from ~/QAI/multidim/chunks/chunk_*.csv when available.
- Quantum terminology is quantum-inspired numerical modelling, not physical qubits.
- 'negative energy' is not measured; inverse/negative structure means negative correlation/phase.
"""
from __future__ import annotations
import csv, glob, json, math, time, wave
from pathlib import Path
import numpy as np
import torch

SEED = 13
STEPS = 512
NODES = 256
SR = 44100
ROOT = Path.home()/"QAI"
CHUNKS = sorted(glob.glob(str(ROOT/"multidim"/"chunks"/"chunk_*.csv")))
OUT = ROOT/"qai_v5"
AUDIO = OUT/"audio"
REPORT = OUT/"report"
for d in (OUT, AUDIO, REPORT): d.mkdir(parents=True, exist_ok=True)

COLS = [
    "cpu_package_c","core_spread_c","voltage_mean_v","fan_mean_rpm",
    "gpu_temp_c","gpu_util_pct","gpu_vram_mib","load1","mem_used_pct",
    "net_rx_Bps","net_tx_Bps","tcp_established","listening_sockets",
]

if not CHUNKS:
    raise SystemExit("No telemetry chunks found under ~/QAI/multidim/chunks")
PATH = CHUNKS[-1]

with open(PATH, newline="") as f:
    rows = list(csv.DictReader(f))
X = np.array([[float(r[c]) for c in COLS] for r in rows], dtype=np.float64)
for j in range(X.shape[1]):
    col=X[:,j]; good=np.isfinite(col); fill=col[good].mean() if good.any() else 0.0; col[~good]=fill; X[:,j]=col
mu=X.mean(0); sd=X.std(0); variable=sd>1e-9
active=[c for c,ok in zip(COLS,variable) if ok]
Z=(X[:,variable]-mu[variable])/sd[variable]

# backend
device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
torch.manual_seed(SEED)
if device.type=="cuda": torch.cuda.manual_seed_all(SEED)

# deterministic telemetry embedding into 256-node complex field
flat=torch.tensor(Z.reshape(-1),dtype=torch.float32,device=device)
idx=torch.arange(NODES,device=device)
base=flat[idx % flat.numel()]
phase_src=flat[(idx*7+3) % flat.numel()]
psi=torch.complex(torch.tanh(base), torch.tanh(phase_src))
psi=psi/(torch.linalg.vector_norm(psi)+1e-12)

# sparse symmetric coupling seeded deterministically
G=torch.Generator(device=device); G.manual_seed(SEED)
A=torch.randn((NODES,NODES),generator=G,device=device,dtype=torch.float32)
A=(A+A.T)/2
mask=torch.rand((NODES,NODES),generator=G,device=device)<0.035
mask=torch.triu(mask,1); mask=mask|mask.T
A=A*mask
A.fill_diagonal_(0)

coupling=0.14
nonlinearity=0.18
phase_drive=0.031
history=[]
perturb_steps={128,256,384}

# Lyapunov companion
psi2=psi.clone()
eps=1e-6
psi2[0]+=torch.complex(torch.tensor(eps,device=device),torch.tensor(0.0,device=device))
psi2=psi2/(torch.linalg.vector_norm(psi2)+1e-12)
ly_logs=[]

def metrics(v):
    p=torch.abs(v)**2; p=p/(p.sum()+1e-12)
    H=-(p*torch.log(p+1e-12)).sum()
    PR=1.0/(torch.sum(p*p)+1e-12)
    PLV=torch.abs(torch.mean(torch.exp(1j*torch.angle(v))))
    return float(H.item()),float(PR.item()),float(PLV.item())

def step(v,t):
    amp2=torch.abs(v)**2
    lin=torch.matmul(A.to(torch.complex64),v)
    drive=torch.exp(1j*(phase_drive*t + torch.linspace(0,math.pi,NODES,device=device)))
    nv=v + coupling*lin/NODES + 1j*nonlinearity*amp2*v + 0.002*drive
    return nv/(torch.linalg.vector_norm(nv)+1e-12)

start=time.perf_counter()
for t in range(STEPS):
    psi=step(psi,t); psi2=step(psi2,t)
    if t in perturb_steps:
        j=(t//128*37)%NODES
        psi[j]+=torch.complex(torch.tensor(0.01,device=device),torch.tensor(-0.006,device=device))
        psi=psi/(torch.linalg.vector_norm(psi)+1e-12)
    delta=psi2-psi; d=torch.linalg.vector_norm(delta).item()
    if d>0:
        ly_logs.append(math.log(max(d,1e-30)/eps))
        psi2=psi + delta*(eps/(d+1e-30)); psi2=psi2/(torch.linalg.vector_norm(psi2)+1e-12)
    H,PR,PLV=metrics(psi)
    history.append((t,H,PR,PLV,float(torch.max(torch.abs(psi)).item())))
if device.type=="cuda": torch.cuda.synchronize()
elapsed=time.perf_counter()-start
lambda_est=float(np.mean(ly_logs)) if ly_logs else float("nan")

# final node anomaly score
amp=torch.abs(psi).detach().cpu().numpy()
strength=torch.sum(torch.abs(A),dim=1).detach().cpu().numpy()
za=(amp-amp.mean())/(amp.std()+1e-12); zs=(strength-strength.mean())/(strength.std()+1e-12)
score=np.abs(za)+np.abs(zs)
top=np.argsort(score)[::-1][:16]

# real-telemetry correlations
C=np.corrcoef(Z,rowvar=False); pairs=[]
for i in range(len(active)):
    for j in range(i+1,len(active)):
        pairs.append((float(C[i,j]),active[i],active[j]))
pos=sorted(pairs,reverse=True)[:8]; neg=sorted(pairs)[:8]

# history csv
with open(OUT/"evolution.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["step","entropy","participation_ratio","plv","max_amp"]); w.writerows(history)

# compact sonification of H/PR/PLV + negative-correlation bridge pulses
def tone(freq,dur=.05,amp=.25,phase=0):
    t=np.arange(int(SR*dur))/SR
    return amp*np.sin(2*np.pi*freq*t+phase)*np.hanning(len(t))
def write_wav(path,x):
    x=np.asarray(x,float); x=x/(np.max(np.abs(x))+1e-12); pcm=(x*.88*32767).astype('<i2')
    with wave.open(str(path),'wb') as f: f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR); f.writeframes(pcm.tobytes())

parts=[]
for t,H,PR,PLV,M in history[::8]:
    parts.append(tone(180+H*35,.035,.24)+tone(260+PR*2.5,.035,.12,math.pi/2)+tone(420+PLV*500,.035,.10))
write_wav(AUDIO/"qai_v5_evolution.wav",np.concatenate(parts))
negparts=[]
for r,a,b in neg:
    f=180+abs(r)*700
    negparts.append(tone(f,.16,.3,math.pi))
write_wav(AUDIO/"negative_correlation_trace.wav",np.concatenate(negparts) if negparts else np.zeros(SR//2))

report={
 "input":PATH,"samples":len(rows),"active_dimensions":active,
 "backend":str(device),"gpu":torch.cuda.get_device_name(0) if device.type=="cuda" else None,
 "steps":STEPS,"nodes":NODES,"elapsed_s":elapsed,"steps_per_s":STEPS/elapsed,
 "final":{"entropy":history[-1][1],"participation_ratio":history[-1][2],"plv":history[-1][3],"max_amp":history[-1][4]},
 "lyapunov_style_log_stretch_mean":lambda_est,
 "positive_links":[{"r":r,"a":a,"b":b} for r,a,b in pos],
 "negative_links":[{"r":r,"a":a,"b":b} for r,a,b in neg],
 "top_nodes":[{"node":int(i),"score":float(score[i]),"amp":float(amp[i]),"strength":float(strength[i])} for i in top],
 "grounding":"Quantum-inspired numerical evolution. Negative trace means negative correlation/phase, not physical negative energy."
}
json.dump(report,open(REPORT/"qai_v5_report.json","w"),indent=2)

print("╔════ ⚛️ QAI V5 REAL→CUDA COMPLETE ════╗")
print("input:",PATH)
print("backend:",device)
if device.type=="cuda": print("gpu:",torch.cuda.get_device_name(0))
print("samples:",len(rows),"active dims:",len(active),"nodes:",NODES,"steps:",STEPS)
print("elapsed:",round(elapsed,4),"s | steps/s:",round(STEPS/elapsed,2))
print("final H/PR/PLV/max:",*[round(x,6) for x in history[-1][1:]])
print("Lyapunov-style mean log stretch:",round(lambda_est,6))
print("\n🔗 strongest positive")
for r,a,b in pos[:5]: print(f"{r:+.5f} {a} ↔ {b}")
print("\n🌑 strongest negative")
for r,a,b in neg[:5]: print(f"{r:+.5f} {a} ↔ {b}")
print("\n👻 top numerical nodes")
for i in top[:8]: print(f"node={int(i):3d} score={score[i]:.5f} amp={amp[i]:.6f} strength={strength[i]:.5f}")
print("\n🎵",AUDIO/"qai_v5_evolution.wav")
print("🎵",AUDIO/"negative_correlation_trace.wav")
print("📄",REPORT/"qai_v5_report.json")
print("NOTE: quantum-inspired simulation; no physical negative-energy detection.")
