#!/usr/bin/env python

# This file is part of PyPop

# Copyright (C) 2003. The Regents of the University of California (Regents)
# All Rights Reserved.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.

# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.

# IN NO EVENT SHALL REGENTS BE LIABLE TO ANY PARTY FOR DIRECT,
# INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING
# LOST PROFITS, ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS
# DOCUMENTATION, EVEN IF REGENTS HAS BEEN ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.

# REGENTS SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING
# DOCUMENTATION, IF ANY, PROVIDED HEREUNDER IS PROVIDED "AS
# IS". REGENTS HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT,
# UPDATES, ENHANCEMENTS, OR MODIFICATIONS.

"""Python population genetics statistics.
"""

import sys, os, string, time

from ParseFile import ParseGenotypeFile
from Arlequin import ArlequinExactHWTest
from Haplo import Emhaplofreq, HaploArlequin
from HardyWeinberg import HardyWeinberg, HardyWeinbergGuoThompson, HardyWeinbergGuoThompsonArlequin
from Homozygosity import Homozygosity, HomozygosityEWSlatkinExact
from ConfigParser import ConfigParser, NoOptionError
from Utils import XMLOutputStream, TextOutputStream
from Filter import PassThroughFilter, AnthonyNolanFilter, AlleleCountAnthonyNolanFilter

def getConfigInstance(configFilename = None,
                      altpath = None,
                      usage_message = None):
    """Create and return ConfigParser instance.

    Taken a specific .ini filename and an alternative path to search
    if no .ini filename is given.
    """
    config = ConfigParser()

    if os.path.isfile(configFilename):
        config.read(configFilename)
    else:
        if specifiedConfigFile:
          sys.exit("Could not find config file: `%s' " % configFilename)
        else:
          if os.path.isfile(altpath):
            config.read(altpath)
          else:
            sys.exit("Could not find config file either in current directory or " +
                     altpath + os.linesep + usage_message)

    if len(config.sections()) == 0:
        sys.exit("No output defined!  Exiting...")

    return config


