#!/usr/bin/env python

import getopt, sys

KB = 1024
MB = 1024 * KB
GB = 1024 * MB
TB = 1024 * GB

#------------------------------------------------------------------------------

def compute_hpt_size(total_memory_size, hpt_ratio):
    power_of_two_size = 1 << (total_memory_size.bit_length() - 1)
    if 4 * total_memory_size > 5 * power_of_two_size:
        power_of_two_size <<= 1
    return max(256 * KB, power_of_two_size >> hpt_ratio)

#------------------------------------------------------------------------------

def format_size(bytes, units=GB):
    blocks = bytes / float(units)
    if blocks.is_integer():
        blocks = int(blocks)
    blocks = str(blocks)
    if units == KB:
        blocks += "KB"
    elif units == MB:
        blocks += "MB"
    elif units == GB:
        blocks += "GB"
    elif units == TB:
        blocks += "TB"
    else:
        assert units == 1
    return blocks

#------------------------------------------------------------------------------

def print_help(message):
    if message:
        print("Error: %s" % (message))
    print('''
hpt_for_vpmem.py [options]*
    -h, --help                 Displays the help text.
    -m GB, --memory GB         Desired DRAM memory for the partition, in GB.
    -l [Nx]GB, --lun [Nx]GB    VPMEM LUN size in GB, can be specified multiple
                               times.  Can also be specified with a preceding 
                               replication factor N, as in '3x1000' for three
                               1000GB LUNs.
    -i, --ibmi                 Partition type is IBMi.
    -n, --linux                Partition type is Linux.
    -a, --aix                  Partition type is AIX.

Examples:
    hpt_for_vpmem.py --memory 1000 --lun 6000 --linux
    hpt_for_vpmem.py -m 1000 -l 6000 -n
    hpt_for_vpmem.py --memory 3000 --lun 6000 --lun 5000 --lun 6000 --aix
    hpt_for_vpmem.py --memory 3000 --lun 16x1024 --linux''')
    exit(1)

#------------------------------------------------------------------------------

# Parse the command line options.
try:
    opts, args = getopt.getopt(sys.argv[1:], "hm:l:ina", ["help", "memory=", "lun=", "ibmi", "linux", "aix"])
except getopt.GetoptError as err:
    print_help(str(err))
desired_memory_size = 0
vpmem_size = 0
is_ibmi = False
is_linux = False
is_aix = False
lun_sizes = []
for flag,value in opts:
    if flag == "--help" or flag == "-h":
        print_help("")
    elif flag == "--memory" or flag == "-m":
        desired_memory_size += int(value) * GB
    elif flag == "--lun" or flag == "-l":
        x = value.find("x")
        if x == -1:
            num_luns = 1
            lun_size = int(value) * GB
        else:
            num_luns = int(value[:x])
            lun_size = int(value[x+1:]) * GB
        vpmem_size += num_luns * lun_size
        lun_sizes += [lun_size] * num_luns
    elif flag == "--ibmi" or flag == "-i":
        is_ibmi = True
    elif flag == "--linux" or flag == "-n":
        is_linux = True
    elif flag == "--aix" or flag == "-a":
        is_aix = True
    else:
        print_help("Unrecognized command line option: " + flag)
if args:
    print_help("Unrecognized command line argument: " + str(args))
if desired_memory_size <= 0:
    print_help("Must specify the --memory option")
if vpmem_size < 0:
    print_help("Illegal --lun value")
if is_ibmi + is_linux + is_aix != 1:
    print_help("Must specify exactly one partition type: IBMi, Linux, or AIX")

#------------------------------------------------------------------------------

# Display the input values specified by the user.
hpt_ratio = 6 if is_ibmi else 7
ppt_ratio = 6
print("")
print("Inputs:")
print("    desired_memory_size = %s" % (format_size(desired_memory_size)))
print("    vpmem_size          = %s" % (format_size(vpmem_size)))
print("    hpt_ratio           = 1/%d (%d)" % (1 << hpt_ratio, hpt_ratio))
print("    ppt_ratio           = 1/%d (%d)" % (64 * (1 << ppt_ratio), ppt_ratio))

#------------------------------------------------------------------------------

