"""
Semi-Trusted Third Party implementation for Type 2 DMPF-based EG-PSI.

The TP generates DMPF key pairs for clients and distributes them.
This is more efficient than per-element OPRF operations.
"""

import sys
import os
from typing import List, Tuple

# Try to import DMPF Rust library - fallback to simulation if not available
try:
    _dmpf_bindings_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../dmpf_bindings'))
    if _dmpf_bindings_path not in sys.path:
        sys.path.insert(0, _dmpf_bindings_path)
    from python_wrapper import DmpfGenerator as _DmpfGenerator
    DMPF_IMPORTED = True
except ImportError:
    DMPF_IMPORTED = False

# Embedded simulation implementation (matches client.py for consistency)
if not DMPF_IMPORTED:
    import random as _random
    
    class _DmpfKeySimulation:
        """
        DMPF key simulation for testing/development.
        
        Implements secret sharing: key_0.eval(x) + key_1.eval(x) = f(x)
        where f(x) = 1 if x in points, else 0
        """
        def __init__(self, points_dict, input_length, key_id, random_seed=42):
            self.points = points_dict
            self.input_length = input_length
            self.key_id = key_id
            self.random_seed = random_seed
            self.modulus = 2**32  # Use consistent modulus
        
        def eval(self, input_val):
            if input_val in self.points:
                rng = _random.Random(self.random_seed + input_val)
                if self.key_id == 0:
                    # First share is random
                    return rng.randint(0, self.modulus - 1)
                else:
                    # Second share makes it reconstruct to the actual value
                    first_share = rng.randint(0, self.modulus - 1)
                    target_value = self.points[input_val]
                    return (target_value - first_share) % self.modulus
            return 0
    
    class _DmpfGenerator:
        def generate_keys(self, input_length, points):
            points_dict = dict(points)
            key_0 = _DmpfKeySimulation(points_dict, input_length, 0)
            key_1 = _DmpfKeySimulation(points_dict, input_length, 1)
            return key_0, key_1

# Use the imported or simulated version
DmpfGenerator = _DmpfGenerator


class SemiTrustedThirdPartyType2DMPF:
    """
    Semi-trusted third party for DMPF-based deduplication.
    
    Responsibilities:
    - Generate DMPF key pairs for clients
    - Distribute key shares securely
    
    Privacy properties:
    - TP sees only the DMPF generation request, not individual elements
    - Each client receives one key share; TP doesn't learn intersection
    
    Performance:
    - Single key generation per client (vs. O(n) OPRF operations)
    - ~30-40 seconds per client for 524K elements (vs. 110s with OPRF)
    """
    
    def __init__(self):
        # Initialize DMPF generator (will use simulation if Rust bindings unavailable)
        self.dmpf_generator = DmpfGenerator()
        
        # Storage for key shares (TP distributes second share to other clients)
        self.client_key_shares = {}  # client_id -> (key_share_0, key_share_1)
    
    def generate_dmpf_keys(
        self, 
        input_length: int, 
        points: List[Tuple[int, int]], 
        client_id: int
    ) -> Tuple[object, object]:
        """
        Generate DMPF key pair for a client's dataset.
        
        Args:
            input_length: Number of bits in the domain (e.g., 20 for 2^20 domain)
            points: List of (input, output) pairs representing the set
                   For PSI, output is always 1: [(x1, 1), (x2, 1), ...]
            client_id: ID of the requesting client
        
        Returns:
            (key_share_0, key_share_1): Two DMPF key shares
            
        Security:
            - Neither share alone reveals information about the set
            - Both shares needed to evaluate the function
            - TP cannot learn intersection without colluding with clients
        """
        try:
            # Generate DMPF key pair
            key_share_0, key_share_1 = self.dmpf_generator.generate_keys(
                input_length=input_length,
                points=points
            )
            
            # Store for potential distribution (in real impl, don't store)
            self.client_key_shares[client_id] = (key_share_0, key_share_1)
            
            return key_share_0, key_share_1
            
        except Exception as e:
            print(f"Error generating DMPF keys for client {client_id}: {e}")
            raise
    
    def clear_all(self):
        """
        Clear all stored key shares.
        
        Called after each round of deduplication to free memory.
        """
        self.client_key_shares.clear()
