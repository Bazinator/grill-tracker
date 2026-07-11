# Use a robust Ubuntu base
FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# Avoid prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# 1. Install C++ Toolchain & Systems Utilities
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    gdb \
    cppcheck \
    valgrind \
    libopencv-dev \
    # 2. Install Python & IPC dependencies
    python3-pip \
    python3-dev \
    socat \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. Install Python libraries for your Perception layer
# We do this here so the container is ready to run your tracker
RUN pip3 install --no-cache-dir \
    opencv-python \
    ultralytics \
    numpy \
    lap \
    filterpy 

# Set the working directory inside the container
WORKDIR /workspaces/steakTracker
