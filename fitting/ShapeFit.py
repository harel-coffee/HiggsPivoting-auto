# run it with HistFitter.py -w -f -d -D "after,corrMatrix" -F excl -a --userArg input_dir TemplateAnalysisSimple.py

import ROOT, sys
from argparse import ArgumentParser

# HistFitter imports
from configManager import configMgr
from configWriter import fitConfig,Measurement,Channel,Sample
from systematic import Systematic

from HistogramImporter import HistogramImporter

# read the path of the directory containing the input template histograms
indir = configMgr.userArg

configMgr.doExclusion = True
configMgr.calculatorType = 2
configMgr.testStatType = 3
configMgr.nPoints = 20

configMgr.analysisName = "TemplateAnalysisSimple"
configMgr.outputFileName = "results/{}.root".format(configMgr.analysisName)

# signal regions that are to be used for this fit
region_names = ["SR1", "SR2"]

# names of the individual input files for the above regions
# Note: these must exist in the directory 'indir' passed above
region_infiles = ["templates_SR1.root", "templates_SR2.root"]

# names of the individual signal templates available in each region
template_names = ["sig", "bkg"]
template_colors = [ROOT.kGreen - 9, ROOT.kPink]

# turn off any additional selection cuts
for region_name in region_names:
    configMgr.cutsDict[region_name] = "1."

# configMgr.cutsDict["SR1"] = "1."
# configMgr.cutsDict["SR2"] = "1."

configMgr.weights = "1."

samples = []
channels = []
POIs = []

# prepare the fit configuration
ana = configMgr.addFitConfig("shape_fit")
meas = ana.addMeasurement(name = "shape_fit", lumi = 1.0, lumiErr = 0.01)

# load all MC templates ...
for template_name, template_color in zip(template_names, template_colors):

    cur_sample = Sample(template_name, template_color)
    POI_name = "mu_" + template_name
    cur_sample.setNormFactor(POI_name, 1, 0, 100)

    # ... for all regions
    for region_name, region_infile in zip(region_names, region_infiles):
        binvals, edges = HistogramImporter.import_histogram(os.path.join(indir, region_infile), template_name)
        bin_width = edges[1] - edges[0]

        cur_sample.buildHisto(binvals, region_name, "mBB", binLow = edges[0], binWidth = bin_width)

    samples.append(cur_sample)
    POIs.append(POI_name)

# create a Channel object for each analysis region
for region_name in region_names:
    cur_channel = ana.addChannel("mBB", [region_name], nBins = len(binvals), binLow = edges[0], binHigh = edges[-1])

    # add all the samples to it
    for sample in samples:
        cur_channel.addSample(sample)

    channels.append(cur_channel)

# add all POIs to the fit configuration
for POI in POIs:
    meas.addPOI(POI)

# ignore luminosity uncertainty
meas.addParamSetting("Lumi", True, 1)

# finally, add all the channels
ana.addSignalChannels(channels)

# remove temporary files
if configMgr.executeHistFactory:
    if os.path.isfile("data/{}.root".format(configMgr.analysisName)):
        os.remove("data/{}.root".format(configMgr.analysisName))

