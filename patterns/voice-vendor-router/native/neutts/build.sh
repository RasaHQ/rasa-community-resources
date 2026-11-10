#!/bin/bash
# Build the native NeuTTS runtime for Apple silicon: Neuphonic's llama.cpp fork
# with Metal (llama-server and llama-completion) and a C++ NeuCodec decoder on
# ONNX Runtime. No Python, no torch, no numpy.
#
#   ./build.sh            build into ./build (gitignored)
#   ./build.sh --check    only verify an existing build against the pins
#
# Every source is pinned in DEPENDENCIES.lock and refused on mismatch. The
# script downloads source code and the ONNX Runtime archive; it never
# downloads model weights (prepare_models.py does that, with digests).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

lock() { awk -F= -v k="$1" '$1==k {print substr($0, length(k)+2)}' DEPENDENCIES.lock; }

LLAMA_REPO="$(lock llama.cpp.repository)"
LLAMA_COMMIT="$(lock llama.cpp.commit)"
ORT_VERSION="$(lock onnxruntime.version)"
ORT_ARCHIVE="$(lock onnxruntime.archive)"
ORT_URL="$(lock onnxruntime.url)"
ORT_SHA="$(lock onnxruntime.sha256)"
NEUTTS_REPO="$(lock neutts.repository)"
NEUTTS_COMMIT="$(lock neutts.commit)"
NEUTTS_LICENSE_SHA="$(lock neutts.license.sha256)"
NEUCODEC_REPO="$(lock neucodec.repository)"
NEUCODEC_COMMIT="$(lock neucodec.commit)"
NEUCODEC_LICENSE_SHA="$(lock neucodec.license.sha256)"

BUILD="$HERE/build"
SRC="$BUILD/src/llama.cpp"
ORT_PARENT="$BUILD/vendor"
ORT="$ORT_PARENT/onnxruntime-osx-arm64-${ORT_VERSION}"
OUT="$BUILD/bin"
LIB="$BUILD/lib"
LICENSES="$BUILD/licenses"

refuse() { echo "REFUSED: $*" >&2; exit 65; }
sha() { shasum -a 256 "$1" | awk '{print $1}'; }

[[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]] \
  || refuse "this build targets macOS on Apple silicon (Metal); got $(uname -s) $(uname -m)."

