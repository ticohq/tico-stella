#!/bin/bash
# Desktop (Linux) build of tico-stella with the Vulkan renderer, for testing
# shaders off-device. Needs SDL2, SDL2_mixer, libcurl and a Vulkan driver.
# Run from the repo root; the binary expects to be started from here too
# (it reads tico/fonts, tico/shaders and tico/lang relative to the cwd).
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BUILD="$ROOT/build_desktop"
JOBS=$(nproc)
CORE="$ROOT/src/os/libretro"

# Objects live beside the sources and the NRO build leaves aarch64 ones.
make -C "$CORE" clean platform=unix STATIC_LINKING=1 >/dev/null
make -C "$CORE" -j"$JOBS" platform=unix STATIC_LINKING=1 STATIC_LINKING_LINK=1 \
    TARGET=stella_libretro_unix.a
cmake -S "$ROOT/tico" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DSTELLA_CORE_LIB="$CORE/stella_libretro_unix.a"
cmake --build "$BUILD" -j"$JOBS"
echo "Built $BUILD/tico-stella"
