#!/bin/sh
# usage: runaud.sh tag
cd /home/claude/se; rm -f aud_$1_*.jsonl base2_Swarm*
node audit2.js 0 2 aud_$1_0.jsonl '^Swarm(Stereo)?/' & node audit2.js 1 2 aud_$1_1.jsonl '^Swarm(Stereo)?/' & wait
node sumrun.js $1 > sum_$1.txt
