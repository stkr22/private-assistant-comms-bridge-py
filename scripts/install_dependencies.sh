#!/bin/sh

apt-get install -y libspeexdsp-dev # needed for noise suppression
apt-get install libsndfile1 # needed for librosa - seem to be a sufficient substitute for this use case instead of using ffmpeg
