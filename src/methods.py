import csv
import glob
import logging
import time
import random
from uuid import uuid4
from helpers import handlers as handle
from helpers import parameters as params
from helpers import bamgineerHelpers as bamhelp
from utils import *



global bases
bases = ('A', 'T', 'C', 'G')


def initPool(queue, level, terminating_):
    # This causes the logging module to be initialized with the necessary info in pool threads
    logging.getLogger('').setLevel(level)
    global terminating
    terminating = terminating_


def initialize0(results_path, cancer_dir_path):
    try:
        vcf_path = bamhelp.GetVCF()
        exons_path = bamhelp.GetExons()
        reference_path = bamhelp.GetRef()
        bedtools_path = bamhelp.GetBedtoolsPath()
        vpath, vcf = os.path.split(vcf_path)

        if params.GetPhase():
            phasedvcf = "/".join([results_path, sub('.vcf$', '_phased.vcf.gz', vcf)])
            vcftobed = "/".join([results_path, sub('.vcf$', '.bed', vcf)])

            hap1vcf = "/".join([results_path, "hap1_het.vcf"])
            hap2vcf = "/".join([results_path, "hap2_het.vcf"])
            hap1vcffiltered = "/".join([results_path, "hap1_het_filtered"])
            hap2vcffiltered = "/".join([results_path, "hap2_het_filtered"])
            hap1vcffilteredtobed = "/".join([results_path, "hap1_het_filtered.bed"])
            hap2vcffilteredtobed = "/".join([results_path, "hap2_het_filtered.bed"])
            phased_bed = "/".join([results_path, "PHASED.BED"])

            phaseVCF(vcf_path, phasedvcf)
            getVCFHaplotypes(phasedvcf, hap1vcf, hap2vcf)
            #thinVCF(hap1vcf, hap1vcffiltered)
            #thinVCF(hap2vcf, hap2vcffiltered)
            convertvcftobed(hap1vcf, hap1vcffilteredtobed)
            convertvcftobed(hap2vcf, hap2vcffilteredtobed)

            generatePhasedBed(hap1vcffilteredtobed, hap2vcffilteredtobed, phased_bed)

    except:

        logger.exception("Initialization error !")
        raise

    return


def initialize_pipeline(phase_path, haplotype_path, cnv_path):
    exons_path = bamhelp.GetExons()

    event, extension = os.path.splitext(os.path.basename(cnv_path))

    phased_bed = "/".join([phase_path, "PHASED.BED"])
    bedtools_path = bamhelp.GetBedtoolsPath()

    try:
        logger.debug(' --- Initializing input files  --- ')
        exonsinroibed = "/".join([haplotype_path, "exons_in_roi" + str(event) + ".bed"])

        nonhetbed = "/".join([haplotype_path, "non_het" + str(event) + ".bed"])
        hetbed = "/".join([haplotype_path, "het" + str(event) + ".bed"])
        hetsnpbed = "/".join([haplotype_path, "het_snp" + str(event) + ".bed"])

        tmp = "/".join([haplotype_path, str(event) + "_tmp.bed"])
	command = " ".join([bedtools_path, "intersect -a", exons_path, "-b", cnv_path, "-wa -wb > ", tmp])
        runCommand(command)

        filterColumns(tmp, exonsinroibed, [0, 1, 2])

        splitBed(exonsinroibed, '_exons_in_roi' + str(event))
        command = " ".join([bedtools_path, "intersect -a", phased_bed, "-b", exonsinroibed, "-wa -wb >", tmp])
        runCommand(command)

        filterColumns(tmp, hetsnpbed, [i for i in range(0, 6)])

        splitBed(hetsnpbed, '_het_snp' + str(event))
        #os.remove(tmp)
    except:
        logger.exception("Initialization error !")
        raise
    logger.debug("--- initialization complete ---")
    return


def init_file_names(chr, tmpbams_path, haplotypedir, event=''):
    flist = []

    roibam = "/".join([tmpbams_path, chr + "_roi" + event + ".bam"])
    splitbams = params.GetSplitBamsPath()
    hetsnp = "/".join([haplotypedir, chr + '_het_snp' + event + '.bed'])

    if not splitbams:
        splitbams = "/".join([res_path, 'splitbams'])

    sortbyname = "/".join([splitbams, chr + '.byname.bam'])
    sortbyCoord = "/".join([splitbams, chr + '.bam'])

    flist.extend([roibam, sortbyname, sortbyCoord, hetsnp])
    return flist


def find_roi_bam(chromosome_event):
    chr, event = chromosome_event.split("_")
    roi, sortbyname, sortbyCoord, hetsnp = init_file_names(chr, tmpbams_path, haplotype_path, event)
    exonsinroibed = "/".join([haplotype_path, chr + "_exons_in_roi" + event + ".bed"])
    success = False
    try:
        if not terminating.is_set():
            roisort = sub('.bam$', '.sorted', roi)
            if os.path.isfile(exonsinroibed):

                cmd = " ".join(["sort -u", exonsinroibed, "-o", exonsinroibed]);
                runCommand(cmd)
                extractPairedReadfromROI(sortbyname, exonsinroibed, roi)
                removeIfEmpty(tmpbams_path, ntpath.basename(roi))
                pysam.sort(roi, roisort)
                pysam.index(roisort + '.bam')
                os.remove(roi)
                success = True

            else:
                logger.debug(exonsinroibed + ' does not exist!')
                return
    except (KeyboardInterrupt):
        logger.error('Exception Crtl+C pressed in the child process  in find_roi_bam for chr ' + chr + event)
        terminating.set()
        success = False
        return
    except Exception as e:
        logger.exception("Exception in find_roi_bam %s", e)
        terminating.set()
        success = False
        return
    if (success):
        logger.debug("find_roi_bam complete successfully for " + chr + event)
    return

