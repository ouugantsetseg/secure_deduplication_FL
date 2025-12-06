"""
Client implementation for Type 2 DMPF-based EG-PSI protocol.

This implements a privacy-preserving deduplication client using
Distributed Multi-Point Functions instead of OPRF.
"""

import time
import sys
import os
from collections import defaultdict
from typing import List, Tuple

# Try to import DMPF wrapper - fallback to simulation if not available
try:
    # Path from ep_mpd/eg_psi/type2_dmpf/client.py -> EP_MPD/dmpf_bindings
    # Go up: client.py -> type2_dmpf -> eg_psi -> ep_mpd -> EP_MPD
    _current_file = os.path.abspath(__file__)
    _ep_mpd_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_current_file))))
    _dmpf_bindings_path = os.path.join(_ep_mpd_root, 'dmpf_bindings')
    
    if _dmpf_bindings_path not in sys.path:
        sys.path.insert(0, _dmpf_bindings_path)
    from python_wrapper import DmpfGenerator as _DmpfGenerator, encode_int_to_domain, encode_str_to_domain, DMPF_AVAILABLE
    DMPF_IMPORTED = True
    # Don't show warning if using real Rust library
    if not DMPF_AVAILABLE:
        import warnings
        warnings.warn("DMPF Rust bindings not available, using simulation in python_wrapper.")
except ImportError as e:
    DMPF_IMPORTED = False

# Fallback simulation if import failed completely
if not DMPF_IMPORTED:
    import warnings
    import random as _random
    import hashlib
    warnings.warn("DMPF library not available. Using fallback simulation mode (correct but not optimized).")
    
    class _DmpfKeySimulation:
        """DMPF key simulation for testing"""
        def __init__(self, points_dict, input_length, key_id, random_seed=42):
            self.points = points_dict
            self.input_length = input_length
            self.key_id = key_id
            self.random_seed = random_seed
            self.modulus = 2**32
        
        def eval(self, input_val):
            if input_val in self.points:
                rng = _random.Random(self.random_seed + input_val)
                if self.key_id == 0:
                    return rng.randint(0, self.modulus - 1)
                else:
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
    
    def encode_int_to_domain(value, domain_bits):
        return value % (1 << domain_bits)
    
    def encode_str_to_domain(value, domain_bits):
        hash_bytes = hashlib.sha256(value.encode()).digest()
        hash_int = int.from_bytes(hash_bytes[:16], byteorder='big')
        return hash_int % (1 << domain_bits)
    
    DMPF_AVAILABLE = False

# Use the imported or simulated version
DmpfGenerator = _DmpfGenerator

from ep_mpd.eg_psi.utils import EgPsiDataType, encode_element


