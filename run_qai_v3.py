#!/usr/bin/env python3
"""QAI V3.1 — deterministic simulation/art sonification + graph-pattern laboratory.

Terms such as ghost, plasma, dark link, spacetime, magic bytes and exotic particle
are labels for numerical/synthetic features. They are not physical detections.
"""
from __future__ import annotations
import csv, hashlib, json, math, wave
from pathlib import Path
import numpy as np

SEED=13; SR=44100; N=256
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'outputs'; GHOST=OUT/'ghost'
DIRS=[OUT,GHOST,GHOST/'audio',GHOST/'circuits',GHOST/'13d',GHOST/'kml',GHOST/'patterns',GHOST/'inverted',GHOST/'hashes',GHOST/'bridges',GHOST/'magic_bytes']
for d in DIRS:d.mkdir(parents=True,exist_ok=True)
rng=np.random.default_rng(SEED)

def wav(path,x):
    x=np.asarray(x,float); x=x/(np.max(np.abs(x))+1e-12); pcm=(x*0.88*32767).astype('<i2')
    with wave.open(str(path),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(SR);f.writeframes(pcm.tobytes())

def stereo_wav(path,l,r):
    n=max(len(l),len(r)); l=np.pad(np.asarray(l,float),(0,n-len(l))); r=np.pad(np.asarray(r,float),(0,n-len(r)))
    peak=max(np.max(np.abs(l))+1e-12,np.max(np.abs(r))+1e-12); pcm=np.column_stack((l/peak,r/peak))*0.88*32767
    with wave.open(str(path),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes(pcm.astype('<i2').tobytes())

def tone(freq,dur=.08,amp=.35,phase=0):
    t=np.arange(int(SR*dur))/SR; return amp*np.sin(2*np.pi*freq*t+phase)*np.hanning(len(t))

def concat(parts,gap=.012):
    z=np.zeros(int(SR*gap)); return np.concatenate([np.concatenate((p,z)) for p in parts]) if parts else np.zeros(SR)

def bridge_tone(root,ratio,dur=.18,amp=.28):
    a=tone(root,dur,amp); b=tone(root*ratio,dur,amp*.8); n=max(len(a),len(b)); return np.pad(a,(0,n-len(a)))+np.pad(b,(0,n-len(b)))

# Synthetic complex field and sparse symmetric graph
psi=(rng.normal(size=N)+1j*rng.normal(size=N)); psi/=np.linalg.norm(psi)
A=rng.normal(size=(N,N)); A=(A+A.T)/2; mask=np.triu(rng.random((N,N))<.08,1); mask=mask+mask.T; A*=mask; np.fill_diagonal(A,0)
strength=np.sum(np.abs(A),axis=1); degree=np.sum(A!=0,axis=1)
phase=np.angle(psi); amp=np.abs(psi)

# Circuit motifs
bits=(amp>np.median(amp)).astype(int); gates=[]
qg=['H','X','Y','Z','RX','RY','RZ','CNOT']
for i in range(0,N-2,2):
    a,b,c=bits[i:i+3]; vals={'AND':a&b,'OR':a|b,'XOR':a^b,'NAND':1-(a&b),'NOT':1-a}
    lg=min(vals,key=lambda k:abs(vals[k]-c)); q=qg[(i+int(abs(phase[i])*1000))%len(qg)]
    gates.append({'node':i,'logic':lg,'quantum_inspired':q,'state':[int(a),int(b),int(c)]})
json.dump(gates,open(GHOST/'circuits'/'gates.json','w'),indent=2)
F={'AND':220,'OR':247,'XOR':277,'NAND':294,'NOT':330,'H':392,'X':440,'Y':466,'Z':494,'RX':523,'RY':587,'RZ':659,'CNOT':698}
wav(GHOST/'audio'/'circuit.wav',concat([tone(F[g['logic']],.045)+tone(F[g['quantum_inspired']],.045,.18) for g in gates[:96]],.006))

# Odd characters -> qubit-style Bloch encoding
symbols='⚛️👻🌀∑∆ψφλ⊕⊗⟂∞𓂀◊⧉⟁☍'
odd=[]; audio=[]
for ch in symbols:
    cp=ord(ch); theta=(cp%1009)/1009*math.pi; phi=((cp//7)%1021)/1021*2*math.pi
    alpha=math.cos(theta/2); beta=[math.sin(theta/2)*math.cos(phi),math.sin(theta/2)*math.sin(phi)]
    odd.append({'char':ch,'codepoint':cp,'theta':theta,'phi':phi,'alpha':alpha,'beta_re':beta[0],'beta_im':beta[1]})
    audio.append(tone(180+(cp%72)*9,.11,.4,phi))
json.dump(odd,open(GHOST/'patterns'/'odd_char_qubits.json','w'),ensure_ascii=False,indent=2); wav(GHOST/'audio'/'odd_chars_qubits.wav',concat(audio,.018))

# Payload / SHA256 / 13D fold
payload=np.column_stack((amp,phase,strength,degree)).astype('<f8').tobytes(); digest=hashlib.sha256(payload).hexdigest(); raw=bytes.fromhex(digest)
dims=[]
for i in range(13):
    j=(2*i)%32; v=int.from_bytes(raw[j:j+2],'big'); dims.append(2*v/65535-1)
lat=90*dims[1]; lon=180*dims[0]; alt=10000*dims[2]; time_index=(int(digest[-8:],16)%31557600)
hashmap={'sha256':digest,'dimensions':dims,'projection':{'longitude':lon,'latitude':lat,'altitude_m':alt,'time_index_s':time_index}}
json.dump(hashmap,open(GHOST/'hashes'/'spacetime_hash.json','w'),indent=2)
with open(GHOST/'13d'/'folded_13d.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['dimension','value']);w.writerows((i+1,v) for i,v in enumerate(dims))
kml=f'''<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>QAI V3 Hash Projection</name><Placemark><name>SHA256 numerical projection</name><description>Simulation/art coordinate derived deterministically from SHA-256; not a physical detection.</description><Point><coordinates>{lon},{lat},{alt}</coordinates></Point></Placemark></Document></kml>'''
(GHOST/'kml'/'qai_hash_projection.kml').write_text(kml)

# Magic-byte sonification: bytes from payload SHA digest and common file-signature motifs as symbolic references
common_magic={'PNG':'89504e470d0a1a0a','PDF':'25504446','ZIP':'504b0304','GZIP':'1f8b','ELF':'7f454c46','WAV':'52494646'}
magic_records=[]; magic_parts=[]
for idx,b in enumerate(raw):
    freq=160+(b/255)*1760; phase0=(idx%8)/8*2*math.pi; magic_records.append({'index':idx,'byte':b,'hex':f'{b:02x}','freq_hz':freq}); magic_parts.append(tone(freq,.065,.32,phase0))
json.dump({'sha256_bytes':magic_records,'reference_magic_signatures':common_magic},open(GHOST/'magic_bytes'/'magic_bytes.json','w'),indent=2)
wav(GHOST/'audio'/'magic_bytes.wav',concat(magic_parts,.006))

# Pattern labels
z=(amp-amp.mean())/(amp.std()+1e-12); hot=np.where(z>1.5)[0]; islands=[]
for n in hot:
    if not islands or n>islands[-1][-1]+1:islands.append([int(n)])
    else:islands[-1].append(int(n))
grad=np.abs(np.gradient(amp)); plasma=np.argsort(grad)[-16:][::-1].tolist()
edges=np.argwhere(np.triu(A<0,1)); dark=sorted(([int(i),int(j),float(A[i,j])] for i,j in edges),key=lambda x:x[2])[:64]
score=np.abs(z)+np.abs((strength-strength.mean())/(strength.std()+1e-12)); rare=np.argsort(score)[-16:][::-1]
particles=[{'node':int(i),'score':float(score[i]),'label':f'XQ-{rank:02d}'} for rank,i in enumerate(rare,1)]
rare_nodes={int(i) for i in rare}; overlaps=[{'a':i,'b':j,'weight':w,'rare_endpoint':[n for n in (i,j) if n in rare_nodes]} for i,j,w in dark if i in rare_nodes or j in rare_nodes]
report={'definitions':{'plasma':'high numerical amplitude-gradient nodes','dark_links':'negative-weight synthetic graph edges','exotic_particles':'rare statistical feature clusters; not physical particles','islands':'contiguous high-amplitude node runs','magic_bytes':'SHA-256 digest bytes sonified as deterministic pitches','harmonic_bridges':'musical interval constructions from numerical ratios'},'islands':islands,'plasma_nodes':plasma,'dark_links':dark,'rare_clusters':particles,'rare_dark_overlaps':overlaps}
json.dump(report,open(GHOST/'patterns'/'pattern_report.json','w'),indent=2)

# Pattern + inverted sonification
pattern_parts=[tone(240+7*i,.07,.35) for i in plasma]+[tone(120+3*(abs(i-j)%80),.05,.25,math.pi) for i,j,_ in dark[:32]]
wav(GHOST/'audio'/'patterns_plasma_dark_rare.wav',concat(pattern_parts,.008))
inv=-psi; inv_audio=[tone(160+900*abs(inv[i]),.045,.35,np.angle(inv[i])) for i in range(96)]
wav(GHOST/'inverted'/'inverted_field.wav',concat(inv_audio,.004))

# Rare-node <-> dark-link stereo sonification
left=[]; right=[]
for o in overlaps:
    rare_score=max(score[n] for n in o['rare_endpoint']); mag=abs(o['weight'])
    left.append(tone(220+rare_score*90,.10,.34))
    right.append(tone(180+mag*170,.10,.34,math.pi))
rare_audio=concat(left,.008); dark_audio=concat(right,.008)
stereo_wav(GHOST/'audio'/'rare_dark_overlap_stereo.wav',rare_audio,dark_audio)

# Harmonic bridges from 13D magnitudes + musically stable ratios
ratios=[3/2,4/3,5/4,6/5,8/5,9/8]
bridges=[]; bridge_audio=[]
for i,d in enumerate(dims):
    ratio=ratios[int(abs(d)*1000)%len(ratios)]; root=180+abs(d)*420; bridges.append({'dimension':i+1,'value':d,'root_hz':root,'ratio':ratio,'bridge_hz':root*ratio}); bridge_audio.append(bridge_tone(root,ratio,.16,.27))
json.dump(bridges,open(GHOST/'bridges'/'harmonic_bridges.json','w'),indent=2)
wav(GHOST/'audio'/'harmonic_bridges.wav',concat(bridge_audio,.02))

manifest={'seed':SEED,'sample_rate':SR,'nodes':N,'sha256':digest,'gate_count':len(gates),'island_count':len(islands),'plasma_count':len(plasma),'dark_link_count':len(dark),'rare_cluster_count':len(particles),'rare_dark_overlap_count':len(overlaps),'ghost_directories':[str(d.relative_to(ROOT)) for d in DIRS],'audio':['circuit.wav','odd_chars_qubits.wav','magic_bytes.wav','patterns_plasma_dark_rare.wav','rare_dark_overlap_stereo.wav','harmonic_bridges.wav','inverted_field.wav']}
json.dump(manifest,open(OUT/'manifest.json','w'),indent=2)
print('╔════ ⚛️ QAI V3.1 COMPLETE ════╗')
print('SHA256:',digest);print('13D:',*[round(x,5) for x in dims]);print('KML projection:',round(lat,5),round(lon,5),round(alt,2));print('gates:',len(gates),'islands:',len(islands),'dark links:',len(dark),'rare clusters:',len(particles));print('rare↔dark overlaps:',len(overlaps));print('magic bytes sonified:',len(raw));print('harmonic bridges:',len(bridges));print('👻 ghost tree:',GHOST);print('🎵 V3.1 WAV sonifications written');print('NOTE: named phenomena are simulation labels, not physical detections.')