def split_hap(bamsortfn, chr, event=''):
    fn, sortbyname, sortbyCoord, bedfn = init_file_names(chr, tmpbams_path, haplotype_path, event)
    cmd = " ".join(["sort -u", bedfn, "-o", bedfn]);
    runCommand(cmd)


    hap1_bamfn = sub('.sorted.bam$', ".hap1.bam", bamsortfn)
    hap2_bamfn = sub('.sorted.bam$', ".hap2.bam", bamsortfn)
    hap1_bamsortfn = sub('.sorted.bam$', ".hap1.sorted", bamsortfn)
    hap2_bamsortfn = sub('.sorted.bam$', ".hap2.sorted", bamsortfn)

    hap12_bamfn = sub('.sorted.bam$', ".hap12.bam", bamsortfn)
    hap12_bamsortfn = sub('.sorted.bam$', ".hap12.sorted", bamsortfn)


    intersnpbamfn = sub('.sorted.bam$', ".intersnp.bam", bamsortfn)
    intersnpbamsortfn = sub('.sorted.bam$', ".intersnp.sorted", bamsortfn)


    hap1_intersnpbamfn = sub('.sorted.bam$', ".hap1_intersnp.bam", bamsortfn)
    hap2_intersnpbamfn = sub('.sorted.bam$', ".hap2_intersnp.bam", bamsortfn) 
    hap1_intersnpbamsortfn = sub('.sorted.bam$', ".hap1_intersnp.sorted", bamsortfn)
    hap2_intersnpbamsortfn = sub('.sorted.bam$', ".hap2_intersnp.sorted", bamsortfn)

    hap1_finalbamfn = sub('.sorted.bam$', ".hap1_final.bam", bamsortfn)
    hap2_finalbamfn = sub('.sorted.bam$', ".hap2_final.bam", bamsortfn)
    hap1_finalbamsortfn = sub('.sorted.bam$', ".hap1_final.sorted", bamsortfn)
    hap2_finalbamsortfn = sub('.sorted.bam$', ".hap2_final.sorted", bamsortfn)


    newbedfn = sub('.bed$', ".new.bed",bedfn)
