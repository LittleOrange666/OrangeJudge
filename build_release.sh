#!/bin/bash
if [ -z $1 ]; then
  echo "version is required for the release build"
  echo "Usage: $0 <version>"
else
  echo "Building version $1"
  docker build . -t littleorange666/orange_judge:$1 --no-cache
  echo "Building latest"
  docker build . -t littleorange666/orange_judge:latest
  echo "Pushing version $1"
  docker push littleorange666/orange_judge:$1
  echo "Pushing latest"
  docker push littleorange666/orange_judge:latest
fi