# hpt-for-vpmem

Use this script to recommend configuration changes for a partition's page tables with VPMEM devices attached.

Possible script options:
```
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
    hpt_for_vpmem.py --memory 3000 --lun 16x1024 --linux
```