# try:

    if not terminating.is_set():

        if (os.path.isfile(bamsortfn) and os.path.isfile(bedfn)):

            samfile = pysam.Samfile(bamsortfn, "rb")
            alignmentfile = pysam.AlignmentFile(bamsortfn, "rb")
            outbam1 = pysam.Samfile(hap1_bamfn, 'wb', template=samfile)
            outbam2 = pysam.Samfile(hap2_bamfn, 'wb', template=samfile)

            # allreads = pysam.Samfile(allreadsfn, 'wb', template=samfile)

            bedfile = open(bedfn, 'r')
            # covpath = "/".join([haplotype_path, "written_coverage_het.txt"])
            # snpratiopath = "/".join([haplotype_path, "het_snp_ratio.txt"])

            num_reads_written = 0
            num_total_reads = 0
	    
            newsnps = []
	    bedlist = []
	    problem_snps = []
	    newbedlist = []
	    #readid1 = []
	    #readid2 = []

	    newbed = open(newbedfn, 'w') 

            for bedline in bedfile:
                c = bedline.strip().split()

                if len(c) == 7:
                    chr2 = c[0]
                    chr = c[0].strip("chr")
                    start = int(c[1])
                    end = int(c[2])
                    refbase = str(c[3])
                    altbase = str(c[4])
                    haplotype = str(c[5])
                    copy_number = int(c[6])
                else:
                    continue
	
	    	bedlist.append(c) 
	     

	    bedlist2 = bedlist[:]
	    
	    for i in range(0,(len(bedlist2)-1),2):
            	if abs((int(bedlist2[i][1]))-(int(bedlist2[i+1][1]))) <= 75:
                	problem_snps.append(bedlist2[i])
                	problem_snps.append(bedlist2[i+1])
			bedlist.remove(bedlist2[i])
			bedlist.remove(bedlist2[i+1])		
		 
	    newbedlist.extend(bedlist)

	    for i in range(0,(len(problem_snps)-1),2):
		readid1 = []
		readid2 = []
	    	readid3 = []

		c = problem_snps[i]
		c2 = problem_snps[i+1]

		if len(c) == 7:
			chr1 = c[0]
		    	start1 = int(c[1])
		    	end1 = int(c[2])
		    	refbase1 = str(c[3])
		    	altbase1 = str(c[4])
			haplotype1 = str(c[5])
		    	copy_number1 = int(c[6])

		if len(c2) == 7:
		    	chr2 = c2[0]
		    	start2 = int(c2[1])
		    	end2 = int(c2[2])
		    	refbase2 = str(c2[3])
		    	altbase2 = str(c2[4])
		    	haplotype2 = str(c2[5])
		    	copy_number2 = int(c2[6])


        	maps1 = alignmentfile.fetch(chr1, start1, end1)
        	maps2 = alignmentfile.fetch(chr2, start2, end2)

		for read1 in maps1:
                	index1 = read1.get_reference_positions(full_length=True).index(start1)
                	tmpread1 = read1.query_sequence
                	qual1 = read1.query_qualities
                	tmpread_index1 = tmpread1[index1]

                	if tmpread_index1 == altbase1:
                        	readid1.append(read1.qname)


		for read2 in maps2:
                	index2 = read2.get_reference_positions(full_length=True).index(start2)
                	tmpread2 = read2.query_sequence
                	qual2 = read2.query_qualities
                	tmpread_index2 = tmpread2[index2]

                	if tmpread_index2 == altbase2:
                        	readid2.append(read2.qname)


        	for readid in readid1:
                	if readid in readid2:
                        	readid3.append(readid)

        	if any(readid3):
                	c2[5] = c[5]


        	else:
                	if c[5] == "hap1":
                        	c2[5] = "hap2"

                	elif c[5] == "hap2":
                        	c2[5] = "hap1"

		
	    newbedlist.extend(problem_snps)
	    
	    newbedlist2 = sorted(newbedlist, key=lambda x: x[1])
	    
	    for i in range(len(newbedlist2)):
                c = newbedlist2[i]
	    	newbed.write(c[0] + '\t' + str(c[1]) + '\t' + str(c[2]) + '\t' +  str(c[3]) + '\t' + str(c[4]) + '\t' + str(c[5]) + '\t' + str(c[6]) + '\n')  # chr start stop ref alt
	    newbed.close()
	    bedfile2 = open(newbedfn, 'r')
	    readids = []

	    for bedline in bedfile2:
                c = bedline.strip().split()
	
                if len(c) == 7:
                    chr2 = c[0]
                    chr = c[0].strip("chr")
                    start = int(c[1])
                    end = int(c[2])
                    refbase = str(c[3])
                    altbase = str(c[4])
                    haplotype = str(c[5])
                    copy_number = int(c[6])
                else:
                    continue

		
                readmappings = alignmentfile.fetch(chr2, start, end)

                # sex chromosome
                # if params.GetXY() and (chr == 'chrX' or chr == 'chrY'):
                #     haplotype = 'hap1'
                #     print('sex chromosome ' + str(chr))

                for shortread in readmappings:
	        	if shortread.qname not in readids:	
				#allreads.write(shortread)
                        	num_total_reads += 1
				problem_with_read = False

				try:
				    index = shortread.get_reference_positions(full_length=True).index(start)
				    tmpread = shortread.query_sequence
				    qual = shortread.query_qualities
				    tmpread_index = tmpread[index]
				    readids.append(shortread.qname)
	 
				    if tmpread_index == altbase and haplotype == "hap1":
					outbam1.write(shortread)
				    elif tmpread_index == refbase and haplotype == "hap1":
					outbam2.write(shortread)
				    elif tmpread_index == altbase and haplotype == "hap2":
					outbam2.write(shortread)
				    elif tmpread_index == refbase and haplotype == "hap2":
					outbam1.write(shortread)
				    #mutated_hap2 = tmpread[:index] + refbase + tmpread[index + 1:]

				    #if haplotype == "hap1":
				     #   shortread.query_sequence = mutated_hap1

				    #elif haplotype == "hap2":
				     #   shortread.query_sequence = mutated_hap2
				    else: 
					problem_with_read = True
	     
				    shortread.query_qualities = qual

				except Exception as e:
				    problem_with_read = True
				    pass

				#if not problem_with_read:
				 #   if haplotype == "hap1":
				  #  	outbam1.write(newread)

				   # elif haplotype == "hap2":
				    #    outbam2.write(newread)

            #newbed.close()
	    outbam1.close()
	    outbam2.close()

            # sort hap1 and hap2
            sortBam(hap1_bamfn, hap1_bamsortfn + '.bam', tmpbams_path)
            sortBam(hap2_bamfn, hap2_bamsortfn + '.bam', tmpbams_path)

	    
	    # ***MODIFY HAP FUNCTION***

	    # merge hap1 + hap2 -> hap12 
	    merge_bams(hap1_bamsortfn + '.bam', hap2_bamsortfn + '.bam', hap12_bamfn)
	    # sort hap12
	    sortBam(hap12_bamfn, hap12_bamsortfn + '.bam', tmpbams_path)

	    # difference between normal bam and hap12  
	    bamDiff(bamsortfn, hap12_bamsortfn + '.bam', tmpbams_path)

	    # sort intersnps
	    sortBam("/".join([tmpbams_path, 'diff_only1_' + os.path.basename(bamsortfn)]), intersnpbamsortfn + '.bam', tmpbams_path)

	    # subsample 50% of reads from inter_snps and assign to hap1
	    subsample(intersnpbamsortfn + '.bam', hap1_intersnpbamfn, str(0.5))

	    # sort hap1_intersnpbam
	    sortBam(hap1_intersnpbamfn, hap1_intersnpbamsortfn + '.bam', tmpbams_path)

	    # difference between hap1 inter_snp bam and total inter_snp bam 
	    bamDiff(intersnpbamsortfn + '.bam', hap1_intersnpbamsortfn + '.bam', tmpbams_path)

	    # sort hap2_intersnpbam
	    sortBam("/".join([tmpbams_path, 'diff_only1_' + os.path.basename(intersnpbamsortfn + '.bam')]), hap2_intersnpbamsortfn + '.bam', tmpbams_path)

	    # merge hap1 with hap1 intersnps and hap2 with hap2 intersnps
	    merge_bams(hap1_bamsortfn + '.bam', hap1_intersnpbamsortfn + '.bam', hap1_finalbamfn)
	    merge_bams(hap2_bamsortfn + '.bam', hap2_intersnpbamsortfn + '.bam', hap2_finalbamfn)

	    # sort final bams
	    sortBam(hap1_finalbamfn, hap1_finalbamsortfn + '.bam', tmpbams_path)
	    sortBam(hap2_finalbamfn, hap2_finalbamsortfn + '.bam', tmpbams_path)


