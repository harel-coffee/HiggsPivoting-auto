import os
import numpy as np
import pandas as pd
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from sklearn import metrics
from sklearn.feature_selection import mutual_info_regression

class ModelEvaluator:

    def __init__(self, env):
        self.env = env

    # computes the Kolmogorov-Smirnov test statistic from samples p and q, drawn from some distributions, given some event weights
    def _get_KS(self, p, p_weights, q, q_weights, num_pts = 1000):
        # don't attempt to do anything if there is no data
        if len(p) == 0 or len(q) == 0:
            return 1.0

        # also refuse to do anything for very unbalanced data
        if min(len(p), len(q)) / max(len(p), len(q)) < 0.05:
            return 1.0

        p = p.flatten()
        q = q.flatten()

        # first, need to compute the cumulative distributions
        p_inds_sorted = np.argsort(p)
        p_sorted = p[p_inds_sorted]
        p_weights_sorted = p_weights[p_inds_sorted]

        q_inds_sorted = np.argsort(q)
        q_sorted = q[q_inds_sorted]
        q_weights_sorted = q_weights[q_inds_sorted]

        # these hold the values of the cumulative distributions, evaluated at the positions
        # corresponding to "p_stored" and "q_stored"
        p_cum = np.cumsum(p_weights_sorted)
        p_cum /= p_cum[-1]

        q_cum = np.cumsum(q_weights_sorted)
        q_cum /= q_cum[-1]

        # now, need to evaluate them on a common grid such that can look for the maximum absolute difference between 
        # the two distributions
        absmin = min(p_sorted[0], q_sorted[0])
        absmax = max(p_sorted[-1], q_sorted[-1])
        valgrid = np.linspace(absmin, absmax, num_pts)

        p_cum_interp = np.interp(valgrid, p_sorted, p_cum, left = 0.0, right = 1.0)
        q_cum_interp = np.interp(valgrid, q_sorted, q_cum, left = 0.0, right = 1.0)

        # then get the KS metric as the maximum distance between them
        KS = np.amax(np.abs(p_cum_interp - q_cum_interp))

        return KS

    # computes a series of performance measures and saves them to a file
    # currently, computes AUROC as robust performance measure, KL as robust fairness measure
    def get_performance_metrics(self, data_sig, data_bkg, nuis_sig, nuis_bkg, sig_weights, bkg_weights, labels_sig, labels_bkg, sigeffs = [0.5, 0.25]):
        perfdict = {}

        pred_bkg = [self.env.predict(data = sample)[:,1] for sample in data_bkg]
        pred_sig = [self.env.predict(data = sample)[:,1] for sample in data_sig]

        pred_sig_merged = np.concatenate(pred_sig)
        pred_bkg_merged = np.concatenate(pred_bkg)

        nuis_bkg_merged = np.concatenate(nuis_bkg)
        weights_bkg_merged = np.concatenate(bkg_weights)

        # compute the AUROC of this classifier
        pred = np.concatenate([pred_sig_merged, pred_bkg_merged], axis = 0)
        weights = np.concatenate(sig_weights + bkg_weights, axis = 0)
        labels = np.concatenate([np.ones(len(pred_sig_merged)), np.zeros(len(pred_bkg_merged))], axis = 0)

        auroc = metrics.roc_auc_score(labels, pred, sample_weight = weights)
        perfdict["AUROC"] = auroc

        # to get the KS fairness metrics, need to compute the cut values for the given signal efficiencies
        pred_sig_merged = np.concatenate(pred_sig, axis = 0)
        weights_sig_merged = np.concatenate(sig_weights, axis = 0)

        cutvals = [self._weighted_percentile(pred_sig_merged, 1 - sigeff, weights = weights_sig_merged) for sigeff in sigeffs]

        # apply the classifier cuts
        for cutval, sigeff in zip(cutvals, sigeffs):

            KS_vals = []

            # compute the KS test statistic separately for each signal and background component, as well as for each given signal efficiency
            for cur_pred, cur_nuis, cur_weights, cur_label in zip(pred_sig + pred_bkg, nuis_sig + nuis_bkg, sig_weights + bkg_weights, labels_sig + labels_bkg):

                cut_passed = np.where(cur_pred > cutval)
                cur_nuis_passed = cur_nuis[cut_passed]
                cur_weights_passed = cur_weights[cut_passed]

                cur_KS = self._get_KS(cur_nuis, cur_weights, cur_nuis_passed, cur_weights_passed)
                KS_vals.append(cur_KS)

                cur_dictlabel = "KS_" + str(int(sigeff * 100)) + "_" + cur_label
                perfdict[cur_dictlabel] = cur_KS
                
            perfdict["KS_" + str(int(sigeff * 100)) + "_avg"] = sum(KS_vals) / len(KS_vals)

            # also compute KS for the combined background (all components merged)
            cut_passed = np.where(pred_bkg_merged > cutval)
            cur_nuis_passed = nuis_bkg_merged[cut_passed]
            cur_weights_passed = weights_bkg_merged[cut_passed]
            cur_KS = self._get_KS(nuis_bkg_merged, weights_bkg_merged, cur_nuis_passed, cur_weights_passed)
            perfdict["KS_" + str(int(sigeff * 100)) + "_bkg"] = cur_KS

        # also add some information on the evaluated model itself, which could be useful for the combined plotting later on
        paramdict = self.env.create_paramdict()
        perfdict.update(paramdict)

        return perfdict

    # plot the ROC of the classifier
    def plot_roc(self, data_sig, data_bkg, sig_weights, bkg_weights, outpath):
        # need to merge all signal- and background samples
        data_sig = np.concatenate(data_sig, axis = 0)
        data_bkg = np.concatenate(data_bkg, axis = 0)
        sig_weights = np.concatenate(sig_weights, axis = 0)
        bkg_weights = np.concatenate(bkg_weights, axis = 0)

        pred_bkg = self.env.predict(data = data_bkg)[:,1]
        pred_sig = self.env.predict(data = data_sig)[:,1]

        pred = np.concatenate([pred_sig, pred_bkg], axis = 0)
        weights = np.concatenate([sig_weights, bkg_weights], axis = 0)
        labels = np.concatenate([np.ones(len(pred_sig)), np.zeros(len(pred_bkg))], axis = 0)

        fpr, tpr, thresholds = metrics.roc_curve(labels, pred, sample_weight = weights)
        auc = metrics.roc_auc_score(labels, pred, sample_weight = weights)

        # plot the ROC
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.plot(tpr, fpr, color = 'black')
        ax.set_xlabel("signal efficiency")
        ax.set_ylabel("background efficiency")
        ax.set_aspect(1.0)
        ax.text(0.75, 0.0, "AUC = {:.2f}".format(auc))
        plt.tight_layout()

        # create the output directory if it doesn't already exist and save the figure(s)
        if not os.path.exists(outpath):
            os.makedirs(outpath)
        fig.savefig(os.path.join(outpath, "ROC.pdf"))
        plt.close()

    # plot the mBB spectrum of the passed signal and background datasets
    def plot_mBB_distortion(self, data_sig, data_bkg, nuis_sig, nuis_bkg, weights_sig, weights_bkg, sigeffs, outpath, labels_sig = None, labels_bkg = None, num_cols = 2):
        pred_bkg = [self.env.predict(data = sample)[:,1] for sample in data_bkg]
        pred_sig = [self.env.predict(data = sample)[:,1] for sample in data_sig]
        
        # create the output directory if it doesn't already exist and save the figure(s)
        if not os.path.exists(outpath):
            os.makedirs(outpath)
        
        # compute the classifier cut values needed to achieve a certain signal efficiency
        pred_sig_merged = np.concatenate(pred_sig)
        weights_sig_merged = np.concatenate(weights_sig)
        cutvals = [self._weighted_percentile(pred_sig_merged, 1 - sigeff, weights = weights_sig_merged) for sigeff in sigeffs]

        for cutval, sigeff in zip(cutvals, sigeffs):
            print("classifier cut for {}% signal efficiency: {}".format(sigeff * 100, cutval))

        pred = pred_sig + pred_bkg
        nuis = nuis_sig + nuis_bkg
        weights = weights_sig + weights_bkg
        labels = labels_sig + labels_bkg

        fig = plt.figure(figsize = (15, 10))
        num_rows = len(pred) / num_cols

        # iterate over all data samples and fill a separate subplot for each
        for ind, (cur_pred, cur_nuis, cur_weights, cur_label) in enumerate(zip(pred, nuis, weights, labels)):
            plot_data = [cur_nuis]
            plot_weights = [cur_weights]
            plot_labels = [cur_label]

            # apply the classifier cuts
            for cutval, sigeff in zip(cutvals, sigeffs):
                cut_passed = np.where(cur_pred > cutval)
                plot_data.append(cur_nuis[cut_passed])
                plot_weights.append(cur_weights[cut_passed])
                plot_labels.append(cur_label + " ({}% signal eff.)".format(sigeff * 100))
                
            self._add_subplot(fig, vals = plot_data, weights = plot_weights, labels = plot_labels, nrows = num_rows, ncols = num_cols, num = ind + 1)
            
        # save the completed figure
        plt.tight_layout()
        fig.savefig(os.path.join(outpath, "dists_separate.pdf")) 
        plt.close()

    def _weighted_percentile(self, data, percentile, weights):
        # ensure that everything operates on flat data
        data = data.flatten()
        weights = weights.flatten()

        # first, reshuffle the data and the weights such that the data
        # is given in ascending order
        inds_sorted = np.argsort(data)
        data = data[inds_sorted]
        weights = weights[inds_sorted]

        # Note: the subtraction is just a tiebreaker
        weighted_percentiles = np.cumsum(weights) - 0.5 * weights

        # normalize between zero and one
        weighted_percentiles -= weighted_percentiles[0]
        weighted_percentiles /= weighted_percentiles[-1]

        retval = np.interp(percentile, weighted_percentiles, data)
        return retval

    def _add_subplot(self, fig, vals, weights, labels, nrows, ncols, num):
        ax = fig.add_subplot(nrows, ncols, num)
        ax.hist(vals, weights = weights, bins = 40, range = (0, 500), density = True, histtype = 'step', stacked = False, fill = False, label = labels)
        ax.legend()
        ax.set_xlabel(r'$m_{bb}$ [GeV]')
        ax.set_ylabel('a.u.')
        
    # produce all performance plots showing an individual model: show the ROC curve as well as the distortion of the mBB spectrum
    def performance_plots(self, data_sig, data_bkg, nuis_sig, nuis_bkg, weights_sig, weights_bkg, outpath, labels_sig = None, labels_bkg = None):
        self.plot_roc(data_sig, data_bkg, weights_sig, weights_bkg, outpath)
        self.plot_mBB_distortion(data_sig, data_bkg, nuis_sig, nuis_bkg, weights_sig, weights_bkg, [0.5, 0.25], outpath, labels_sig, labels_bkg)