class Main:
    """Main interface to the PyPop modules.

    Given a config instance, which can be:

    - created from a filename passed from command-line argument or;

    - from values populated by the GUI (currently selected from an
      .ini file, but can ultimately be set directly from the GUI or
      values based from a form to a web server or the).
      
    runs the specified modules.
    """
    def __init__(self,
                 config=None,
                 debugFlag=0,
                 fileName=None,
                 datapath=None,
                 use_libxsltmod=1,
                 use_FourSuite=0,
                 thread=None):

        self.config = config
        self.debugFlag = debugFlag
        self.fileName = fileName
        self.datapath = datapath
        self.use_libxsltmod = use_libxsltmod
        self.use_FourSuite = use_FourSuite

        # for threading to work
        self.thread = thread

        # parse out the parts of the filename
        baseFileName = os.path.basename(self.fileName)
        prefixFileName = string.split(baseFileName, ".")[0]

        # generate date and time

        now = time.time()
        datestr = time.strftime("%Y-%m-%d", time.localtime(now))
        timestr = time.strftime("%H-%M-%S", time.localtime(now))

        # Parse "General" section

        try:
          debug = self.config.getboolean("General", "debug")
        except NoOptionError:
          debug=0
        except ValueError:
          sys.exit("require a 0 or 1 as debug flag")

        # if "-d" command line option used, then respect that, overriding
        # self.config file setting

        if debugFlag == 1:
          debug = 1

        # generate file prefix
        try:
          outFilePrefixType = self.config.get("General", "outFilePrefixType")
          if outFilePrefixType == 'filename':
            uniquePrefix = prefixFileName
          else:
            sys.exit("outFilePrefixType: %s must be 'filename'" % outFilePrefixType)
        except NoOptionError:
          uniquePrefix = "%s-%s-%s" % (prefixFileName, datestr, timestr)  


        # generate filenames for both text and XML files

        defaultTxtOutFilename = uniquePrefix + "-out.txt"
        try:
          txtOutFilename = self.config.get("General", "txtOutFilename")
          if txtOutFilename == '':
            txtOutFilename = defaultTxtOutFilename
        except NoOptionError:
          txtOutFilename = defaultTxtOutFilename

        defaultXmlOutFilename = uniquePrefix + "-out.xml"
        try:
          xmlOutFilename = self.config.get("General", "xmlOutFilename")
          if xmlOutFilename == '':
            xmlOutFilename = defaultXmlOutFilename
        except NoOptionError:
          xmlOutFilename = defaultXmlOutFilename

        # generate filename for logging filter output

        defaultFilterLogFilename = uniquePrefix + "-filter.xml"

        if debug:
          for section in self.config.sections():
            print section
            for option in self.config.options(section):
              print " ", option, "=", self.config.get(section, option)

        # if 'frozen' look for VERSION info in current directory
        if hasattr(sys, 'frozen'):
          versionpath = 'VERSION'
        # otherwise look in installed self.datapath, by default
        else:
          versionpath = os.path.join(self.datapath, 'VERSION')

        # bein a development version trumps all..
        if os.path.isfile('DEVEL_VERSION'):
          version = 'DEVEL_VERSION'
        elif os.path.isfile(versionpath):
          f = open(versionpath)
          version = string.strip(f.readline())
        else:
          sys.exit("Could not find a version!  Exiting...")

        altpath = os.path.join(self.datapath, 'self.config.ini')

        # Parse "ParseFile" section
        try:
          alleleDesignator = self.config.get("ParseFile", "alleleDesignator")
        except NoOptionError:
          alleleDesignator = '*'

        try:
          untypedAllele = self.config.get("ParseFile", "untypedAllele")
        except NoOptionError:
          untypedAllele = '****'

        try:
          fieldPairDesignator = self.config.get("ParseFile", "fieldPairDesignator")
        except NoOptionError:
          fieldPairDesignator = '(2)'

        try:
          validPopFields = self.config.get("ParseFile", "validPopFields")
        except NoOptionError:
          sys.exit("No valid population fields defined")

        try:
          popNameDesignator = self.config.get("ParseFile", "popNameDesignator")
        except NoOptionError:
          popNameDesignator = "+"

        try:
          validSampleFields = self.config.get("ParseFile", "validSampleFields")
        except NoOptionError:
          sys.exit("No valid sample fields defined")

        try:
          useAnthonyNolanFilter=self.config.getboolean("ParseFile", "useAnthonyNolanFilter")
        except NoOptionError:
          useAnthonyNolanFilter=0

        if useAnthonyNolanFilter:
          try:
            anthonynolanPath=self.config.get("ParseFile", "anthonynolanPath")
          except NoOptionError:
            anthonynolanPath=os.path.join(self.datapath, "anthonynolan", "HIG-seq-pep-text")
            if debug:
              print "Defaulting to system datapath %s for anthonynolanPath data" % anthonynolanPath

          # open log file for filter in append mode
          filterLogFile = XMLOutputStream(open(defaultFilterLogFilename, 'w'))

          # create a data cleaning filter to pass all data through

          filter = AnthonyNolanFilter(debug=debug,
                                      directoryName=anthonynolanPath,
                                      untypedAllele=untypedAllele,
                                      filename=fileName,
                                      logFile=filterLogFile)

          #filter = AlleleCountAnthonyNolanFilter(debug=debug,
          #                                       directoryName=anthonynolanPath,
          #                                       untypedAllele=untypedAllele,
          #                                       filename=fileName,
          #                                       logFile=filterLogFile,
          #                                       lumpThreshold=5)

        else:
          # don't use filter, just create a "pass through filter"
          filter = PassThroughFilter()

        # Generate the parse file object
        input = ParseGenotypeFile(fileName,
                                  validPopFields=validPopFields,
                                  validSampleFields=validSampleFields,
                                  alleleDesignator=alleleDesignator, 
                                  untypedAllele=untypedAllele,
                                  popNameDesignator=popNameDesignator,
                                  fieldPairDesignator=fieldPairDesignator,
                                  filter=filter,
                                  debug=debug)

        # start output
        
        # create XML stream
        xmlStream = XMLOutputStream(open(xmlOutFilename, 'w'))

        # opening tag
        xmlStream.opentag('dataanalysis xmlns:xi="http://www.w3.org/2001/XInclude"', date="%s-%s" % (datestr, timestr))
        xmlStream.writeln()

        if useAnthonyNolanFilter:

            # if and only if filtering is done, generate XInclude XML
            # file output reference, to include
            # <popfilename>-filter.log
            
            xmlStream.opentag('xi:include', href=defaultFilterLogFilename, parse="xml")
            xmlStream.writeln()
            xmlStream.emptytag('xi:fallback')
            xmlStream.writeln()
            xmlStream.closetag('xi:include')
            xmlStream.writeln()

        # more meta-data
        xmlStream.tagContents('filename', baseFileName)
        xmlStream.writeln()
        xmlStream.tagContents('pypop-version', version)
        xmlStream.writeln()

        # serialize summary info for population in XML
        input.serializeMetadataTo(xmlStream)

        loci = input.getLocusList()

        for locus in loci:

          if thread and thread._want_abort:
            from wxPython.wx import wxPostEvent
            from GUIApp import ResultEvent
            # Use a result of None to acknowledge the abort (of
            # course you can use whatever you'd like or even
            # a separate event type)
            wxPostEvent(thread._notify_window,ResultEvent(None))
            return
            
          xmlStream.opentag('locus', name=locus)
          xmlStream.writeln()

          input.serializeAlleleCountDataAt(xmlStream, locus)

          # Parse "HardyWeinberg" section

          if self.config.has_section("HardyWeinberg") and \
             len(self.config.options("HardyWeinberg")) > 0:

            try:
              lumpBelow =  self.config.getint("HardyWeinberg", "lumpBelow")
            except NoOptionError:
              lumpBelow=5
            except ValueError:
              sys.exit("require integer value")

            hwObject = HardyWeinberg(input.getLocusDataAt(locus), 
                                     input.getAlleleCountAt(locus), 
                                     lumpBelow=lumpBelow,
                                     debug=debug)

            # serialize HardyWeinberg
            hwObject.serializeTo(xmlStream)

          # Parse "HardyWeinbergGuoThompson"

          if self.config.has_section("HardyWeinbergGuoThompson") and \
             len(self.config.options("HardyWeinbergGuoThompson")) > 0:

            try:
              dememorizationSteps = self.config.getint("HardyWeinbergGuoThompson",
                                                  "dememorizationSteps")
            except NoOptionError:
              dememorizationSteps=2000
            except ValueError:
              sys.exit("require integer value")

            try:
              samplingNum = self.config.getint("HardyWeinbergGuoThompson", "samplingNum")
            except NoOptionError:
              samplingNum=1000
            except ValueError:
              sys.exit("require integer value")

            try:
              samplingSize = self.config.getint("HardyWeinbergGuoThompson", "samplingSize")
            except NoOptionError:
              samplingSize=1000
            except ValueError:
              sys.exit("require integer value")

            try:
              maxMatrixSize = self.config.getint("HardyWeinbergGuoThompson", "maxMatrixSize")
            except NoOptionError:
              maxMatrixSize=250
            except ValueError:
              sys.exit("require integer value")

            # guo & thompson implementation
            hwObject=HardyWeinbergGuoThompson(input.getLocusDataAt(locus), 
                                              input.getAlleleCountAt(locus),
                                              dememorizationSteps=dememorizationSteps,
                                              samplingNum=samplingNum,
                                              samplingSize=samplingSize,
                                              maxMatrixSize=maxMatrixSize,
                                              debug=debug)

            hwObject.dumpTable(locus, xmlStream)
            xmlStream.writeln()

          if self.config.has_section("HardyWeinbergGuoThompsonArlequin"):

            # default location for Arlequin executable
            arlequinExec = 'arlecore.exe'

            if self.config.has_section("Arlequin"):

              try:
                arlequinExec = self.config.get("Arlequin", "arlequinExec")
              except NoOptionError:
                print "Location to Arlequin executable file not given: assume `arlecore.exe' is in user's PATH"

            try:
              markovChainStepsHW = self.config.getint("HardyWeinbergGuoThompsonArlequin", \
                                                 "markovChainStepsHW")
            except NoOptionError:
              samplingNum=100000
            except ValueError:
              sys.exit("require integer value")

            try:
              markovChainDememorisationStepsHW = self.config.getint("HardyWeinbergGuoThompsonArlequin", "markovChainDememorisationStepsHW")
            except NoOptionError:
              samplingNum=100000
            except ValueError:
              sys.exit("require integer value")


            hwArlequin=HardyWeinbergGuoThompsonArlequin(input.getIndividualsData(),
                                                        locusName = locus,
                                                        arlequinExec = arlequinExec,
                                                        markovChainStepsHW = \
                                                        markovChainStepsHW,
                                                        markovChainDememorisationStepsHW=markovChainDememorisationStepsHW,
                                                        untypedAllele=untypedAllele,
                                                        debug=debug)
            hwArlequin.serializeTo(xmlStream)


          # Parse "Homozygosity" section

          if self.config.has_section("Homozygosity"):

            try:
              rootPath=self.config.get("Homozygosity", "rootPath")
            except NoOptionError:
              rootPath=os.path.join(self.datapath, "homozygosity")
              if debug:
                print "Defaulting to system datapath %s for homozygosity tables" % rootPath


            hzObject = Homozygosity(input.getAlleleCountAt(locus),
                                    rootPath=rootPath,
                                    debug=debug)

            hzObject.serializeHomozygosityTo(xmlStream)

          if self.config.has_section("HomozygosityEWSlatkinExact"):

            try:
              numReplicates=self.config.getint("HomozygosityEWSlatkinExact", \
                                          "numReplicates")
            except NoOptionError:
              numReplicates=10000

            hzExactObj = HomozygosityEWSlatkinExact(input.getAlleleCountAt(locus),
                                                    numReplicates=numReplicates,
                                                    debug=debug)

            hzExactObj.serializeHomozygosityTo(xmlStream)

          xmlStream.closetag('locus')
          xmlStream.writeln()

        # estimate haplotypes

        if self.config.has_section("Emhaplofreq"):

          # create object to generate haplotype and LD statistics
          # a wrapper around the emhaplofreq module
          haplo = Emhaplofreq(input.getIndividualsData(),
                              debug=debug,
                              untypedAllele=untypedAllele)

          try:
            allPairwiseLD = self.config.getboolean("Emhaplofreq", "allPairwiseLD")
          except NoOptionError:
            allPairwiseLD=0
          except ValueError:
            sys.exit("require a 0 or 1 as a flag")

          try:
            allPairwiseLDWithPermu = self.config.getboolean("Emhaplofreq",
                                                       "allPairwiseLDWithPermu")
          except NoOptionError:
            allPairwiseLDWithPermu=0
          except ValueError:
            sys.exit("require a 0 or 1 as a flag")

          if allPairwiseLD:
            print "estimating all pairwise LD:",
            if allPairwiseLDWithPermu:
              print "with permutation test"
            else:
              print "with no permutation test"


          # first set the list of 2-locus haplotypes to show to empty
          twoLocusHaplosToShow = []

          try:
            locusKeys=self.config.get("Emhaplofreq", "lociToEstHaplo")

            if locusKeys == '*':
              print "wildcard '*' given for lociToEstHaplo, assume entire data set"
              locusKeys=string.join(input.getIndividualsData().colList,':')

            # if we will be running allPairwise*, then exclude any two-locus
            # haplotypes, since we will estimate them as part of 'all pairwise'
            if allPairwiseLD:

              modLocusKeys = []
              for group in string.split(locusKeys, ','):

                # if a two-locus haplo, add it to the list that allPairwise
                # will use
                if len(string.split(group, ':')) == 2:
                  twoLocusHaplosToShow.append(string.upper(group))

                # otherwise add it to the regular output
                else:
                  modLocusKeys.append(group)

              locusKeys = string.join(modLocusKeys, ',')

            # estimate haplotypes on set of locusKeys *only* if there are
            # locus groups that remain after excluding two locus haplotypes
            if locusKeys:
                haplo.estHaplotypes(locusKeys)

          except NoOptionError:
            print "no loci provided for which to estimate haplotype frequencies"

          try:
            locusKeysLD=self.config.get("Emhaplofreq", "lociToEstLD")

            if locusKeysLD == '*':
              print "wildcard '*' given for lociToEstLD, assume entire data set"
              locusKeysLD=string.join(input.getIndividualsData().colList,':')

            # estimate LD for the specified loci
            haplo.estLinkageDisequilibrium(locusKeysLD)

          except NoOptionError:
            print "no loci provided for which to estimate LD"

          # do all pairwise LD, w/ or w/o permutation test
          if allPairwiseLD:
            haplo.allPairwise(permutationFlag=allPairwiseLDWithPermu,
                              haploSuppressFlag=0,
                              haplosToShow=twoLocusHaplosToShow)

          # serialize to XML
          haplo.serializeTo(xmlStream)

        # closing tag
        xmlStream.closetag('dataanalysis')

        # close XML stream
        xmlStream.close()

        # create default XSL stylesheet location
        xslFilenameDefault = os.path.join(self.datapath, 'text.xsl')

        # check self.config options, and use that location, if provided
        try:
          xslFilename = self.config.get("General", "xslFilename")
        except NoOptionError:
          xslFilename=xslFilenameDefault

        # check to see if file exists, otherwise fail with an error
        if os.path.isfile(xslFilename):
          pass
        else:
          sys.exit("Could not find xsl file: `%s' " % xslFilename)

        if self.use_libxsltmod:

          # now use bindings that are part of libxml2/libxslt 
          import libxml2
          import libxslt

          # read and parse stylesheet
          styledoc = libxml2.parseFile(xslFilename)
          style = libxslt.parseStylesheetDoc(styledoc)

          # read output XML file
          doc = libxml2.parseFile(xmlOutFilename)

          # resolve and perform any XIncludes the document may have
          doc.xincludeProcess()

          # process via stylesheet
          result = style.applyStylesheet(doc, None)

          # save result to file
          style.saveResultToFilename(txtOutFilename, result, 0)

          # cleanup
          style.freeStylesheet()
          doc.freeDoc()
          result.freeDoc()

        if self.use_FourSuite:

          from xml.xslt.Processor import Processor

          # open XSLT stylesheet
          styleSheet = open(xslFilename, 'r')

          # re-open text stream
          xmlStream = open(xmlOutFilename, 'r')

          # open new txt output
          newOut = TextOutputStream(open(txtOutFilename, 'w'))

          # create xsl process
          p = Processor()

          # attach the stylesheet
          p.appendStylesheetStream(styleSheet)

          # run the stylesheet on the XML output
          p.runStream(xmlStream, outputStream=newOut)

          # close streams
          newOut.close()
          styleSheet.close()