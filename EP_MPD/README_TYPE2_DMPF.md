# DMPF-Based Multi-Party Deduplication

## Overview

This is an enhanced implementation of the EP-MPD (Efficient Private Multi-Party Deduplication) protocol that uses **Distributed Multi-Point Functions (DMPF)** instead of traditional OPRF (Oblivious Pseudorandom Functions) for Type 2 deduplication.



---

## Table of Contents

- [Features](#features)
- [Performance](#performance)
- [Installation](#installation)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Benchmarking](#benchmarking)
- [Technical Details](#technical-details)
- [Limitations](#limitations)
- [Citation](#citation)

---

## Features

### Privacy Features

- **Same Security Model**: Maintains original EP-MPD privacy guarantees
- **Secret Sharing**: DMPF keys use cryptographic secret sharing (XOR-based)
- **Semi-Trusted Third Party**: TP generates keys without learning actual elements


### DMPF Type Performance

| DMPF Type | Element Range | Evaluation Time | Key Size | Best For |
|-----------|---------------|-----------------|----------|----------|
| **DpfDmpf** | < 5,000 | Medium | Large | Small sets |
| **OkvsDmpf** | 5,000 - 4,999,999 | **0.03ms**  | Medium | Most use cases |
| **BatchCodeDmpf** | ≥ 5,000,000 | 182ms | Small | Massive datasets |

---

## Installation

### Prerequisites

- **Python**: 3.10
- **Rust**: Nightly toolchain
- **Maturin**: For building Rust-Python bindings
- **Conda** (recommended): For environment management

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd deduplication/EP_MPD
```

### Step 2: Create Conda Environment

```bash
conda create -n epmpd python=3.10
conda activate epmpd
```

### Step 3: Install Rust Nightly

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup install nightly
rustup default nightly
```

### Step 4: Install Maturin

```bash
pip install maturin
```

### Step 5: Build DMPF Bindings

```bash
cd dmpf_bindings
maturin develop --release
cd ..
```

### Step 6: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Verification

```bash
python -c "from dmpf_bindings.python_wrapper import DMPF_AVAILABLE; print('DMPF Available:', DMPF_AVAILABLE)"
```

Should output: `DMPF Available: True`

---

## Usage

### Basic Usage

```bash
python main_int_dmpf.py --num-clients 10 --num-ele 32768 --dup-per 0.3
```

**Parameters:**
- `--num-clients`: Number of participating clients (default: 10)
- `--num-ele`: Number of elements per client (default: 10)
- `--num-seed`: Random seed for reproducibility (default: 42)
- `--dup-per`: Duplication percentage between clients (0.0-1.0, default: 0.3)


### Example Commands

**Small Scale Test:**
```bash
python main_int_dmpf.py --num-clients 5 --num-ele 1000 --dup-per 0.3
```

**Medium Scale Test:**
```bash
python main_int_dmpf.py --num-clients 10 --num-ele 32768 --dup-per 0.3
```

**Large Scale Test:**
```bash
python main_int_dmpf.py --num-clients 25 --num-ele 100000 --dup-per 0.5
```

**Compare with OPRF:**
```bash
python main_int_dmpf.py --num-clients 5 --num-ele 5000 --dup-per 0.3 --compare
```

### Programmatic Usage

```python
from ep_mpd import MultiPartyDeduplicator, EgPsiType, EgPsiDataType

#  Client data
client_data = [
    [100, 200, 300, 400],  # Client 0
    [200, 250, 300, 350],  # Client 1
    [150, 250, 400, 450],  # Client 2
]

# Create deduplicator with DMPF
mpd = MultiPartyDeduplicator(
    client_data=client_data,
    data_type=EgPsiDataType.INT,
    eg_type=EgPsiType.TYPE2_DMPF
)

# Run deduplication
mpd.deduplicate()

# Get results
deduplicated_data = mpd.get_combined_dataset()
print(f"Deduplicated elements: {len(deduplicated_data)}")
```

---

## How It Works

### Protocol Flow

```

 PHASE 1: Initialization                                         
   - Create clients and semi-trusted third party                
   - Each client has dataset S_i                                 


 PHASE 2: DMPF Key Generation                                    
  For each client:                                              
   1. Encode elements to domain [0, 2^20)                        
   2. Create points: [(ele_1, 1), (ele_2, 1), ...]              
   3. TP generates DMPF keys: (key_0, key_1)                     
   4. Client stores both keys                                    


 PHASE 3: Hierarchical Deduplication (Binary Tree)              
   Same as original EP-MPD:                                      
   - Recursive divide-and-conquer                                
   - Group 0 (left) vs Group 1 (right) at each level            
   - log₂(n) rounds for n clients                                


 PHASE 4: Key Exchange & Evaluation                             
   For each comparison:                                          
   1. Group 1 → Group 0: Send DMPF keys                          
   2. Group 0 evaluates:                                         
      For each element e:                                        
        result = key_0.eval(e) ⊕ key_1.eval(e)                  
        if result == 1: mark e as duplicate                      
   3. Group 0 removes duplicates                                 

                            

 PHASE 5: Result Collection                                      
   - Combine remaining elements from all clients                
   - Return deduplicated dataset                                 

```



## Configuration

### Domain Size

The domain size determines the input space for DMPF functions:

**File:** `ep_mpd/eg_psi/type2_dmpf/client.py` (lines 129-132)

```python
def _get_domain_bits(self) -> int:
    if self.data_type == EgPsiDataType.INT:
        return 20  # 2^20 = 1,048,576 (adjust for your data range)
    else:
        return 24  # 2^24 = 16,777,216 (for strings)
```

**Trade-offs:**
- **Larger domain** = fewer collisions, slower evaluation (deeper tree)
- **Smaller domain** = faster evaluation, more collisions

### DMPF Type Thresholds

**File:** `dmpf_bindings/src/lib.rs` (lines 116-117)

```rust
let use_okvs = num_points >= 5000 && num_points < 500000;
let use_batch = num_points >= 500000;
```

**Customization:**
```rust
// For a specific use case, adjust thresholds:
let use_okvs = num_points >= 3000 && num_points < 1000000;  // Wider OkvsDmpf range
```

After changing, rebuild:
```bash
cd dmpf_bindings
maturin develop --release
```

---

## Benchmarking

### Running Benchmark Suite

```bash
cd run_small_scale
bash run.sh
```

This runs:
- **Effect of Client Count**: 5, 10, 15, 20, 25 clients (32K elements, 30% dup)
- **Effect of Dataset Size**: 32, 128, 1K, 8K, 32K elements (10 clients, 30% dup)
- **Effect of Duplication**: 10%, 30%, 50%, 70%, 90% (10 clients, 32K elements)

Results saved to `run_small_scale/type2_runs/*.log`

### Plotting Results

```bash
cd run_small_scale
python plot_epmpd.py  # Generate performance graphs
```


---

## Technical Details

### DMPF Implementation

**Library:** https://github.com/MatanHamilis/dmpf (IEEE S&P 2025)

**Components:**
- **PyO3 Bindings**: Rust ↔ Python interface
- **Three DMPF Types**: DpfDmpf, OkvsDmpf, BatchCodeDmpf
- **Auto-Selection**: Based on element count
- **ChaCha8Rng**: Cryptographic random number generator

### DMPF Key Structure

```rust
struct DmpfKey {
    seed: u128,           // 128-bit pseudorandom seed
    sign: bool,           // Sign bit
    okvs: OKVS,          // Oblivious Key-Value Store (shared)
    corrections: Vec,     // Correction words for tree traversal
}
```

### Evaluation Process

```
Input: element x, DMPF keys (key_0, key_1)

1. Encode x to domain: x' = x mod 2^domain_bits

2. Evaluate key_0:
   - Start with seed_0
   - Traverse 20-level binary tree (for domain_bits=20)
   - Apply corrections from OKVS at each level
   - Get output_0

3. Evaluate key_1:
   - Start with seed_1 (different!)
   - Traverse same tree structure
   - Use same OKVS corrections
   - Get output_1

4. Reconstruct: result = output_0 ⊕ output_1
   - If result == 1: x is in the programmed set
   - If result == 0: x is not in the set
```



## Limitations

### Current Implementation

1. **Full Key Disclosure**: Clients send both DMPF key shares
   - Suitable for cooperative deduplication
   - Not ideal for adversarial settings

2. **Fixed Domain Size**: Domain hardcoded at initialization
   - May cause collisions for large data ranges
   - No automatic adaptation


3. **Memory Usage**: O(n) per client for encodings and keys
   - Can be significant for very large sets


---


## Citation

If you use this implementation in your research, please cite:

```bibtex
@inproceedings{hamilis2025dmpf,
  title={Distributed Multi-Point Functions},
  author={Hamilis, Matan and others},
  booktitle={IEEE Symposium on Security and Privacy (S\&P)},
  year={2025}
}

@article{epmpd,
  title={EP-MPD: Efficient Private Multi-Party Deduplication},
  author={Original EP-MPD Authors},
  year={2023}
}
```

---


## Acknowledgments

- **DMPF Library**: Matan Hamilis et al. (IEEE S&P 2025)
- **Original EP-MPD**: Original authors of the Privacy-Preserving Data Deduplication for Enhancing Federated Learning of Language Model
- **PyO3**: Rust-Python binding framework