def readBamStrand(bamsortfn, strand):
    read1fn = sub('.bam$', '.read1_' + strand + '.bam', bamsortfn)
    read2fn = sub('.bam$', '.read2_' + strand + '.bam', bamsortfn)

    if not os.path.isfile(read1fn) or not os.path.isfile(read2fn):
        splitPairAndStrands(bamsortfn)
    
    pysam.index(read1fn)
    pysam.index(read2fn)
    
    splt1 = pysam.Samfile(read1fn, 'rb')
    splt2 = pysam.Samfile(read2fn, 'rb')
    
    itrA = splt1.fetch(until_eof=True)
    itrB = splt2.fetch(until_eof=True)
    
    return itrA, itrB, splt1, splt2

def defineSearchSpace(readX, strand, direction):
    if (strand == 'neg' and direction == 'back') or (strand == 'pos' and direction == 'forw'):
        insert_size = readX.tlen - readX.qlen
        minpos = readX.pos + 75 + insert_size
        maxpos = readX.pos + 150 + insert_size
    
    elif (strand == 'pos' and direction == 'back') or (strand == 'neg' and direction == 'forw'):
        insert_size = abs(readX.tlen) - readX.qlen
        maxpos = readX.pos - 75 - insert_size
        minpos = readX.pos - 150 - insert_size
    
    return insert_size, minpos, maxpos

def generateReadPairs(tmpA, tmpB, strand, direction):
    tlenFR = tmpB.pos - tmpA.pos + tmpB.qlen
    tlenRF = tmpA.pos - tmpB.pos + tmpA.qlen
    
    tmpqname = str(uuid4())
    
    tmpA.pnext = tmpB.pos
    tmpA.qname = tmpqname
    tmpB.pnext = tmpA.pos
    tmpB.qname = tmpqname
    
    if (strand == 'neg' and direction == 'back') or (strand == 'pos' and direction == 'forw'):
        tmpA.tlen = tlenFR
        tmpB.tlen = -tlenFR
    elif (strand == 'pos' and direction == 'back') or (strand == 'neg' and direction == 'forw'):
        tmpA.tlen = -tlenRF
        tmpB.tlen = tlenRF
    
    return tmpA, tmpB

def rePair1(bamsortfn):
    # Throws an error if bamsortfn is not found
    if not os.path.isfile(bamsortfn):
        raise ValueError('Could not find file bamsortfn')
    bamrepairedfn = sub('.bam$', ".re_paired.bam", bamsortfn)
    bamrepairedsortfn = sub('.bam$', ".re_paired.sorted.bam", bamsortfn)
 
    inbam = pysam.Samfile(bamsortfn, 'rb')
    outbam = pysam.Samfile(bamrepairedfn, 'wb', template=inbam)

    writtencount = 0
    strands = ['pos', 'neg']

    for strand in strands:
        # Takes bamsortfn and splits it based on Read 1/2 and Strand
        itrA, itrB, splt1, splt2 = readBamStrand(bamsortfn, strand)
        counter = 0	
        
        while (True):
            try:
                counter += 1
                direction='forw'
                    # ODDS: takes all odd-reads from splt1 and defines search space on splt2
                #if counter != 1:  # Skips the first read
                #	readRef = itrA.next()
                readRef = itrA.next()  # Every other read
                    # Defines the search space for the other read in the opposite splt
                insert_size, minpos, maxpos = defineSearchSpace(readRef, strand, direction)
                itrTarget = splt2.fetch("chr21", minpos, maxpos)
                
		listTarget = []
                itrs_list = list(itrTarget)
                
                
                if len(itrs_list) <= 5: # Takes all target reads
                    listTarget = itrs_list
                elif len(itrs_list) > 5: # Takes a random sample of target reads
                    listTarget = [i for i in random.sample(itrs_list, 5)]
                
                # Loops through all target reads
                for i in range(len(listTarget)):
                    readTarget = listTarget[i]
                    # If the read IDs dont match, create a new read-pair by altering the description of the read and output
                    if readRef.qname != readTarget.qname:
                        tmpA, tmpB = generateReadPairs(readRef, readTarget, strand, direction)
                    	if counter % 2 != 0:
				outbam.write(tmpA)
                    		outbam.write(tmpB)
            except StopIteration:
                break
            
        splt1.close()
        splt2.close()
    inbam.close()
    outbam.close()

    bamrepairedsortfn = sub('sorted.re_paired', 're_paired', bamrepairedsortfn)
    sortBam(bamrepairedfn, bamrepairedsortfn, tmpbams_path)
    os.remove(bamrepairedfn)

    return


