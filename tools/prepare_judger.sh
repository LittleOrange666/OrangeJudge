#!/bin/bash
cd ..
git clone https://github.com/LittleOrange666/OrangeJudge_Judger.git --recursive --depth 1
cd OrangeJudge_Judger
chmod +x ./build.sh
./build.sh
cd ../OrangeJudge
mkdir sandbox
docker-compose -f docker-compose-judgeronly.yml up -d