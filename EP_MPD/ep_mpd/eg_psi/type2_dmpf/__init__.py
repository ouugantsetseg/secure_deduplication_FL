"""
Type 2 DMPF-based EG-PSI implementation.

This module implements the Type 2 Efficient Group Private Set Intersection
protocol using Distributed Multi-Point Functions (DMPF) instead of OPRF.

DMPF provides better performance for large sets by representing the entire
set as a compact function rather than encrypting each element individually.
"""

from .client import ClientType2DMPF
from .tp import SemiTrustedThirdPartyType2DMPF

__all__ = ['ClientType2DMPF', 'SemiTrustedThirdPartyType2DMPF']