def rePair2(bamsortfn):
    # Throws an error if bamsortfn is not found
    if not os.path.isfile(bamsortfn):
        raise ValueError('Could not find file bamsortfn')
    bamrepaired2fn = sub('.bam$', ".re_paired2.bam", bamsortfn)
    bamrepaired2sortfn = sub('.bam$', ".re_paired2.sorted.bam", bamsortfn)
 
    inbam = pysam.Samfile(bamsortfn, 'rb')
    outbam2 = pysam.Samfile(bamrepaired2fn, 'wb', template=inbam)

    writtencount = 0
    strands = ['pos', 'neg']

    for strand in strands:
        # Takes bamsortfn and splits it based on Read 1/2 and Strand
        itrA, itrB, splt1, splt2 = readBamStrand(bamsortfn, strand)
        counter = 0	
        
        while (True):
            try:
                counter += 1
                direction='back'
                    # EVENS: takes all even-reads from splt2 and defines search space on splt1
                readRef = itrB.next()
                #    readRef = itrB.next()
                    # Defines the search space for the other read in the opposite splt
                insert_size, minpos, maxpos = defineSearchSpace(readRef, strand, direction)
                itrTarget = splt1.fetch("chr21", minpos, maxpos)
                
                listTarget = []
                itrs_list = list(itrTarget)
                
                
                if len(itrs_list) <= 5: # Takes all target reads
                    listTarget = itrs_list
                elif len(itrs_list) > 5: # Takes a random sample of target reads
                    listTarget = [i for i in random.sample(itrs_list, 5)]
                
                # Loops through all target reads
                for i in range(len(listTarget)):
                    readTarget = listTarget[i]
                    # If the read IDs dont match, create a new read-pair by altering the description of the read and output
                    if readRef.qname != readTarget.qname:
                        tmpA, tmpB = generateReadPairs(readRef, readTarget, strand, direction)
                    	if counter % 2 == 0:
				outbam2.write(tmpA)
                    		outbam2.write(tmpB)
            except StopIteration:
                break
            
        splt1.close()
        splt2.close()
    inbam.close()
    outbam2.close()

    bamrepaired2sortfn = sub('sorted.re_paired', 're_paired', bamrepaired2sortfn)
    sortBam(bamrepaired2fn, bamrepaired2sortfn, tmpbams_path)
    os.remove(bamrepaired2fn)

    return






def re_pair_reads(bamsortfn, copy_number):
    if os.path.isfile(bamsortfn):

        bamrepairedfn = sub('.bam$', ".re_paired.bam", bamsortfn)
        bamrepairedsortfn = sub('.bam$', ".re_paired.sorted.bam", bamsortfn)

        inbam = pysam.Samfile(bamsortfn, 'rb')
        outbam = pysam.Samfile(bamrepairedfn, 'wb', template=inbam)

        writtencount = 0
        strands = ['pos', 'neg']

    	for strand in strands:
    	    read1fn = sub('.bam$', '.read1_' + strand + '.bam', bamsortfn)
            read2fn = sub('.bam$', '.read2_' + strand + '.bam', bamsortfn)

            if not os.path.isfile(read1fn) or not os.path.isfile(read2fn):
                splitPairAndStrands(bamsortfn)
	    
	    pysam.index(read1fn)
	    pysam.index(read2fn)
            
	    splt1 = pysam.Samfile(read1fn, 'rb')
            splt2 = pysam.Samfile(read2fn, 'rb')
	    rePair1(splt1,splt2)
	    rePair2(splt2,splt1)            
#	    itrA = splt2.fetch(until_eof=True)
	    #itrB = splt2.fetch(until_eof=True)
            #if (params.GetctDNA()):
            #    sigma = 40
            #    coff = 2
            #    block_size = int(copy_number)
            #else:
            #    sigma = 85
            #    coff = 5
            #    block_size = int(copy_number) * 4 

 #           writtenreads = []

#            while (True):
	    #for i in range(0,len(itrA),2):            	
#		try:
#                    listb = []
#		    readA = itrA.next()
#		    qlen = readA.qlen
#                    tlen = readA.tlen
#                    pos = readA.pos
                    #rname = readA.reference_name

#                    if strand == 'neg':
#                        insert_size = tlen-qlen 
#                   	minpos = pos + 75 + insert_size
#                   	maxpos = pos + 150 + insert_size                    
#			
#                    elif strand == 'pos':
#                        insert_size = abs(tlen)-qlen
#			maxpos = pos - 75 - insert_size
#			minpos = pos - 150 - insert_size 
#		    
#                    itrB = splt1.fetch("chr21", minpos, maxpos)    
#		    itrs_list = list(itrB)
#test section
#		    if len(itrs_list) == 0:
#		    	for i in itrs_list:
#			    readB = i
#			    listb.append(readB)
#		    elif len(itrs_list) >= 1:	
#		    	for i in random.sample(itrs_list,1):
#		    	    readB = i
#			    listb.append(readB)
#	
#		    if len(itrs_list) <= 5:
#                    	for i in itrs_list:
#                      	    readB = i
#                            listb.append(readB)
#
#		    elif len(itrs_list) > 5:
#                        for i in random.sample(itrs_list, 5):
#                            readB = i
#                            listb.append(readB)
#                   
#		    for i in range(len(listb)):
#                        tmpA = readA
#			readB = listb[i]
#			tmpB = readB

