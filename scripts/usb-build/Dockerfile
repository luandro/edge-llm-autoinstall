# syntax=docker/dockerfile:1
# Build both Linux architectures from one laptop. No native CPU flags.
ARG BASE_IMAGE=debian:bookworm-slim
FROM ${BASE_IMAGE} AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates python3 coreutils libc-bin && rm -rf /var/lib/apt/lists/*
FROM runtime AS build
ARG LLAMA_REV
ARG WHISPER_REV
ARG JOBS=2
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends git cmake build-essential espeak-ng ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git init llama && cd llama && git remote add origin https://github.com/ggml-org/llama.cpp.git && git fetch --depth 1 origin "$LLAMA_REV" && git checkout --detach FETCH_HEAD
RUN git init whisper && cd whisper && git remote add origin https://github.com/ggml-org/whisper.cpp.git && git fetch --depth 1 origin "$WHISPER_REV" && git checkout --detach FETCH_HEAD
# x86-64 baseline: deliberately no AVX-512/AMX/native. ARM64: baseline Armv8-A.
RUN set -eux; \
    flags="-DGGML_NATIVE=OFF -DBUILD_SHARED_LIBS=OFF -DGGML_BACKEND_DL=OFF -DGGML_CPU_ALL_VARIANTS=OFF -DGGML_OPENMP=OFF -DGGML_BLAS=OFF"; \
    if [ "$TARGETARCH" = arm64 ]; then flags="$flags -DGGML_CPU_ARM_ARCH=armv8-a -DGGML_CPU_KLEIDIAI=OFF"; \
    elif [ "$TARGETARCH" = amd64 ]; then flags="$flags -DGGML_AVX512=OFF -DGGML_AVX512_VBMI=OFF -DGGML_AVX512_VNNI=OFF -DGGML_AVX_VNNI=OFF -DGGML_AMX_TILE=OFF -DGGML_AMX_INT8=OFF -DGGML_AMX_BF16=OFF"; else exit 1; fi; \
    cmake -S llama -B llama/build -DCMAKE_BUILD_TYPE=Release $flags -DGGML_VULKAN=OFF -DGGML_CUDA=OFF -DGGML_CURL=OFF -DLLAMA_BUILD_SERVER=ON '-DCMAKE_EXE_LINKER_FLAGS=-static-libstdc++ -static-libgcc'; \
    cmake --build llama/build --parallel "$JOBS" --target llama-server; \
    cmake -S whisper -B whisper/build -DCMAKE_BUILD_TYPE=Release $flags -DWHISPER_BUILD_TESTS=OFF '-DCMAKE_EXE_LINKER_FLAGS=-static-libstdc++ -static-libgcc'; \
    cmake --build whisper/build --parallel "$JOBS" --target whisper-cli; \
    mkdir /out; cp llama/build/bin/llama-server whisper/build/bin/whisper-cli /out/; \
    cp llama/LICENSE /out/LICENSE-llama.cpp; cp whisper/LICENSE /out/LICENSE-whisper.cpp; \
    /out/llama-server --version; /out/whisper-cli --help >/dev/null 2>&1; \
    ldd /out/llama-server; ldd /out/whisper-cli; \
    printf 'llama=%s\nwhisper=%s\narch=%s\n' "$LLAMA_REV" "$WHISPER_REV" "$TARGETARCH" >/out/build-info.txt; \
    cp llama/build/CMakeCache.txt /out/llama-CMakeCache.txt; cp whisper/build/CMakeCache.txt /out/whisper-CMakeCache.txt
RUN espeak-ng -v pt-br -s 135 -w /tmp/pt.wav 'A rádio comunitária entrevistou três moradores. A reunião será na sexta-feira, às nove horas.' && \
    espeak-ng -v en -s 135 -w /tmp/en.wav 'The community radio interviewed three residents. The meeting is on Friday at nine in the morning.' && \
    ffmpeg -v error -i /tmp/pt.wav -ar 16000 -ac 1 -c:a pcm_s16le /out/sample-pt.wav && \
    ffmpeg -v error -i /tmp/en.wav -ar 16000 -ac 1 -c:a pcm_s16le /out/sample-en.wav
FROM scratch AS export
COPY --from=build /out/ /
