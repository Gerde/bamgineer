#!/usr/bin/env python
import sys
import argparse
import time
from helpers import parameters as params
from methods import *

def main(args):
    outbamfn = args.outBamFile
    configReader = params.GetConfigReader()
    params.InitConfigReader(args.configfile)
    params.SetGainCNV(args.cnvAmpFile)
    params.SetLossCNV(args.cnvDelFile)
    params.SetCancerType(args.cancerType)
    params.SetOutputFileName(args.outBamFile)
    
    params.SetSplitBamsPath(args.splitbams)
    params.SetPhase(args.phase)
    params.SetctDNA(args.ctDNA)

    if(args.inbamFile):
        params.SetInputBam(args.inbamFile)

    results_path = configReader.get('RESULTS', 'results_path')

    #set software paths
    java_path, beagle_path,samtools_path, bedtools_path, vcftools_path,sambamba_path = params.GetSoftwarePath()
    params.SetSoftwarePath(java_path, beagle_path,samtools_path, bedtools_path, vcftools_path,sambamba_path)


    if(args.phase):
        run_pipeline(results_path)
    else:
        print ("user should provide phased vcf files")

    
        
if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(description='adds CN spikes to reads, outputs modified reads as .bam along with mates')
    parser.add_argument('-outbam', dest='outBamFile', required=True,
                        help='.bam file name for output')  
    parser.add_argument('-cnv_amp', dest='cnvAmpFile', required=False,
                        help='CNV amplification .bed file name')
    parser.add_argument('-cnv_del', dest='cnvDelFile', required=False,
                        help='CNV deletion .bed file name')
    parser.add_argument('-inbam', dest='inbamFile', required=False,
                        help='sam/bam file from which to obtain reads')
    parser.add_argument('-cancertype', dest='cancerType', required=False,
                        help='acronyms for cancer type')
    parser.add_argument('-splitbamdir', dest='splitbams', required=False,
                        help='input bam split by chromosomes')
    parser.add_argument('-c', '--configFile', action='store', required=True, dest='configfile',
                        help='/path/to/config_file.cfg')
    parser.add_argument('-phase',dest= 'phase', action="store_true")
    parser.add_argument('-ctDNA', dest='ctDNA', action="store_true")

    args = parser.parse_args()
    
    t0 = time.time()
    main(args)
    t1 = time.time()
    