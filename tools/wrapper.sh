#!/bin/bash
#
# a simple wrapper to activate the conda virtual environment before executing a script
#
# for conda, add the following to .bashrc:
#export PATH=/home/flocklab/conda_venv/bin/python:$PATH
#[[ -f /scratch/flocklab/conda/bin/conda ]] && eval "$(/scratch/flocklab/conda/bin/conda shell.bash hook)"
#conda activate py36

source ~/.profile
$*