if [[ "${1:-}" != "--check" ]]; then
  command -v cmake >/dev/null || refuse "cmake is required (brew install cmake)."
  command -v clang++ >/dev/null || refuse "clang++ is required (xcode-select --install)."
  mkdir -p "$BUILD/src" "$ORT_PARENT" "$OUT" "$LIB" "$LICENSES"

  # 1. llama.cpp, Neuphonic's fork at the pinned commit.
  if [[ ! -d "$SRC/.git" ]]; then
    git clone --filter=blob:none --no-checkout "$LLAMA_REPO" "$SRC"
    git -C "$SRC" checkout --detach "$LLAMA_COMMIT"
  fi
  [[ "$(git -C "$SRC" rev-parse HEAD)" == "$LLAMA_COMMIT" ]] \
    || refuse "llama.cpp checkout is not the pinned commit $LLAMA_COMMIT."
  [[ -z "$(git -C "$SRC" status --porcelain --untracked-files=no)" ]] \
    || refuse "llama.cpp checkout has local changes."

  # Metal on, static libraries, no web UI (it would be fetched at build time)
  # and no OpenSSL: the server only ever listens on the loopback interface.
  cmake -S "$SRC" -B "$SRC/build-metal" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF \
    -DGGML_METAL=ON \
    -DGGML_METAL_EMBED_LIBRARY=ON \
    -DGGML_ACCELERATE=ON \
    -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_EXAMPLES=OFF \
    -DLLAMA_BUILD_TOOLS=ON \
    -DLLAMA_BUILD_SERVER=ON \
    -DLLAMA_BUILD_UI=OFF \
    -DLLAMA_OPENSSL=OFF >/dev/null
  cmake --build "$SRC/build-metal" --target llama-server llama-completion -j "$(sysctl -n hw.ncpu)"
  cp "$SRC/build-metal/bin/llama-server" "$SRC/build-metal/bin/llama-completion" "$OUT/"

  # 2. ONNX Runtime, the prebuilt macOS arm64 release, digest-checked.
  if [[ ! -f "$ORT_PARENT/$ORT_ARCHIVE" ]]; then
    curl --fail --location --retry 3 "$ORT_URL" -o "$ORT_PARENT/$ORT_ARCHIVE.partial"
    mv "$ORT_PARENT/$ORT_ARCHIVE.partial" "$ORT_PARENT/$ORT_ARCHIVE"
  fi
  [[ "$(sha "$ORT_PARENT/$ORT_ARCHIVE")" == "$ORT_SHA" ]] \
    || refuse "ONNX Runtime archive failed SHA-256 verification."
  [[ -d "$ORT" ]] || tar -xzf "$ORT_PARENT/$ORT_ARCHIVE" -C "$ORT_PARENT"

  # 3. The NeuCodec decoder, linked against that runtime.
  cp "$ORT/lib/libonnxruntime.${ORT_VERSION}.dylib" "$LIB/"
  clang++ -std=c++17 -O2 -Wall -Wextra \
    -I "$ORT/include" neucodec_decoder.cpp \
    -L "$LIB" -lonnxruntime.${ORT_VERSION} -Wl,-rpath,@executable_path/../lib \
    -o "$OUT/neucodec_decoder"

  # 4. Licences of everything the build contains or runs.
  fetch_license() {
    local url="$1" target="$2" expected="$3"
    [[ -f "$target" ]] || curl --fail --location --retry 3 "$url" -o "$target"
    [[ "$(sha "$target")" == "$expected" ]] || refuse "licence failed SHA-256 verification: $target"
  }
  cp "$SRC/LICENSE" "$LICENSES/llama.cpp-LICENSE"
  cp "$ORT/LICENSE" "$LICENSES/onnxruntime-LICENSE"
  cp "$ORT/ThirdPartyNotices.txt" "$LICENSES/onnxruntime-ThirdPartyNotices.txt"
  fetch_license "${NEUTTS_REPO/github.com/raw.githubusercontent.com}/$NEUTTS_COMMIT/LICENSE" \
    "$LICENSES/NeuTTS-LICENSE" "$NEUTTS_LICENSE_SHA"
  fetch_license "${NEUCODEC_REPO/github.com/raw.githubusercontent.com}/$NEUCODEC_COMMIT/LICENSE" \
    "$LICENSES/NeuCodec-LICENSE" "$NEUCODEC_LICENSE_SHA"
fi

# 5. Check what was built, and record it.
for bin in llama-server llama-completion neucodec_decoder; do
  [[ -x "$OUT/$bin" ]] || refuse "$OUT/$bin is missing; run ./build.sh."
done
if otool -L "$OUT/llama-server" "$OUT/llama-completion" "$OUT/neucodec_decoder" | grep -Eq '/opt/homebrew|/usr/local'; then
  refuse "a binary links a Homebrew or /usr/local library; the build must be self-contained."
fi
otool -L "$OUT/llama-server" | grep -q 'Metal.framework' \
  || refuse "llama-server does not link Metal.framework."
"$OUT/neucodec_decoder" --version | grep -q "onnxruntime=$ORT_VERSION" \
  || refuse "neucodec_decoder does not report ONNX Runtime $ORT_VERSION."

python3 - "$BUILD" "$LLAMA_COMMIT" "$ORT_VERSION" <<'PY'
import hashlib, json, pathlib, platform, subprocess, sys
build, commit, ort = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
info = {
    "llama.cpp.commit": commit,
    "onnxruntime.version": ort,
    "macos": platform.mac_ver()[0],
    "machine": subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip(),
    "clang": subprocess.run(["clang++", "--version"], capture_output=True, text=True).stdout.splitlines()[0],
    "binaries": {p.name: digest(p) for p in sorted((build / "bin").iterdir()) if p.is_file()},
}
(build / "BUILD-INFO.json").write_text(json.dumps(info, indent=2) + "\n")
print(json.dumps(info, indent=2))
PY
echo "Native NeuTTS runtime ready in $BUILD (llama-server with Metal, neucodec_decoder)."