#			tlenFR = tmpB.pos - tmpA.pos + tmpB.qlen
#			tlenRF = tmpA.pos - tmpB.pos + tmpA.qlen
			
			#read_length_A = tmpA.tlen
			#read_length_B = tmpB.tlen
			#read_length_average = (read_length_A + read_length_B)/2

#			if readA.qname != readB.qname:
#			    tmpqname = str(uuid4())
			    
#			    if strand == 'pos':
#			    	tmpA.tlen = tlenFR
#				tmpB.tlen = -tlenFR
#				tmpA.pnext = tmpB.pos  
#				tmpB.pnext = tmpA.pos
#				tmpA.qname = tmpqname
#				tmpB.qname = tmpqname
#				outbam.write(tmpA)
#				outbam.write(tmpB)
				#writtenreads.append(tmpB.qname)

#			    elif strand == 'neg':
#				print ("TLENRF:",tlenRF)
#				print ("Tmpa.tlen:",tmpA.tlen)
#
#				tmpA.tlen = -tlenRF
#				tmpB.tlen = tlenRF
##				tmpA.pnext = tmpB.pos
#				tmpB.pnext = tmpA.pos
#				tmpA.qname = tmpqname
#				tmpB.qname = tmpqname
#				outbam.write(tmpA)
#				outbam.write(tmpB)
				#writtenreads.append(tmpB.qname)

#                except StopIteration:
#                    break

            #os.remove(read1fn)
            #os.remove(read2fn)

    	splt1.close()
    	splt2.close()

    	inbam.close()
    	outbam.close()

        bamrepairedsortfn = sub('sorted.re_paired', 're_paired', bamrepairedsortfn)
        sortBam(bamrepairedfn, bamrepairedsortfn, tmpbams_path)
        os.remove(bamrepairedfn)

    return


def mutate_reads(bamsortfn, chr, event=''):
    fn, sortbyname, sortbyCoord, bedfn = init_file_names(chr, tmpbams_path, haplotype_path, event)
    cmd = " ".join(["sort -u", bedfn, "-o", bedfn]);
    runCommand(cmd)
    hetbamfn = sub('.sorted.bam$', ".mutated_het.bam", bamsortfn)
    hetbamfnsorted = sub('.sorted.bam$', ".mutated_het.sorted", bamsortfn)
    allreadsfn = sub('.sorted.bam$', ".all.reads.bam", bamsortfn)
    allreadssortfn = sub('.sorted.bam$', ".all.reads.sorted", bamsortfn)
    mergedsortfn = sub('.sorted.bam$', ".mutated_merged.sorted.bam", bamsortfn)
    try:
        if not terminating.is_set():

            if (os.path.isfile(bamsortfn) and os.path.isfile(bedfn)):

                samfile = pysam.Samfile(bamsortfn, "rb")
                alignmentfile = pysam.AlignmentFile(bamsortfn, "rb")
                outbam = pysam.Samfile(hetbamfn, 'wb', template=samfile)
                allreads = pysam.Samfile(allreadsfn, 'wb', template=samfile)

                bedfile = open(bedfn, 'r')
                covpath = "/".join([haplotype_path, "written_coverage_het.txt"])
                snpratiopath = "/".join([haplotype_path, "het_snp_ratio.txt"])

                num_reads_written = 0
                num_total_reads = 0

                for bedline in bedfile:
                    c = bedline.strip().split()

                    if len(c) == 7:
                        chr2 = c[0]
                        chr = c[0].strip("chr")
                        start = int(c[1])
                        end = int(c[2])
                        refbase = str(c[3])
                        altbase = str(c[4])
                        haplotype = str(c[5])
                        copy_number = int(c[6])
                    else:
                        continue

                    readmappings = alignmentfile.fetch(chr2, start, end)

                    # sex chromosome
                    if params.GetXY() and (chr == 'chrX' or chr == 'chrY'):
                        haplotype = 'hap1'
                        print('sex chromosome ' + str(chr))

                    for shortread in readmappings:

                        allreads.write(shortread)
                        num_total_reads += 1
                        problem_with_read = False

                        try:
                            index = shortread.get_reference_positions(full_length=True).index(start)
                            tmpread = shortread.query_sequence
                            qual = shortread.query_qualities
                            mutated_hap1 = tmpread[:index] + altbase + tmpread[index + 1:]
                            mutated_hap2 = tmpread[:index] + refbase + tmpread[index + 1:]
                            if haplotype == "hap1":
                                shortread.query_sequence = mutated_hap1

                            elif haplotype == "hap2":
                                shortread.query_sequence = mutated_hap2

                            shortread.query_qualities = qual

                        except Exception as e:
                            problem_with_read = True
                            pass

                        if not problem_with_read:
                            outbam.write(shortread)
                            num_reads_written += 1

                outbam.close()
                allreads.close()

                sortBam(hetbamfn, hetbamfnsorted + '.bam', tmpbams_path)
                sortBam(allreadsfn, allreadssortfn + '.bam', tmpbams_path)

                os.remove(hetbamfn)
                os.remove(allreadsfn)

                # ratio of het reads to nonhet reads, we need to adjust the coverage
                ratio = float(num_reads_written) / float(num_total_reads)
                bamsortfnsampled = sub('.sorted.bam$', ".sampled.nh.bam", bamsortfn)
                subsample(bamsortfn, bamsortfnsampled, str(ratio))
                bamDiff(bamsortfnsampled, allreadssortfn + '.bam', tmpbams_path)

                if "/".join([tmpbams_path, 'diff_only1_' + os.path.basename(bamsortfnsampled)]):
                    merge_bams("/".join([tmpbams_path, 'diff_only1_' + os.path.basename(bamsortfnsampled)]),
                               hetbamfnsorted + '.bam', mergedsortfn)
                    os.remove("/".join([tmpbams_path, 'diff_only1_' + os.path.basename(bamsortfnsampled)]))

                os.remove(bamsortfnsampled)
                os.remove(allreadssortfn + '.bam')
                os.remove(allreadssortfn + '.bam.bai')

                os.remove(hetbamfnsorted + '.bam')
                os.remove(hetbamfnsorted + '.bam.bai')

    except KeyboardInterrupt:
        logger.error('Exception Crtl+C pressed in the child process  in mutaute_reads')
        terminating.set()
        return
    except Exception as e:
        logger.exception("Exception in mutate_reads %s", e)
        terminating.set()
        return
    return


