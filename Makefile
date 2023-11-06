.PHONY: _path_build _path_lib _path_assets _build_posix _build_win assets pack patches sign tests

ARCH_LINUX_X86 := x86_64-unknown-linux-gnu
ARCH_LINUX_ARM := aarch64-unknown-linux-gnu
ARCH_MAC_X86 := x86_64-apple-darwin
ARCH_MAC_ARM := aarch64-apple-darwin
ARCH_WIN := x86_64-pc-windows-msvc
TARGET := install
BUILD_VERSION := latest

_path_build:
	$(eval BUILDPATH := build/${ARCH}/release/${TARGET})
_path_lib: _path_build
	$(eval LIBPATH := ${BUILDPATH}/lib)
_path_assets: _path_build
	$(eval ASSETSPATH := ${BUILDPATH}/assets)

clean_build: _path_build
	@rm -rf ${BUILDPATH}

clean_src:
	@rm -rf src/*

clean_dist:
	@rm -rf dist

clean_vendor:
	@rm -rf vendor

sources: clean_src
	@git clone https://github.com/python/importlib_metadata.git src/importlib_metadata && cd src/importlib_metadata && git checkout v4.12.0
	@git clone https://github.com/lark-parser/lark.git src/lark && cd src/lark && git checkout 1.1.8
	@git clone https://github.com/python-poetry/poetry.git src/poetry && cd src/poetry && git checkout 1.6.0
	@git clone https://github.com/python-poetry/poetry-core.git src/poetry-core && cd src/poetry-core && git checkout 1.8.1
	@git clone https://github.com/pypa/virtualenv.git src/virtualenv && cd src/virtualenv && git checkout 20.24.6

patches:
	@cd src/importlib_metadata && git diff --binary HEAD > ../../patches/importlib_metadata.patch
	@cd src/lark && git diff --binary HEAD > ../../patches/lark.patch
	@cd src/poetry-core && git diff --binary HEAD > ../../patches/poetry-core.patch
	@cd src/poetry && git diff --binary HEAD > ../../patches/poetry.patch
	@cd src/virtualenv && git diff --binary HEAD > ../../patches/virtualenv.patch

apply_patches:
	@cd src/importlib_metadata && git apply --reject --ignore-whitespace ../../patches/importlib_metadata.patch
	@cd src/lark && git apply --reject --ignore-whitespace ../../patches/lark.patch
	@cd src/poetry-core && git apply --reject --ignore-whitespace ../../patches/poetry-core.patch
	@cd src/poetry && git apply --reject --ignore-whitespace ../../patches/poetry.patch
	@cd src/virtualenv && git apply --reject --ignore-whitespace ../../patches/virtualenv.patch

vendor: clean_vendor
	@mkdir -p vendor
	@cp -R src/* vendor
	@find vendor -type d -name .git | xargs rm -r

tests:
	@cd vendor/importlib_metadata && \
		python -m venv .venv && \
		.venv/bin/pip install .[testing] pyfakefs && \
		.venv/bin/python -m unittest discover && \
		rm -r .venv
	@cd vendor/virtualenv && \
		python -m venv .venv && \
		.venv/bin/pip install .[test] && \
		.venv/bin/pytest && \
		rm -r .venv
	@cd vendor/poetry-core && \
		python -m venv .venv && \
		.venv/bin/pip install -r vendors/deps.txt && \
		.venv/bin/pip install ../lark . && \
		.venv/bin/pip install build pytest pytest-mock tomli-w && \
		.venv/bin/pytest && \
		rm -r .venv
	@cd vendor/poetry && \
		python -m venv .venv && \
		.venv/bin/pip install ../importlib_metadata ../lark ../virtualenv && \
		.venv/bin/pip install -r ../poetry-core/vendors/deps.txt && \
		.venv/bin/pip install ../poetry-core . && \
		.venv/bin/pip install cachy deepdiff flatdict httpretty pytest pytest-mock pytest-xdist[psutil] && \
		.venv/bin/pytest && \
		rm -r .venv

build_linux: ARCH := ${ARCH_LINUX_X86}
build_linux: _build_posix assets

build_mac: ARCH := ${ARCH_MAC_X86}
build_mac: _build_posix assets sign

build_win: ARCH := ${ARCH_WIN}
build_win: _build_win assets

_build_posix: _path_build _path_lib clean_build
	pyoxidizer build --release --target-triple=${ARCH}
	@rm ${BUILDPATH}/COPYING.txt

_build_win: _path_build _path_lib clean_build
	pyoxidizer build --release --target-triple=${ARCH} --var WIN_BUILD 1

assets: _path_assets
	@mkdir -p ${ASSETSPATH}
	@mkdir -p ${ASSETSPATH}/core/version
	@mkdir -p ${ASSETSPATH}/virtualenv/create
	@mkdir -p ${ASSETSPATH}/virtualenv/discovery
	@mkdir -p ${ASSETSPATH}/virtualenv/seed/wheels
	@cp -R vendor/poetry-core/src/poetry/core/version/grammars ${ASSETSPATH}/core/version/grammars
	@cp vendor/virtualenv/src/virtualenv/create/debug.py ${ASSETSPATH}/virtualenv/create/debug.py
	@cp vendor/virtualenv/src/virtualenv/discovery/py_info.py ${ASSETSPATH}/virtualenv/discovery/py_info.py
	@cp vendor/virtualenv/src/virtualenv/seed/wheels/embed/*.whl ${ASSETSPATH}/virtualenv/seed/wheels

sign: _path_build _path_lib
	@codesign -s - ${BUILDPATH}/poetry
	@find ${LIBPATH} -name '*.so' -type f | xargs -I $$ codesign -s - $$

verify_build_linux: ARCH := ${ARCH_LINUX_X86}
verify_build_linux: _verify_build

verify_build_mac: ARCH := ${ARCH_MAC_X86}
verify_build_mac: _verify_build

verify_build_win: ARCH := ${ARCH_WIN}
verify_build_win: _verify_build

_verify_build: _path_build
	${BUILDPATH}/poetry --version
	${BUILDPATH}/poetry config virtualenvs.in-project true
	@cd tests && ../${BUILDPATH}/poetry install -vvv
	@rm -rf tests/.venv

pack_linux: ARCH := ${ARCH_LINUX_X86}
pack_linux: pack

pack_mac: ARCH := ${ARCH_MAC_X86}
pack_mac: pack

pack_win: ARCH := ${ARCH_WIN}
pack_win: pack

pack: _path_build clean_dist
	@mkdir -p dist
	@cd ${BUILDPATH} && tar -czvf poetry-bin-${BUILD_VERSION}-${ARCH}.tar.gz *
	@mv ${BUILDPATH}/poetry-bin-${BUILD_VERSION}-${ARCH}.tar.gz dist
	@openssl sha256 < dist/poetry-bin-${BUILD_VERSION}-${ARCH}.tar.gz | sed 's/^.* //' > dist/poetry-bin-${BUILD_VERSION}-${ARCH}.sha256sum
	@cat dist/poetry-bin-${BUILD_VERSION}-${ARCH}.sha256sum
