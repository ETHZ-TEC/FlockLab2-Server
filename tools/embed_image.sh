#!/bin/bash
#
# Copyright (c) 2020, ETH Zurich, Computer Engineering Group
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# 
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

# embeds an exe/elf file into a the FlockLab XML config file
#
# in order to use "drag&drop" to pass the image file and XML config to this script,
# you will need to create a *.desktop file with the following content:
#    [Desktop Entry]
#    Name=Embed FlockLab Image Wrapper
#    Comment=Drop FlockLab XML config and target image file here
#    Exec=[absolute_path_to_embed_image_script] %U
#    Type=Application

SEDCMD=sed
B64CMD=base64
XMLFILE=flocklab.xml     # default file name, if not provided via argument

# check if sed tool is installed
which $SEDCMD > /dev/null 2>&1
if [ $? -ne 0 ]
then
  echo "command '$SEDCMD' not found"
  exit 1
fi

# check if base64 tool is installed
which $B64CMD > /dev/null 2>&1
if [ $? -ne 0 ]
then
  echo "command '$B64CMD' not found"
  exit 1
fi

# at least one arguments are required (the target image)
if [ $# -lt 1 ]
then
  echo "usage: $0 [image file (exe/elf)] ([input / output XML file])"
  exit 1
fi

# if an additional argument is provided, check if it is an xml file
IMGFILE=$1
if [ $# -gt 1 ]
then
  XMLFILE=$2
  if [[ $1 == *.xml ]]
  then
    # swap the two files
    XMLFILE=$1
    IMGFILE=$2
  fi
fi

# check file extension of image
if [[ ! $IMGFILE == *.exe ]] && [[ ! $IMGFILE == *.elf ]] && [[ ! $IMGFILE == *.hex ]] && [[ ! $IMGFILE == *.sky ]] && [[ ! $IMGFILE == *.out ]]
then
  echo "invalid image file format"
  exit 2
fi

# check if files exist
if [ ! -f $IMGFILE ]
then
  echo "file $IMGFILE not found"
  exit 3
fi
if [ ! -f $XMLFILE ]
then
  echo "file $XMLFILE not found"
  exit 4
fi

if [ ! -f $XMLFILE ]
then
  echo "file $XMLFILE not found"
  exit 5
fi

B64FILE="$IMGFILE.b64"

# convert to base 64
$B64CMD $IMGFILE > $B64FILE
# insert binary into xml (in-place)
$SEDCMD -i -n '1h;1!H;${ g;s/<data>.*<\/data>/<data>\n<\/data>/;p}' $XMLFILE
$SEDCMD -i "/<data>/r ${B64FILE}" $XMLFILE
# remove temporary file
rm $B64FILE

echo "image $IMGFILE embedded into $XMLFILE"