def split_bam_by_chr(chr):
    inbam = params.GetInputBam()
    spltbams_path = "/".join([res_path, 'splitbams'])

    try:
        if not terminating.is_set():
            logger.debug("___ spliting bam by chromosome ___")
            splitBamByChr(inbam, spltbams_path, str(chr))
            sortByName("/".join([spltbams_path, str(chr) + ".bam"]),
                       "/".join([spltbams_path, str(chr) + ".byname.bam"]))

    except KeyboardInterrupt:
        logger.error('Exception Crtl+C pressed in the child process  in split_bam_by_chr')
        terminating.set()
        return False
    except Exception as e:
        logger.exception("Exception in split_bam_by_chr %s", e)
        terminating.set()
        return False
    return


# cn change is 1 for CN=1,2,...,8
def calculate_sample_rate(inbam, outbam, cnchange, purity):
    logger.debug("___ adjusting sample rate ___")


def implement_cnv(chromosome_event):
    chr, event = chromosome_event.split("_")

    logger.debug("___ Bamgineer main engine started ___")
    success = True
    try:
        if not terminating.is_set():
            bamfn, sortbyname, sortbyCoord, bedfn = init_file_names(chr, tmpbams_path, haplotype_path, event)
            bamsortfn = sub('.bam$', '.sorted.bam', bamfn)

            if os.path.isfile(bedfn):
                fn = list(csv.reader(open(bedfn, 'rb'), delimiter='\t'))
                copy_number = int(fn[0][6])

                if not params.GetXY() or (chr != 'chrX' and chr != 'chrY'):

                    if copy_number == 2:
                        event = 'loh'
                    elif copy_number == 3:
                        event = 'gain'
                    elif copy_number > 3:
                        event = 'amp'

                else:

                    logger.debug("*** handling single sex chromosome for: " + ntpath.basename(bamsortfn))
                    if copy_number == 1:
                        event = 'loh'
                    elif copy_number == 2:
                        event = 'gain'
                    elif copy_number > 2:
                        event = 'amp'

                if event.startswith('amp') or event.startswith('gain'):

                    
		    bamrepairedsortfn = sub('.sorted.bam$', ".re_paired.sorted.bam", bamsortfn)
		    hap1_finalbamsortfn = sub('.sorted.bam$', ".hap1_final.sorted.bam", bamsortfn)
		    hap2_finalbamsortfn = sub('.sorted.bam$', ".hap2_final.sorted.bam", bamsortfn)
                    mergedsortfn = sub('.sorted.bam$', ".mutated_merged.sorted.bam", bamrepairedsortfn)
                    GAIN_FINAL = "/".join([finalbams_path, str(chr).upper() + '_GAIN.bam'])

                    if os.path.isfile(bamsortfn):

                        split_hap(bamsortfn, chr, event)
		        #re_pair_reads(hap1_finalbamsortfn, copy_number)
                        #re_pair_reads(hap2_finalbamsortfn, copy_number)
			rePair1(hap1_finalbamsortfn)
			rePair2(hap1_finalbamsortfn)
			mutate_reads(bamrepairedsortfn, chr, event)
                        coverageratio = float(countReads(mergedsortfn)) / float(countReads(bamsortfn))
                        logger.debug(
                            "+++ coverage ratio for: " + ntpath.basename(bamsortfn) + ": " + str(coverageratio))

                        if coverageratio < copy_number - 2:
                            logger.error('not enough reads for ' + ntpath.basename(bamsortfn))
                            return
                        else:
                            samplerate = float(copy_number - 2) / coverageratio
                            subsample(mergedsortfn, GAIN_FINAL, str(samplerate))

                elif event == 'loss':

                    inbam_deletion = "/".join([finalbams_path, str(chr).upper() + '_LOSS.bam'])

                    if os.path.isfile(bamsortfn):

                        mutate_reads(bamsortfn, chr, 'loss')
                        mergedsortfn = sub('.sorted.bam$', ".mutated_merged.sorted.bam", bamsortfn)
                        mergedsortsampledfn = sub('.sorted.bam$', ".mutated_merged.sampled.sorted.bam", bamsortfn)

                        ratio_kept = float(countReads(mergedsortfn)) / float(countReads(bamsortfn))
                        samplerate = round(0.5 / ratio_kept, 2)
                        LOSS_FINAL = "/".join([finalbams_path, str(chr).upper() + '_LOSS.bam'])
                        logger.debug("ratios kept for:" + ntpath.basename(bamsortfn) + ": " + str(ratio_kept))
                        subsample(mergedsortfn, mergedsortsampledfn, str(samplerate))
                        bamDiff(sortbyCoord, mergedsortsampledfn, tmpbams_path)
                        os.rename("/".join([tmpbams_path, 'diff_only1_' + chr + '.bam']), LOSS_FINAL)

                    elif (not os.path.isfile(inbam_deletion) and os.path.isfile(
                            sortbyCoord)):  # if it exists from previous runs

                        os.symlink(sortbyCoord, inbam_deletion)

            else:
                logger.debug(bedfn + ' does not exist!')
                success = False

    except KeyboardInterrupt:
        logger.error('Exception Crtl+C pressed in the child process  in find_roi_bam for chr ' + chr + event)
        terminating.set()
        success = False
        return
    except Exception as e:
        logger.exception("Exception in find_roi_bam %s", e)
        terminating.set()
        success = False
        return
    if success:
        logger.debug("implement_cnv complete successfully for " + chr + event)
    return


