from configparser import ConfigParser
from utils.CondorJobSubmitter import CondorJobSubmitter
from utils.LocalJobSubmitter import LocalJobSubmitter

import os
import tensorflow as tf

class TrainingConfig:
    # branches to use for the training
    training_branches = ["mBB", "dRBB", "pTB1", "pTB2", "MET", "dEtaBB", "dPhiMETdijet", "SumPtJet"]
    nuisance_branches = ["mBB"]
    auxiliary_branches = ["EventWeight", "mBB", "dRBB", "nJ"]

    training_pars = {"pretrain_batches": 100, "training_batches": 800, "statistics_interval": 10}

    training_slice = [0.0, 0.33]
    validation_slice = [0.33, 0.44]
    test_slice = [0.44, 1.0]

    data_path = os.path.join(os.environ["ROOTDIR"], "examples", "training-MadGraphPy8-ATLAS-small.h5")
    submitter = LocalJobSubmitter # "CondorJobSubmitter" also works

    sig_samples = ["Hbb"]
    sig_sampling_lengths = [1.0]

    bkg_samples = ["Zjets", "Wjets", "ttbar", "diboson"]
    bkg_sampling_lengths = [1.0, 1.0, 1.0, 1.0]

    # bkg_samples = ["Zjets"]
    # bkg_sampling_lengths = [1.0]

    sample_reweighting = {"Hbb": 1.0, "Zjets": 1.0, "Wjets": 1.0, "ttbar": 1.0, "diboson": 1.0}

    session_config = tf.ConfigProto(intra_op_parallelism_threads = 1, 
                                    inter_op_parallelism_threads = 1,
                                    allow_soft_placement = True, 
                                    device_count = {'CPU': 1})
    
    @classmethod
    def from_file(cls, config_dir):
        gconfig = ConfigParser()
        gconfig.read(os.path.join(config_dir, "meta.conf"))

        cur_pars = {key: float(val) for key, val in gconfig["TrainingConfig"].items()}

        obj = cls()
        obj.training_pars.update(cur_pars)

        return obj        
