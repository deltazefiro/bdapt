#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Building test container...${NC}"
docker build -f Dockerfile.test -t bdapt-test .

echo -e "${YELLOW}Running tests in container...${NC}"
if docker run --rm -v "$(pwd):/app" bdapt-test "$@"; then
    echo -e "${GREEN}Tests passed!${NC}"
else
    echo -e "${RED}Tests failed!${NC}"
    exit 1
fi 