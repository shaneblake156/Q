#!/usr/bin/env python3
"""Hardware-aware QAI core.

Detects real host capabilities and selects a supported backend.
Intel CPU features are treated as CPU/control-plane capabilities;
CUDA is used only when a working NVIDIA/PyTorch CUDA backend is present.
No NPU/iGPU acceleration is assumed unless exposed by the OS.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
from pathlib import Path

try:
    import torch
except Exception:
    torch = None


def sh(args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=3).strip()
    except Exception:
        return ""


def detect_cpu():
    model = "unknown"
    vendor = "unknown"
    try:
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name') and model == 'unknown':
                model = line.split(':', 1)[1].strip()
            elif line.startswith('vendor_id') and vendor == 'unknown':
                vendor = line.split(':', 1)[1].strip()
    except Exception:
        pass
    return {
        'model': model,
        'vendor': vendor,
        'logical_cpus': os.cpu_count(),
        'kvm_intel_loaded': Path('/sys/module/kvm_intel').exists(),
        'intel_rapl_loaded': Path('/sys/module/intel_rapl_common').exists() or Path('/sys/module/intel_rapl_msr').exists(),
    }


def detect_accel():
    npu = Path('/dev/accel').exists()
    i915 = Path('/sys/module/i915').exists()
    xe = Path('/sys/module/xe').exists()
    return {
        'intel_npu_device': npu,
        'intel_i915_loaded': i915,
        'intel_xe_loaded': xe,
    }


def detect_cuda():
    out = {
        'torch_present': torch is not None,
        'cuda_available': False,
        'device': None,
        'capability': None,
        'torch_version': getattr(torch, '__version__', None) if torch else None,
        'cuda_runtime': getattr(torch.version, 'cuda', None) if torch else None,
    }
    if torch is not None and torch.cuda.is_available():
        out.update({
            'cuda_available': True,
            'device': torch.cuda.get_device_name(0),
            'capability': tuple(torch.cuda.get_device_capability(0)),
        })
    return out


def choose_backend(cuda):
    if cuda.get('cuda_available'):
        return 'cuda'
    return 'cpu'


def benchmark(device: str, n: int = 1024, repeats: int = 8):
    if torch is None:
        return {'status': 'torch unavailable'}
    dev = torch.device(device)
    x = torch.randn((n, n), device=dev)
    y = torch.randn((n, n), device=dev)
    if device == 'cuda':
        torch.cuda.synchronize()
    import time
    t0 = time.perf_counter()
    z = None
    for _ in range(repeats):
        z = x @ y
    if device == 'cuda':
        torch.cuda.synchronize()
    dt = time.perf_counter() - t0
    return {
        'matrix_n': n,
        'repeats': repeats,
        'seconds': dt,
        'ops_per_second_est': (2 * n**3 * repeats) / max(dt, 1e-12),
        'checksum': float(z.mean().detach().cpu()) if z is not None else None,
    }


def main():
    cpu = detect_cpu()
    accel = detect_accel()
    cuda = detect_cuda()
    backend = choose_backend(cuda)
    report = {
        'platform': platform.platform(),
        'cpu': cpu,
        'acceleration': accel,
        'cuda': cuda,
        'selected_backend': backend,
        'benchmark': benchmark(backend),
        'interpretation': {
            'intel_role': 'CPU/orchestration/RAPL/KVM unless a real iGPU/NPU device is exposed',
            'gpu_role': 'tensor-heavy QAI kernels when CUDA is available',
            'npu_role': 'disabled unless /dev/accel is present',
        },
    }
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
