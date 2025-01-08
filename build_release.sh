#!/bin/bash
if [ -z $1 ]; then
  echo "version is required for the release build"
  echo "Usage: $0 <version>"
else
  echo "Building version $1"
  docker build . -t littleorange666/orange_judge:$1 --no-cache
fi