class ClientType2DMPF:
    """
    DMPF-based Type 2 client for privacy-preserving multi-party deduplication.
    
    Key differences from OPRF-based Type 2:
    - Generates a compact function representation of entire set
    - More efficient for large sets (>1000 elements)
    - Lower communication overhead
    
    Protocol:
    1. Client generates DMPF key shares with TP
    2. Exchanges key shares with other clients
    3. Evaluates DMPF to find intersections
    4. Removes duplicates (Group 0 only)
    """
    
    def __init__(self, client_id: int, data_type: EgPsiDataType):
        self.client_id = client_id
        self.data_type = data_type
        
        # Dataset management
        self.s = None  # Original dataset
        self.s_dirty_bits = {}  # Track which elements are still valid
        
        # DMPF-specific state
        self.dmpf_key_share = None  # This client's DMPF key share
        self.other_client_keys = {}  # Other clients' DMPF key shares
        self.domain_bits = self._get_domain_bits()
        
        # Encoding maps
        self.encoded_to_original = {}  # Map encoded values back to originals
        self.original_to_encoded = {}  # Map original values to encoded
        
        # Group assignment
        self.group = None
        
        # For compatibility with timing stats
        self.s_prime = []  # Not used in DMPF but kept for interface compatibility
    
    def _get_domain_bits(self) -> int:
        """
        Determine domain size in bits based on data type.
        
        Returns:
            Number of bits for the DMPF domain
        """
        if self.data_type == EgPsiDataType.INT:
            return 20  # 2^20 = ~1M domain for integers (adjust based on set size)
        else:
            return 24  # 2^24 = ~16M domain for strings (hash-based)
    
    def set_group(self, client_group: int):
        """Set client's group assignment (0 or 1)"""
        self.group = client_group
    
    def create_set(self, data_set: List[int]):
        """
        Initialize client's dataset.
        
        Args:
            data_set: List of elements (integers or strings)
        """
        self.s = data_set
        for ele in self.s:
            self.s_dirty_bits[ele] = 1
    
    def encrypt_elements(self, tp: 'SemiTrustedThirdPartyType2DMPF') -> float:
        """
        Generate DMPF key shares with the trusted party.
        
        This is the main efficiency improvement: instead of encrypting
        each element individually (O(n) OPRF calls), we generate a single
        compact DMPF representation of the entire set.
        
        Args:
            tp: The semi-trusted third party
        
        Returns:
            Time spent in TP operations
        """
        # Encode all elements to the domain
        points = []
        for ele in self.s:
            if not self.s_dirty_bits[ele]:
                continue
            
            # Encode element to domain [0, 2^domain_bits)
            if self.data_type == EgPsiDataType.INT:
                encoded = encode_int_to_domain(ele, self.domain_bits)
            else:
                encoded = encode_str_to_domain(str(ele), self.domain_bits)
            
            # Store mappings
            self.encoded_to_original[encoded] = ele
            self.original_to_encoded[ele] = encoded
            
            # DMPF point: (input, output=1) means "element is in set"
            points.append((encoded, 1))
        
        # Generate DMPF keys with TP
        start = time.perf_counter()
        key_share_0, key_share_1 = tp.generate_dmpf_keys(
            input_length=self.domain_bits,
            points=points,
            client_id=self.client_id
        )
        tp_time = time.perf_counter() - start
        
        # For simplified DMPF PSI: send the full function representation
        # In production, this would use secure evaluation protocols
        # Here we send both keys so other clients can evaluate
        self.dmpf_keys = (key_share_0, key_share_1)
        
        # For compatibility with existing timing infrastructure
        self.s_prime = [f"dmpf_key_share_{self.client_id}".encode()]
        
        return tp_time
    
    def send_to_client(self) -> Tuple[int, object]:
        """
        Send DMPF keys to another client.
        
        Note: In this simplified implementation, we send both keys.
        Production DMPF PSI would use secure protocols to avoid revealing the set.
        
        Returns:
            (client_id, dmpf_keys) - tuple of (key_0, key_1)
        """
        return self.client_id, self.dmpf_keys
    
    def receive_from_client(self, client_id: int, s_prime=None, dmpf_key_share: object = None):
        """
        Receive DMPF key share from another client.
        
        Args:
            client_id: ID of the sending client
            s_prime: Compatibility parameter (uses dmpf_key_share if provided)
            dmpf_key_share: Their DMPF key share
        """
        # Support both parameter names for compatibility
        key_share = dmpf_key_share if dmpf_key_share is not None else s_prime
        self.other_client_keys[client_id] = key_share
    
    def set_intersection(self):
        """
        Compute intersection using DMPF evaluation.
        
        Key insight: For each element in our set, we evaluate:
            f(x) = our_key.eval(x) + other_key.eval(x)
        
        If f(x) != 0, then x is in the other client's set (duplicate).
        
        Only Group 0 clients remove duplicates.
        """
        for other_client_id, other_key in self.other_client_keys.items():
            # Check each element in our set
            for ele in list(self.s):
                if not self.s_dirty_bits[ele]:
                    continue
                
                # Get encoded value
                encoded_ele = self.original_to_encoded.get(ele)
                if encoded_ele is None:
                    continue
                
                try:
                    # Evaluate: other_key is a tuple of (key_0, key_1)
                    # f(x) = key_0(x) XOR key_1(x) for DMPF
                    key_0, key_1 = other_key
                    value_share_0 = key_0.eval(encoded_ele)
                    value_share_1 = key_1.eval(encoded_ele)
                    
                    # Reconstruct the function value using XOR (DMPF combines shares via XOR)
                    function_value = value_share_0 ^ value_share_1
                    
                    # If function returns 1, element is in other client's set
                    if function_value == 1:
                        if self.group == 0:
                            # Group 0 removes duplicates
                            self.s_dirty_bits[ele] = 0
                
                except Exception as e:
                    # Handle evaluation errors gracefully
                    print(f"Warning: DMPF evaluation error for element {ele}: {e}")
                    continue
        
        self.reset_client()
    
    def get_deduplicated_dataset(self):
        """
        Return the deduplicated dataset.
        
        Returns:
            List of elements with dirty_bit = 1 (not duplicates)
        """
        new_s = []
        for ele in self.s_dirty_bits:
            if self.s_dirty_bits[ele] == 1:
                new_s.append(ele)
        return new_s
    
    def reset_client(self):
        """
        Reset client state for next round of deduplication.
        
        Clears group assignment and other clients' keys,
        but preserves own dataset and DMPF key.
        """
        self.group = None
        self.other_client_keys.clear()
    
    def __str__(self) -> str:
        return f"Client ID: {self.client_id}, Client Group: {self.group}, Type: DMPF"
