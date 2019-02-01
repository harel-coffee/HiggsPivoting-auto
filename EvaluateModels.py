import os, pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_selection import mutual_info_regression
from argparse import ArgumentParser

from models.AdversarialEnvironment import AdversarialEnvironment
from plotting.ModelEvaluator import ModelEvaluator
from plotting.TrainingStatisticsPlotter import TrainingStatisticsPlotter
from plotting.PerformancePlotter import PerformancePlotter
from DatasetExtractor import TrainNuisAuxSplit

def main():
    parser = ArgumentParser(description = "evaluate adversarial networks")
    parser.add_argument("--data", action = "store", dest = "infile_path")
    parser.add_argument("--plot_dir", action = "store", dest = "plot_dir")
    parser.add_argument("model_dirs", nargs = '+', action = "store")
    args = vars(parser.parse_args())

    infile_path = args["infile_path"]
    model_dirs = args["model_dirs"]
    plot_dir = args["plot_dir"]

    # read the training data
    sig_samples = ["Hbb"]
    bkg_samples = ["ttbar", "Zjets", "Wjets", "diboson", "singletop"]

    print("loading data ...")
    sig_data = [pd.read_hdf(infile_path, key = sig_sample) for sig_sample in sig_samples]
    bkg_data = [pd.read_hdf(infile_path, key = bkg_sample) for bkg_sample in bkg_samples]

    # extract the test dataset
    test_size = 0.2
    sig_data_test = []
    sig_nuis_test = []
    sig_weights_test = []
    for sample in sig_data:
        _, cur_test = train_test_split(sample, test_size = test_size, shuffle = True, random_state = 12345)
        cur_testdata, cur_nuisdata, cur_weights = TrainNuisAuxSplit(cur_test)
        sig_data_test.append(cur_testdata)
        sig_nuis_test.append(cur_nuisdata)
        sig_weights_test.append(cur_weights)

    bkg_data_test = []
    bkg_nuis_test = []
    bkg_weights_test = []
    for sample in bkg_data:
        _, cur_test = train_test_split(sample, test_size = test_size, shuffle = True, random_state = 12345)
        cur_testdata, cur_nuisdata, cur_weights = TrainNuisAuxSplit(cur_test)
        bkg_data_test.append(cur_testdata)
        bkg_nuis_test.append(cur_nuisdata)
        bkg_weights_test.append(cur_weights)

    for model_dir in model_dirs:
        print("now evaluating " + model_dir)

        mce = AdversarialEnvironment.from_file(model_dir)

        plots_outdir = plot_dir

        # generate performance plots for each model individually
        ev = ModelEvaluator(mce)
        ev.performance_plots(sig_data_test, bkg_data_test, sig_nuis_test, bkg_nuis_test, sig_weights_test, bkg_weights_test,
                             plots_outdir, labels_sig = sig_samples, labels_bkg = bkg_samples)

        # get performance metrics and save them
        perfdict = ev.get_performance_metrics(sig_data_test, bkg_data_test, sig_nuis_test, bkg_nuis_test, sig_weights_test, 
                                              bkg_weights_test, labels_sig = sig_samples, labels_bkg = bkg_samples)
        print("got perfdict = " + str(perfdict))
        with open(os.path.join(plots_outdir, "perfdict.pkl"), "wb") as outfile:
           pickle.dump(perfdict, outfile)

        # generate plots showing the evolution of certain parameters during training
        tsp = TrainingStatisticsPlotter(model_dir)
        tsp.plot(outdir = plots_outdir)

if __name__ == "__main__":
    main()
