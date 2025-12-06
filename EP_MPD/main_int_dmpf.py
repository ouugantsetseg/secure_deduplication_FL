#!/usr/bin/env python3
"""
Test script for DMPF-based Type 2 deduplication protocol.

This demonstrates the usage of the new TYPE2_DMPF protocol which uses
Distributed Multi-Point Functions for more efficient deduplication
compared to OPRF-based TYPE2.

Usage:
    python main_int_dmpf.py --num-clients 10 --num-ele 1000 --dup-per 0.3
"""

from ep_mpd import MultiPartyDeduplicator, EgPsiType, EgPsiDataType, create_int_elements_pairwise
import random
import argparse
import time

parser = argparse.ArgumentParser(description="Runs the EP-MPD deduplication protocol with DMPF")
parser.add_argument('--num-clients', type=int, help="Number of clients (Integer). Default is 10.", default=10)
parser.add_argument('--num-ele', type=int, help="Number of elements in each client's dataset (Integer). Default is 10.", default=10)
parser.add_argument('--seed', type=int, help="Random seed for dataset creation (Integer). Default is 42.", default=42)
parser.add_argument('--dup-per', type=float, help="Percentage of duplicates (Between 0.0 and 1.0). Default is 0.3.", default=0.3)
parser.add_argument('--compare', action='store_true', help="Compare TYPE2_DMPF with TYPE2 OPRF")

args = parser.parse_args()

num_elements = args.num_ele
num_clients = args.num_clients
dup_per = args.dup_per

random.seed(args.seed)

print("=" * 80)
print("EP-MPD Protocol with DMPF (Distributed Multi-Point Functions)")
print("=" * 80)
print(f"\nConfiguration:")
print(f"  - Clients: {num_clients}")
print(f"  - Elements per client: {num_elements}")
print(f"  - Duplication percentage: {dup_per * 100}%")
print(f"  - Random seed: {args.seed}")
print()

# Create client data with pairwise duplicates
client_data = []
client_data_dict = create_int_elements_pairwise(num_clients, num_elements, dup_per)

for i in client_data_dict:
    client_data.append(client_data_dict[i])

# Calculate expected results
non_duplicated_list = []
for data in client_data:
    non_duplicated_list.extend(data)

print(f"Total data points (with duplicates): {len(non_duplicated_list)}")
print(f"Unique data points (expected): {len(set(non_duplicated_list))}")
print()

# Run DMPF-based Type 2 deduplication
print("-" * 80)
print("Running TYPE2_DMPF (DMPF-based protocol)...")
print("-" * 80)

start_time = time.time()

mpd_dmpf = MultiPartyDeduplicator(
    client_data=client_data, 
    data_type=EgPsiDataType.INT, 
    eg_type=EgPsiType.TYPE2_DMPF
)
mpd_dmpf.deduplicate()

dmpf_time = time.time() - start_time

mpd_full_dataset = mpd_dmpf.get_combined_dataset()

# Verify correctness
client_data_full = []
for data in client_data:
    client_data_full += data
client_data_full = list(set(client_data_full))
client_data_full.sort()

mpd_full_dataset.sort()

# Check if results match expected
try:
    for x, y in zip(client_data_full, mpd_full_dataset):
        assert x == y
    
except AssertionError:
    print("✗ Correctness check FAILED: Mismatch in deduplicated output")
    print(f"  Expected {len(client_data_full)} elements, got {len(mpd_full_dataset)}")

print(f"\nDMPF Protocol Results:")
print(f"  - Total time: {dmpf_time:.4f} seconds")
print(f"  - Deduplicated elements: {len(mpd_full_dataset)}")
print()

mpd_dmpf.print_timing_stats()

# Optional: Compare with original TYPE2 (OPRF)
if args.compare and num_elements < 10000:  # Only compare for reasonable sizes
    print("\n" + "=" * 80)
    print("Running TYPE2 (OPRF-based protocol) for comparison...")
    print("=" * 80)
    
    start_time = time.time()
    
    mpd_oprf = MultiPartyDeduplicator(
        client_data=client_data,
        data_type=EgPsiDataType.INT,
        eg_type=EgPsiType.TYPE2
    )
    mpd_oprf.deduplicate()
    
    oprf_time = time.time() - start_time
    
    print(f"\nOPRF Protocol Results:")
    print(f"  - Total time: {oprf_time:.4f} seconds")
    print()
    
    mpd_oprf.print_timing_stats()
    
    print("\n" + "=" * 80)
    print("Performance Comparison:")
    print("=" * 80)
    print(f"  TYPE2_DMPF time: {dmpf_time:.4f}s")
    print(f"  TYPE2_OPRF time: {oprf_time:.4f}s")
    if oprf_time > 0:
        speedup = oprf_time / dmpf_time
        print(f"  Speedup: {speedup:.2f}x")
        if speedup > 1:
            print(f"  ✓ DMPF is {speedup:.2f}x faster!")
        else:
            print(f"  Note: OPRF faster for small sets (overhead of DMPF setup)")
else:
    print("\n" + "-" * 80)


print("\n" + "=" * 80)
print("Summary:")
print("=" * 80)
print(f"Protocol: TYPE2_DMPF")
print(f"Total data with duplicates: {len(non_duplicated_list)}")
print(f"Total data without duplicates: {len(mpd_full_dataset)}")
print(f"Duplicates removed: {len(non_duplicated_list) - len(mpd_full_dataset)}")
print(f"Deduplication rate: {(1 - len(mpd_full_dataset)/len(non_duplicated_list))*100:.2f}%")
print("=" * 80)
