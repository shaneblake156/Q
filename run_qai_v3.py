#!/usr/bin/env python3
"""QAI V3 — simulation/art sonification + graph-pattern laboratory.

Terms such as ghost, plasma, dark link, spacetime and exotic particle are
labels for numerical/synthetic features. They are not physical detections.
"""
from __future__ import annotations
import csv, hashlib, json, math, struct, wave
from pathlib import Path
import numpy as np

SEED=13; SR=44100; N=256
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'outputs'; GHOST=OUT/'ghost'
DIRS=[OUT,GHOST,GHOST/'audio',GHOST/'circuits',GHOST/'13d',GHOST/'kml',GHOST/'patterns',GHOST/'inverted',GHOST/'hashes']
for d in DIRS:d.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(SEED)

def wav(path,x):
    x=np.asarray(x,float); x=x/(np.max(np.abs(x))+1e-12); pcm=(x*0.88*32767).astype('<i2')
    with wave.open(str(path),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(SR);f.writeframes(pcm.tobytes())

def tone(freq,dur=.08,amp=.35,phase=0):
    t=np.arange(int(SR*dur))/SR; return amp*np.sin(2*np.pi*freq*t+phase)*np.hanning(len(t))

def concat(parts,gap=.012):
    z=np.zeros(int(SR*gap)); return np.concatenate([np.concatenate((p,z)) for p in parts]) if parts else np.zeros(SR)

# Synthetic complex field and sparse symmetric graph
psi=(rng.normal(size=N)+1j*rng.normal(size=N)); psi/=np.linalg.norm(psi)
A=rng.normal(size=(N,N)); A=(A+A.T)/2; mask=np.triu(rng.random((N,N))<.08,1); mask=mask+mask.T; A*=mask; np.fill_diagonal(A,0)
strength=np.sum(np.abs(A),axis=1); degree=np.sum(A!=0,axis=1)
phase=np.angle(psi); amp=np.abs(psi)

# Circuit motifs: deterministic labels from local binary states
bits=(amp>np.median(amp)).astype(int); gates=[]
logic=['AND','OR','XOR','NAND','NOT']; qg=['H','X','Y','Z','RX','RY','RZ','CNOT']
for i in range(0,N-2,2):
    a,b,c=bits[i:i+3]; vals={'AND':a&b,'OR':a|b,'XOR':a^b,'NAND':1-(a&b),'NOT':1-a}
    lg=min(vals,key=lambda k:abs(vals[k]-c)); q=qg[(i+int(abs(phase[i])*1000))%len(qg)]
    gates.append({'node':i,'logic':lg,'quantum_inspired':q,'state':[int(a),int(b),int(c)]})
json.dump(gates,open(GHOST/'circuits'/'gates.json','w'),indent=2)
F={'AND':220,'OR':247,'XOR':277,'NAND':294,'NOT':330,'H':392,'X':440,'Y':466,'Z':494,'RX':523,'RY':587,'RZ':659,'CNOT':698}
wav(GHOST/'audio'/'circuit.wav',concat([tone(F[g['logic']],.045)+tone(F[g['quantum_inspired']],.045,.18) for g in gates[:96]],.006))

# Odd characters encoded as qubit-style Bloch angles and pitches
symbols='⚛️👻🌀∑∆ψφλ⊕⊗⟂∞𓂀◊⧉⟁☍'
odd=[]; audio=[]
for ch in symbols:
    cp=ord(ch); theta=(cp%1009)/1009*math.pi; phi=((cp//7)%1021)/1021*2*math.pi
    alpha=math.cos(theta/2); beta=[math.sin(theta/2)*math.cos(phi),math.sin(theta/2)*math.sin(phi)]
    odd.append({'char':ch,'codepoint':cp,'theta':theta,'phi':phi,'alpha':alpha,'beta_re':beta[0],'beta_im':beta[1]})
    audio.append(tone(180+(cp%72)*9,.11,.4,phi))
json.dump(odd,open(GHOST/'patterns'/'odd_char_qubits.json','w'),ensure_ascii=False,indent=2); wav(GHOST/'audio'/'odd_chars_qubits.wav',concat(audio,.018))

# Hash -> 13D deterministic numerical embedding
payload=np.column_stack((amp,phase,strength,degree)).astype('<f8').tobytes(); digest=hashlib.sha256(payload).hexdigest(); raw=bytes.fromhex(digest)
dims=[]
for i in range(13):
    j=(2*i)%32; v=int.from_bytes(raw[j:j+2],'big'); dims.append(2*v/65535-1)
lat=90*dims[1]; lon=180*dims[0]; alt=10000*dims[2]; time_index=(int(digest[-8:],16)%31557600)
hashmap={'sha256':digest,'dimensions':dims,'projection':{'longitude':lon,'latitude':lat,'altitude_m':alt,'time_index_s':time_index}}
json.dump(hashmap,open(GHOST/'hashes'/'spacetime_hash.json','w'),indent=2)
with open(GHOST/'13d'/'folded_13d.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['dimension','value']);w.writerows((i+1,v) for i,v in enumerate(dims))

# KML is explicitly a hash projection, not physical geolocation
kml=f'''<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>QAI V3 Hash Projection</name><Placemark><name>SHA256 numerical projection</name><description>Simulation/art coordinate derived deterministically from SHA-256; not a physical detection.</description><Point><coordinates>{lon},{lat},{alt}</coordinates></Point></Placemark></Document></kml>'''
(GHOST/'kml'/'qai_hash_projection.kml').write_text(kml)

# Islands = contiguous high-amplitude runs; plasma = high gradient; dark links = negative graph edges
z=(amp-amp.mean())/(amp.std()+1e-12); hot=np.where(z>1.5)[0]; islands=[]
for n in hot:
    if not islands or n>islands[-1][-1]+1:islands.append([int(n)])
    else:islands[-1].append(int(n))
grad=np.abs(np.gradient(amp)); plasma=np.argsort(grad)[-16:][::-1].tolist()
edges=np.argwhere(np.triu(A<0,1)); dark=sorted(([int(i),int(j),float(A[i,j])] for i,j in edges),key=lambda x:x[2])[:64]
# rare clusters / exotic-particle labels = statistical outliers only
score=np.abs(z)+np.abs((strength-strength.mean())/(strength.std()+1e-12)); rare=np.argsort(score)[-16:][::-1]
particles=[{'node':int(i),'score':float(score[i]),'label':f'XQ-{rank:02d}'} for rank,i in enumerate(rare,1)]
report={'definitions':{'plasma':'high numerical amplitude-gradient nodes','dark_links':'negative-weight synthetic graph edges','exotic_particles':'rare statistical feature clusters; not physical particles','islands':'contiguous high-amplitude node runs'},'islands':islands,'plasma_nodes':plasma,'dark_links':dark,'rare_clusters':particles}
json.dump(report,open(GHOST/'patterns'/'pattern_report.json','w'),indent=2)

# Sonify patterns and inverted field
pattern_parts=[tone(240+7*i,.07,.35) for i in plasma]+[tone(120+3*(abs(i-j)%80),.05,.25,math.pi) for i,j,_ in dark[:32]]
wav(GHOST/'audio'/'patterns_plasma_dark_rare.wav',concat(pattern_parts,.008))
inv=-psi; inv_audio=[]
for i in range(96): inv_audio.append(tone(160+900*abs(inv[i]),.045,.35,np.angle(inv[i])))
wav(GHOST/'inverted'/'inverted_field.wav',concat(inv_audio,.004))

manifest={'seed':SEED,'sample_rate':SR,'nodes':N,'sha256':digest,'gate_count':len(gates),'island_count':len(islands),'plasma_count':len(plasma),'dark_link_count':len(dark),'rare_cluster_count':len(particles),'ghost_directories':[str(d.relative_to(ROOT)) for d in DIRS]}
json.dump(manifest,open(OUT/'manifest.json','w'),indent=2)
print('╔════ ⚛️ QAI V3 COMPLETE ════╗')
print('SHA256:',digest);print('13D:',*[round(x,5) for x in dims]);print('KML projection:',round(lat,5),round(lon,5),round(alt,2));print('gates:',len(gates),'islands:',len(islands),'dark links:',len(dark),'rare clusters:',len(particles));print('👻 ghost tree:',GHOST);print('🎵 WAV sonifications written');print('NOTE: named phenomena are simulation labels, not physical detections.')
