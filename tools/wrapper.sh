#!/bin/bash
#
# a simple wrapper to activate the conda virtual environment before executing a script
#
# for conda:
#export PATH=/home/flocklab/conda_venv/bin/python:$PATH
#[[ -f /scratch/flocklab/conda/bin/conda ]] && eval "$(/scratch/flocklab/conda/bin/conda shell.bash hook)"
#conda activate py36
#
# alternatively, add the above to .bashrc:
#source ~/.bashrc

which conda > /dev/null 2>&1
if [ $? -ne 0 ]
then
  source ~/.bashrc
else
  source ~/pyvenv/bin/activate
fi
$*