def removeReadsOverlappingHetRegion(inbamfn, bedfn, outbamfn, path):
    print "___ removing reads overlapping heterozygous region ___"
    inbamsorted = sub('.bam$', '.sorted', inbamfn)
    pysam.sort(inbamfn, inbamsorted)
    pysam.index(inbamsorted + '.bam')

    alignmentfile = pysam.AlignmentFile(inbamsorted + '.bam', "rb")
    outbam = pysam.Samfile(outbamfn, 'wb', template=alignmentfile)

    bedfile = open(bedfn, 'r')

    for bedline in bedfile:
        c = bedline.strip().split()

        if len(c) == 3:
            chr2 = c[0]
            chr = c[0].strip("chr")
            start = int(c[1])
            end = int(c[2])
        else:
            continue

        try:
            readmappings = alignmentfile.fetch(chr2, start, end)
        except  ValueError as e:
            print("problem fetching the read ")

        for shortread in readmappings:
            try:
                outbam.write(shortread)
            except ValueError as e:
                print ("problem removing read :" + shortread.qname)
    outbamsorted = sub('.bam$', '.sorted', outbamfn)
    pysam.sort(outbamfn, outbamsorted)
    bamDiff(inbamsorted + '.bam', outbamsorted + '.bam', path)
    outbam.close()


def run_pipeline(results_path):
    print(results_path)
    global haplotype_path, cancer_dir_path, tmpbams_path, finalbams_path, log_path, logfile, terminating, logger, logQueue, res_path
    res_path = results_path
    haplotype_path, cancer_dir_path, tmpbams_path, finalbams_path, log_path, logfile = handle.GetProjectPaths(
        results_path)
    terminating, logger, logQueue = handle.GetLoggings(logfile)

    chr_list = ['chr' + str(x) for x in range(1, 23)]
    chr_list.extend(['chrX', 'chrY'])

    t0 = time.time()
    outbamfn = params.GetOutputFileName()

    cnv_list = glob.glob("/".join([params.GetCNVDir(), '*.*']))
    chromosome_event = create_chr_event_list(cnv_list, chr_list)

    logger.debug('pipeline started!')

    phase_path = '/'.join([results_path, 'phasedvcfdir'])
    if not os.path.exists('/'.join([results_path, 'phasedvcfdir'])):
        os.makedirs(phase_path)

    initialize0(phase_path, cancer_dir_path)

    for cnv_path in cnv_list:
        initialize_pipeline(phase_path, haplotype_path, cnv_path)

    pool1 = multiprocessing.Pool(processes=12, initializer=initPool,
                                 initargs=[logQueue, logger.getEffectiveLevel(), terminating])
    try:

        if not params.GetSplitBamsPath():

            if not os.path.exists("/".join([res_path, 'splitbams'])):
                os.makedirs("/".join([res_path, 'splitbams']))
                params.SetSplitBamsPath("/".join([res_path, 'splitbams']))

            result0 = pool1.map_async(split_bam_by_chr, chromosome_event).get(9999999)

        result1 = pool1.map_async(find_roi_bam, chromosome_event).get(9999999)
        result2 = pool1.map_async(implement_cnv, chromosome_event).get(9999999)
        pool1.close()
    except KeyboardInterrupt:
        logger.debug('You cancelled the program!')
        pool1.terminate()
    except Exception as e:
        logger.exception("Exception in main %s", e)
        pool1.terminate()
    finally:
        pool1.join()
    time.sleep(.1)
    mergeSortBamFiles(outbamfn, finalbams_path)
    t1 = time.time()
    #shutil.rmtree(tmpbams_path)
    logger.debug(' ***** pipeline finished in ' + str(round((t1 - t0) / 60.0, 1)) + ' minutes ***** ')
    logging.shutdown()
