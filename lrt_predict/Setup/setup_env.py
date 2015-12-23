#!/usr/bin/env python
"""A class to set up the LRT prediction environment. This will take user
supplied variables and store them in a configuration file."""

#   Import standard library modules here
from distutils import spawn
import datetime
import subprocess
try: # This version of ConfigParser is only available on Python 2.6, 2.7, or 2.8
    import ConfigParser
except ImportError:
    import sys # We require 2.7 or higher for argparse
    sys.exit("Please use Python 2.7.XX or Python 2.8.XX")

#   Import the file functions script
import lrt_predict.General.file_funcs as file_funcs
#   Import the script to give verbose messages
import lrt_predict.General.set_verbosity as set_verbosity


class SetupEnv(object):
    """A class to write user-supplied variables from the command line into a
    text configuration file. The format of the file is a structure[1]-like
    file format. The general form is
        // comment
        #define KEYWORD value
    for the following KEYWORDs:
        BASE (str)                Base directory for LRT prediction data.
        TARGET_SPECIES (str)      Query species, omitted from alignments.
        EVAL_THRESHOLD (float)    Max. E-value for accepting hit into the
                                  multiple sequence alignment.
        MISSING_THRESHOLD (float) Max. missing (gap) for a codon to be
                                  considered in prediction.
        BASH (str)                Path to bash.
        GZIP (str)                Path to gzip.
        SUM (str)                 Path to sum.
        TBLASTX (str)             Path to tblastx.
        PASTA (str)               Path to pasta.
        HYPHY (str)               Path to HyPhy

    Contains no class attributes.

    Contains the following instance attributes:
        mainlog (logger)          Print and format logging messages.
        base (str)                Base directory.
        deps (str)                Directory to hold dependencies
        target_species (str)      Target species.
        eval_thresh (str)         E-value threshold (casted from float).
        alignment_model (str)     Prank alignment model.
        miss_thresh (str)         Missing (gap) threshold (casted from float).
        config_file (str)         File to store configuration data.
        missing_progs (list)      Missing executables.

    Inherits no attributes and methods from a parent class.

    Contains the following methods:
        __init__(self, base, deps, target, evalue,
                 model, missingness, cfg, verbose):
            Set all configuration variables. Create a list of the required
            executables that do not exist.

        write_config(self):
            Write the configuration file with all the user specified variables.
    """

    def __init__(self, base, deps, target, evalue,
                 model, missingness, cfg, verbose):
        self.mainlog = set_verbosity.verbosity('Setup_Env', verbose)
        self.base = base
        self.deps = deps
        self.target_species = target
        self.eval_thresh = str(evalue)
        self.miss_thresh = str(missingness)
        self.config_file = cfg
        self.missing_progs = []
        self.mainlog.debug(
            'Config file in ' + self.config_file + '\n' +
            'Setting variables: \n' +
            '#define BASE ' + self.base + '\n' +
            '#define TARGET_SPECIES ' + self.target_species + '\n' +
            '#define EVAL_THRESHOLD ' + self.eval_thresh + '\n' +
            '#define MISSING_THRESHOLD ' + self.miss_thresh + '\n'
            )
        self.bash_path = spawn.find_executable('bash') or ''
        self.gzip_path = spawn.find_executable('gzip') or ''
        self.sum_path = spawn.find_executable('sum') or ''
        self.tblastx_path = spawn.find_executable('tblastx') or ''
        self.pasta_path = spawn.find_executable('run_pasta.py') or ''
        self.hyphy_path = spawn.find_executable('HYPHYSP') or ''
        self.mainlog.debug(
            'Setting executable path variables:\n' +
            '#define BASH ' + self.bash_path + '\n' +
            '#define GZIP ' + self.gzip_path + '\n' +
            '#define SUM ' + self.sum_path + '\n' +
            '#define TBLASTX ' + self.tblastx_path + '\n' +
            '#define PASTA ' + self.pasta_path + '\n' +
            '#define HYPHY ' + self.hyphy_path)
        #   Print out some warnings if executables are not found
        if not self.bash_path:
            self.mainlog.error('Cannot find BASH!')
        if not self.gzip_path:
            self.mainlog.error('Cannot find gzip!')
        if not self.sum_path:
            self.mainlog.error('Cannot find sum!')
        if not self.tblastx_path:
            self.mainlog.warning('Cannot find tblastx! Will download')
            self.missing_progs.append('tBLASTx')
        if not self.pasta_path:
            self.mainlog.warning('Cannot find PASTA! Will download')
            self.missing_progs.append('PASTA')
        if not self.hyphy_path:
            self.mainlog.warning('Cannot find HyPhy! Will download')
            self.missing_progs.append('HyPhy')
        return

    def get_deps(self):
        """Download the dependencies that are missing. Uses the instance
        attribute `missing_progs' as a list of arguments to a shell script."""
        if not self.missing_progs:
            self.mainlog.info('No missing dependencies :D')
            return
        self.mainlog.warning('Missing the following dependencies: ' + ', '.join(self.missing_progs))
        download_script = './Shell_Scripts/get_dependencies.sh'
        download_command = ['bash', download_script, self.deps] + self.missing_progs
        download_shell = subprocess.Popen(download_command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = download_shell.communicate()
        self.mainlog.info(out)
        self.mainlog.error
        if 'PASTA' in self.missing_progs:
            self.pasta_path = self.deps + '/pasta-master/run_pasta.py'
        if 'tBLASTx' in self.missing_progs:
            self.tblastx_path = self.deps + '/ncbi_blast+/bin/tblastx'
        if 'HyPhy' in self.missing_progs:
            self.hyphy_path = self.deps + '/hyphy-master/HYPHYMP'
        return

    def write_config(self):
        """Write the configuration file with all user-specified variables"""
        if file_funcs.file_exists(self.config_file, self.mainlog):
            self.mainlog.warning('Config file ' + self.config_file + 'already exists. It will be overwritten!')
        BAD_Mutations_Config = ConfigParser.RawConfigParser()
        config_section = "Config"
        BAD_Mutations_Config.add_config(config_section)
        BAD_Mutations_Config.set(config_section, "BASH", self.bash_path)
        BAD_Mutations_Config.set(config_section, "GZIP", self.gzip_path)
        BAD_Mutations_Config.set(config_section, "SUM", self.sum_path)
        BAD_Mutations_Config.set(config_section, "TBlastX", self.tblastx_path)
        BAD_Mutations_Config.set(config_section, "HyPhy", self.hyphy_path)
        BAD_Mutations_Config.set(config_section, "Base", self.base)
        BAD_Mutations_Config.set(config_section, "Target", self.target_species)
        BAD_Mutations_Config.set(config_section, "Evalue", self.eval_thresh)
        BAD_Mutations_Config.set(config_section, "Missing", self.miss_thresh)
        cfile = open(self.config_file, 'w')
        BAD_Mutations_Config.write(cfile)
        self.mainlog.info('Write configuration into ' + self.config_file)
        return
