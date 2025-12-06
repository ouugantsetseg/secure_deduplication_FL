# DMPF Python Bindings

This directory contains Python bindings for the DMPF (Distributed Multi-Point Function) library.

## Building the Bindings

### Prerequisites

1. Install Rust and Cargo:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

2. Install PyO3 development tools:
```bash
pip install maturin
```

### Building

1. Clone the DMPF repository:
```bash
cd dmpf_bindings
git clone https://github.com/MatanHamilis/dmpf.git
```

2. Build the Python bindings:
```bash
cd dmpf
# Add PyO3 bindings (see Cargo.toml below)
maturin develop --release
```

3. Test the installation:
```python
import dmpf_py
print("DMPF bindings installed successfully!")
```

## Usage

```python
from ep_mpd import MultiPartyDeduplicator, EgPsiType, EgPsiDataType

# Use DMPF-based Type 2
mpd = MultiPartyDeduplicator(
    client_data=[[1,2,3], [3,4,5], [1,5,7]],
    data_type=EgPsiDataType.INT,
    eg_type=EgPsiType.TYPE2_DMPF  # New DMPF-based protocol
)
mpd.deduplicate()
```

## Architecture

- `dmpf_py/`: Rust crate with PyO3 bindings
- `python_wrapper.py`: Pure Python fallback interface
- Integration with EP-MPD via `ep_mpd/eg_psi/type2_dmpf/`

## Performance

DMPF-based Type 2 is expected to be 3-5x faster than OPRF-based Type 2 for large sets (>10K elements).
