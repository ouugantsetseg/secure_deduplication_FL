"""
Python wrapper for DMPF (Distributed Multi-Point Function) library.

This module provides a pure Python interface to the DMPF functionality.
It will attempt to import the compiled Rust bindings (dmpf_py), and fall back
to a simulation mode for development/testing.
"""

import warnings
from typing import List, Tuple
import struct

# Try to import the actual DMPF Rust bindings
try:
    from dmpf_py import DmpfGenerator as RustDmpfGenerator
    from dmpf_py import DmpfKey as RustDmpfKey
    DMPF_AVAILABLE = True
    print("✓ Using optimized Rust DMPF library")
except ImportError:
    DMPF_AVAILABLE = False
    warnings.warn(
        "DMPF Rust bindings not available. Using simulation mode. "
        "Build the bindings with: cd dmpf_bindings && maturin develop --release"
    )


class DmpfKeySimulation:
    """
    Simulation of DMPF key for development/testing.
    This is NOT cryptographically secure - only for testing the interface.
    
    In real DMPF: key_0.eval(x) + key_1.eval(x) = f(x)
    In simulation: We split the output between two shares using XOR-like behavior
    """
    
    def __init__(self, points_dict: dict, input_length: int, key_id: int, random_seed: int = 42):
        self.points = points_dict  # Maps input -> output
        self.input_length = input_length
        self.key_id = key_id  # 0 or 1 for the two shares
        self.random_seed = random_seed
        
    def eval(self, input_val: int) -> int:
        """
        Evaluate DMPF at a single point.
        
        Simulation: Use deterministic pseudo-random splitting
        - If input_val in points: key_0 returns random r, key_1 returns (value - r)
        - If input_val not in points: both return 0
        
        This ensures: key_0.eval(x) + key_1.eval(x) = f(x)
        """
        if input_val in self.points:
            # Use deterministic pseudo-random share
            import random
            rng = random.Random(self.random_seed + input_val)
            
            if self.key_id == 0:
                # First share: random value mod 2^32
                return rng.randint(0, 2**16)
            else:
                # Second share: (output - first_share) to make sum = output
                first_share = rng.randint(0, 2**16)
                return self.points[input_val] - first_share
        return 0
    
    def eval_all(self) -> List[int]:
        """
        Evaluate DMPF at all points in the domain.
        
        Returns list of outputs for domain [0, 2^input_length)
        """
        domain_size = 1 << self.input_length
        result = [0] * domain_size
        for point, value in self.points.items():
            if point < domain_size:
                result[point] = value if self.key_id == 0 else 0
        return result
    
    def point_count(self) -> int:
        """Return number of non-zero points"""
        return len(self.points)
    
    def input_length(self) -> int:
        """Return input length in bits"""
        return self.input_length


class DmpfGenerator:
    """
    DMPF key generation interface.
    
    Wraps either the real Rust implementation or simulation.
    """
    
    def __init__(self, use_simulation: bool = None):
        if use_simulation is None:
            use_simulation = not DMPF_AVAILABLE
        
        self.use_simulation = use_simulation
        
        if not use_simulation and not DMPF_AVAILABLE:
            raise RuntimeError(
                "DMPF Rust bindings not available. "
                "Build them or use use_simulation=True"
            )
        
        if not use_simulation:
            # Initialize the Rust DMPF generator
            self.generator = RustDmpfGenerator()
    
    def generate_keys(
        self, 
        input_length: int, 
        points: List[Tuple[int, int]]
    ) -> Tuple[DmpfKeySimulation, DmpfKeySimulation]:
        """
        Generate a pair of DMPF keys.
        
        Args:
            input_length: Number of bits in the input domain
            points: List of (input, output) pairs where the function is non-zero
        
        Returns:
            (key_0, key_1): Two DMPF key shares
        
        Security property: 
            For any x: key_0.eval(x) + key_1.eval(x) = f(x)
            where f(x) = output if (x, output) in points, else 0
        """
        if self.use_simulation:
            return self._generate_simulated_keys(input_length, points)
        else:
            return self._generate_real_keys(input_length, points)
    
    def _generate_simulated_keys(
        self, 
        input_length: int, 
        points: List[Tuple[int, int]]
    ) -> Tuple[DmpfKeySimulation, DmpfKeySimulation]:
        """Generate simulated DMPF keys for testing"""
        points_dict = dict(points)
        key_0 = DmpfKeySimulation(points_dict, input_length, 0)
        key_1 = DmpfKeySimulation(points_dict, input_length, 1)
        return key_0, key_1
    
    def _generate_real_keys(
        self, 
        input_length: int, 
        points: List[Tuple[int, int]]
    ):
        """Generate real DMPF keys using Rust implementation"""
        # Generate keys using Rust DMPF library
        key_0, key_1 = self.generator.generate_keys(
            input_length=input_length,
            points=points
        )
        
        return key_0, key_1


def encode_int_to_domain(value: int, domain_bits: int) -> int:
    """
    Encode an integer value to fit in the DMPF domain.
    
    Args:
        value: The integer value to encode
        domain_bits: Number of bits in the domain
    
    Returns:
        Encoded value in range [0, 2^domain_bits)
    """
    # For now, use simple modulo encoding
    # In production, use a proper hash function
    return value % (1 << domain_bits)


def encode_str_to_domain(value: str, domain_bits: int) -> int:
    """
    Encode a string value to fit in the DMPF domain.
    
    Args:
        value: The string value to encode
        domain_bits: Number of bits in the domain
    
    Returns:
        Encoded value in range [0, 2^domain_bits)
    """
    # Hash the string to get a fixed-size value
    import hashlib
    hash_bytes = hashlib.sha256(value.encode()).digest()
    
    # Take first domain_bits bits
    hash_int = int.from_bytes(hash_bytes[:16], byteorder='big')
    return hash_int % (1 << domain_bits)


# Export main classes
__all__ = [
    'DmpfGenerator',
    'DmpfKeySimulation',
    'encode_int_to_domain',
    'encode_str_to_domain',
    'DMPF_AVAILABLE'
]