# Ideally, we want the HPT to be sized the same as if all the LUN storage was DRAM storage instead.
max_memory_size = desired_memory_size
target_hpt_size = compute_hpt_size(max_memory_size + vpmem_size, hpt_ratio)
print("")
print("Goals:")
print("    target_hpt_size     = %s" % (format_size(target_hpt_size)))

#------------------------------------------------------------------------------

# Increase the HPT size by modifying the HPT ratio first.
# There are fewer internal data structures tied to the ratio than to the max memory size.
original_hpt_ratio = hpt_ratio
original_ppt_ratio = ppt_ratio
actual_hpt_size = compute_hpt_size(max_memory_size, hpt_ratio)
while actual_hpt_size < target_hpt_size and hpt_ratio > 5:
    hpt_ratio -= 1
    ppt_ratio -= 1
    actual_hpt_size = compute_hpt_size(max_memory_size, hpt_ratio)

#------------------------------------------------------------------------------

# If we reach the HPT ratio limit, and the HPT is still too small, then increase max memory.
# Note that there are breakpoints at 25% of the distance between two power-of-two sizes.
while actual_hpt_size < target_hpt_size:
    lower_power_of_two = 1 << (max_memory_size.bit_length() - 1)
    upper_power_of_two = lower_power_of_two << 1
    if 4 * max_memory_size < 5 * lower_power_of_two:
        max_memory_size = (5 * lower_power_of_two) // 4
    elif 4 * max_memory_size == 5 * lower_power_of_two:
        max_memory_size += 1 * GB
    else:
        max_memory_size = (5 * upper_power_of_two) // 4
    actual_hpt_size = compute_hpt_size(max_memory_size, hpt_ratio)

#------------------------------------------------------------------------------

# Print the recommendations for HPT/PPT ratios and max memory, for optimal performance.
print("")
print("Outputs:")
print("    max_memory_size     = %s" % (format_size(max_memory_size)))
print("    hpt_ratio           = 1/%d (%d)" % (1 << hpt_ratio, hpt_ratio))
print("    ppt_ratio           = 1/%d (%d)" % (64 * (1 << ppt_ratio), ppt_ratio))
print("    actual_hpt_size     = %s" % (format_size(actual_hpt_size)))

#------------------------------------------------------------------------------

# Print the rough estimate for the layout of the ELMM tree.
elmm_base_address = max_memory_size
if is_linux or is_aix:
    elmm_base_address += max_memory_size - desired_memory_size
if elmm_base_address % (4*TB):
    elmm_base_address += 4*TB - (elmm_base_address % (4*TB))
print("")
print("ELMM Tree Structure:")
print("    elmm_base_address   = %s" % (format_size(elmm_base_address, TB)))
elmm_end_address = elmm_base_address
pci_vas_xive = 4*TB
print("    PCI/VAS/XIVE        = %s..%s" % (format_size(elmm_end_address, TB), format_size(elmm_end_address + pci_vas_xive, TB)))
elmm_end_address += pci_vas_xive
for lun_size in lun_sizes:
    allocation_size = lun_size
    lower_power_of_two = 1 << (allocation_size.bit_length() - 1)
    if allocation_size > lower_power_of_two:
        allocation_size = lower_power_of_two << 1
    if elmm_end_address % allocation_size:
        allocation_size += allocation_size - (elmm_end_address % allocation_size)
    print("    LUN %-7s         = %s..%s" % (format_size(lun_size), format_size(elmm_end_address, TB), format_size(elmm_end_address + allocation_size, TB)))
    elmm_end_address += allocation_size
print("    elmm_end_address    = %s" % (format_size(elmm_end_address, TB)))

#------------------------------------------------------------------------------

# Print the recommendations for changing the configuration of the partition.
print("")
print("Recommendations:")
if original_hpt_ratio != hpt_ratio:
    print("    Change the HPT ratio from 1/%d to 1/%d." % (1 << original_hpt_ratio, 1 << hpt_ratio))
if original_ppt_ratio != ppt_ratio:
    print("    Change the PPT ratio from 1/%d to 1/%d." % (64 * (1 << original_ppt_ratio), 64 * (1 << ppt_ratio)))
if desired_memory_size != max_memory_size:
    print("    Change the maximum memory size from %s to %s." % (format_size(desired_memory_size), format_size(max_memory_size)))
if is_linux and elmm_end_address > 64*TB:
    print("    *** WARNING: This configuration may not fit within Linux's 64TB memory footprint restriction. ***")
print("")
